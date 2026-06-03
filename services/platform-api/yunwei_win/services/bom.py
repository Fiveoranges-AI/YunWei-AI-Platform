"""BOM (配料单) explode service.

``explode(bom_id, batch_quantity)`` 把 BOM 的单位用量乘以批量,
返回每个原料的需求量 + 当前余量 + 缺口. 锦泰 demo "配料单 D"
展示的"本批需 4000 kg vs 现存 1080 kg, 缺 2920 kg" 就是这个.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    Material,
)


@dataclass
class ExplodedLine:
    material_id: uuid.UUID
    code: str
    name: str
    unit: str
    quantity_per_output: Decimal
    scrap_rate: Decimal
    required_qty: Decimal
    current_balance: Decimal
    shortage: Decimal
    available: bool


@dataclass
class ExplodeResult:
    bom_id: uuid.UUID
    product_code: str
    product_name: str
    version: str
    output_unit: str
    batch_quantity: Decimal
    lines: list[ExplodedLine]
    fully_available: bool


class BomNotFoundError(ValueError):
    pass


async def explode_bom(
    *, bom_id: uuid.UUID, batch_quantity: Decimal, session: AsyncSession,
) -> ExplodeResult:
    bom = await session.get(BillOfMaterials, bom_id)
    if bom is None:
        raise BomNotFoundError(f"bom {bom_id} not found")
    if batch_quantity <= 0:
        raise ValueError("batch_quantity must be > 0")

    lines = (
        await session.execute(
            select(BillOfMaterialsLine)
            .where(BillOfMaterialsLine.bom_id == bom_id)
            .order_by(BillOfMaterialsLine.sort_order)
        )
    ).scalars().all()

    if not lines:
        return ExplodeResult(
            bom_id=bom.id,
            product_code=bom.product_code,
            product_name=bom.product_name,
            version=bom.version,
            output_unit=bom.output_unit,
            batch_quantity=batch_quantity,
            lines=[],
            fully_available=True,
        )

    mids = {line.material_id for line in lines}
    mat_rows = (await session.execute(select(Material).where(Material.id.in_(mids)))).scalars().all()
    mat_by_id = {m.id: m for m in mat_rows}

    output_qty = Decimal(bom.output_quantity) or Decimal("1")
    batches = batch_quantity / output_qty

    out_lines: list[ExplodedLine] = []
    fully_avail = True
    for line in lines:
        m = mat_by_id.get(line.material_id)
        if m is None:
            continue
        per_output = Decimal(line.quantity_per_output)
        scrap = Decimal(line.scrap_rate)
        required = (per_output * batches) * (Decimal("1") + scrap)
        required_q = required.quantize(Decimal("0.0001"))
        balance = Decimal(m.last_balance)
        shortage = required_q - balance
        if shortage < 0:
            shortage = Decimal("0")
        avail = balance >= required_q
        if not avail:
            fully_avail = False
        out_lines.append(ExplodedLine(
            material_id=m.id,
            code=m.code,
            name=m.name,
            unit=line.unit or m.unit,
            quantity_per_output=per_output,
            scrap_rate=scrap,
            required_qty=required_q,
            current_balance=balance,
            shortage=shortage,
            available=avail,
        ))

    return ExplodeResult(
        bom_id=bom.id,
        product_code=bom.product_code,
        product_name=bom.product_name,
        version=bom.version,
        output_unit=bom.output_unit,
        batch_quantity=batch_quantity,
        lines=out_lines,
        fully_available=fully_avail,
    )
