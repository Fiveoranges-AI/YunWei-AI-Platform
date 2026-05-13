"""Customer metrics aggregation — feeds the frontend's metric tiles.

Returns the shape the design expects: contractTotal / receivable / contracts /
tasks / contacts. Computed in a single round-trip per customer.

Schema notes (yunwei-tools v0.2):
- Each Order has amount_total (Numeric).
- Each Contract is attached to one Order via order_id.
- payment_milestones is a JSON array on Contract. The current extractor only
  guarantees ``ratio``; if a later workflow adds ``status=paid`` with either
  ``amount`` or ``ratio``, we subtract that from receivable.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.api.customer_profile._helpers import load_customer
from yunwei_win.db import get_session
from yunwei_win.models import Contact, Contract, Order
from yunwei_win.models.customer_memory import CustomerTask, TaskStatus

router = APIRouter()


def _milestones_paid(payment_milestones: list | None, order_amount: Decimal) -> Decimal:
    if not payment_milestones:
        return Decimal(0)
    paid = Decimal(0)
    for m in payment_milestones:
        if not isinstance(m, dict):
            continue
        if str(m.get("status", "")).lower() == "paid":
            try:
                if m.get("amount") is not None:
                    paid += Decimal(str(m.get("amount") or 0))
                else:
                    paid += order_amount * Decimal(str(m.get("ratio") or 0))
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

        order_amounts = {
            row[0]: Decimal(str(row[1] or 0))
            for row in (
                await session.execute(
                    select(Order.id, Order.amount_total).where(Order.customer_id == customer_id)
                )
            ).all()
        }

        contracts = (
            await session.execute(
                select(Contract).where(Contract.order_id.in_(order_ids))
            )
        ).scalars().all()
        for c in contracts:
            paid_total += _milestones_paid(c.payment_milestones, order_amounts.get(c.order_id, Decimal(0)))

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
