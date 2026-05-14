"""租户公司 schema 目录 (catalog) 表。

每个租户的 Win 数据库里都会有这套元数据表，记录"租户认为自己有哪些业务表、
每张表有哪些字段"。Review 在生成 ReviewDraft 时，先读这套表拿到全部启用
字段，再叠加抽取结果——这样空字段也能作为 ``missing`` 单元格呈现。

设计要点:
- ``category``、``data_type``、``proposal_type``、``status`` 这些枚举语义都
  写成普通字符串列，方便后续 AI / 用户扩展（不强约束到 SQLEnum，避免改一
  次就要做一次 schema migration）。
- 主键统一用 UUID。
- 时间戳同时配 ``server_default=func.now()`` 和客户端 ``_utcnow``，让 raw
  insert 也有值，且 async flush 后不会因为 lazy refresh 触发 MissingGreenlet。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yunwei_win.db import Base


def _utcnow() -> datetime:
    """Client-side default — mirrors ``models/ingest_job._utcnow``."""
    return datetime.now(timezone.utc)


class CompanySchemaTable(Base):
    """一张业务表的元数据（如 ``orders``、``invoices``）。"""

    __tablename__ = "company_schema_tables"
    __table_args__ = (
        UniqueConstraint("table_name", "version", name="uq_company_schema_table_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    # profile | commercial | finance | logistics | manufacturing | memory
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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

    fields: Mapped[list[CompanySchemaField]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="CompanySchemaField.sort_order",
    )


class CompanySchemaField(Base):
    """单个字段的元数据。"""

    __tablename__ = "company_schema_fields"
    __table_args__ = (
        UniqueConstraint("table_id", "field_name", name="uq_company_schema_field_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("company_schema_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # text | uuid | date | datetime | decimal | integer | boolean | enum | json
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_array: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enum_values: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    default_value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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

    table: Mapped[CompanySchemaTable] = relationship(back_populates="fields")


class SchemaChangeProposal(Base):
    """AI 或人提的"该改 schema"请求；等人审批后落到目录里。"""

    __tablename__ = "schema_change_proposals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    source_extraction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # add_table | add_field | alter_field | deactivate_field
    proposal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    table_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | approved | rejected | applied
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
