"""RQ queue + enqueue helper for ingest jobs.

The actual worker function lives in ``yinhu_brain.workers.ingest_rq``
(Agent B). This module just wires up the Redis connection + Queue
singleton + a small enqueue() helper API handlers call. JSONSerializer is
used so the queue can only carry a single string job_id (no pickled
Python objects).
"""

from __future__ import annotations

import os
from functools import lru_cache

from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

INGEST_QUEUE_NAME = "win-ingest"
WORKER_FN = "yinhu_brain.workers.ingest_rq.run_ingest_job"

# Redis hash mapping business job_id -> enterprise_id. The worker reads
# this to know which tenant DB to route to. Lossy-OK: a missing entry
# simply means the worker can't find the job and logs an error; the
# next retry from the API restores the mapping.
_JOB_ENT_HASH = "win-ingest:job-enterprise"


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


def enqueue_ingest_job(job_id: str, *, attempt: int) -> str:
    """Enqueue the worker function with the business job_id. Returns the
    RQ job id (we keep a different namespace per attempt so retries don't
    collide on RQ side).
    """
    queue = get_ingest_queue()
    rq_id = _rq_id_for(job_id, attempt)
    queue.enqueue(
        WORKER_FN,
        job_id,
        job_id=rq_id,
        job_timeout=600,  # 10 min per job
        result_ttl=300,
        failure_ttl=24 * 3600,
    )
    return rq_id


def remember_enterprise_for_job(job_id: str, enterprise_id: str) -> None:
    """Store ``job_id -> enterprise_id`` so the worker can resolve the
    tenant DB without scanning. RQ's JSONSerializer only carries the
    string job_id, so we side-channel the enterprise via Redis. Lossy-OK:
    on Redis hiccups the worker will log and skip; retry restores it.
    """
    try:
        _redis().hset(_JOB_ENT_HASH, job_id, enterprise_id)
    except Exception:
        # Same swallow policy as enqueue: callers handle Redis-down via
        # the surrounding try/except that marks jobs failed. We log via
        # the standard logging chain but never raise from a side-channel.
        import logging

        logging.getLogger(__name__).exception(
            "remember_enterprise_for_job: redis hset failed for %s", job_id
        )


def lookup_enterprise_for(job_id: str) -> str | None:
    """Return the enterprise_id previously stored for ``job_id`` or None
    if no mapping exists. Sync — the underlying redis client is sync."""
    raw = _redis().hget(_JOB_ENT_HASH, job_id)
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8")
    return str(raw)


def forget_enterprise_for_job(job_id: str) -> None:
    """Remove the mapping. Currently unused — kept for completeness so
    a future GC step doesn't need to reach into Redis directly."""
    try:
        _redis().hdel(_JOB_ENT_HASH, job_id)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "forget_enterprise_for_job: redis hdel failed for %s", job_id
        )
