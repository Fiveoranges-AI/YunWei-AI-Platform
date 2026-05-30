"""锦泰 BOM (配料单 / Bill of Materials) 模型.

锦泰 demo 前端 "配料单 D" 展示的就是这个: 一个产品(承烧板/坩埚/...)按配方
对应一组原料 + 用量. ``explode(batch_qty)`` 把单位用量乘以批量得到本批材料需求,
对比 ``Material.last_balance`` 判断每个料是否够.

模型保持最小:
  * ``BillOfMaterials`` (head) — product_code + product_name + version + 每批输出量
  * ``BillOfMaterialsLine`` — material_id + 单位输出对应的用量

不在此次 scope:
  * 自动按 BOM 批量出 IssueVouchers (consume 行为) — 留给主线 + UI 触发
  * 多级 BOM (assembly of sub-assemblies)
  * 损耗率 / scrap_rate 的复杂处理 (字段留了, 默认 0)
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
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


class BomStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    retired = "retired"


class BillOfMaterials(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """BOM head — 一个产品 / 一个 version 一行."""

    __tablename__ = "procurement_bills_of_materials"
    __table_args__ = (
        UniqueConstraint("product_code", "version", name="uq_bom_product_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    output_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("1"))
    output_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="件")
    status: Mapped[BomStatus] = mapped_column(
        SQLEnum(BomStatus, name="bom_status"),
        nullable=False, default=BomStatus.active, index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BillOfMaterialsLine(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """BOM line — 一个原料 + 单位产品对应的用量."""

    __tablename__ = "procurement_bill_of_materials_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bom_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_bills_of_materials.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("procurement_materials.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    quantity_per_output: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    scrap_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=Decimal("0"))
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
