"""POST /api/ingest/* endpoints — entity-first ingest.

These are the V1.5 surface that writes Customer / Contact / Order / Contract
rows directly. The newer customer-scoped surface at
`/api/customers/{id}/ingest` (see app.api.customer_profile) is memory-first
and writes to the inbox for human confirmation. Both surfaces persist a
Document and an llm_calls audit row.

Routes:
- /api/ingest/contract          PDF/DOC/DOCX/PPT/PPTX → draft, then confirm writes entities
- /api/ingest/business_card     image → Customer + Contact + provenance
- /api/ingest/wechat_screenshot image → chat_log Document + extracted hints

All three endpoints stream their response as NDJSON
(``application/x-ndjson``). The server emits named
``{"status":"progress","stage":"ocr","message":"..."}`` events for UI
pipeline nodes, plus ``{"status":"processing"}`` heartbeats every 20 seconds
so Cloudflare's 100-second edge timeout (the source of the historical 524
failures on app.fiveoranges.ai) doesn't kill the request mid-extraction. The
final line of the stream is either ``{"status":"done", ...result}`` (with
the same fields the legacy JSON shape returned, plus the status sentinel) or
``{"status":"error", "error": "..."}``. Clients should parse the last
non-empty done/error line as the result.
"""

from __future__ import annotations

import asyncio
import json
import logging

from typing import Any, AsyncIterator, Awaitable, Callable, Literal
from uuid import UUID

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.db import ensure_ingest_job_tables_for, get_session
from yinhu_brain.models import (
    Document,
    DocumentReviewStatus,
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yinhu_brain.services.ingest.job_queue import (
    enqueue_ingest_job,
    get_ingest_queue,
    remember_enterprise_for_job,
)
from yinhu_brain.services.storage import store_upload
from yinhu_brain.services.ingest.auto import auto_ingest
from yinhu_brain.services.ingest.auto_confirm import (
    AutoConfirmResult,
    commit_auto_extraction,
)
from yinhu_brain.services.ingest.business_card import ingest_business_card
from yinhu_brain.services.ingest.contract import (
    MatchCandidate,
    commit_contract_extraction,
    extract_contract_draft,
)
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.schemas import ContractConfirmRequest
from yinhu_brain.services.ingest.unified_schemas import AutoConfirmRequest
from yinhu_brain.services.ingest.wechat import ingest_wechat_screenshot
from yinhu_brain.services.llm import LLMCallFailed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest")

# How long to wait between {"status":"processing"} heartbeats. Must be
# comfortably under Cloudflare's 100s edge timeout to keep the connection
# alive while the LLM runs.
_HEARTBEAT_SECONDS = 20.0
_CONTRACT_FILE_EXTS = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}
_CONTRACT_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _json_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


