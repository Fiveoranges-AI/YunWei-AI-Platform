"""锦泰 老板视角 经营日报 KPI 聚合.

Mounted under ``/api/win/briefing``. Pure read-only aggregation over
the procurement + payable tables. Front-end 锦泰 demo's "经营日报" tab
calls this to render the 7 大 KPI 卡片 + 今日要事 列表.

We compute on-the-fly (no materialized cache) — the volumes for a
single tenant are small enough that a few count + sum queries finish
in tens of ms. If this becomes a hot endpoint, swap to a per-day
denormalized snapshot.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.models import (
    ActionLog,
    Material,
    Payable,
    PayableStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionStatus,
    StockAlert,
)


router = APIRouter(prefix="/briefing")


class BriefingKpiOut(BaseModel):
    payable_total: Decimal
    payable_overdue_total: Decimal
    payable_overdue_count: int
    payable_due_soon_total: Decimal  # 0-30 days
    payable_count: int
    low_stock_count: int
    out_of_stock_count: int
    pending_pr_count: int
    open_po_count: int
    in_transit_po_count: int
    today_event_count: int
    today_events: list["BriefingEventOut"] = Field(default_factory=list)


class BriefingEventOut(BaseModel):
    occurred_at: datetime
    actor: str
    actor_kind: str
    action_type: str
    summary: str


BriefingKpiOut.model_rebuild()


async def _ensure_tables(request: Request) -> None:
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if enterprise_id:
        await ensure_schema_ingest_tables_for(enterprise_id)


@router.get("/kpi", response_model=BriefingKpiOut)
async def kpi_snapshot(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> BriefingKpiOut:
    await _ensure_tables(request)
    today = date.today()
    cutoff_30 = today + timedelta(days=30)

    # Payables: aggregate by aging bucket.
    payables = (
        await session.execute(
            select(Payable).where(Payable.status != PayableStatus.paid)
        )
    ).scalars().all()
    payable_total = Decimal("0")
    payable_overdue_total = Decimal("0")
    payable_overdue_count = 0
    payable_due_soon_total = Decimal("0")
    for p in payables:
        outstanding = Decimal(p.amount) - Decimal(p.paid_amount)
        payable_total += outstanding
        if p.due_date < today:
            payable_overdue_total += outstanding
            payable_overdue_count += 1
        elif p.due_date <= cutoff_30:
            payable_due_soon_total += outstanding

    # Materials: how many below safety, how many out.
    materials = (
        await session.execute(select(Material).where(Material.is_deleted == False))
    ).scalars().all()
    low_stock_count = 0
    out_of_stock_count = 0
    for m in materials:
        bal = Decimal(m.last_balance)
        safety = Decimal(m.safety_stock)
        if bal <= 0:
            out_of_stock_count += 1
        elif safety > 0 and bal < safety:
            low_stock_count += 1

    pending_pr_count = (
        await session.execute(
            select(func.count())
            .select_from(PurchaseRequisition)
            .where(PurchaseRequisition.status == PurchaseRequisitionStatus.pending_approval)
        )
    ).scalar_one() or 0

    open_po_count = (
        await session.execute(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.status == PurchaseOrderStatus.open)
        )
    ).scalar_one() or 0

    in_transit_po_count = (
        await session.execute(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.status == PurchaseOrderStatus.in_transit)
        )
    ).scalar_one() or 0

    # Today events: last 24h of ActionLog. Lightweight — no joins.
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    events_rows = (
        await session.execute(
            select(ActionLog)
            .where(ActionLog.executed_at >= cutoff)
            .order_by(ActionLog.executed_at.desc())
            .limit(20)
        )
    ).scalars().all()
    today_events = [
        BriefingEventOut(
            occurred_at=ev.executed_at,
            actor=ev.actor,
            actor_kind=ev.actor_kind,
            action_type=ev.action_type.value,
            summary=ev.input_summary or ev.output_summary or "",
        )
        for ev in events_rows
    ]

    return BriefingKpiOut(
        payable_total=payable_total,
        payable_overdue_total=payable_overdue_total,
        payable_overdue_count=payable_overdue_count,
        payable_due_soon_total=payable_due_soon_total,
        payable_count=len(payables),
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        pending_pr_count=pending_pr_count,
        open_po_count=open_po_count,
        in_transit_po_count=in_transit_po_count,
        today_event_count=len(today_events),
        today_events=today_events,
    )
