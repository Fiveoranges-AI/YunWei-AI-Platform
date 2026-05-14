"""Durable parse-attempt record for one document.

A ``document_parses`` row is the persisted output of one parser provider run
over one ``Document``. vNext ingest captures parser output here so downstream
extraction/review/confirm can reference the parse artifact and its source
refs without re-running parsing.
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
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentParseStatus(str, enum.Enum):
    parsed = "parsed"
    failed = "failed"


class DocumentParse(Base):
    __tablename__ = "document_parses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[DocumentParseStatus] = mapped_column(
        SQLEnum(DocumentParseStatus, name="document_parse_status"),
        nullable=False,
        default=DocumentParseStatus.parsed,
        index=True,
    )
    artifact: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
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
