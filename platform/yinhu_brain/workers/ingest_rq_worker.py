"""Run an RQ worker for win-ingest.

Usage::

    python -m yinhu_brain.workers.ingest_rq_worker

Environment::

    REDIS_URL        redis connection string (default ``redis://localhost:6379/0``)
    LOG_LEVEL        stdlib log level (default INFO)
    WORKER_MAX_JOBS  process this many jobs then exit so the supervisor
                     restarts us (default 100). Prevents memory growth
                     from LandingAI / httpx pool churn. Set to 0 or empty
                     to disable.
"""

from __future__ import annotations

import logging
import os
import sys

from redis import Redis
from rq import Queue, Worker
from rq.serializers import JSONSerializer

from yinhu_brain.services.ingest.job_queue import INGEST_QUEUE_NAME


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    url = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
    conn = Redis.from_url(url)
    queue = Queue(INGEST_QUEUE_NAME, connection=conn, serializer=JSONSerializer)
    worker = Worker([queue], connection=conn, serializer=JSONSerializer)
    max_jobs_raw = os.environ.get("WORKER_MAX_JOBS", "100")
    try:
        max_jobs = int(max_jobs_raw) if max_jobs_raw else None
    except ValueError:
        max_jobs = 100
    if max_jobs is not None and max_jobs <= 0:
        max_jobs = None
    worker.work(with_scheduler=False, max_jobs=max_jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
