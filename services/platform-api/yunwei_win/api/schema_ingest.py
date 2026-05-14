"""Schema-first ingest API.

Mounted under ``/api/win/ingest``. Uploads become schema-first review jobs:
the worker extracts a table/cell ReviewDraft, and confirm writes reviewed
cells into company data tables.

Endpoints:
- ``POST /jobs``                              — stage files / text and enqueue.
- ``GET /jobs``                               — list jobs (active / history).
- ``GET /jobs/{job_id}``                      — single job (+ embedded draft).
- ``POST /jobs/{job_id}/retry``               — re-enqueue a failed/canceled job.
- ``POST /jobs/{job_id}/cancel``              — cancel a queued/running job.
- ``GET /extractions/{extraction_id}``        — fetch the stored ReviewDraft.
- ``PATCH /extractions/{extraction_id}``      — overwrite the stored ReviewDraft.
- ``POST /extractions/{extraction_id}/confirm`` — apply patches + write business rows.
- ``POST /extractions/{extraction_id}/ignore`` — mark draft + linked job ignored.

The confirm endpoint returns ``invalid_cells`` in the response body. When
non-empty we surface that as HTTP 400 so the frontend can read the body and
highlight the offending cells.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import (
    ensure_ingest_job_tables_for,
    ensure_schema_ingest_tables_for,
    get_session,
)
from yunwei_win.models import (
    Document,
    DocumentReviewStatus,
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.services.ingest.job_queue import (
    enqueue_ingest_job,
    get_ingest_queue,
    reset_stale_running_jobs,
)
from yunwei_win.services.ingest.unified_schemas import PipelineRoutePlan  # noqa: F401
from yunwei_win.services.schema_ingest import (
    ConfirmExtractionRequest,
    ConfirmExtractionResponse,
    ReviewDraft,
    confirm_review_draft,
)
from yunwei_win.services.storage import store_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest")


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


# ---- helpers --------------------------------------------------------


def _enterprise_id_from_request(request: Request) -> str:
    eid = getattr(request.state, "enterprise_id", None)
    if not eid:
        raise HTTPException(401, "not_authenticated")
    return eid


def _job_dict(j: IngestJob) -> dict[str, Any]:
    return {
        "id": str(j.id),
        "batch_id": str(j.batch_id),
        "enterprise_id": j.enterprise_id,
        "document_id": str(j.document_id) if j.document_id else None,
        "extraction_id": str(j.extraction_id) if j.extraction_id else None,
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


def _extraction_dict(e: DocumentExtraction) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "document_id": str(e.document_id),
        "schema_version": e.schema_version,
        "provider": e.provider,
        "status": e.status.value,
        "warnings": e.warnings,
        "review_draft": e.review_draft,
        "route_plan": e.route_plan,
        "created_by": e.created_by,
        "confirmed_by": e.confirmed_by,
        "confirmed_at": e.confirmed_at.isoformat() if e.confirmed_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


async def _load_job(
    session: AsyncSession, *, job_id: UUID, enterprise_id: str
) -> IngestJob:
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
    return j


# ---- POST /jobs -----------------------------------------------------


@router.post("/jobs")
async def create_ingest_jobs(
    request: Request,
    files: list[UploadFile] = File(default_factory=list),
    text: str | None = Form(default=None),
    source_hint: Literal["file", "camera", "pasted_text"] = Form(default="file"),
    uploader: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Stage files / text into an IngestBatch + IngestJob rows, then enqueue."""

    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)

    staged: list[dict[str, Any]] = []
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
    await session.commit()

    for j in jobs:
        try:
            j.attempts = 1
            j.rq_job_id = enqueue_ingest_job(
                str(j.id), attempt=1, enterprise_id=enterprise_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("enqueue failed for job %s", j.id)
            j.status = IngestJobStatus.failed
            j.error_message = f"enqueue failed: {exc!s}"
            j.finished_at = datetime.now(timezone.utc)
    await session.commit()

    return {
        "batch_id": str(batch.id),
        "jobs": [_job_dict(j) for j in jobs],
    }


# ---- GET /jobs ------------------------------------------------------


@router.get("/jobs")
async def list_ingest_jobs(
    request: Request,
    status: Literal["active", "history", "all"] = "active",
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)

    reset_ids = await reset_stale_running_jobs(session)
    for jid in reset_ids:
        j = (
            await session.execute(
                select(IngestJob).where(
                    IngestJob.id == jid,
                    IngestJob.enterprise_id == enterprise_id,
                )
            )
        ).scalar_one_or_none()
        if j is None:
            continue
        try:
            j.attempts = (j.attempts or 0) + 1
            j.rq_job_id = enqueue_ingest_job(
                str(j.id), attempt=j.attempts, enterprise_id=enterprise_id,
            )
        except Exception as exc:  # noqa: BLE001
            j.status = IngestJobStatus.failed
            j.error_message = f"watchdog re-enqueue failed: {exc!s}"
            j.finished_at = datetime.now(timezone.utc)
    if reset_ids:
        await session.commit()

    stmt = select(IngestJob).where(IngestJob.enterprise_id == enterprise_id)
    if status == "active":
        stmt = stmt.where(IngestJob.status.in_(_ACTIVE_STATUSES))
    elif status == "history":
        stmt = stmt.where(IngestJob.status.in_(_HISTORY_STATUSES))
    stmt = stmt.order_by(desc(IngestJob.created_at)).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_job_dict(j) for j in rows]


