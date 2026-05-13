"""Customer management endpoints — edit / delete / bulk clear.

These are operator-facing maintenance endpoints for the Win UI:

- PATCH  /api/win/customers/{customer_id}             — update top-level fields
- PUT    /api/win/customers/{customer_id}/contacts    — full contact-list replace
- DELETE /api/win/customers/{customer_id}             — cascade delete one customer
- DELETE /api/win/customers?confirm=...               — bulk wipe (gated by confirm)

The cascade for a single delete touches: customers, contacts, orders, contracts,
field_provenance (manually — entity_id is not a real FK), and every
customer-memory table. Documents are intentionally preserved (audit trail) with
``assigned_customer_id`` / ``detected_customer_id`` nulled out.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.models import (
    Contact,
    ContactRole,
    Contract,
    Customer,
    CustomerCommitment,
    CustomerEvent,
    CustomerInboxItem,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    EntityType,
    FieldProvenance,
    Order,
)

router = APIRouter()


# ---------- response/request shapes --------------------------------------


def _customer_dict(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "full_name": c.full_name,
        "short_name": c.short_name,
        "address": c.address,
        "tax_id": c.tax_id,
        "created_at": c.created_at.isoformat(),
    }


def _contact_dict(ct: Contact) -> dict:
    return {
        "id": str(ct.id),
        "name": ct.name,
        "title": ct.title,
        "phone": ct.phone,
        "mobile": ct.mobile,
        "email": ct.email,
        "role": ct.role.value,
        "address": ct.address,
        "wechat_id": ct.wechat_id,
        "needs_review": ct.needs_review,
    }


class CustomerPatchRequest(BaseModel):
    full_name: str | None = None
    short_name: str | None = None
    address: str | None = None
    tax_id: str | None = None


class ContactUpsertItem(BaseModel):
    id: UUID | None = None
    name: str
    title: str | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    role: str | None = None
    address: str | None = None
    wechat_id: str | None = None


class ContactsPutRequest(BaseModel):
    contacts: list[ContactUpsertItem]


# ---------- PATCH /api/win/customers/{id} --------------------------------


@router.patch("/customers/{customer_id}")
async def patch_customer(
    customer_id: UUID,
    payload: CustomerPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    customer = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(404, "customer not found")

    updates = payload.model_dump(exclude_unset=True)
    if "full_name" in updates:
        full_name = (updates["full_name"] or "").strip()
        if not full_name:
            raise HTTPException(400, "full_name must be non-empty if provided")
        customer.full_name = full_name
    if "short_name" in updates:
        customer.short_name = updates["short_name"]
    if "address" in updates:
        customer.address = updates["address"]
    if "tax_id" in updates:
        customer.tax_id = updates["tax_id"]

    await session.commit()
    await session.refresh(customer)
    return _customer_dict(customer)


# ---------- PUT /api/win/customers/{id}/contacts -------------------------


@router.put("/customers/{customer_id}/contacts")
async def put_contacts(
    customer_id: UUID,
    payload: ContactsPutRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    customer = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(404, "customer not found")

    # Reject empties up front (don't write a partial change).
    for item in payload.contacts:
        if not item.name or not item.name.strip():
            raise HTTPException(400, "every contact must have a non-empty name")

    existing = (
        await session.execute(select(Contact).where(Contact.customer_id == customer_id))
    ).scalars().all()
    existing_by_id = {c.id: c for c in existing}

    seen_ids: set[UUID] = set()
    final_contacts: list[Contact] = []
    for item in payload.contacts:
        role = ContactRole(item.role) if item.role else ContactRole.other
        if item.id is not None and item.id in existing_by_id:
            ct = existing_by_id[item.id]
            ct.name = item.name.strip()
            ct.title = item.title
            ct.phone = item.phone
            ct.mobile = item.mobile
            ct.email = item.email
            ct.role = role
            ct.address = item.address
            ct.wechat_id = item.wechat_id
            seen_ids.add(ct.id)
            final_contacts.append(ct)
        else:
            ct = Contact(
                customer_id=customer_id,
                name=item.name.strip(),
                title=item.title,
                phone=item.phone,
                mobile=item.mobile,
                email=item.email,
                role=role,
                address=item.address,
                wechat_id=item.wechat_id,
            )
            session.add(ct)
            final_contacts.append(ct)

    deleted_ids = [c.id for c in existing if c.id not in seen_ids]
    if deleted_ids:
        # Clean orphan provenance rows that point at the deleted contacts.
        await session.execute(
            delete(FieldProvenance).where(
                FieldProvenance.entity_type == EntityType.contact,
                FieldProvenance.entity_id.in_(deleted_ids),
            )
        )
        await session.execute(delete(Contact).where(Contact.id.in_(deleted_ids)))

    await session.commit()
    # Refresh newly-inserted ones to surface generated ids.
    for ct in final_contacts:
        await session.refresh(ct)

    return {
        "customer_id": str(customer_id),
        "contacts": [_contact_dict(c) for c in final_contacts],
    }


# ---------- DELETE helpers ------------------------------------------------


async def _delete_customer_cascade(
    session: AsyncSession, customer_id: UUID
) -> dict[str, int]:
    """Delete customer + cascading entities; return per-table delete counts.

    Caller is responsible for the final commit. All deletions run in the
    caller's session so the whole cascade lives in one transaction.
    """
    contacts = (
        await session.execute(select(Contact).where(Contact.customer_id == customer_id))
    ).scalars().all()
    contact_ids = [c.id for c in contacts]

    orders = (
        await session.execute(select(Order).where(Order.customer_id == customer_id))
    ).scalars().all()
    order_ids = [o.id for o in orders]

    contracts: list[Contract] = []
    if order_ids:
        contracts = (
            await session.execute(
                select(Contract).where(Contract.order_id.in_(order_ids))
            )
        ).scalars().all()
    contract_ids = [k.id for k in contracts]

    # Provenance — entity_id is a plain Uuid (not a real FK), so wipe it ourselves.
    if contact_ids:
        await session.execute(
            delete(FieldProvenance).where(
                FieldProvenance.entity_type == EntityType.contact,
                FieldProvenance.entity_id.in_(contact_ids),
            )
        )
    if order_ids:
        await session.execute(
            delete(FieldProvenance).where(
                FieldProvenance.entity_type == EntityType.order,
                FieldProvenance.entity_id.in_(order_ids),
            )
        )
    if contract_ids:
        await session.execute(
            delete(FieldProvenance).where(
                FieldProvenance.entity_type == EntityType.contract,
                FieldProvenance.entity_id.in_(contract_ids),
            )
        )
    await session.execute(
        delete(FieldProvenance).where(
            FieldProvenance.entity_type == EntityType.customer,
            FieldProvenance.entity_id == customer_id,
        )
    )

    # Customer-memory tables — ondelete=CASCADE handles this in Postgres, but
    # we need the row counts for the response and don't want behaviour to
    # differ between SQLite (tests) and Postgres (prod), so delete explicitly.
    events_count = len(
        (
            await session.execute(
                select(CustomerEvent.id).where(CustomerEvent.customer_id == customer_id)
            )
        ).scalars().all()
    )
    commitments_count = len(
        (
            await session.execute(
                select(CustomerCommitment.id).where(
                    CustomerCommitment.customer_id == customer_id
                )
            )
        ).scalars().all()
    )
    tasks_count = len(
        (
            await session.execute(
                select(CustomerTask.id).where(CustomerTask.customer_id == customer_id)
            )
        ).scalars().all()
    )
    risks_count = len(
        (
            await session.execute(
                select(CustomerRiskSignal.id).where(
                    CustomerRiskSignal.customer_id == customer_id
                )
            )
        ).scalars().all()
    )
    memory_count = len(
        (
            await session.execute(
                select(CustomerMemoryItem.id).where(
                    CustomerMemoryItem.customer_id == customer_id
                )
            )
        ).scalars().all()
    )
    inbox_count = len(
        (
            await session.execute(
                select(CustomerInboxItem.id).where(
                    CustomerInboxItem.customer_id == customer_id
                )
            )
        ).scalars().all()
    )

    await session.execute(
        delete(CustomerEvent).where(CustomerEvent.customer_id == customer_id)
    )
    await session.execute(
        delete(CustomerCommitment).where(CustomerCommitment.customer_id == customer_id)
    )
    await session.execute(
        delete(CustomerTask).where(CustomerTask.customer_id == customer_id)
    )
    await session.execute(
        delete(CustomerRiskSignal).where(CustomerRiskSignal.customer_id == customer_id)
    )
    await session.execute(
        delete(CustomerMemoryItem).where(CustomerMemoryItem.customer_id == customer_id)
    )
    await session.execute(
        delete(CustomerInboxItem).where(CustomerInboxItem.customer_id == customer_id)
    )

    # Documents are preserved for audit — just null the customer pointers so
    # the orders/customers cascade doesn't trip the FK.
    await session.execute(
        update(Document)
        .where(Document.assigned_customer_id == customer_id)
        .values(assigned_customer_id=None)
    )
    await session.execute(
        update(Document)
        .where(Document.detected_customer_id == customer_id)
        .values(detected_customer_id=None)
    )

    # Contracts → orders → contacts → customer. Order matters because
    # orders.customer_id is ondelete=RESTRICT.
    if contract_ids:
        await session.execute(delete(Contract).where(Contract.id.in_(contract_ids)))
    if order_ids:
        await session.execute(delete(Order).where(Order.id.in_(order_ids)))
    if contact_ids:
        await session.execute(delete(Contact).where(Contact.id.in_(contact_ids)))
    await session.execute(delete(Customer).where(Customer.id == customer_id))

    return {
        "contacts": len(contact_ids),
        "orders": len(order_ids),
        "contracts": len(contract_ids),
        "events": events_count,
        "commitments": commitments_count,
        "tasks": tasks_count,
        "risks": risks_count,
        "memory_items": memory_count,
        "inbox_items": inbox_count,
    }


# ---------- DELETE /api/win/customers (bulk) — declared BEFORE the {id} route -


@router.delete("/customers")
async def delete_all_customers(
    confirm: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if confirm != "DELETE_ALL_IMPORTED_CUSTOMERS":
        raise HTTPException(
            400,
            "must pass ?confirm=DELETE_ALL_IMPORTED_CUSTOMERS to wipe all customers",
        )

    customer_ids = (
        await session.execute(select(Customer.id))
    ).scalars().all()

    totals: dict[str, int] = {
        "contacts": 0,
        "orders": 0,
        "contracts": 0,
        "events": 0,
        "commitments": 0,
        "tasks": 0,
        "risks": 0,
        "memory_items": 0,
        "inbox_items": 0,
    }
    for cid in customer_ids:
        counts = await _delete_customer_cascade(session, cid)
        for k, v in counts.items():
            totals[k] += v

    await session.commit()
    return {
        "deleted_customers": len(customer_ids),
        "deleted_counts": totals,
    }


# ---------- DELETE /api/win/customers/{id} -------------------------------


@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    customer = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(404, "customer not found")

    counts = await _delete_customer_cascade(session, customer_id)
    await session.commit()
    return {
        "customer_id": str(customer_id),
        "deleted": True,
        "deleted_counts": counts,
    }
