"""RQ worker function for /api/win/ingest jobs.

Enqueued by ``yunwei_win.services.ingest.job_queue.enqueue_ingest_job``.
The queue carries two strings — ``job_id`` and ``enterprise_id`` — under
JSONSerializer. The worker reads the IngestJob row from the tenant DB,
dispatches schema-first extraction, and persists result pointers + status
transitions.

Tenant routing: the enqueue path passes ``enterprise_id`` as a positional
arg so the worker can resolve the tenant engine directly via
``yunwei_win.db.get_engine_for(enterprise_id)`` — no Redis side-channel.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_ingest_job_tables, ensure_schema_ingest_tables, get_engine_for
from yunwei_win.models import IngestJob, IngestJobStage, IngestJobStatus
from yunwei_win.services.schema_ingest.upload import PreStoredFile
from yunwei_win.services.schema_ingest import auto_ingest as schema_auto_ingest

logger = logging.getLogger(__name__)


# ---------- stage mapping -------------------------------------------------
#
# ``auto_ingest`` emits free-form stage strings via the progress callback.
# Persist them onto IngestJob.stage as the matching enum value so the UI's
# pipeline-step indicator stays in lock-step. Unknown stage names roll up
# to ``extract`` (the most common intermediate bucket) instead of crashing.

_STAGE_BY_NAME: dict[str, IngestJobStage] = {
    "received": IngestJobStage.received,
    "stored": IngestJobStage.stored,
    "ocr": IngestJobStage.ocr,
    "route": IngestJobStage.route,
    "extract": IngestJobStage.extract,
    "merge": IngestJobStage.merge,
    "auto_done": IngestJobStage.done,
    # auto.py emits ``auto`` (entry) and the per-extractor sub-stages.
    "auto": IngestJobStage.received,
    "identity_extract": IngestJobStage.extract,
    "commercial_extract": IngestJobStage.extract,
    "ops_extract": IngestJobStage.extract,
    "commitment_task_risk_extract": IngestJobStage.extract,
    "route_done": IngestJobStage.route,
    "extract_done": IngestJobStage.extract,
    "merge_done": IngestJobStage.merge,
    # vNext stage names from schema_ingest.auto.
    "parsing": IngestJobStage.ocr,
    "routing": IngestJobStage.route,
    "extracting": IngestJobStage.extract,
    "validating": IngestJobStage.extract,
    "resolving": IngestJobStage.merge,
    "review_ready": IngestJobStage.done,
}


def _stage_for(name: str) -> IngestJobStage:
    return _STAGE_BY_NAME.get(name, IngestJobStage.extract)


class _CanceledMidFlight(Exception):
    """Raised inside progress() when the job was canceled externally so the
    worker can bail at the next stage boundary without writing a draft."""


# ---------- RQ entrypoint ------------------------------------------------


def run_ingest_job(job_id: str, enterprise_id: str) -> None:
    """Synchronous entrypoint RQ calls. Boots an asyncio loop, runs the
    actual coroutine, and lets RQ record completion. Every exception is
    caught and persisted as ``status=failed`` so the worker never crashes
    its RQ runner mid-job."""
    asyncio.run(process_ingest_job(job_id, enterprise_id))


async def process_ingest_job(job_id: str, enterprise_id: str) -> None:
    """Drive a single ingest job end-to-end.

    Postgres is the source of truth; every status/stage change is committed
    immediately. If the job was canceled (status flipped externally while
    queued or partway through), the worker bails at the next stage
    boundary instead of writing extracted/result_json.
    """
    job_uuid = UUID(job_id)

    engine = await get_engine_for(enterprise_id)
    await ensure_ingest_job_tables(engine)
    await ensure_schema_ingest_tables(engine)

    # Phase 1: load + mark running. Skip terminal/extracted jobs so a
    # duplicate enqueue (retry races, RQ replay) is idempotent.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        job = (
            await session.execute(
                select(IngestJob).where(IngestJob.id == job_uuid)
            )
        ).scalar_one_or_none()
        if job is None:
            logger.warning("worker: job %s not found", job_id)
            return
        if job.status in (IngestJobStatus.canceled, IngestJobStatus.confirmed):
            logger.info(
                "worker: job %s already in terminal state %s; skipping",
                job_id,
                job.status.value,
            )
            return
        if job.status == IngestJobStatus.extracted:
            logger.info(
                "worker: job %s already extracted; nothing to do", job_id
            )
            return

        job.status = IngestJobStatus.running
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        await session.commit()

    # Phase 2: run extraction. The auto_ingest path commits its own
    # transactions; we use a dedicated session per phase to avoid
    # interfering with that.
    try:
        await _run_extraction(engine, job_uuid)
    except BaseException as exc:
        logger.exception("worker: job %s failed", job_id)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            j = (
                await session.execute(
                    select(IngestJob).where(IngestJob.id == job_uuid)
                )
            ).scalar_one_or_none()
            if j is None:
                return
            if j.status == IngestJobStatus.canceled:
                # External cancel won the race — don't overwrite it.
                return
            j.status = IngestJobStatus.failed
            j.error_message = _safe_error_message(exc)
            j.finished_at = datetime.now(timezone.utc)
            await session.commit()


def _safe_error_message(exc: BaseException) -> str:
    raw = f"{type(exc).__name__}: {exc!s}"
    sanitized = re.sub(
        r"\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\b",
        "credential",
        raw,
    )
    return sanitized[:2000]


async def _run_extraction(engine, job_uuid: UUID) -> None:
    """Phase 2 body: hydrate inputs from the job row, run auto_ingest, and
    persist the result.

    Split out so ``process_ingest_job`` can wrap a single try/except
    around the heavy work without the cancel-check and status-flip
    plumbing leaking into the failure handler.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        job = (
            await session.execute(
                select(IngestJob).where(IngestJob.id == job_uuid)
            )
        ).scalar_one_or_none()
        assert job is not None  # phase 1 already confirmed existence

        async def progress(stage_name: str, message: str) -> None:
            """Progress callback the extractors invoke at stage boundaries.

            We reload the row in a side session so an external cancel flip
            (POST /jobs/{id}/cancel) is honored mid-flight: when we see
            ``status=canceled`` we raise so the caller can bail before
            writing the extracted draft.
            """
            async with AsyncSession(engine, expire_on_commit=False) as sub:
                j = (
                    await sub.execute(
                        select(IngestJob).where(IngestJob.id == job_uuid)
                    )
                ).scalar_one_or_none()
                if j is None:
                    return
                if j.status == IngestJobStatus.canceled:
                    raise _CanceledMidFlight()
                j.stage = _stage_for(stage_name)
                j.progress_message = (message or "")[:500]
                await sub.commit()

        # Reuse the API-staged file via PreStoredFile when one exists. Text
        # jobs (pasted_text) go through the existing text_content path.
        pre: PreStoredFile | None = None
        if job.staged_file_url:
            pre = PreStoredFile(
                path=job.staged_file_url,
                sha256=job.file_sha256 or "",
                size=job.file_size_bytes or 0,
                original_filename=job.original_filename,
                content_type=job.content_type,
            )

        # ``auto_ingest`` accepts file_bytes for the image / scanned-PDF /
        # office OCR paths. With pre_stored we let collect_evidence read
        # bytes on demand so the happy native-text PDF path stays free.
        file_bytes: bytes | None = None
        if pre and pre.path and Path(pre.path).exists() and not job.text_content:
            # Only preload bytes when the modality is likely to need them
            # (image/office). PDF native-text reads from disk directly.
            ct = (job.content_type or "").lower()
            fn = (job.original_filename or "").lower()
            needs_bytes = (
                ct.startswith("image/")
                or fn.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"))
                or fn.endswith((".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt"))
            )
            if needs_bytes:
                try:
                    file_bytes = Path(pre.path).read_bytes()
                except FileNotFoundError:
                    logger.warning(
                        "worker: pre_stored file missing for job %s at %s",
                        job_uuid,
                        pre.path,
                    )

        source_hint = job.source_hint or "file"
        try:
            result = await schema_auto_ingest(
                session=session,
                file_bytes=file_bytes,
                original_filename=job.original_filename,
                content_type=job.content_type,
                text_content=job.text_content,
                source_hint=source_hint,  # type: ignore[arg-type]
                uploader=job.uploader,
                progress=progress,
                pre_stored=pre,
            )
        except _CanceledMidFlight:
            logger.info("worker: job %s canceled mid-flight", job_uuid)
            return

        # Schema-first ingest only ``flush()`` the Document row; we own the
        # surrounding commit so the row survives this session context and the
        # follow-up session can stamp ``IngestJob.document_id`` without
        # violating the documents FK.
        await session.commit()

    # Persist result on a fresh session. The earlier commit above made the
    # Document + extraction rows durable; this second session writes the
    # IngestJob columns against committed data.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        j = (
            await session.execute(
                select(IngestJob).where(IngestJob.id == job_uuid)
            )
        ).scalar_one_or_none()
        if j is None:
            return
        if j.status == IngestJobStatus.canceled:
            return
        j.document_id = result.document_id
        j.extraction_id = result.extraction_id
        # vNext result_json: a compact pointer + summary, not the full
        # draft. The full draft is the canonical
        # ``DocumentExtraction.review_draft`` — clients should fetch via
        # GET /extractions/{id}/review instead of reading job.result_json.
        j.result_json = {
            "workflow": "vnext",
            "document_id": str(result.document_id),
            "parse_id": str(result.parse_id),
            "extraction_id": str(result.extraction_id),
            "selected_tables": [
                t.get("table_name") for t in (result.selected_tables or [])
                if isinstance(t, dict)
            ],
        }
        j.status = IngestJobStatus.extracted
        j.stage = IngestJobStage.done
        j.progress_message = "已生成 vNext 草稿，待人工确认"
        j.finished_at = datetime.now(timezone.utc)
        await session.commit()
