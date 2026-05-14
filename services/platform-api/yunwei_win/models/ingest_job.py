"""Persistent ingest job + batch rows.

Postgres is the source of truth for job state. Redis/RQ only holds the
in-flight queue + per-attempt worker handle (``rq_job_id``). Worker progress
updates land on the IngestJob row at stage boundaries.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


def _utcnow() -> datetime:
    """Client-side default for created/updated timestamps.

    We pair this with ``server_default=func.now()`` so the row has a value
    even when inserted via raw SQL, but rely on the client value to avoid a
    refresh() round-trip immediately after flush (which would otherwise
    trigger a sync lazy-load and trip ``MissingGreenlet`` in async code).
    """
    return datetime.now(timezone.utc)


class IngestJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    extracted = "extracted"
    confirmed = "confirmed"
    failed = "failed"
    canceled = "canceled"


class IngestJobStage(str, enum.Enum):
    received = "received"
    stored = "stored"
    ocr = "ocr"
    route = "route"
    extract = "extract"
    merge = "merge"
    draft = "draft"
    done = "done"


class IngestBatch(Base):
    __tablename__ = "ingest_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    enterprise_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploader: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="win-upload")
    total_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ingest_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enterprise_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Staged-file metadata. The actual file lives at staged_file_url; we
    # don't store bytes in the row.
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staged_file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # For pasted-text jobs, no file is stored; we keep the raw text inline.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hint: Mapped[str] = mapped_column(String(32), nullable=False, default="file")
    uploader: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[IngestJobStatus] = mapped_column(
        SQLEnum(IngestJobStatus, name="ingest_job_status"),
        nullable=False,
        default=IngestJobStatus.queued,
        index=True,
    )
    stage: Mapped[IngestJobStage] = mapped_column(
        SQLEnum(IngestJobStage, name="ingest_job_stage"),
        nullable=False,
        default=IngestJobStage.received,
    )
    progress_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rq_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # On success, the worker writes the materialized ReviewDraft JSON so the
    # Review page can rehydrate from a job_id alone.
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Schema-first ingest links each job to its materialized ReviewDraft.
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("document_extractions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
