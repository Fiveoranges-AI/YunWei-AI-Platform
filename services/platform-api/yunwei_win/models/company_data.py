"""业务数据落地表 —— Confirm 阶段写入的目标表。

跟 ``customers / contacts / orders / contracts / documents`` 一起构成完整的
租户公司数据层。每张表保持精简，只放当前 ReviewDraft 真正会落的字段；后续要
扩列时走 ``schema_change_proposals`` 流程。

Notes:
- ``CustomerTask`` 已经在 ``customer_memory.py`` 里定义了，这里不重复声明，
  confirm 直接复用旧模型。
- 金额/数量统一用 ``Numeric(18, 4)``，比 V1 的 ``Numeric(15, 2)`` 多两位以
  支撑小批量制造件的单价。
- 时间戳用 ``_utcnow + server_default=func.now()`` 的写法，跟 ``ingest_job``
  保持一致，避免 raw insert 没值或 flush 后 lazy refresh。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _StampedColumns:
    """共享的 created_at / updated_at 列描述符。

    没有用 TimestampMixin 是因为它只配 server_default，async flush 后 refresh
    会触发 lazy-load。我们要的是 ``_utcnow + server_default`` 双保险，
    跟 ``ingest_job`` 一致。
    """

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


class Product(Base, _StampedColumns):
    """产品 / SKU 主表。"""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ProductRequirement(Base, _StampedColumns):
    """客户对产品的工艺 / 验收 / 包装等要求。"""

    __tablename__ = "product_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requirement_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requirement_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tolerance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )


class ContractPaymentMilestone(Base, _StampedColumns):
    """合同付款节点（替代 V1 的 ``contracts.payment_milestones`` JSON 列）。"""

    __tablename__ = "contract_payment_milestones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    trigger_event: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trigger_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Invoice(Base, _StampedColumns):
    """开票主表。"""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    invoice_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)


class InvoiceItem(Base, _StampedColumns):
    """开票行项。"""

    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)


class Payment(Base, _StampedColumns):
    """收 / 付款记录。"""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Shipment(Base, _StampedColumns):
    """发货 / 物流记录主表。"""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shipment_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ShipmentItem(Base, _StampedColumns):
    """发货行项。"""

    __tablename__ = "shipment_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CustomerJournalItem(Base, _StampedColumns):
    """客户时间线统一表 —— 把抽取出来的承诺/风险/记忆/备注按
    journal item 汇总到这里。比 V1 的事件/承诺/风险/记忆分表更适合做
    timeline UI。"""

    __tablename__ = "customer_journal_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