async def _stream_with_progress(
    work_factory: Callable[[ProgressCallback], Awaitable[dict]],
    *,
    session: AsyncSession,
    label: str,
) -> AsyncIterator[bytes]:
    """Run ``work`` while streaming named progress events and heartbeats.

    ``work_factory`` receives an async ``emit(stage, message)`` callback.
    Those events are streamed as ``{"status":"progress", ...}`` lines so
    clients can render the current pipeline node instead of a generic spinner.
    Heartbeats continue every ~20s to keep long OCR / LLM calls alive.

    The factory must return the success-payload dict; this wrapper adds the
    ``status`` sentinel and handles the session.commit() / rollback so the
    caller's coroutine stays focused on extraction logic.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    last_stage = "received"
    last_message = "服务器已收到文件，准备处理"

    async def emit(stage: str, message: str) -> None:
        await queue.put({"status": "progress", "stage": stage, "message": message})
        # Let the stream flush the progress line before a following synchronous
        # step (for example local PDF text extraction) monopolizes the loop.
        await asyncio.sleep(0)

    task = asyncio.create_task(work_factory(emit))
    get_task: asyncio.Task[dict[str, Any]] | None = asyncio.create_task(queue.get())

    try:
        while True:
            wait_set = {task}
            if get_task is not None:
                wait_set.add(get_task)
            done, _ = await asyncio.wait(
                wait_set,
                timeout=_HEARTBEAT_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if get_task is not None and get_task in done:
                event = get_task.result()
                last_stage = str(event.get("stage") or last_stage)
                last_message = str(event.get("message") or last_message)
                yield _json_line(event)
                get_task = asyncio.create_task(queue.get())
                continue
            if task in done:
                if get_task is not None and not get_task.done():
                    get_task.cancel()
                while not queue.empty():
                    event = queue.get_nowait()
                    last_stage = str(event.get("stage") or last_stage)
                    last_message = str(event.get("message") or last_message)
                    yield _json_line(event)
                break
            yield _json_line(
                {
                    "status": "processing",
                    "stage": last_stage,
                    "message": last_message,
                }
            )
    finally:
        if get_task is not None and not get_task.done():
            get_task.cancel()

    try:
        result = await task
    except LLMCallFailed as exc:
        logger.exception("%s LLM call failed", label)
        await session.rollback()
        yield _json_line({"status": "error", "error": f"upstream LLM error: {exc!s}"})
        return
    except Exception as exc:
        logger.exception("%s failed", label)
        await session.rollback()
        yield _json_line({"status": "error", "error": f"{label} failed: {exc!s}"})
        return

    await session.commit()
    payload: dict[str, Any] = {"status": "done", **result}
    yield _json_line(payload)


def _ndjson(stream: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="application/x-ndjson",
        # Disable nginx/CDN buffering so the heartbeats actually reach
        # the edge instead of being held until the body completes.
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )


@router.post("/contract")
async def upload_contract_preview(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Phase 1: extract a draft from the PDF. Persists the Document and the
    LLM's structured output but does NOT create Customer/Order/Contract rows.
    Frontend reviews the draft and POSTs to /confirm.

    Streamed NDJSON — see module docstring."""
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(400, "empty file")
    name = file.filename or ""
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    ct = (file.content_type or "").lower()
    if ext not in _CONTRACT_FILE_EXTS and ct not in _CONTRACT_CONTENT_TYPES:
        raise HTTPException(400, "expected a PDF, DOC, DOCX, PPT, or PPTX contract file")

    fname = file.filename or "contract.pdf"

    async def _do(progress: ProgressCallback) -> dict:
        await progress("received", "服务器已收到合同文件")
        draft = await extract_contract_draft(
            session=session,
            pdf_bytes=pdf_bytes,
            original_filename=fname,
            content_type=file.content_type,
            uploader=uploader,
            progress=progress,
        )
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

    return _ndjson(
        _stream_with_progress(_do, session=session, label="contract draft"),
    )


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
) -> StreamingResponse:
    img = await file.read()
    if not img:
        raise HTTPException(400, "empty file")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "expected an image")

    fname = file.filename or "card.jpg"
    ct = file.content_type

    async def _do(progress: ProgressCallback) -> dict:
        await progress("received", "服务器已收到名片图片")
        result = await ingest_business_card(
            session=session,
            image_bytes=img,
            original_filename=fname,
            content_type=ct,
            uploader=uploader,
            progress=progress,
        )
        return {
            "document_id": str(result.document_id),
            "contact_id": str(result.contact_id),
            "customer_id": str(result.customer_id) if result.customer_id else None,
            "customer_name": result.customer_name,
            "contact_name": result.contact_name,
            "needs_review": result.needs_review,
            "warnings": result.warnings,
        }

    return _ndjson(
        _stream_with_progress(_do, session=session, label="business_card ingest"),
    )


# ---------- Unified /auto pipeline -----------------------------------------
#
# The newer entry point that replaces the per-document-type endpoints above.
# Same NDJSON shape, but a single request handles file uploads, camera
# captures, and pasted text — the planner inside ``auto_ingest`` decides
# which extractors to fan out to. The legacy ``/contract``,
# ``/business_card``, ``/wechat_screenshot`` endpoints are kept until the
# frontend (Agent H) cuts over.


