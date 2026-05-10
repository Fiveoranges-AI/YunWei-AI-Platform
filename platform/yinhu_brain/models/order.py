from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yinhu_brain.db import Base
from yinhu_brain.models._base import TimestampMixin

if TYPE_CHECKING:
    from yinhu_brain.models.contract import Contract
    from yinhu_brain.models.customer import Customer


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    amount_currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="CNY"
    )
    delivery_promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    contracts: Mapped[list[Contract]] = relationship(back_populates="order")
