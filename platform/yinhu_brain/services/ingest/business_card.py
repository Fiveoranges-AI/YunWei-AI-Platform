"""Business-card ingest: image → Customer/Contact rows + provenance.

Single Claude vision call with the business_card tool. Post-validates phone/
email and halves confidence on regex-fail (also flags Contact.needs_review).
"""

from __future__ import annotations

import base64
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.models import (
    Contact,
    ContactRole,
    Customer,
    Document,
    DocumentReviewStatus,
    DocumentType,
    EntityType,
)
from yinhu_brain.services.ingest.schemas import (
    BUSINESS_CARD_TOOL_NAME,
    BusinessCardExtraction,
    business_card_tool,
)
from yinhu_brain.services.ingest.provenance import upsert_field_provenance
from yinhu_brain.config import settings
from yinhu_brain.services.llm import call_claude, extract_tool_use_input
from yinhu_brain.services.match import find_customer_candidates
from yinhu_brain.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_image_to_markdown,
)
from yinhu_brain.services.storage import store_upload

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "prompts" / "business_card_extraction.md"
)


_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_GENERIC_EMAIL_DOMAINS = {
    "126.com",
    "139.com",
    "163.com",
    "foxmail.com",
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "msn.com",
    "outlook.com",
    "qq.com",
    "sina.com",
    "sohu.com",
    "yahoo.com",
}
_FIELD_ALIASES = {
    "company": "company_full_name",
    "company_name": "company_full_name",
    "companyname": "company_full_name",
    "organization": "company_full_name",
    "organization_name": "company_full_name",
    "org": "company_full_name",
    "business_name": "company_full_name",
    "企业": "company_full_name",
    "企业名称": "company_full_name",
    "公司": "company_full_name",
    "公司名称": "company_full_name",
    "单位": "company_full_name",
    "单位名称": "company_full_name",
    "brand": "company_short_name",
    "brand_name": "company_short_name",
    "logo": "company_short_name",
    "logo_text": "company_short_name",
    "short_name": "company_short_name",
    "简称": "company_short_name",
    "品牌": "company_short_name",
    "姓名": "name",
    "联系人": "name",
    "职位": "title",
    "职务": "title",
    "手机": "mobile",
    "手机号": "mobile",
    "电话": "phone",
    "座机": "phone",
    "邮箱": "email",
    "地址": "address",
    "网址": "website",
    "网站": "website",
}


@dataclass
class BusinessCardIngestResult:
    document_id: uuid.UUID
    contact_id: uuid.UUID
    needs_review: bool
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    contact_name: str | None = None
    warnings: list[str] = field(default_factory=list)


CUSTOMER_AUTO_MERGE_THRESHOLD = 0.95


