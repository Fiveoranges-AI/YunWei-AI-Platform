from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin
from yunwei_win.models._mixins import (
    HumanVerificationMixin,
    OwnershipMixin,
    RowAuditMixin,
    RowProvenanceMixin,
    SoftDeleteMixin,
)

if TYPE_CHECKING:
    from yunwei_win.models.contract import Contract
    from yunwei_win.models.customer import Customer


class Order(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
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
    order_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    amount_currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="CNY"
    )
    delivery_promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    # The legacy ``contracts.order_id`` direction. The new
    # ``orders.contract_id`` ("order fulfils contract") direction has no
    # ORM convenience relationship — query it on the Order side
    # explicitly. See ``docs/architecture/ontology.md`` for the
    # relationship rationale.
    contracts: Mapped[list[Contract]] = relationship(
        back_populates="order",
        foreign_keys="Contract.order_id",
    )
