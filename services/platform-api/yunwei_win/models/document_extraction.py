"""Document extraction record.

Stores the durable AI proposal for one document: the route plan, raw pipeline
results, and the materialized ReviewDraft. Confirm flips ``status`` and
writes business rows in separate tables; the extraction row stays as the
historical trail of "what AI found before humans touched it".
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


def _utcnow() -> datetime:
    """Client-side default — mirrors ``models/ingest_job._utcnow``."""
    return datetime.now(timezone.utc)


class DocumentExtractionStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    ignored = "ignored"
    failed = "failed"


class DocumentExtraction(Base):
    """One AI extraction attempt for one Document.

    ``review_draft`` is the materialized table/cell payload the review UI
    renders. ``raw_pipeline_results`` keeps the upstream extractor output
    around for debugging / re-materialization without re-running OCR.
    """

    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_pipeline_results: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    review_draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[DocumentExtractionStatus] = mapped_column(
        SQLEnum(DocumentExtractionStatus, name="document_extraction_status"),
        nullable=False,
        default=DocumentExtractionStatus.pending_review,
        index=True,
    )
    warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
