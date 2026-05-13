"""Field-level provenance.

Every business field extracted from a document gets a row pointing back to:
- which document (document_id)
- which entity row (entity_type + entity_id)
- which field (field_name) — supports nested paths like 'payment_milestones[0].ratio'
- exact value extracted (value JSONB)
- where in the source it came from (source_page, source_excerpt)
- model self-confidence (confidence)

UNIQUE(document_id, entity_type, entity_id, field_name) — re-extracting upserts.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


class EntityType(str, enum.Enum):
    customer = "customer"
    contact = "contact"
    order = "order"
    contract = "contract"


class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "entity_type", "entity_id", "field_name",
            name="uq_field_provenance"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, name="provenance_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    excerpt_match: Mapped[bool | None] = mapped_column(nullable=True)
    extracted_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
