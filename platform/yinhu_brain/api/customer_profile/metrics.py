"""Customer metrics aggregation — feeds the frontend's metric tiles.

Returns the shape the design expects: contractTotal / receivable / contracts /
tasks / contacts. Computed in a single round-trip per customer.

Schema notes (yunwei-tools v0.2):
- Each Order has amount_total (Numeric).
- Each Contract is attached to one Order via order_id.
- payment_milestones is a JSON array on Contract; each milestone may have
  ``status`` ∈ {pending, paid, overdue, cancelled} and ``amount``. We treat
  receivable = total - sum of milestones marked paid.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.api.customer_profile._helpers import load_customer
from yinhu_brain.db import get_session
from yinhu_brain.models import Contact, Contract, Order
from yinhu_brain.models.customer_memory import CustomerTask, TaskStatus

router = APIRouter()


def _milestones_paid(payment_milestones: list | None) -> Decimal:
    if not payment_milestones:
        return Decimal(0)
    paid = Decimal(0)
    for m in payment_milestones:
        if not isinstance(m, dict):
            continue
        if str(m.get("status", "")).lower() == "paid":
            try:
                paid += Decimal(str(m.get("amount") or 0))
            except (ValueError, ArithmeticError):
                continue
    return paid


@router.get("/{customer_id}/metrics")
async def customer_metrics(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    await load_customer(session, customer_id)

    # contracts joined through orders
    order_ids = (
        await session.execute(
            select(Order.id).where(Order.customer_id == customer_id)
        )
    ).scalars().all()
    contracts = []
    contract_total = Decimal(0)
    paid_total = Decimal(0)
    if order_ids:
        # contractTotal: sum of order amount_total
        order_sum = (
            await session.execute(
                select(func.coalesce(func.sum(Order.amount_total), 0)).where(
                    Order.customer_id == customer_id
                )
            )
        ).scalar_one()
        contract_total = Decimal(str(order_sum or 0))

        contracts = (
            await session.execute(
                select(Contract).where(Contract.order_id.in_(order_ids))
            )
        ).scalars().all()
        for c in contracts:
            paid_total += _milestones_paid(c.payment_milestones)

    receivable = max(contract_total - paid_total, Decimal(0))

    contacts_count = (
        await session.execute(
            select(func.count()).select_from(Contact).where(Contact.customer_id == customer_id)
        )
    ).scalar_one()

    open_tasks_count = (
        await session.execute(
            select(func.count()).select_from(CustomerTask).where(
                CustomerTask.customer_id == customer_id,
                CustomerTask.status.in_([TaskStatus.open, TaskStatus.in_progress]),
            )
        )
    ).scalar_one()

    return {
        "contractTotal": float(contract_total),
        "receivable": float(receivable),
        "contracts": len(contracts),
        "tasks": int(open_tasks_count),
        "contacts": int(contacts_count),
    }
