"""Procurement / inventory ontology — 锦泰耐火材料 主线后端表.

Adds the manufacturing-side counterpart to the existing sales-side ontology
(``customer.py`` / ``order.py``). New entities:

  * ``Supplier``      供应商 ref 表 — payment_terms_days drives AP due date.
  * ``Material``      物料 ref 表 — safety_stock + denormalized last_balance.
  * ``StockMovement`` 库存流水 — append-only ledger keyed by reference_type+id.
  * ``IssueVoucher``  车间领料单 — head row that, on confirm-and-issue,
                       drives a stock decrement and may auto-draft a PR.
  * ``PurchaseRequisition`` + ``PurchaseRequisitionItem`` — 申购单 (草稿 →
                       审批 → 转 PO).
  * ``PurchaseOrder`` + ``PurchaseOrderItem`` — 采购订单.
  * ``GoodsReceipt``  入库单 — 1:1 with PO; receipt drives stock increment
                       and creates a Payable.
  * ``Payable``       应付账款 — due_date = received_at + supplier.payment_terms_days.
  * ``StockAlert``    缺料预警 — 事件流水, level=low|out.

Audit / provenance / soft-delete is delegated to the standard mixins; the
``StockMovement`` and ``StockAlert`` tables intentionally drop
``HumanVerificationMixin`` and ``SoftDeleteMixin`` because they are
append-only event records, not editable entities.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin
from yunwei_win.models._mixins import (
    HumanVerificationMixin,
    OwnershipMixin,
    RowAuditMixin,
    RowProvenanceMixin,
    RowSourceMixin,
    SoftDeleteMixin,
)


# ============================== enums =====================================


class StockMovementDirection(str, enum.Enum):
    in_ = "in"
    out = "out"
    init = "init"
    adjustment = "adjustment"


class StockMovementReferenceType(str, enum.Enum):
    issue_voucher = "issue_voucher"
    goods_receipt = "goods_receipt"
    opening = "opening"
    adjustment = "adjustment"


class IssueVoucherStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    cancelled = "cancelled"


class PurchaseRequisitionStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    closed_to_po = "closed_to_po"


class PurchaseRequisitionSource(str, enum.Enum):
    manual = "manual"
    ai_autodraft = "ai_autodraft"


class PurchaseOrderStatus(str, enum.Enum):
    open = "open"
    in_transit = "in_transit"
    closed = "closed"
    cancelled = "cancelled"


class PayableStatus(str, enum.Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"


class StockAlertLevel(str, enum.Enum):
    low = "low"
    out = "out"


class MaterialKind(str, enum.Enum):
    raw = "raw"           # 原材料
    wip = "wip"           # 在制品
    finished = "finished" # 成品
    consumable = "consumable"


# ============================== tables ====================================


class Supplier(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """供应商. ``payment_terms_days`` 驱动入库时应付账款 due_date 计算."""

    __tablename__ = "procurement_suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    payment_terms_days: Mapped[int] = mapped_column(default=60, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Material(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """物料. ``last_balance`` 是反范式聚合,每次 StockMovement 写入时同步更新,
    用于 KPI 列表查询免去 SUM(stock_movements) 的开销."""

    __tablename__ = "procurement_materials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    kind: Mapped[MaterialKind] = mapped_column(
        SQLEnum(MaterialKind, name="material_kind"),
        nullable=False,
        default=MaterialKind.raw,
    )
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    last_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    # 加权平均成本 (WAC). Receive PO 时更新:
    #   new_cost = (old_balance × old_cost + receipt_qty × receipt_unit_price) / new_balance
    # 用于存货价值估算 (会企01 资产负债表 "存货" 行) + 营业成本 (会企02 损益表).
    last_unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StockMovement(
    Base,
    TimestampMixin,
    RowSourceMixin,
    RowAuditMixin,
):
    """库存流水 — append-only ledger. ``balance_after`` 是写入瞬时的余额快照."""

    __tablename__ = "procurement_stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[StockMovementDirection] = mapped_column(
        SQLEnum(StockMovementDirection, name="stock_movement_direction"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_type: Mapped[StockMovementReferenceType] = mapped_column(
        SQLEnum(StockMovementReferenceType, name="stock_movement_reference_type"),
        nullable=False,
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class IssueVoucher(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """车间领料单 head. 单 line(本次 demo 简化),如未来要多行就拆 IssueVoucherItem."""

    __tablename__ = "procurement_issue_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    voucher_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    workshop: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[IssueVoucherStatus] = mapped_column(
        SQLEnum(IssueVoucherStatus, name="issue_voucher_status"),
        nullable=False,
        default=IssueVoucherStatus.draft,
    )


class PurchaseRequisition(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """申购单 head. AI auto-draft 时 ``source = ai_autodraft`` + ``human_verified = False``;
    张主管点 approve 时才把 ``human_verified`` 翻成 True."""

    __tablename__ = "procurement_requisitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pr_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    dept: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    apply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("procurement_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[PurchaseRequisitionStatus] = mapped_column(
        SQLEnum(PurchaseRequisitionStatus, name="purchase_requisition_status"),
        nullable=False,
        default=PurchaseRequisitionStatus.draft,
        index=True,
    )
    source: Mapped[PurchaseRequisitionSource] = mapped_column(
        SQLEnum(PurchaseRequisitionSource, name="purchase_requisition_source"),
        nullable=False,
        default=PurchaseRequisitionSource.manual,
    )
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    po_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PurchaseRequisitionItem(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """申购单 line."""

    __tablename__ = "procurement_requisition_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pr_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_requisitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    arrive_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)


class PurchaseOrder(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """采购订单 head."""

    __tablename__ = "procurement_purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    po_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    from_pr_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("procurement_requisitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SQLEnum(PurchaseOrderStatus, name="purchase_order_status"),
        nullable=False,
        default=PurchaseOrderStatus.open,
        index=True,
    )
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    warehouse: Mapped[str | None] = mapped_column(String(128), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PurchaseOrderItem(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """采购订单 line."""

    __tablename__ = "procurement_purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)


class GoodsReceipt(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
):
    """入库单. 1:1 with PO (demo simplification — multi-receipt 后续再加)."""

    __tablename__ = "procurement_goods_receipts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    po_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse: Mapped[str | None] = mapped_column(String(128), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Payable(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """应付账款. due_date = invoice_date + supplier.payment_terms_days (在 service 算)."""

    __tablename__ = "procurement_payables"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="po")
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_po_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("procurement_purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[PayableStatus] = mapped_column(
        SQLEnum(PayableStatus, name="payable_status"),
        nullable=False,
        default=PayableStatus.pending,
        index=True,
    )


class StockAlert(
    Base,
    TimestampMixin,
    RowAuditMixin,
):
    """缺料预警. 事件流水,不挂 HumanVerification / SoftDelete."""

    __tablename__ = "procurement_stock_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[StockAlertLevel] = mapped_column(
        SQLEnum(StockAlertLevel, name="stock_alert_level"),
        nullable=False,
    )
    balance_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    safety_stock_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    related_pr_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("procurement_requisitions.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
