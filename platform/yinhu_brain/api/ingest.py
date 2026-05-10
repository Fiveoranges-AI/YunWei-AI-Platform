"""POST /api/ingest/* endpoints — entity-first ingest.

These are the V1.5 surface that writes Customer / Contact / Order / Contract
rows directly. The newer customer-scoped surface at
`/api/customers/{id}/ingest` (see app.api.customer_profile) is memory-first
and writes to the inbox for human confirmation. Both surfaces persist a
Document and an llm_calls audit row.

Routes:
- /api/ingest/contract          PDF → Customer + Contacts + Order + Contract
- /api/ingest/business_card     image → Contact + provenance
- /api/ingest/wechat_screenshot image → chat_log Document + extracted hints
"""

from __future__ import annotations

import logging

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.db import get_session
from yinhu_brain.models import Document, DocumentReviewStatus
from yinhu_brain.services.ingest.business_card import ingest_business_card
from yinhu_brain.services.ingest.contract import (
    MatchCandidate,
    commit_contract_extraction,
    extract_contract_draft,
)
from yinhu_brain.services.ingest.schemas import ContractConfirmRequest
from yinhu_brain.services.ingest.wechat import ingest_wechat_screenshot
from yinhu_brain.services.llm import LLMCallFailed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest")


@router.post("/contract")
async def upload_contract_preview(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Phase 1: extract a draft from the PDF. Persists the Document and the
    LLM's structured output but does NOT create Customer/Order/Contract rows.
    Frontend reviews the draft and POSTs to /confirm."""
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(400, "empty file")
    if not (file.filename or "").lower().endswith(".pdf") and (file.content_type or "") != "application/pdf":
        raise HTTPException(400, "expected a PDF")

    try:
        draft = await extract_contract_draft(
            session=session,
            pdf_bytes=pdf_bytes,
            original_filename=file.filename or "contract.pdf",
            uploader=uploader,
        )
    except LLMCallFailed as exc:
        logger.exception("contract draft LLM call failed")
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc
    except Exception as exc:
        logger.exception("contract draft failed")
        raise HTTPException(422, f"draft failed: {exc!s}") from exc

    await session.commit()

    needs_review = [
        path
        for path, conf in draft.result.field_confidence.items()
        if isinstance(conf, (int, float)) and conf < 0.7
    ]

    return {
        "document_id": str(draft.document_id),
        "draft": draft.result.model_dump(mode="json"),
        "candidates": {
            "customer": [_candidate_dict(c) for c in draft.candidates.customer],
            "contacts": [
                [_candidate_dict(c) for c in slot]
                for slot in draft.candidates.contacts
            ],
        },
        "ocr_text": draft.ocr_text[:20000],
        "warnings": draft.warnings,
        "needs_review_fields": needs_review,
    }


def _candidate_dict(c: MatchCandidate) -> dict:
    return {
        "id": str(c.id),
        "score": c.score,
        "reason": c.reason,
        "fields": c.fields,
    }


@router.post("/contract/{document_id}/confirm")
async def upload_contract_confirm(
    document_id: UUID,
    payload: ContractConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Phase 2: persist the user-reviewed draft. Each entity carries a
    decision (new vs merge into existing) — see ContractConfirmRequest."""
    try:
        ingest = await commit_contract_extraction(
            session=session,
            document_id=document_id,
            request=payload,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("contract confirm failed")
        raise HTTPException(422, f"confirm failed: {exc!s}") from exc

    await session.commit()

    return {
        "document_id": str(ingest.document_id),
        "created_entities": {
            "customer_id": str(ingest.customer_id),
            "contact_ids": [str(x) for x in ingest.contact_ids],
            "order_id": str(ingest.order_id),
            "contract_id": str(ingest.contract_id),
        },
        "confidence_overall": ingest.confidence_overall,
        "warnings": ingest.warnings,
        "needs_review_fields": ingest.needs_review_fields,
    }


@router.post("/contract/{document_id}/cancel")
async def upload_contract_cancel(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """User dropped the draft. Document row + raw_llm_response are preserved
    for audit; review_status flips to ignored."""
    doc = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, f"document {document_id} not found")
    if doc.review_status == DocumentReviewStatus.confirmed:
        raise HTTPException(409, "document already confirmed")
    doc.review_status = DocumentReviewStatus.ignored
    await session.commit()
    return {"document_id": str(document_id), "status": "ignored"}


@router.post("/business_card")
async def upload_business_card(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    img = await file.read()
    if not img:
        raise HTTPException(400, "empty file")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "expected an image")

    try:
        result = await ingest_business_card(
            session=session,
            image_bytes=img,
            original_filename=file.filename or "card.jpg",
            content_type=file.content_type,
            uploader=uploader,
        )
    except LLMCallFailed as exc:
        logger.exception("business_card ingest LLM call failed")
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc

    await session.commit()

    return {
        "document_id": str(result.document_id),
        "contact_id": str(result.contact_id),
        "needs_review": result.needs_review,
        "warnings": result.warnings,
    }


@router.post("/wechat_screenshot")
async def upload_wechat_screenshot(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    img = await file.read()
    if not img:
        raise HTTPException(400, "empty file")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "expected an image")

    try:
        r = await ingest_wechat_screenshot(
            session=session,
            image_bytes=img,
            original_filename=file.filename or "wechat.jpg",
            content_type=file.content_type,
            uploader=uploader,
        )
    except LLMCallFailed as exc:
        logger.exception("wechat ingest LLM call failed")
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc

    await session.commit()

    return {
        "document_id": str(r.document_id),
        "message_count": r.message_count,
        "extracted_entity_count": r.extracted_entity_count,
        "summary": r.summary,
        "confidence_overall": r.confidence_overall,
        "warnings": r.warnings,
    }


