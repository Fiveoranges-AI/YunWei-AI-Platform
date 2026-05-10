from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yinhu_brain.db import Base
from yinhu_brain.models._base import TimestampMixin

if TYPE_CHECKING:
    from yinhu_brain.models.order import Order


class Contract(Base, TimestampMixin):
    """合同记录。一份 PDF / 文档对应一条 contracts row。

    payment_milestones 是 JSONB，1-N 个节点，schema 见 services/ingest/schemas.py
    PaymentMilestone。允许任意付款节奏（不硬编码 4 阶段）。
    """

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_no_external: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    contract_no_internal: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_milestones: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    delivery_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    signing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence_overall: Mapped[float | None] = mapped_column(nullable=True)

    order: Mapped[Order] = relationship(back_populates="contracts")
