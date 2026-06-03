"""BOM (配料单) API.

Mounted under ``/api/win/procurement/boms``. List + get + explode.
不在此次 scope: 创建 BOM 走 /confirm/entities (BOM head 是 entity_type
=BillOfMaterials, line 是 BillOfMaterialsLine; relationship
"BillOfMaterials-has-Line"). 留给后续若有 UI/AI 抽取再加.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    BomStatus,
)
from yunwei_win.services.bom import BomNotFoundError, explode_bom


router = APIRouter(prefix="/procurement/boms")


async def _ensure_tables(request: Request) -> None:
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if enterprise_id:
        await ensure_schema_ingest_tables_for(enterprise_id)


@router.get("")
async def list_boms(
    request: Request,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    await _ensure_tables(request)
    stmt = select(BillOfMaterials).order_by(BillOfMaterials.created_at.desc())
    if status:
        try:
            stmt = stmt.where(BillOfMaterials.status == BomStatus(status))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from e
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(b.id),
            "product_code": b.product_code,
            "product_name": b.product_name,
            "version": b.version,
            "output_quantity": str(b.output_quantity),
            "output_unit": b.output_unit,
            "status": b.status.value,
            "notes": b.notes,
        }
        for b in rows
    ]


@router.get("/{bom_id}")
async def get_bom(
    request: Request,
    bom_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    bom = await session.get(BillOfMaterials, bom_id)
    if bom is None:
        raise HTTPException(status_code=404, detail=f"bom {bom_id} not found")
    lines = (
        await session.execute(
            select(BillOfMaterialsLine)
            .where(BillOfMaterialsLine.bom_id == bom_id)
            .order_by(BillOfMaterialsLine.sort_order)
        )
    ).scalars().all()
    return {
        "id": str(bom.id),
        "product_code": bom.product_code,
        "product_name": bom.product_name,
        "version": bom.version,
        "output_quantity": str(bom.output_quantity),
        "output_unit": bom.output_unit,
        "status": bom.status.value,
        "notes": bom.notes,
        "lines": [
            {
                "id": str(l.id),
                "material_id": str(l.material_id),
                "quantity_per_output": str(l.quantity_per_output),
                "unit": l.unit,
                "scrap_rate": str(l.scrap_rate),
                "sort_order": l.sort_order,
                "notes": l.notes,
            }
            for l in lines
        ],
    }


class ExplodePayload(BaseModel):
    batch_quantity: Decimal


@router.post("/{bom_id}/explode")
async def post_bom_explode(
    request: Request,
    bom_id: UUID,
    payload: ExplodePayload,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """按批量爆开 BOM, 返回每条材料需求 + 当前余量 + 缺口."""
    await _ensure_tables(request)
    try:
        result = await explode_bom(
            bom_id=bom_id, batch_quantity=payload.batch_quantity, session=session,
        )
    except BomNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "bom_id": str(result.bom_id),
        "product_code": result.product_code,
        "product_name": result.product_name,
        "version": result.version,
        "output_unit": result.output_unit,
        "batch_quantity": str(result.batch_quantity),
        "lines": [
            {
                "material_id": str(l.material_id),
                "code": l.code,
                "name": l.name,
                "unit": l.unit,
                "quantity_per_output": str(l.quantity_per_output),
                "scrap_rate": str(l.scrap_rate),
                "required_qty": str(l.required_qty),
                "current_balance": str(l.current_balance),
                "shortage": str(l.shortage),
                "available": l.available,
            }
            for l in result.lines
        ],
        "fully_available": result.fully_available,
    }
