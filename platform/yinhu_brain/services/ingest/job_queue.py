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


def enqueue_ingest_job(job_id: str, *, attempt: int) -> str:
    """Enqueue the worker function with the business job_id. Returns the
    RQ job id (we keep a different namespace per attempt so retries don't
    collide on RQ side).
    """
    queue = get_ingest_queue()
    rq_id = f"ingest:{job_id}:a{attempt}"
    queue.enqueue(
        WORKER_FN,
        job_id,
        job_id=rq_id,
        job_timeout=600,  # 10 min per job
        result_ttl=300,
        failure_ttl=24 * 3600,
    )
    return rq_id