def _media_type(filename: str, content_type: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return content_type
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = value.strip()
    return cleaned or None


def _alias_value(raw: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = raw.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _canonical_field_name(path: str) -> str:
    attr = path.split(".")[-1] if "." in path else path
    normalized = re.sub(r"[\s\-_]+", "_", attr.strip()).lower()
    return _FIELD_ALIASES.get(normalized, _FIELD_ALIASES.get(attr.strip(), attr))


def _normalize_tool_input(raw: dict[str, Any]) -> dict[str, Any]:
    """Recover common non-schema keys before Pydantic drops them.

    Vision models often return ``company`` / ``company_name`` / ``公司名称``
    even when the schema asks for ``company_full_name``. Dropping those aliases
    is exactly what makes the final customer unresolved, so normalize them
    before validation.
    """
    normalized = dict(raw)
    normalized["company_full_name"] = _clean(normalized.get("company_full_name")) or _alias_value(
        raw,
        "company",
        "company_name",
        "companyName",
        "organization",
        "organization_name",
        "org",
        "business_name",
        "企业名称",
        "公司名称",
        "公司",
        "单位名称",
        "单位",
    )
    normalized["company_short_name"] = _clean(normalized.get("company_short_name")) or _alias_value(
        raw,
        "company_short",
        "company_short_name",
        "short_name",
        "brand",
        "brand_name",
        "logo",
        "logo_text",
        "简称",
        "品牌",
    )
    normalized["name"] = _clean(normalized.get("name")) or _alias_value(raw, "姓名", "联系人", "person_name")
    normalized["title"] = _clean(normalized.get("title")) or _alias_value(raw, "职位", "职务", "job_title")
    normalized["mobile"] = _clean(normalized.get("mobile")) or _alias_value(raw, "手机", "手机号", "cellphone")
    normalized["phone"] = _clean(normalized.get("phone")) or _alias_value(raw, "电话", "座机", "tel")
    normalized["email"] = _clean(normalized.get("email")) or _alias_value(raw, "邮箱", "mail")
    normalized["address"] = _clean(normalized.get("address")) or _alias_value(raw, "地址")
    normalized["website"] = _clean(normalized.get("website")) or _alias_value(raw, "网址", "网站", "url")
    return normalized


def _extract_domain(value: str | None) -> str | None:
    value = _clean(value)
    if not value:
        return None
    if "@" in value and not value.startswith("http"):
        domain = value.rsplit("@", 1)[-1]
    else:
        parsed = urlsplit(value if "://" in value else f"https://{value}")
        domain = parsed.netloc or parsed.path.split("/", 1)[0]
    domain = domain.lower().strip().removeprefix("www.")
    return domain or None


def _fill_company_from_domain(result: BusinessCardExtraction) -> str | None:
    if _clean(result.company_full_name) or _clean(result.company_short_name):
        return None
    domain = _extract_domain(result.website) or _extract_domain(result.email)
    if not domain or domain in _GENERIC_EMAIL_DOMAINS:
        return None
    result.company_full_name = domain
    result.company_short_name = domain.split(".", 1)[0]
    return domain


async def _resolve_customer(
    session: AsyncSession,
    result: BusinessCardExtraction,
) -> Customer | None:
    """Create or reuse the customer named on the card.

    Business-card ingest used to write only ``Contact``. That left the Win
    customer list empty after importing a card. A card with company text is a
    customer-bearing document, so attach the contact to a concrete Customer.
    """
    full_name = _clean(result.company_full_name) or _clean(result.company_short_name)
    if not full_name:
        return None

    hits = await find_customer_candidates(session, full_name)
    customer: Customer | None = None
    if hits and hits[0][1] >= CUSTOMER_AUTO_MERGE_THRESHOLD:
        customer = hits[0][0]
        if not customer.short_name and _clean(result.company_short_name):
            customer.short_name = _clean(result.company_short_name)
        if not customer.address and _clean(result.address):
            customer.address = _clean(result.address)
    else:
        customer = Customer(
            full_name=full_name,
            short_name=_clean(result.company_short_name),
            address=_clean(result.address),
            tax_id=None,
        )
        session.add(customer)

    await session.flush()
    return customer


async def ingest_business_card(
    *,
    session: AsyncSession,
    image_bytes: bytes,
    original_filename: str,
    content_type: str | None = None,
    uploader: str | None = None,
) -> BusinessCardIngestResult:
    file_path, sha, size = store_upload(
        image_bytes, original_filename, default_ext=".jpg"
    )

    doc = Document(
        type=DocumentType.business_card,
        file_url=file_path,
        original_filename=original_filename,
        content_type=content_type,
        file_sha256=sha,
        file_size_bytes=size,
        ocr_text=None,
        uploader=uploader,
    )
    session.add(doc)
    await session.flush()

    media_type = _media_type(original_filename, content_type)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    ocr_text = ""
    ocr_warnings: list[str] = []
    try:
        ocr_text = await parse_image_to_markdown(
            image_bytes,
            original_filename,
            content_type,
        )
    except MistralOCRUnavailable as exc:
        ocr_warnings.append(f"Mistral OCR unavailable: {exc!s}")
        logger.warning("business card OCR failed for %s: %s", original_filename, exc)
    if ocr_text:
        doc.ocr_text = ocr_text
        prompt = (
            prompt
            + "\n\n## Mistral OCR 识别文本\n"
            + "下面是 OCR 从名片图片中识别出的 markdown 文本。请结合图片和 OCR，优先使用图片核对，"
              "但不要忽略 OCR 中出现的公司名、邮箱、电话、地址。\n\n"
            + ocr_text[:12000]
        )
    await session.flush()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]
    response = await call_claude(
        messages,
        purpose="business_card_extraction",
        session=session,
        model=settings.model_vision,
        tools=[business_card_tool()],
        tool_choice={"type": "tool", "name": BUSINESS_CARD_TOOL_NAME},
        max_tokens=2000,
        document_id=doc.id,
    )
    tool_input = extract_tool_use_input(response, BUSINESS_CARD_TOOL_NAME)
    doc.raw_llm_response = tool_input
    await session.flush()

    result = BusinessCardExtraction.model_validate(_normalize_tool_input(tool_input))

    # Post-validate phone/email; halve confidence on bad ones, flag needs_review
    warnings: list[str] = ocr_warnings + list(result.parse_warnings)
    needs_review = False
    if result.mobile and not _MOBILE_RE.match(result.mobile.strip()):
        warnings.append(f"mobile {result.mobile!r} does not match Chinese mobile pattern")
        needs_review = True
    if result.email and not _EMAIL_RE.match(result.email.strip()):
        warnings.append(f"email {result.email!r} does not look valid")
        needs_review = True
    if not result.name:
        warnings.append("no name extracted; needs review")
        needs_review = True
    domain_fallback = _fill_company_from_domain(result)
    if domain_fallback:
        warnings.append(f"company inferred from domain {domain_fallback!r}; needs review")
        needs_review = True

    customer = await _resolve_customer(session, result)
    if customer is None:
        warnings.append("no company extracted; contact is not attached to a customer")
        needs_review = True
    else:
        doc.assigned_customer_id = customer.id
        doc.detected_customer_id = customer.id

    contact = Contact(
        customer_id=customer.id if customer else None,
        name=result.name or "(未识别)",
        title=result.title,
        phone=result.phone,
        mobile=result.mobile,
        email=result.email,
        role=ContactRole.other,
        address=result.address,
        wechat_id=result.wechat_id,
        needs_review=needs_review,
    )
    session.add(contact)
    await session.flush()

    # Provenance — paths all point at the single Contact row.
    for entry in result.field_provenance:
        attr = _canonical_field_name(entry.path)
        entity_type = EntityType.contact
        entity_id = contact.id
        field_name = attr
        value = getattr(result, attr, None)
        if customer is not None and attr in {"company_full_name", "company_short_name"}:
            entity_type = EntityType.customer
            entity_id = customer.id
            field_name = "full_name" if attr == "company_full_name" else "short_name"
        await upsert_field_provenance(
            session,
            document_id=doc.id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            value=value,
            source_page=entry.source_page,
            source_excerpt=entry.source_excerpt,
            confidence=result.confidence_overall,
            excerpt_match=None,
            extracted_by=settings.model_vision,
        )

    doc.parse_warnings = warnings
    doc.review_status = DocumentReviewStatus.confirmed
    await session.flush()

    return BusinessCardIngestResult(
        document_id=doc.id,
        contact_id=contact.id,
        needs_review=needs_review,
        customer_id=customer.id if customer else None,
        customer_name=customer.full_name if customer else None,
        contact_name=contact.name,
        warnings=warnings,
    )
