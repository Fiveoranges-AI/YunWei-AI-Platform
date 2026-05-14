"""Document extraction record (vNext).

One ``document_extractions`` row per extraction attempt over one parse
attempt. Holds the selected-table router output, normalized extraction
payload, validation warnings, entity-resolution proposal, server-side
review draft, and lock/version metadata used by the review wizard.
Confirm writeback flips ``status`` and stamps ``confirmed_by`` /
``confirmed_at``; business rows go to dedicated tables elsewhere.
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
    return datetime.now(timezone.utc)


class DocumentExtractionStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    ignored = "ignored"
    failed = "failed"


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parse_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("document_parses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[DocumentExtractionStatus] = mapped_column(
        SQLEnum(DocumentExtractionStatus, name="document_extraction_status"),
        nullable=False,
        default=DocumentExtractionStatus.pending_review,
        index=True,
    )
    selected_tables: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    extraction_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    entity_resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lock_token: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