@router.delete("/jobs/history")
async def clear_ingest_history(
    request: Request,
    status: Literal["failed", "canceled", "confirmed", "all"] = Query(default="failed"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)

    if status == "failed":
        target = (IngestJobStatus.failed,)
    elif status == "canceled":
        target = (IngestJobStatus.canceled,)
    elif status == "confirmed":
        target = (IngestJobStatus.confirmed,)
    else:
        target = _HISTORY_STATUSES

    stmt = select(IngestJob).where(
        IngestJob.enterprise_id == enterprise_id,
        IngestJob.status.in_(target),
    )
    rows = (await session.execute(stmt)).scalars().all()
    deleted = len(rows)
    if deleted:
        await session.execute(
            delete(IngestJob).where(
                IngestJob.enterprise_id == enterprise_id,
                IngestJob.status.in_(target),
            )
        )
        await session.commit()
    return {"deleted": deleted, "status_filter": status}


@router.get("/jobs/{job_id}")
async def get_ingest_job(
    job_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)
    j = await _load_job(session, job_id=job_id, enterprise_id=enterprise_id)
    payload = _job_dict(j)
    if j.extraction_id is not None:
        extraction = (
            await session.execute(
                select(DocumentExtraction).where(DocumentExtraction.id == j.extraction_id)
            )
        ).scalar_one_or_none()
        payload["review_draft"] = extraction.review_draft if extraction else None
        payload["extraction"] = _extraction_dict(extraction) if extraction else None
    else:
        payload["review_draft"] = None
        payload["extraction"] = None
    return payload


# ---- retry / cancel ------------------------------------------------


@router.post("/jobs/{job_id}/retry")
async def retry_ingest_job(
    job_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)
    j = await _load_job(session, job_id=job_id, enterprise_id=enterprise_id)
    if j.status not in (IngestJobStatus.failed, IngestJobStatus.canceled):
        raise HTTPException(409, f"cannot retry job in status {j.status.value}")
    j.attempts = (j.attempts or 0) + 1
    j.status = IngestJobStatus.queued
    j.stage = IngestJobStage.received
    j.error_message = None
    j.finished_at = None
    j.progress_message = None
    try:
        j.rq_job_id = enqueue_ingest_job(
            str(j.id), attempt=j.attempts, enterprise_id=enterprise_id,
        )
    except Exception as exc:  # noqa: BLE001
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
) -> dict[str, Any]:
    enterprise_id = _enterprise_id_from_request(request)
    await ensure_ingest_job_tables_for(enterprise_id)
    await ensure_schema_ingest_tables_for(enterprise_id)
    j = await _load_job(session, job_id=job_id, enterprise_id=enterprise_id)
    if j.status in (IngestJobStatus.confirmed, IngestJobStatus.canceled):
        return _job_dict(j)
    if j.status == IngestJobStatus.failed:
        raise HTTPException(409, "cannot cancel a failed job; use retry")
    # Best-effort RQ cancel.
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


