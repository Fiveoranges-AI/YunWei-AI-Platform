"""RQ queue + enqueue helper for ingest jobs.

The actual worker function lives in ``yunwei_win.workers.ingest_rq``.
This module just wires up the Redis connection + Queue singleton + a small
enqueue() helper API handlers call. JSONSerializer is used so the queue
can only carry primitive args (job_id + enterprise_id strings).

Tenant routing: ``enterprise_id`` is passed positionally to the worker
function so the worker can resolve the tenant engine directly — no Redis
side-channel hash. Loud failure if a caller forgets it (required kw-only
arg on ``enqueue_ingest_job``).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from redis import Redis
from rq import Queue, Retry
from rq.serializers import JSONSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

INGEST_QUEUE_NAME = "win-ingest"
WORKER_FN = "yunwei_win.workers.ingest_rq.run_ingest_job"

# Stale-running watchdog threshold. Jobs whose status is ``running`` but
# whose ``updated_at`` is older than this are considered orphaned (worker
# died mid-job) and get flipped back to ``queued`` so the next pickup can
# retry them.
STALE_RUNNING_AFTER_MINUTES = 15


@lru_cache(maxsize=1)
def _redis() -> Redis:
    url = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
    return Redis.from_url(url)


@lru_cache(maxsize=1)
def get_ingest_queue() -> Queue:
    return Queue(
        INGEST_QUEUE_NAME,
        connection=_redis(),
        serializer=JSONSerializer,
    )


def _rq_id_for(job_id: str, attempt: int) -> str:
    """Build the RQ job id for a given business job + attempt.

    RQ rejects any id with characters outside ``[A-Za-z0-9_-]`` so we
    can't use colons as separators (commit ``be56aee`` originally did and
    every enqueue blew up on real Redis with
    ``Job ID must only contain letters, numbers, underscores and dashes``).
    UUIDs use dashes already, so segment separators are dashes too.
    """
    return f"ingest-{job_id}-a{attempt}"


def enqueue_ingest_job(
    job_id: str,
    *,
    attempt: int,
    enterprise_id: str,
) -> str:
    """Enqueue the worker function with the business job_id + enterprise_id.
    Returns the RQ job id (we keep a different namespace per attempt so
    retries don't collide on RQ side).

    ``enterprise_id`` is required so the worker can resolve the tenant DB
    directly from the job args — no Redis side-channel.

    Also configures RQ's built-in retry policy: 3 in-worker retries with
    1m / 5m / 15m backoff for transient LandingAI/OCR failures. This is
    distinct from the IngestJob-row ``attempts`` field used for manual
    user-initiated retries.
    """
    queue = get_ingest_queue()
    rq_id = _rq_id_for(job_id, attempt)
    queue.enqueue(
        WORKER_FN,
        job_id,
        enterprise_id,
        job_id=rq_id,
        job_timeout=600,  # 10 min per job
        result_ttl=300,
        failure_ttl=24 * 3600,
        retry=Retry(max=3, interval=[60, 300, 900]),
    )
    return rq_id


async def reset_stale_running_jobs(
    session: AsyncSession,
    *,
    threshold_minutes: int = STALE_RUNNING_AFTER_MINUTES,
) -> list[uuid.UUID]:
    """Flip any IngestJob stuck in ``running`` past the staleness threshold
    back to ``queued`` so the next worker pickup can retry it.

    Returns the affected job ids. Caller decides whether to re-enqueue
    them on RQ; the API endpoint just resets state, the worker tick also
    re-enqueues so the next tick picks them up.
    """
    from yunwei_win.models import IngestJob, IngestJobStatus

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    stmt = select(IngestJob).where(
        IngestJob.status == IngestJobStatus.running,
        IngestJob.updated_at < cutoff,
    )
    rows = (await session.execute(stmt)).scalars().all()
    ids: list[uuid.UUID] = []
    for j in rows:
        j.status = IngestJobStatus.queued
        j.progress_message = (
            f"worker did not check in for >{threshold_minutes} min; reset to queued"
        )
        ids.append(j.id)
    if ids:
        await session.commit()
    return ids
