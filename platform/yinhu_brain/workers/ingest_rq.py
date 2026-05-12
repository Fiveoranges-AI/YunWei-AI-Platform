"""RQ worker function for /win/api/ingest/jobs.

Enqueued by ``yinhu_brain.services.ingest.job_queue.enqueue_ingest_job``.
The queue carries two strings — ``job_id`` and ``enterprise_id`` — under
JSONSerializer. The worker reads the IngestJob row from the tenant DB,
drives ``auto_ingest``, and persists ``result_json`` + status transitions.

Tenant routing: the enqueue path passes ``enterprise_id`` as a positional
arg so the worker can resolve the tenant engine directly via
``yinhu_brain.db.get_engine_for(enterprise_id)`` — no Redis side-channel.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.db import ensure_ingest_job_tables, get_engine_for
from yinhu_brain.models import IngestJob, IngestJobStage, IngestJobStatus
from yinhu_brain.services.ingest.auto import auto_ingest
from yinhu_brain.services.ingest.evidence import PreStoredFile

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
            j.error_message = f"{type(exc).__name__}: {exc!s}"[:2000]
            j.finished_at = datetime.now(timezone.utc)
            await session.commit()


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
        # jobs (pasted_text) go through the legacy text_content path.
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
            result = await auto_ingest(
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

        # ``auto_ingest`` itself does not always commit — the Mistral path
        # commits before its extractor fan-out, but the LandingAI path only
        # ``flush()``-es Document inserts and the raw_llm_response update.
        # The web /auto endpoint commits in its surrounding NDJSON stream
        # wrapper; the worker has no such wrapper. Without an explicit
        # commit here the ``async with`` exits and rolls back the Document
        # INSERT → the follow-up session's UPDATE on IngestJob.document_id
        # then violates the documents FK. This was the root cause of
        # ``ForeignKeyViolationError: ingest_jobs_document_id_fkey`` on the
        # SCYN250620 / LandingAI deploy.
        await session.commit()

    # Persist result on a fresh session. The earlier commit above made the
    # Document + raw_llm_response durable; this second session writes the
    # IngestJob.document_id + result_json against committed data.
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
        j.result_json = {
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
        j.status = IngestJobStatus.extracted
        j.stage = IngestJobStage.done
        j.progress_message = "已生成草稿，待人工确认"
        j.finished_at = datetime.now(timezone.utc)
        await session.commit()


def _candidate_dict(c) -> dict:
    return {
        "id": str(c.id),
        "score": c.score,
        "reason": c.reason,
        "fields": c.fields,
    }
