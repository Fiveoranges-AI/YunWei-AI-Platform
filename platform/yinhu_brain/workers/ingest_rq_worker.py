"""Run an RQ worker for win-ingest.

Usage::

    python -m yinhu_brain.workers.ingest_rq_worker

Environment::

    REDIS_URL   redis connection string (default ``redis://localhost:6379/0``)
    LOG_LEVEL   stdlib log level (default INFO)
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
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
