"""Read endpoints — let the operator drill into ingested data.

- GET /api/win/customers
- GET /api/win/customers/{id}
- GET /api/win/contracts
- GET /api/win/contracts/{id}
- GET /api/win/documents/{id}
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.models import (
    Contact,
    Contract,
    Customer,
    Document,
    EntityType,
    FieldProvenance,
    Order,
)

router = APIRouter()


def _customer_dict(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "full_name": c.full_name,
        "short_name": c.short_name,
        "address": c.address,
        "tax_id": c.tax_id,
        "created_at": c.created_at.isoformat(),
    }


def _contract_dict(k: Contract) -> dict:
    return {
        "id": str(k.id),
        "order_id": str(k.order_id),
        "contract_no_external": k.contract_no_external,
        "contract_no_internal": k.contract_no_internal,
        "payment_milestones": k.payment_milestones,
        "delivery_terms": k.delivery_terms,
        "penalty_terms": k.penalty_terms,
        "signing_date": k.signing_date.isoformat() if k.signing_date else None,
        "effective_date": k.effective_date.isoformat() if k.effective_date else None,
        "expiry_date": k.expiry_date.isoformat() if k.expiry_date else None,
        "confidence_overall": k.confidence_overall,
        "created_at": k.created_at.isoformat(),
    }


@router.get("/customers")
async def list_customers(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(Customer).order_by(Customer.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [_customer_dict(c) for c in rows]


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    c = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "customer not found")

    contacts = (
        await session.execute(select(Contact).where(Contact.customer_id == customer_id))
    ).scalars().all()
    orders = (
        await session.execute(select(Order).where(Order.customer_id == customer_id))
    ).scalars().all()
    contracts = (
        await session.execute(
            select(Contract).where(Contract.order_id.in_([o.id for o in orders] or [None]))
        )
    ).scalars().all()

    return {
        **_customer_dict(c),
        "contacts": [
            {
                "id": str(ct.id),
                "name": ct.name,
                "title": ct.title,
                "phone": ct.phone,
                "mobile": ct.mobile,
                "email": ct.email,
                "role": ct.role.value,
                "needs_review": ct.needs_review,
            }
            for ct in contacts
        ],
        "orders": [
            {
                "id": str(o.id),
                "amount_total": float(o.amount_total) if o.amount_total else None,
                "amount_currency": o.amount_currency,
                "delivery_promised_date": (
                    o.delivery_promised_date.isoformat() if o.delivery_promised_date else None
                ),
                "delivery_address": o.delivery_address,
                "description": o.description,
            }
            for o in orders
        ],
        "contracts": [_contract_dict(k) for k in contracts],
    }


@router.get("/contracts")
async def list_contracts(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(Contract).order_by(Contract.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [_contract_dict(k) for k in rows]


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    k = (
        await session.execute(select(Contract).where(Contract.id == contract_id))
    ).scalar_one_or_none()
    if k is None:
        raise HTTPException(404, "contract not found")

    order = (
        await session.execute(select(Order).where(Order.id == k.order_id))
    ).scalar_one_or_none()
    customer = None
    if order is not None:
        customer = (
            await session.execute(select(Customer).where(Customer.id == order.customer_id))
        ).scalar_one_or_none()

    # Provenance for this contract row
    prov = (
        await session.execute(
            select(FieldProvenance).where(
                FieldProvenance.entity_type == EntityType.contract,
                FieldProvenance.entity_id == contract_id,
            )
        )
    ).scalars().all()

    return {
        **_contract_dict(k),
        "order": (
            {
                "id": str(order.id),
                "amount_total": float(order.amount_total) if order.amount_total else None,
                "amount_currency": order.amount_currency,
                "delivery_promised_date": (
                    order.delivery_promised_date.isoformat()
                    if order.delivery_promised_date else None
                ),
            }
            if order else None
        ),
        "customer": _customer_dict(customer) if customer else None,
        "provenance": [
            {
                "field_name": p.field_name,
                "value": p.value,
                "source_page": p.source_page,
                "source_excerpt": p.source_excerpt,
                "confidence": float(p.confidence) if p.confidence is not None else None,
                "excerpt_match": p.excerpt_match,
                "extracted_by": p.extracted_by,
            }
            for p in prov
        ],
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    d = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if d is None:
        raise HTTPException(404, "document not found")
    return {
        "id": str(d.id),
        "type": d.type.value,
        "file_url": d.file_url,
        "original_filename": d.original_filename,
        "content_type": d.content_type,
        "file_sha256": d.file_sha256,
        "file_size_bytes": d.file_size_bytes,
        "ocr_text": d.ocr_text,
        "raw_llm_response": d.raw_llm_response,
        "parse_error": d.parse_error,
        "parse_warnings": d.parse_warnings,
        "uploader": d.uploader,
        "created_at": d.created_at.isoformat(),
    }
