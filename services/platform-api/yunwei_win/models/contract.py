from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, ForeignKey, Numeric, String, Text, Uuid
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
    from yunwei_win.models.customer import Customer
    from yunwei_win.models.order import Order


class Contract(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """合同记录。一份 PDF / 文档对应一条 contracts row。

    schema-first 之后 ``customer_id`` 直接挂在 contract 上（不再强依赖 order）；
    ``order_id`` 仍保留以便给老数据 + 已有读路径用，但可空。金额字段
    （amount_total / amount_currency）落在 contract 主表，付款节点拆到
    ``contract_payment_milestones``；旧的 ``payment_milestones`` JSON 列
    暂时保留给老的读路径，新写入通过 ``ContractPaymentMilestone`` 落地。
    """

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    contract_no_external: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    contract_no_internal: Mapped[str | None] = mapped_column(String, nullable=True)
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    payment_milestones: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    delivery_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    signing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # account-period (账期) — typical contract field used when scheduling
    # collection reminders. Free-text because long-tail SMBs phrase this as
    # "月结30天", "见票即付", "货到付款" etc.
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Document-level extraction confidence (legacy column). Row-level seed
    # confidence — what the model thought when this row was first created —
    # lives in ``RowProvenanceMixin.confidence``.
    confidence_overall: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    customer: Mapped[Customer | None] = relationship()
    # Disambiguate: a contract has TWO potential FK links to orders —
    # the legacy ``contracts.order_id`` (contract belongs-to order) and the
    # newer ``orders.contract_id`` (order fulfils contract). The legacy
    # ``Contract.order`` relationship uses the legacy FK; the canonical
    # 1—* "contract has many orders" direction is read via SQL on the
    # Order side and intentionally has no ORM relationship to avoid
    # adding a circular convenience that will then need to stay
    # consistent.
    order: Mapped[Order | None] = relationship(
        back_populates="contracts",
        foreign_keys=[order_id],
    )
