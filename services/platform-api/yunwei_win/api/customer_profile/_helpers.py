"""Helpers shared between the customer_profile sub-routers."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import Customer


async def load_customer(session: AsyncSession, customer_id: UUID) -> Customer:
    cust = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if cust is None:
        raise HTTPException(404, f"customer {customer_id} not found")
    return cust


def filter_by_status(stmt, column, raw: str | None, enum_cls):
    """Append ``WHERE column = enum_cls(raw)`` or raise 400 if the raw value
    isn't a valid enum member. No-op when ``raw`` is None/empty."""
    if not raw:
        return stmt
    try:
        return stmt.where(column == enum_cls(raw))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


async def exec_list(session: AsyncSession, stmt, out_model) -> list:
    """Run ``stmt``, coerce each row through ``out_model.model_validate``."""
    rows = (await session.execute(stmt)).scalars().all()
    return [out_model.model_validate(r) for r in rows]
