"""Upload descriptor shared by the vNext orchestrator and the RQ worker.

The async ``/jobs`` API stages uploaded bytes via ``services.storage.store_upload``
before enqueueing the worker. Passing the resulting descriptor into
``auto_ingest`` (instead of the raw bytes again) lets the worker skip a
second ``store_upload`` round-trip while keeping the Document row in
sync with whatever the API wrote to storage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PreStoredFile:
    path: str
    sha256: str
    size: int
    original_filename: str
    content_type: str | None = None
