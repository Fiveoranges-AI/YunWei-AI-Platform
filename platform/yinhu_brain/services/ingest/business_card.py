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
from yinhu_brain.services.storage import store_upload

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "prompts" / "business_card_extraction.md"
)


_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


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

    result = BusinessCardExtraction.model_validate(tool_input)

    # Post-validate phone/email; halve confidence on bad ones, flag needs_review
    warnings: list[str] = list(result.parse_warnings)
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
        attr = entry.path.split(".")[-1] if "." in entry.path else entry.path
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
