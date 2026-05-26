"""锦泰 财务三表 + 折旧 + 成本拆分 API.

Mounted under ``/api/win/finance``. 所有 endpoint **只读聚合**,从底层
entities (invoices / payments / payables / stock_movements / fixed_assets)
+ ``finance_period_opening_balances`` 算出符合会企01/02/03 格式的 JSON.

不做写入式财务系统 (冲销 / 调账 / 期末结转), 这些是 P2/Kingdee 范畴.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.services.finance import (
    compute_balance_sheet,
    compute_cashflow,
    compute_cost_breakdown,
    compute_depreciation_schedule,
    compute_inventory_ledger,
    compute_pnl,
    ensure_chart_of_accounts_seeded,
    period_bounds,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/finance")


async def _ensure_tables(request: Request) -> None:
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if enterprise_id:
        await ensure_schema_ingest_tables_for(enterprise_id)


def _validate_period(period: str) -> str:
    try:
        period_bounds(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return period


@router.get("/balance-sheet")
async def balance_sheet(
    request: Request,
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    period = _validate_period(period)
    async with session.begin():
        return await compute_balance_sheet(period, session)


@router.get("/pnl-distribution")
async def pnl_distribution(
    request: Request,
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    period = _validate_period(period)
    async with session.begin():
        return await compute_pnl(period, session)


@router.get("/cashflow")
async def cashflow(
    request: Request,
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    period = _validate_period(period)
    async with session.begin():
        return await compute_cashflow(period, session)


@router.get("/depreciation")
async def depreciation(
    request: Request,
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    period = _validate_period(period)
    return await compute_depreciation_schedule(period, session)


@router.get("/cost-breakdown")
async def cost_breakdown(
    request: Request,
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    period = _validate_period(period)
    return await compute_cost_breakdown(period, session)


@router.get("/chart-of-accounts")
async def chart_of_accounts(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List the chart of accounts (seeds on first call if empty)."""
    await _ensure_tables(request)
    async with session.begin():
        await ensure_chart_of_accounts_seeded(session)
    from sqlalchemy import select
    from yunwei_win.models import ChartOfAccount
    rows = (
        await session.execute(
            select(ChartOfAccount).order_by(ChartOfAccount.sort_order)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "account_code": r.account_code,
            "account_name": r.account_name,
            "account_class": r.account_class.value,
            "statement": r.statement.value,
            "report_line_key": r.report_line_key,
            "normal_balance": r.normal_balance.value,
            "sort_order": r.sort_order,
        }
        for r in rows
    ]
