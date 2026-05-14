"""POST /api/customers/{id}/ingest — universal customer-scoped intake.

Persists the original payload as a Document, runs the customer-memory LLM
extraction, and stores the result as a pending CustomerInboxItem awaiting
human confirm/ignore. Company-wide schema ingest is handled separately by
``yunwei_win.api.schema_ingest``.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.models import (
    CustomerInboxItem,
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
    InboxSourceKind,
    InputChannel,
    InputModality,
)
from yunwei_win.schemas.customer import CustomerIngestResponse
from yunwei_win.services.ingest.customer_memory import extract_customer_memory
from yunwei_win.services.llm import LLMCallFailed
from yunwei_win.services.storage import store_upload

from yunwei_win.api.customer_profile._helpers import load_customer

logger = logging.getLogger(__name__)
router = APIRouter()


def _classify_input(
    file: UploadFile | None, text: str | None
) -> tuple[InboxSourceKind, DocumentType, InputModality, str]:
    """Return (source_kind, document_type, modality, default_filename)."""
    if file is None or not (file.filename or ""):
        return (
            InboxSourceKind.text_note,
            DocumentType.text_note,
            InputModality.text,
            "note.txt",
        )
    name = file.filename or ""
    ct = (file.content_type or "").lower()
    if name.lower().endswith(".pdf") or "pdf" in ct:
        return (
            InboxSourceKind.contract,
            DocumentType.contract,
            InputModality.pdf,
            name,
        )
    if ct.startswith("image/"):
        # Default to wechat_screenshot since it's the more common case.
        # Caller can pass `kind=business_card` form param to override.
        return (
            InboxSourceKind.wechat_screenshot,
            DocumentType.chat_log,
            InputModality.image,
            name,
        )
    return (
        InboxSourceKind.other,
        DocumentType.other,
        InputModality.other,
        name,
    )


_KIND_TO_DOC_MODALITY: dict[InboxSourceKind, tuple[DocumentType, InputModality]] = {
    InboxSourceKind.contract: (DocumentType.contract, InputModality.pdf),
    InboxSourceKind.business_card: (DocumentType.business_card, InputModality.image),
    InboxSourceKind.wechat_screenshot: (DocumentType.chat_log, InputModality.image),
    InboxSourceKind.text_note: (DocumentType.text_note, InputModality.text),
}


@router.post("/{customer_id}/ingest", response_model=CustomerIngestResponse)
async def ingest_customer_input(
    customer_id: UUID,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    kind: str | None = Form(
        default=None,
        description="Optional explicit override: contract / business_card / "
                    "wechat_screenshot / text_note",
    ),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> CustomerIngestResponse:
    cust = await load_customer(session, customer_id)

    if file is None and not (text and text.strip()):
        raise HTTPException(400, "must supply either a file or non-empty `text`")

    payload_bytes: bytes | None = None
    text_blob: str | None = None
    src_kind, doc_type, modality, fname = _classify_input(file, text)

    if file is not None:
        payload_bytes = await file.read()
        if not payload_bytes:
            raise HTTPException(400, "empty file")
    if text and text.strip():
        text_blob = text.strip()
        if file is None:
            payload_bytes = text_blob.encode("utf-8")

    if kind:
        try:
            src_kind = InboxSourceKind(kind)
        except ValueError as exc:
            raise HTTPException(400, f"unknown kind {kind!r}") from exc
        if src_kind in _KIND_TO_DOC_MODALITY:
            doc_type, modality = _KIND_TO_DOC_MODALITY[src_kind]

    file_path, sha, size = store_upload(
        payload_bytes, fname, default_ext=".bin"
    )
    doc = Document(
        type=doc_type,
        file_url=file_path,
        original_filename=fname,
        content_type=(file.content_type if file else "text/plain"),
        file_sha256=sha,
        file_size_bytes=size,
        ocr_text=text_blob if modality == InputModality.text else None,
        uploader=uploader,
        assigned_customer_id=cust.id,
        processing_status=DocumentProcessingStatus.processing,
        review_status=DocumentReviewStatus.pending_review,
        input_channel=InputChannel.web_upload,
        input_modality=modality,
    )
    session.add(doc)
    await session.flush()

    try:
        result = await extract_customer_memory(
            session=session,
            customer=cust,
            document_id=doc.id,
            modality=modality.value,
            text_content=text_blob,
            image_bytes=payload_bytes if modality == InputModality.image else None,
            image_filename=fname,
            image_content_type=(file.content_type if file else None),
        )
    except LLMCallFailed as exc:
        doc.processing_status = DocumentProcessingStatus.failed
        doc.parse_error = str(exc)[:2000]
        await session.commit()
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc
    except Exception as exc:
        doc.processing_status = DocumentProcessingStatus.failed
        doc.parse_error = repr(exc)[:2000]
        await session.commit()
        raise HTTPException(422, f"extraction failed: {exc!s}") from exc

    doc.raw_llm_response = result.model_dump(mode="json")
    doc.processing_status = DocumentProcessingStatus.parsed
    doc.parse_warnings = list(result.parse_warnings)
    await session.flush()

    inbox = CustomerInboxItem(
        customer_id=cust.id,
        document_id=doc.id,
        source_kind=src_kind,
        summary=result.summary[:1000] if result.summary else "(空摘要)",
        extracted_payload=result.model_dump(mode="json"),
        confidence=result.confidence_overall,
        parse_warnings=list(result.parse_warnings),
    )
    session.add(inbox)
    await session.flush()
    await session.commit()

    return CustomerIngestResponse(
        inbox_id=inbox.id,
        document_id=doc.id,
        source_kind=src_kind.value,
        summary=inbox.summary,
        confidence_overall=result.confidence_overall,
        proposed_counts={
            "events": len(result.events),
            "commitments": len(result.commitments),
            "tasks": len(result.tasks),
            "risk_signals": len(result.risk_signals),
            "memory_items": len(result.memory_items),
        },
        warnings=list(result.parse_warnings),
    )