# ---- extraction endpoints ------------------------------------------


async def _load_extraction(
    session: AsyncSession, extraction_id: UUID
) -> DocumentExtraction:
    e = (
        await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(404, "extraction not found")
    return e


@router.get("/extractions/{extraction_id}")
async def get_extraction(
    extraction_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _ = _enterprise_id_from_request(request)
    await ensure_schema_ingest_tables_for(request.state.enterprise_id)
    return _extraction_dict(await _load_extraction(session, extraction_id))


@router.patch("/extractions/{extraction_id}")
async def patch_extraction(
    extraction_id: UUID,
    request: Request,
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _ = _enterprise_id_from_request(request)
    await ensure_schema_ingest_tables_for(request.state.enterprise_id)
    extraction = await _load_extraction(session, extraction_id)
    if extraction.status != DocumentExtractionStatus.pending_review:
        raise HTTPException(409, f"cannot patch extraction in status {extraction.status.value}")
    new_draft = payload.get("review_draft")
    if new_draft is None:
        raise HTTPException(400, "review_draft is required")
    # Validate it parses as a ReviewDraft before persisting; surface a 400 if not.
    try:
        ReviewDraft.model_validate(new_draft)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"invalid review_draft: {exc!s}") from exc
    extraction.review_draft = new_draft
    await session.commit()
    return _extraction_dict(extraction)


@router.post("/extractions/{extraction_id}/ignore")
async def ignore_extraction(
    extraction_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _ = _enterprise_id_from_request(request)
    await ensure_schema_ingest_tables_for(request.state.enterprise_id)
    extraction = await _load_extraction(session, extraction_id)
    extraction.status = DocumentExtractionStatus.ignored
    # Also flip the linked job (if any).
    job = (
        await session.execute(
            select(IngestJob).where(IngestJob.extraction_id == extraction_id)
        )
    ).scalar_one_or_none()
    if job is not None and job.status not in (
        IngestJobStatus.confirmed,
        IngestJobStatus.canceled,
    ):
        job.status = IngestJobStatus.canceled
        job.finished_at = datetime.now(timezone.utc)
    # Best-effort: mark the document as ignored too.
    doc = (
        await session.execute(
            select(Document).where(Document.id == extraction.document_id)
        )
    ).scalar_one_or_none()
    if doc is not None and doc.review_status != DocumentReviewStatus.confirmed:
        doc.review_status = DocumentReviewStatus.ignored
    await session.commit()
    return _extraction_dict(extraction)


@router.post("/extractions/{extraction_id}/confirm")
async def confirm_extraction(
    extraction_id: UUID,
    request: Request,
    body: ConfirmExtractionRequest,
    session: AsyncSession = Depends(get_session),
) -> ConfirmExtractionResponse:
    _ = _enterprise_id_from_request(request)
    await ensure_schema_ingest_tables_for(request.state.enterprise_id)
    result = await confirm_review_draft(
        session=session,
        extraction_id=extraction_id,
        request=body,
        confirmed_by=None,
    )
    if result.invalid_cells:
        raise HTTPException(
            status_code=400,
            detail={
                "extraction_id": str(result.extraction_id),
                "document_id": str(result.document_id),
                "status": result.status,
                "invalid_cells": result.invalid_cells,
            },
        )
    return result
