"""Contract ingest pipeline.

Document in → DB rows out. Text-only path: pypdf for born-digital PDFs,
Mistral OCR for scanned PDFs and Office files, then a single text-only LLM
call for extraction. We do not send the original file bytes to the LLM — DeepSeek's
Anthropic-compat doesn't OCR `document` blocks, and Mistral OCR gives
us a clean markdown view.

1. Store original bytes (kept forever).
2. pypdf per-page text; Mistral OCR fallback for scanned PDFs.
3. Insert Document early so subsequent llm_calls reference it.
4. Single `submit_contract_extraction` tool call (text-only) → Pydantic.
5. Insert Customer / Contacts / Order / Contract rows.
6. write_provenance writes one field_provenance row per cited field,
   substring-validated against the OCR text.
7. needs_review_fields = those with confidence < 0.7.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    Contact,
    ContactRole,
    Contract,
    Customer,
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    Order,
)
from yunwei_win.services import pdf as pdf_utils
from yunwei_win.services.match import (
    find_contact_candidates,
    find_customer_candidates,
)
from yunwei_win.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_document_to_markdown,
    parse_pdf_to_markdown,
)
from yunwei_win.services.ingest.provenance import write_provenance
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.storage import store_upload
from yunwei_win.services.ingest.schemas import (
    CONTRACT_TOOL_NAME,
    ContactRoleEx,
    ContractConfirmRequest,
    ContractExtractionResult,
    contract_tool,
)
from yunwei_win.config import settings
from yunwei_win.services.llm import call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)


from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("contract_extraction.md")


@dataclass
class IngestResult:
    document_id: uuid.UUID
    customer_id: uuid.UUID
    order_id: uuid.UUID
    contract_id: uuid.UUID
    contact_ids: list[uuid.UUID] = field(default_factory=list)
    confidence_overall: float = 0.0
    warnings: list[str] = field(default_factory=list)
    needs_review_fields: list[str] = field(default_factory=list)


@dataclass
class MatchCandidate:
    id: uuid.UUID
    score: float
    reason: str
    fields: dict  # current DB row state — full_name/address/... etc.


@dataclass
class DraftCandidates:
    customer: list[MatchCandidate] = field(default_factory=list)
    # contacts[i] holds candidates for the i-th extracted contact slot.
    contacts: list[list[MatchCandidate]] = field(default_factory=list)


@dataclass
class ContractDraft:
    document_id: uuid.UUID
    result: ContractExtractionResult
    ocr_text: str
    warnings: list[str] = field(default_factory=list)
    candidates: DraftCandidates = field(default_factory=DraftCandidates)


async def extract_contract_draft(
    *,
    session: AsyncSession,
    pdf_bytes: bytes,
    original_filename: str,
    content_type: str | None = None,
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
) -> ContractDraft:
    """Phase 1: store the PDF, OCR it, run the LLM, save the draft on the
    Document row. Marks Document.review_status=pending_review. Does NOT
    create Customer/Order/Contract — that happens on confirm."""
    file_path, sha, size = store_upload(pdf_bytes, original_filename)
    await emit_progress(progress, "stored", "原始文件已保存，开始读取文本")
    ext = Path(original_filename).suffix.lower()
    is_pdf = ext == ".pdf" or (content_type or "").lower() == "application/pdf"

    await emit_progress(progress, "ocr", "正在读取文档文本")
    pages = pdf_utils.extract_text_with_pages(file_path) if is_pdf else []
    pypdf_text = pdf_utils.joined_text(pages) if is_pdf else ""

    ocr_warning: str | None = None
    mistral_ocr_note: str | None = None
    if not is_pdf:
        logger.info(
            "document %r is not a PDF; using Mistral OCR directly",
            original_filename,
        )
        await emit_progress(progress, "ocr", "正在调用 Mistral OCR 识别文档")
        try:
            md = await parse_document_to_markdown(
                pdf_bytes,
                original_filename,
                content_type,
            )
            if md.strip():
                pypdf_text = md
                mistral_ocr_note = "OCR via Mistral (document parsed via OCR)"
                logger.info("Mistral OCR returned %d chars", len(md))
        except MistralOCRUnavailable as exc:
            ocr_warning = f"Mistral OCR unavailable: {exc!s}"
            logger.warning(ocr_warning)
    elif pdf_utils.is_scanned(pages):
        logger.info(
            "pdf %r appears scanned (pypdf got %d chars across %d pages); "
            "trying Mistral OCR",
            original_filename, len(pypdf_text), len(pages),
        )
        await emit_progress(progress, "ocr", "扫描件无文本层，正在调用 Mistral OCR")
        try:
            md = await parse_pdf_to_markdown(pdf_bytes, original_filename)
            if md.strip():
                pypdf_text = md
                mistral_ocr_note = "OCR via Mistral (PDF had no text layer)"
                logger.info("Mistral OCR returned %d chars", len(md))
        except MistralOCRUnavailable as exc:
            ocr_warning = f"Mistral OCR unavailable: {exc!s}"
            logger.warning(ocr_warning)

    # If we still have effectively no text, fail fast with a clear, actionable
    # error instead of feeding "(no text extracted)" to the LLM and surfacing
    # whatever Pydantic happens to complain about.
    if len(pypdf_text.strip()) < 40:
        msg = (
            f"未能从文件提取出可读文本 (pypdf {len(pypdf_text.strip())} 字"
            f", {len(pages)} 页, 文件类型 {ext or content_type or 'unknown'})。"
        )
        if ocr_warning:
            msg += "扫描件需要 OCR，但 " + ocr_warning
        else:
            msg += "如果是扫描件请配置 Mistral OCR (MISTRAL_API_KEY)。"
        raise ValueError(msg)

    doc = Document(
        type=DocumentType.contract,
        file_url=file_path,
        original_filename=original_filename,
        content_type=content_type or ("application/pdf" if is_pdf else None),
        file_sha256=sha,
        file_size_bytes=size,
        ocr_text=pypdf_text,
        uploader=uploader,
        processing_status=DocumentProcessingStatus.processing,
        review_status=DocumentReviewStatus.pending_review,
    )
    session.add(doc)
    await session.flush()

    await emit_progress(progress, "extract", "OCR 完成，AI 正在抽取合同字段")
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.format(
        filename=original_filename,
        pypdf_text=(pypdf_text or "(no text extracted)")[:30000],
        vision_hint="(text-only pipeline)",
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    response = await call_claude(
        messages,
        purpose="contract_extraction",
        session=session,
        model=settings.model_parse,
        tools=[contract_tool()],
        tool_choice={"type": "tool", "name": CONTRACT_TOOL_NAME},
        max_tokens=8192,
        document_id=doc.id,
    )
    import json as _json
    try:
        tool_input = extract_tool_use_input(response, CONTRACT_TOOL_NAME)
    except Exception:
        logger.warning(
            "contract_extraction extract_tool_use_input failed; full response=%s",
            _json.dumps(response.model_dump(), ensure_ascii=False)[:4000],
        )
        doc.parse_error = "no tool_use block in response"
        doc.processing_status = DocumentProcessingStatus.failed
        await session.commit()
        raise
    logger.info(
        "contract_extraction tool_input keys=%s len=%d",
        sorted(tool_input.keys()), len(str(tool_input))
    )

    doc.raw_llm_response = tool_input
    await session.flush()

    try:
        result = ContractExtractionResult.model_validate(tool_input)
    except Exception as exc:
        logger.warning(
            "contract_extraction validation failed; tool_input=%s | full_response=%s",
            _json.dumps(tool_input, ensure_ascii=False)[:2000],
            _json.dumps(response.model_dump(), ensure_ascii=False)[:4000],
        )
        doc.parse_error = f"pydantic: {exc!s}"[:2000]
        doc.processing_status = DocumentProcessingStatus.failed
        await session.commit()
        raise

    doc.processing_status = DocumentProcessingStatus.parsed
    warnings: list[str] = list(result.parse_warnings)
    if ocr_warning:
        warnings.insert(0, ocr_warning)
    if mistral_ocr_note:
        warnings.insert(0, mistral_ocr_note)
    doc.parse_warnings = warnings
    await session.flush()

    await emit_progress(progress, "match", "字段抽取完成，正在匹配已有客户")
    # Compute match candidates against existing rows so the review UI can
    # offer "merge into existing vs create new" before any DB write.
    customer_hits = await find_customer_candidates(session, result.customer.full_name)
    customer_candidates = [
        MatchCandidate(
            id=c.id,
            score=score,
            reason=reason,
            fields={
                "full_name": c.full_name,
                "short_name": c.short_name,
                "address": c.address,
                "tax_id": c.tax_id,
            },
        )
        for c, score, reason in customer_hits
    ]

    contact_candidate_lists: list[list[MatchCandidate]] = []
    for ct in result.contacts:
        hits = await find_contact_candidates(
            session, phone=ct.phone, mobile=ct.mobile, email=ct.email
        )
        contact_candidate_lists.append([
            MatchCandidate(
                id=c.id,
                score=score,
                reason=reason,
                fields={
                    "name": c.name,
                    "title": c.title,
                    "phone": c.phone,
                    "mobile": c.mobile,
                    "email": c.email,
                    "role": c.role.value,
                    "address": c.address,
                },
            )
            for c, score, reason in hits
        ])

    return ContractDraft(
        document_id=doc.id,
        result=result,
        ocr_text=pypdf_text,
        warnings=warnings,
        candidates=DraftCandidates(
            customer=customer_candidates,
            contacts=contact_candidate_lists,
        ),
    )


async def commit_contract_extraction(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    request: ContractConfirmRequest,
) -> IngestResult:
    """Phase 2: persist the user-reviewed extraction. Each entity decision
    drives whether we INSERT a new row or UPDATE an existing one with the
    user's reconciled `final` values. Order + Contract are always new
    (single PDF → single new contract). Marks Document.review_status=confirmed."""
    doc = (
        await session.execute(
            select(Document).where(Document.id == document_id)
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError(f"document {document_id} not found")
    if doc.review_status == DocumentReviewStatus.confirmed:
        raise ValueError(f"document {document_id} already confirmed")

    cust_final = request.customer.final
    if not (cust_final.full_name and cust_final.full_name.strip()):
        doc.parse_error = "customer name not extracted (likely OCR failure)"
        await session.flush()
        raise ValueError(
            "customer name is required; OCR likely failed on the buyer/甲方 region"
        )

    # Resolve customer: merge into existing or create new.
    if request.customer.mode == "merge":
        if request.customer.existing_id is None:
            raise ValueError("customer.mode=merge requires existing_id")
        customer = (
            await session.execute(
                select(Customer).where(Customer.id == request.customer.existing_id)
            )
        ).scalar_one_or_none()
        if customer is None:
            raise ValueError(f"customer {request.customer.existing_id} not found")
        customer.full_name = cust_final.full_name.strip()
        customer.short_name = cust_final.short_name
        customer.address = cust_final.address
        customer.tax_id = cust_final.tax_id
    else:
        customer = Customer(
            full_name=cust_final.full_name.strip(),
            short_name=cust_final.short_name,
            address=cust_final.address,
            tax_id=cust_final.tax_id,
        )
        session.add(customer)
    await session.flush()

    # Resolve each contact slot.
    contact_slots: list[uuid.UUID | None] = []
    contact_ids: list[uuid.UUID] = []
    skipped_contacts = 0
    for decision in request.contacts:
        c_final = decision.final
        if not (c_final.name and c_final.name.strip()):
            skipped_contacts += 1
            contact_slots.append(None)
            continue
        try:
            role = ContactRole(c_final.role.value)
        except ValueError:
            role = ContactRole.other
        if decision.mode == "merge":
            if decision.existing_id is None:
                raise ValueError("contact.mode=merge requires existing_id")
            ct = (
                await session.execute(
                    select(Contact).where(Contact.id == decision.existing_id)
                )
            ).scalar_one_or_none()
            if ct is None:
                raise ValueError(f"contact {decision.existing_id} not found")
            ct.customer_id = customer.id  # re-anchor to the resolved customer
            ct.name = c_final.name.strip()
            ct.title = c_final.title
            ct.phone = c_final.phone
            ct.mobile = c_final.mobile
            ct.email = c_final.email
            ct.role = role
            ct.address = c_final.address
        else:
            ct = Contact(
                customer_id=customer.id,
                name=c_final.name.strip(),
                title=c_final.title,
                phone=c_final.phone,
                mobile=c_final.mobile,
                email=c_final.email,
                role=role,
                address=c_final.address,
            )
            session.add(ct)
        await session.flush()
        contact_slots.append(ct.id)
        contact_ids.append(ct.id)

    # Order + Contract are always new — pull from the merged extraction view.
    result = request.to_extraction_result()

    order = Order(
        customer_id=customer.id,
        amount_total=result.order.amount_total,
        amount_currency=result.order.amount_currency,
        delivery_promised_date=result.order.delivery_promised_date,
        delivery_address=result.order.delivery_address,
        description=result.order.description,
    )
    session.add(order)
    await session.flush()

    milestone_dicts: list[dict] = []
    for i, m in enumerate(result.contract.payment_milestones):
        d = m.model_dump(mode="json")
        if not d.get("name"):
            d["name"] = f"阶段{i + 1}"
        milestone_dicts.append(d)

    contract = Contract(
        order_id=order.id,
        contract_no_external=result.contract.contract_no_external,
        contract_no_internal=Path(doc.original_filename).stem,
        payment_milestones=milestone_dicts,
        delivery_terms=result.contract.delivery_terms,
        penalty_terms=result.contract.penalty_terms,
        signing_date=result.contract.signing_date,
        effective_date=result.contract.effective_date,
        expiry_date=result.contract.expiry_date,
        confidence_overall=result.confidence_overall,
    )
    session.add(contract)
    await session.flush()

    excerpt_warnings = await write_provenance(
        session=session,
        document_id=doc.id,
        result=result,
        customer_id=customer.id,
        order_id=order.id,
        contract_id=contract.id,
        contact_ids=contact_slots,
        ocr_text=doc.ocr_text or "",
        extracted_by=settings.model_parse,
    )

    base_warnings = list(doc.parse_warnings or [])
    all_warnings = base_warnings + excerpt_warnings
    if skipped_contacts:
        all_warnings.append(
            f"{skipped_contacts} contact(s) skipped — name field came back null "
            "(likely OCR garbled the signature / stamp area)"
        )
    doc.parse_warnings = all_warnings
    doc.review_status = DocumentReviewStatus.confirmed
    doc.assigned_customer_id = customer.id
    await session.flush()

    needs_review = [
        path
        for path, conf in result.field_confidence.items()
        if isinstance(conf, (int, float)) and conf < 0.7
    ]

    return IngestResult(
        document_id=doc.id,
        customer_id=customer.id,
        order_id=order.id,
        contract_id=contract.id,
        contact_ids=contact_ids,
        confidence_overall=result.confidence_overall,
        warnings=all_warnings,
        needs_review_fields=needs_review,
    )


async def ingest_contract(
    *,
    session: AsyncSession,
    pdf_bytes: bytes,
    original_filename: str,
    uploader: str | None = None,
) -> IngestResult:
    """Single-shot path: extract draft + immediately commit as all-new
    entities (no merge). Used by tests and any caller that doesn't need
    the human-review step."""
    draft = await extract_contract_draft(
        session=session,
        pdf_bytes=pdf_bytes,
        original_filename=original_filename,
        uploader=uploader,
    )
    request = ContractConfirmRequest(
        customer={"mode": "new", "final": draft.result.customer.model_dump()},
        contacts=[
            {"mode": "new", "final": c.model_dump()}
            for c in draft.result.contacts
        ],
        order=draft.result.order.model_dump(),
        contract=draft.result.contract.model_dump(),
        field_provenance=[p.model_dump() for p in draft.result.field_provenance],
        confidence_overall=draft.result.confidence_overall,
        field_confidence=draft.result.field_confidence,
        parse_warnings=draft.result.parse_warnings,
    )
    return await commit_contract_extraction(
        session=session,
        document_id=draft.document_id,
        request=request,
    )