@router.post("/auto")
async def upload_auto(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    source_hint: Literal["file", "camera", "pasted_text"] = Form(default="file"),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Unified entrypoint: file or text → ``UnifiedDraft`` + match candidates.

    Streamed NDJSON. Final ``done`` line carries::

        {
          "status": "done",
          "document_id": "...",
          "plan": {targets, extractors, reason, review_required},
          "draft": {customer, contacts, order, contract, events, ...,
                    needs_review_fields, warnings},
          "candidates": {customer: [...], contacts: [[...], ...]},
          "needs_review_fields": [...]
        }

    The frontend reviews the draft and POSTs back to
    ``/api/ingest/auto/{document_id}/confirm`` (or ``/cancel`` to drop it).
    """
    file_bytes: bytes | None = None
    filename: str | None = None
    ct: str | None = None
    if file is not None:
        file_bytes = await file.read()
        filename = file.filename
        ct = file.content_type
    if not file_bytes and not (text and text.strip()):
        raise HTTPException(400, "缺少 file 或 text")

    async def _do(progress: ProgressCallback) -> dict:
        await progress("received", "服务器已收到上传内容")
        result = await auto_ingest(
            session=session,
            file_bytes=file_bytes,
            original_filename=filename,
            content_type=ct,
            text_content=text,
            source_hint=source_hint,
            uploader=uploader,
            progress=progress,
        )
        return {
            "document_id": str(result.document_id),
            "plan": result.plan.model_dump(mode="json"),
            "route_plan": (
                result.route_plan.model_dump(mode="json")
                if result.route_plan
                else None
            ),
            "draft": result.draft.model_dump(mode="json"),
            "pipeline_results": [
                r.model_dump(mode="json")
                for r in getattr(result.draft, "pipeline_results", [])
            ],
            "candidates": {
                "customer": [
                    _candidate_dict(c) for c in result.candidates.customer_candidates
                ],
                "contacts": [
                    [_candidate_dict(c) for c in slot]
                    for slot in result.candidates.contact_candidates
                ],
            },
            "needs_review_fields": list(result.draft.needs_review_fields),
        }

    return _ndjson(_stream_with_progress(_do, session=session, label="auto ingest"))


@router.post("/auto/{document_id}/confirm")
async def upload_auto_confirm(
    document_id: UUID,
    payload: AutoConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Phase 2 of the /auto pipeline: persist the user-reviewed draft.

    Customer + each contact carry a per-entity decision (``mode`` = ``new`` |
    ``merge``); order + contract are always new (mirrors the legacy
    ``/contract`` confirm shape). Ops rows (events / commitments / tasks /
    risk_signals / memory_items) are append-only and bound to the resolved
    customer.
    """
    try:
        result: AutoConfirmResult = await commit_auto_extraction(
            session=session,
            document_id=document_id,
            request=payload,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("auto confirm failed")
        raise HTTPException(422, f"confirm failed: {exc!s}") from exc

    await session.commit()

    return {
        "document_id": str(result.document_id),
        "created_entities": {
            "customer_id": (
                str(result.customer_id) if result.customer_id else None
            ),
            "contact_ids": [str(x) for x in result.contact_ids],
            "order_id": str(result.order_id) if result.order_id else None,
            "contract_id": str(result.contract_id) if result.contract_id else None,
            "event_ids": [str(x) for x in result.event_ids],
            "commitment_ids": [str(x) for x in result.commitment_ids],
            "task_ids": [str(x) for x in result.task_ids],
            "risk_signal_ids": [str(x) for x in result.risk_signal_ids],
            "memory_item_ids": [str(x) for x in result.memory_item_ids],
        },
        "confidence_overall": result.confidence_overall,
        "warnings": result.warnings,
        "needs_review_fields": result.needs_review_fields,
    }


@router.post("/auto/{document_id}/cancel")
async def upload_auto_cancel(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """User dropped the auto draft. Same semantics as ``/contract/.../cancel``:
    the Document row + raw_llm_response are preserved for audit, only
    ``review_status`` flips to ``ignored``."""
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


@router.post("/wechat_screenshot")
async def upload_wechat_screenshot(
    file: UploadFile = File(...),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    img = await file.read()
    if not img:
        raise HTTPException(400, "empty file")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "expected an image")

    fname = file.filename or "wechat.jpg"
    ct = file.content_type

    async def _do(progress: ProgressCallback) -> dict:
        await progress("received", "服务器已收到截图图片")
        r = await ingest_wechat_screenshot(
            session=session,
            image_bytes=img,
            original_filename=fname,
            content_type=ct,
            uploader=uploader,
            progress=progress,
        )
        return {
            "document_id": str(r.document_id),
            "message_count": r.message_count,
            "extracted_entity_count": r.extracted_entity_count,
            "summary": r.summary,
            "confidence_overall": r.confidence_overall,
            "warnings": r.warnings,
        }

    return _ndjson(
        _stream_with_progress(_do, session=session, label="wechat ingest"),
    )


# ---------- Async /jobs surface (RQ-backed) -------------------------------
#
# These endpoints stage uploads + enqueue an RQ job and return immediately.
# The worker (yinhu_brain.workers.ingest_rq) reads the IngestJob row, runs
# the same auto_ingest internals as /auto, and writes status=extracted +
# result_json back to Postgres. Clients poll GET /jobs/{id} until extracted,
# then call /confirm to commit.


def _job_dict(j: IngestJob) -> dict:
    return {
        "id": str(j.id),
        "batch_id": str(j.batch_id),
        "document_id": str(j.document_id) if j.document_id else None,
        "original_filename": j.original_filename,
        "content_type": j.content_type,
        "source_hint": j.source_hint,
        "uploader": j.uploader,
        "status": j.status.value,
        "stage": j.stage.value,
        "progress_message": j.progress_message,
        "error_message": j.error_message,
        "attempts": j.attempts,
        "result_json": j.result_json,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


def _enterprise_id_from_request(request: Request) -> str:
    eid = getattr(request.state, "enterprise_id", None)
    if not eid:
        raise HTTPException(401, "not_authenticated")
    return eid


@router.post("/jobs")
async def create_ingest_jobs(
    request: Request,
    files: list[UploadFile] = File(default_factory=list),
    text: str | None = Form(default=None),
    source_hint: Literal["file", "camera", "pasted_text"] = Form(default="file"),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Stage uploaded files / text and enqueue worker jobs.

    Returns immediately with batch_id + job_ids. The actual extraction runs
    in an RQ worker (see workers/ingest_rq.py).
    """
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)

    staged: list[dict] = []
    for f in files:
        body = await f.read()
        if not body:
            continue
        stored = store_upload(body, f.filename or "upload.bin")
        staged.append({
            "filename": f.filename or "upload.bin",
            "content_type": f.content_type,
            "size": stored.size,
            "sha256": stored.sha256,
            "path": stored.path,
            "text": None,
        })
    if text and text.strip():
        staged.append({
            "filename": "note.txt",
            "content_type": "text/plain",
            "size": len(text.encode("utf-8")),
            "sha256": None,
            "path": None,
            "text": text,
        })
    if not staged:
        raise HTTPException(400, "no file or text provided")

    batch = IngestBatch(
        enterprise_id=enterprise_id,
        uploader=uploader,
        source="win-upload",
        total_jobs=len(staged),
    )
    session.add(batch)
    await session.flush()

    jobs: list[IngestJob] = []
    for s in staged:
        job = IngestJob(
            batch_id=batch.id,
            enterprise_id=enterprise_id,
            original_filename=s["filename"],
            content_type=s["content_type"],
            file_sha256=s["sha256"],
            file_size_bytes=s["size"],
            staged_file_url=s["path"],
            text_content=s["text"],
            source_hint=source_hint if s["text"] is None else "pasted_text",
            uploader=uploader,
            status=IngestJobStatus.queued,
            stage=IngestJobStage.received,
            attempts=0,
        )
        session.add(job)
        jobs.append(job)
    await session.flush()
    # Commit so the worker can see these rows.
    await session.commit()

    # Now enqueue. If Redis is down, mark queued jobs as failed with a
    # clear error so the user sees something actionable.
    for j in jobs:
        try:
            j.attempts = 1
            remember_enterprise_for_job(str(j.id), enterprise_id)
            j.rq_job_id = enqueue_ingest_job(str(j.id), attempt=1)
        except Exception as exc:
            logger.exception("enqueue failed for job %s", j.id)
            j.status = IngestJobStatus.failed
            j.error_message = f"enqueue failed: {exc!s}"
            j.finished_at = datetime.now(timezone.utc)
    await session.commit()

    return {
        "batch_id": str(batch.id),
        "jobs": [_job_dict(j) for j in jobs],
    }


_ACTIVE_STATUSES = (
    IngestJobStatus.queued,
    IngestJobStatus.running,
    IngestJobStatus.extracted,
)
_HISTORY_STATUSES = (
    IngestJobStatus.confirmed,
    IngestJobStatus.failed,
    IngestJobStatus.canceled,
)


@router.get("/jobs")
async def list_ingest_jobs(
    request: Request,
    status: Literal["active", "history", "all"] = "active",
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    stmt = select(IngestJob).where(IngestJob.enterprise_id == enterprise_id)
    if status == "active":
        stmt = stmt.where(IngestJob.status.in_(_ACTIVE_STATUSES))
    elif status == "history":
        stmt = stmt.where(IngestJob.status.in_(_HISTORY_STATUSES))
    stmt = stmt.order_by(desc(IngestJob.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_job_dict(j) for j in rows]


@router.get("/jobs/{job_id}")
async def get_ingest_job(
    job_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    j = (
        await session.execute(
            select(IngestJob).where(
                IngestJob.id == job_id,
                IngestJob.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if j is None:
        raise HTTPException(404, "job not found")
    return _job_dict(j)


@router.post("/jobs/{job_id}/retry")
async def retry_ingest_job(
    job_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    j = (
        await session.execute(
            select(IngestJob).where(
                IngestJob.id == job_id,
                IngestJob.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status not in (IngestJobStatus.failed, IngestJobStatus.canceled):
        raise HTTPException(409, f"cannot retry job in status {j.status.value}")
    MAX_ATTEMPTS = 3
    if j.attempts >= MAX_ATTEMPTS:
        raise HTTPException(409, f"retry limit reached ({MAX_ATTEMPTS})")
    j.attempts = (j.attempts or 0) + 1
    j.status = IngestJobStatus.queued
    j.stage = IngestJobStage.received
    j.error_message = None
    j.finished_at = None
    j.progress_message = None
    try:
        remember_enterprise_for_job(str(j.id), enterprise_id)
        j.rq_job_id = enqueue_ingest_job(str(j.id), attempt=j.attempts)
    except Exception as exc:
        logger.exception("retry enqueue failed for job %s", j.id)
        j.status = IngestJobStatus.failed
        j.error_message = f"enqueue failed: {exc!s}"
        j.finished_at = datetime.now(timezone.utc)
    await session.commit()
    return _job_dict(j)


@router.post("/jobs/{job_id}/cancel")
async def cancel_ingest_job(
    job_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    j = (
        await session.execute(
            select(IngestJob).where(
                IngestJob.id == job_id,
                IngestJob.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status in (IngestJobStatus.confirmed, IngestJobStatus.canceled):
        return _job_dict(j)  # idempotent
    if j.status == IngestJobStatus.failed:
        raise HTTPException(409, "cannot cancel a failed job; use retry")
    # Best-effort RQ cancel; safe even if rq_job_id missing.
    if j.rq_job_id:
        try:
            from rq.command import send_stop_job_command
            from rq.job import Job as RQJob
            queue = get_ingest_queue()
            try:
                rq_job = RQJob.fetch(
                    j.rq_job_id, connection=queue.connection, serializer=queue.serializer
                )
                if rq_job.is_started:
                    send_stop_job_command(queue.connection, j.rq_job_id)
                else:
                    rq_job.cancel()
            except Exception:
                logger.exception("rq cancel best-effort failed for %s", j.rq_job_id)
        except Exception:
            pass
    j.status = IngestJobStatus.canceled
    j.finished_at = datetime.now(timezone.utc)
    await session.commit()
    return _job_dict(j)


@router.post("/jobs/{job_id}/confirm")
async def confirm_ingest_job(
    job_id: UUID,
    request: Request,
    payload: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Confirm a job's extraction. Internally uses the same commit logic
    as /auto/{document_id}/confirm, then flips the job to status=confirmed.
    """
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    j = (
        await session.execute(
            select(IngestJob).where(
                IngestJob.id == job_id,
                IngestJob.enterprise_id == enterprise_id,
            )
        )
    ).scalar_one_or_none()
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status != IngestJobStatus.extracted:
        raise HTTPException(409, f"cannot confirm job in status {j.status.value}")
    if j.document_id is None:
        raise HTTPException(409, "job has no document_id; cannot confirm")

    try:
        confirm_req = AutoConfirmRequest.model_validate(payload)
    except Exception as exc:
        raise HTTPException(400, f"invalid confirm payload: {exc!s}") from exc
    try:
        ingest = await commit_auto_extraction(
            session=session, document_id=j.document_id, request=confirm_req,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    j.status = IngestJobStatus.confirmed
    j.finished_at = datetime.now(timezone.utc)
    await session.commit()

    return {
        "job_id": str(j.id),
        "document_id": str(ingest.document_id),
        "created_entities": {
            "customer_id": str(ingest.customer_id) if ingest.customer_id else None,
            "contact_ids": [str(x) for x in ingest.contact_ids],
            "order_id": str(ingest.order_id) if ingest.order_id else None,
            "contract_id": str(ingest.contract_id) if ingest.contract_id else None,
        },
        "warnings": ingest.warnings,
    }
