"""光天耐火材料 · AI 库存管家 — SKU 中心后端表.

光天 (宜兴市光天耐火材料) 是 SKU 台账 + 出入库 + 缺货预警 + AI 补产建议. 与锦泰
(``procurement.py``: 采购/生产流转 + 财务) 是**不同业务**, 但共用同一套地基
(per-tenant DB / confirm_writer / ActionLog / parse_pipeline / 安全硬化).

为什么单独建表而不复用 ``procurement.Material``:
  * 光天 SKU 需要 ``location`` (库位) / ``category`` (品类) / ``status`` (5 态)
    这些字段, 而 procurement.Material 是采购物料语义, 没有这些列.
  * 锦泰的 procurement.py 已进 PR (#114/#115), 不能动 (红线: 不破坏既有测试/PR).
  * per-tenant DB 让光天表只落在 ``tenant_guangtian_demo``, 与锦泰物理隔离.

复用的是 *范式* 不是 *表*:
  * 反范式 ``last_balance`` 挂在 SKU 主档, 每笔流水写入时同步 (免 SUM 扫描),
    与 ``procurement.Material.last_balance`` 一致.
  * ``GuangtianStockMovement`` 是 append-only 流水 (mirror ``StockMovement``).
  * ``GuangtianReplenishment.source = ai_autodraft`` + ``human_verified=False``
    沿用锦泰 "AI 先填→人确认" 的待审范式.

``status`` 是**派生值** (live_balance vs safety_stock 算出来), 不落库;
唯一例外是手工标记的 "数据异常", 存在 ``status_override``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
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


class GuangtianSkuKind(str, enum.Enum):
    raw = "raw"            # 耐火原料
    wip = "wip"            # 半成品
    finished = "finished"  # 成品


class GuangtianStockStatus(str, enum.Enum):
    """SKU 库存状态 — 通常派生, ``anomaly`` 是唯一手工置位的覆盖值."""

    normal = "normal"            # 正常
    low = "low"                  # 低库存
    shortage_risk = "shortage_risk"  # 缺货风险 (有未满足订单缺口)
    out = "out"                  # 已缺货
    anomaly = "anomaly"          # 数据异常 (人工/AI 置信度低标记)


class GuangtianMovementOp(str, enum.Enum):
    inbound = "inbound"      # 入库
    outbound = "outbound"    # 出库
    transfer = "transfer"    # 调拨
    stocktake = "stocktake"  # 盘点
    scrap = "scrap"          # 报废


class GuangtianMovementRefType(str, enum.Enum):
    inbound_voucher = "inbound_voucher"
    outbound_voucher = "outbound_voucher"
    opening = "opening"
    adjustment = "adjustment"


class GuangtianVoucherStatus(str, enum.Enum):
    draft = "draft"          # AI 抽取已确认录入, 尚未过账到库存
    applied = "applied"      # 已过账 (扣减/增加库存)
    cancelled = "cancelled"


class GuangtianInboundType(str, enum.Enum):
    production = "production"  # 生产入库
    purchase = "purchase"      # 采购入库
    returned = "returned"      # 退货入库
    other = "other"


class GuangtianOutboundType(str, enum.Enum):
    sales = "sales"        # 销售出库
    sample = "sample"      # 样品出库
    returned = "returned"  # 退货退厂
    other = "other"


class GuangtianOrderLevel(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"


class GuangtianReplenishPriority(str, enum.Enum):
    high = "high"      # 高
    medium = "medium"  # 中
    low = "low"        # 低


class GuangtianReplenishStatus(str, enum.Enum):
    suggested = "suggested"  # AI 建议, 待人工采纳
    adopted = "adopted"      # 已采纳, 挂到工艺组
    dismissed = "dismissed"  # 已忽略


class GuangtianStockAlertLevel(str, enum.Enum):
    low = "low"
    out = "out"


# ============================== tables ====================================


class GuangtianSku(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """SKU 产品档案. ``last_balance`` 是反范式聚合, 每笔流水写入时同步更新."""

    __tablename__ = "guangtian_skus"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="块")
    location: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    kind: Mapped[GuangtianSkuKind] = mapped_column(
        SQLEnum(GuangtianSkuKind, name="guangtian_sku_kind"),
        nullable=False,
        default=GuangtianSkuKind.raw,
    )
    safety_stock: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    last_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    # 仅当人工/AI 标记 "数据异常" 时置位; 其余状态由 last_balance vs safety 派生.
    status_override: Mapped[GuangtianStockStatus | None] = mapped_column(
        SQLEnum(GuangtianStockStatus, name="guangtian_stock_status"), nullable=True
    )
    last_in_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_out_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuangtianStockMovement(
    Base,
    TimestampMixin,
    RowSourceMixin,
    RowAuditMixin,
):
    """库存流水 — append-only ledger. ``balance_after`` 是写入瞬时余额快照.

    ``confidence`` (0-100) + ``confirmed`` 复刻前端 LedgerEntry: AI 识别的流水
    置信度 <80 标记待复核; 人工/系统写入默认 confirmed=true.
    """

    __tablename__ = "guangtian_stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("guangtian_skus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    op: Mapped[GuangtianMovementOp] = mapped_column(
        SQLEnum(GuangtianMovementOp, name="guangtian_movement_op"), nullable=False
    )
    # signed: + 入库 / - 出库; 调拨/盘点可为 0 或带符号.
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_type: Mapped[GuangtianMovementRefType] = mapped_column(
        SQLEnum(GuangtianMovementRefType, name="guangtian_movement_ref_type"),
        nullable=False,
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed: Mapped[bool] = mapped_column(nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuangtianInboundVoucher(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """入库单 head. confirm-and-apply 时 +库存 + 写流水 + 解除缺货预警."""

    __tablename__ = "guangtian_inbound_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    voucher_no: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("guangtian_skus.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    batch: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inbound_type: Mapped[GuangtianInboundType] = mapped_column(
        SQLEnum(GuangtianInboundType, name="guangtian_inbound_type"),
        nullable=False,
        default=GuangtianInboundType.production,
    )
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[GuangtianVoucherStatus] = mapped_column(
        SQLEnum(GuangtianVoucherStatus, name="guangtian_voucher_status"),
        nullable=False,
        default=GuangtianVoucherStatus.draft,
    )
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GuangtianOutboundVoucher(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """出库单 head. confirm-and-apply 时校验库存→ -库存 + 写流水 + 触发预警."""

    __tablename__ = "guangtian_outbound_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    voucher_no: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("guangtian_skus.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outbound_type: Mapped[GuangtianOutboundType] = mapped_column(
        SQLEnum(GuangtianOutboundType, name="guangtian_outbound_type"),
        nullable=False,
        default=GuangtianOutboundType.sales,
    )
    customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[GuangtianVoucherStatus] = mapped_column(
        SQLEnum(GuangtianVoucherStatus, name="guangtian_voucher_status"),
        nullable=False,
        default=GuangtianVoucherStatus.draft,
    )
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GuangtianStockAlert(
    Base,
    TimestampMixin,
    RowAuditMixin,
):
    """缺货/低库存预警 — 事件流水. 入库回补后 ``resolved_at`` 置位."""

    __tablename__ = "guangtian_stock_alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("guangtian_skus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[GuangtianStockAlertLevel] = mapped_column(
        SQLEnum(GuangtianStockAlertLevel, name="guangtian_stock_alert_level"),
        nullable=False,
    )
    balance_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    safety_stock_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuangtianCustomerOrder(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """客户订单 head — 驱动订单缺口预警 (与安全库存预警互补)."""

    __tablename__ = "guangtian_customer_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    customer: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[GuangtianOrderLevel] = mapped_column(
        SQLEnum(GuangtianOrderLevel, name="guangtian_order_level"),
        nullable=False,
        default=GuangtianOrderLevel.medium,
    )
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    ai_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)


class GuangtianCustomerOrderItem(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """客户订单行 — ``needed`` vs 现库存算缺口 (gap)."""

    __tablename__ = "guangtian_customer_order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("guangtian_customer_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("guangtian_skus.id", ondelete="SET NULL"), nullable=True, index=True
    )
    needed: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GuangtianReplenishment(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """AI 补产建议. ``source=ai_autodraft`` + ``human_verified=False`` 沿用锦泰
    "AI 先填→人确认" 范式; 采纳后置 ``status=adopted``, 挂工艺组工单号."""

    __tablename__ = "guangtian_replenishments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sku_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("guangtian_skus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    suggest_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    priority: Mapped[GuangtianReplenishPriority] = mapped_column(
        SQLEnum(GuangtianReplenishPriority, name="guangtian_replenish_priority"),
        nullable=False,
        default=GuangtianReplenishPriority.medium,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[GuangtianReplenishStatus] = mapped_column(
        SQLEnum(GuangtianReplenishStatus, name="guangtian_replenish_status"),
        nullable=False,
        default=GuangtianReplenishStatus.suggested,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai_autodraft")
    work_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
