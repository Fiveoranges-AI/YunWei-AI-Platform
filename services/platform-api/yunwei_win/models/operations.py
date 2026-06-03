"""Customer-operations ontology — P0 new tables.

These tables fill the gaps that `customer.py` / `order.py` / `company_data.py`
left open in the original schema:

  * ``order_items`` — Order had no line-items table (only Shipment and Invoice
    had them). Tracks product / quantity / unit_price per order row.
  * ``deliveries`` — explicit 签收 record per Shipment, with 签收人 / 异常标记 /
    异常原因. Kept distinct from Shipment so a single 发货 can have a delayed
    or repeated 签收 confirmation without forcing Shipment to grow extra
    columns.
  * ``invoice_payment_allocations`` — many-to-many 核销 table letting a
    Payment partially clear several Invoices and vice versa. The legacy
    1:N ``payments.invoice_id`` column stays in place.
  * ``next_actions`` — recommended "next step" rows with action_type + 话术草稿
    (talking-script draft) + owner + due date. Distinct from CustomerTask
    (which is the historical to-do log); NextAction is the new
    suggestion-then-execute slot the AI agent fans out into.
  * ``action_logs`` — every executed action (建档 / 催款 / 跟进 / 核对 ...)
    with input + output snapshot. Acts as the audit trail for what the
    agent / sales rep actually did. Distinct from ``llm_calls`` which is
    the per-LLM-request log.

All tables get the standard ontology mixins (provenance, human verification,
audit, ownership, soft delete) so list views, audit, and review behave
uniformly across the operations layer.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin
from yunwei_win.models._mixins import (
    HumanVerificationMixin,
    OwnershipMixin,
    RowAuditMixin,
    RowProvenanceMixin,
    SoftDeleteMixin,
)


# ============================== enums =====================================


class NextActionType(str, enum.Enum):
    """The recommended next move the agent / sales rep should take."""

    create_profile = "create_profile"      # 建档
    chase_payment = "chase_payment"        # 催款
    follow_up = "follow_up"                # 跟进
    reconcile = "reconcile"                # 核对
    confirm_delivery = "confirm_delivery"  # 催签收
    visit = "visit"                        # 拜访
    quote = "quote"                        # 报价
    escalate = "escalate"                  # 升级
    other = "other"


class NextActionStatus(str, enum.Enum):
    suggested = "suggested"   # AI 建议,未确认
    accepted = "accepted"     # 人工接受
    scheduled = "scheduled"   # 排期中
    in_progress = "in_progress"
    done = "done"
    dismissed = "dismissed"


class ActionTargetType(str, enum.Enum):
    """Polymorphic pointer for NextAction / ActionLog / Risk targets."""

    customer = "customer"
    contact = "contact"
    contract = "contract"
    order = "order"
    invoice = "invoice"
    payment = "payment"
    shipment = "shipment"
    delivery = "delivery"
    other = "other"


class DeliveryStatus(str, enum.Enum):
    pending = "pending"
    signed = "signed"
    partial = "partial"     # 部分签收
    rejected = "rejected"   # 拒收
    abnormal = "abnormal"   # 签收但异常


# ============================== tables ====================================


class OrderItem(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """订单行项 — Order × Product 明细。

    Order 之前只有汇总金额没有明细;新加的这张表让订单可以拆分到 SKU 级别,
    供后续做品类分析、毛利分析、跟单 Agent 回答"客户最近一个月订了哪几款"。
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)


class Delivery(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """签收记录 — 1:1 (occasionally 1:N) child of Shipment.

    Shipment 是"我发了什么";Delivery 是"对方收到了什么(以及收得对不对)"。
    拆开的原因:
      - 一个 Shipment 可能有补签 / 复签,delivery 可以追加记录。
      - 签收异常(数量短少 / 货损 / 拒收)是风险信号入口,放到独立表方便
        驱动 NextAction / Risk。
    """

    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    signed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_abnormal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    abnormal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DeliveryStatus] = mapped_column(
        SQLEnum(DeliveryStatus, name="delivery_status"),
        nullable=False,
        default=DeliveryStatus.pending,
    )
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvoicePaymentAllocation(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    SoftDeleteMixin,
):
    """发票 × 回款 核销中间表 (many-to-many).

    一笔回款可以核销多张发票,一张发票也可以被多笔回款分批核销。
    ``amount`` 记录这笔核销分配到的金额(允许小于 payment 总额 / invoice 总额).
    """

    __tablename__ = "invoice_payment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "invoice_id", "payment_id",
            name="uq_invoice_payment_allocation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    allocated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class NextAction(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """AI 提出的下一步行动 — 建档 / 催款 / 跟进 / 核对 / 拜访 ...

    跟历史 ``customer_tasks`` 的区别:
      - ``customer_tasks`` 是"人工到办列表",字段聚焦在 title / due / priority,
        没有动作类型,也没有话术草稿。
      - ``next_actions`` 由 Agent 生成,带 ``action_type`` 枚举、``suggested_text``
        (建议内容) 和 ``talking_script`` (话术草稿), 是 Agent ↔ 销售之间的
        协作槽位。

    通过 ``target_entity_type`` + ``target_entity_id`` 多态指向客户/订单/合同/
    发票/回款等等 (不强制外键, 避免 polymorphic FK 噪音)。
    """

    __tablename__ = "next_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    target_entity_type: Mapped[ActionTargetType] = mapped_column(
        SQLEnum(ActionTargetType, name="action_target_type"), nullable=False
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[NextActionType] = mapped_column(
        SQLEnum(NextActionType, name="next_action_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    talking_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[NextActionStatus] = mapped_column(
        SQLEnum(NextActionStatus, name="next_action_status"),
        nullable=False,
        default=NextActionStatus.suggested,
        index=True,
    )
    related_risk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("customer_risk_signals.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActionLog(
    Base,
    TimestampMixin,
    RowAuditMixin,
):
    """谁 / 在哪条记录上 / 执行了什么动作 / 输入输出摘要 / 时间。

    不挂 ProvenanceMixin / HumanVerificationMixin / OwnershipMixin / SoftDelete:
    日志是只追加 (append-only) 的事实,不需要可见性 / 验证 / 软删除字段;
    要查谁做的看 ``created_by`` 就够。LLMCall 是 LLM 调用本身的记录,这里记录的
    是业务动作 (无论是不是 AI 触发的)。
    """

    __tablename__ = "action_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    next_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("next_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_entity_type: Mapped[ActionTargetType] = mapped_column(
        SQLEnum(ActionTargetType, name="action_target_type"), nullable=False
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    action_type: Mapped[NextActionType] = mapped_column(
        SQLEnum(NextActionType, name="next_action_type"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="user"
    )
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    succeeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
