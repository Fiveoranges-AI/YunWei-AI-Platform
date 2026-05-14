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
    CustomerTask,
    Document,
    EntityType,
    FieldProvenance,
    Order,
)
from yunwei_win.models.company_data import (
    ContractPaymentMilestone,
    CustomerJournalItem,
    Invoice,
    InvoiceItem,
    Payment,
    Product,
    ProductRequirement,
    Shipment,
    ShipmentItem,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# serializers
# ---------------------------------------------------------------------------


def _customer_dict(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "full_name": c.full_name,
        "short_name": c.short_name,
        "address": c.address,
        "tax_id": c.tax_id,
        "industry": c.industry,
        "notes": c.notes,
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
        # Legacy field — keep on the response so old frontend code that still
        # reads it doesn't crash, but vNext review state lives on
        # ``DocumentExtraction.review_draft`` instead.
        "needs_review": ct.needs_review,
    }


def _order_dict(o: Order) -> dict:
    return {
        "id": str(o.id),
        "customer_id": str(o.customer_id),
        "amount_total": float(o.amount_total) if o.amount_total is not None else None,
        "amount_currency": o.amount_currency,
        "delivery_promised_date": (
            o.delivery_promised_date.isoformat() if o.delivery_promised_date else None
        ),
        "delivery_address": o.delivery_address,
        "description": o.description,
    }


def _contract_dict(k: Contract) -> dict:
    return {
        "id": str(k.id),
        "customer_id": str(k.customer_id) if k.customer_id else None,
        "order_id": str(k.order_id) if k.order_id else None,
        "contract_no_external": k.contract_no_external,
        "contract_no_internal": k.contract_no_internal,
        "amount_total": float(k.amount_total) if k.amount_total is not None else None,
        "amount_currency": k.amount_currency,
        "payment_milestones": k.payment_milestones,
        "delivery_terms": k.delivery_terms,
        "penalty_terms": k.penalty_terms,
        "signing_date": k.signing_date.isoformat() if k.signing_date else None,
        "effective_date": k.effective_date.isoformat() if k.effective_date else None,
        "expiry_date": k.expiry_date.isoformat() if k.expiry_date else None,
        "confidence_overall": k.confidence_overall,
        "created_at": k.created_at.isoformat(),
    }


def _milestone_dict(m: ContractPaymentMilestone) -> dict:
    return {
        "id": str(m.id),
        "contract_id": str(m.contract_id),
        "name": m.name,
        "ratio": float(m.ratio) if m.ratio is not None else None,
        "amount": float(m.amount) if m.amount is not None else None,
        "trigger_event": m.trigger_event,
        "trigger_offset_days": m.trigger_offset_days,
        "due_date": m.due_date.isoformat() if m.due_date else None,
        "raw_text": m.raw_text,
    }


def _product_dict(p: Product) -> dict:
    return {
        "id": str(p.id),
        "sku": p.sku,
        "name": p.name,
        "description": p.description,
        "specification": p.specification,
        "unit": p.unit,
    }


def _product_requirement_dict(r: ProductRequirement) -> dict:
    return {
        "id": str(r.id),
        "customer_id": str(r.customer_id) if r.customer_id else None,
        "product_id": str(r.product_id) if r.product_id else None,
        "requirement_type": r.requirement_type,
        "requirement_text": r.requirement_text,
        "tolerance": r.tolerance,
        "source_document_id": (
            str(r.source_document_id) if r.source_document_id else None
        ),
    }


def _invoice_dict(i: Invoice) -> dict:
    return {
        "id": str(i.id),
        "customer_id": str(i.customer_id),
        "order_id": str(i.order_id) if i.order_id else None,
        "invoice_no": i.invoice_no,
        "issue_date": i.issue_date.isoformat() if i.issue_date else None,
        "amount_total": float(i.amount_total) if i.amount_total is not None else None,
        "amount_currency": i.amount_currency,
        "tax_amount": float(i.tax_amount) if i.tax_amount is not None else None,
        "status": i.status,
    }


def _invoice_item_dict(it: InvoiceItem) -> dict:
    return {
        "id": str(it.id),
        "invoice_id": str(it.invoice_id),
        "product_id": str(it.product_id) if it.product_id else None,
        "description": it.description,
        "quantity": float(it.quantity) if it.quantity is not None else None,
        "unit_price": float(it.unit_price) if it.unit_price is not None else None,
        "amount": float(it.amount) if it.amount is not None else None,
    }


def _payment_dict(p: Payment) -> dict:
    return {
        "id": str(p.id),
        "customer_id": str(p.customer_id),
        "invoice_id": str(p.invoice_id) if p.invoice_id else None,
        "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        "amount": float(p.amount) if p.amount is not None else None,
        "currency": p.currency,
        "method": p.method,
        "reference_no": p.reference_no,
    }


def _shipment_dict(s: Shipment) -> dict:
    return {
        "id": str(s.id),
        "customer_id": str(s.customer_id),
        "order_id": str(s.order_id) if s.order_id else None,
        "shipment_no": s.shipment_no,
        "carrier": s.carrier,
        "tracking_no": s.tracking_no,
        "ship_date": s.ship_date.isoformat() if s.ship_date else None,
        "delivery_date": s.delivery_date.isoformat() if s.delivery_date else None,
        "delivery_address": s.delivery_address,
        "status": s.status,
    }


def _shipment_item_dict(it: ShipmentItem) -> dict:
    return {
        "id": str(it.id),
        "shipment_id": str(it.shipment_id),
        "product_id": str(it.product_id) if it.product_id else None,
        "description": it.description,
        "quantity": float(it.quantity) if it.quantity is not None else None,
        "unit": it.unit,
    }


def _journal_item_dict(j: CustomerJournalItem) -> dict:
    return {
        "id": str(j.id),
        "customer_id": str(j.customer_id),
        "document_id": str(j.document_id) if j.document_id else None,
        "item_type": j.item_type,
        "title": j.title,
        "content": j.content,
        "occurred_at": j.occurred_at.isoformat() if j.occurred_at else None,
        "due_date": j.due_date.isoformat() if j.due_date else None,
        "severity": j.severity,
        "status": j.status,
        "confidence": float(j.confidence) if j.confidence is not None else None,
        "raw_excerpt": j.raw_excerpt,
    }


def _task_dict(t: CustomerTask) -> dict:
    return {
        "id": str(t.id),
        "customer_id": str(t.customer_id),
        "document_id": str(t.document_id) if t.document_id else None,
        "title": t.title,
        "description": t.description,
        "assignee": t.assignee,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "priority": t.priority.value,
        "status": t.status.value,
    }


def _document_ref_dict(d: Document) -> dict:
    return {
        "id": str(d.id),
        "type": d.type.value,
        "original_filename": d.original_filename,
        "content_type": d.content_type,
        "uploader": d.uploader,
        "review_status": d.review_status.value,
        "created_at": d.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


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


async def _scalars(session: AsyncSession, stmt):
    return (await session.execute(stmt)).scalars().all()


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    c = (
        await session.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "customer not found")

    contacts = await _scalars(
        session, select(Contact).where(Contact.customer_id == customer_id)
    )
    orders = await _scalars(
        session, select(Order).where(Order.customer_id == customer_id)
    )
    order_ids = [o.id for o in orders] or [None]

    # Contracts: prefer the direct customer_id link added by Task 1; fall back
    # to the legacy ``order_id`` join so older rows still surface.
    contracts = await _scalars(
        session,
        select(Contract).where(
            (Contract.customer_id == customer_id)
            | (Contract.order_id.in_(order_ids))
        ),
    )
    contract_ids = [k.id for k in contracts] or [None]
    milestones = await _scalars(
        session,
        select(ContractPaymentMilestone).where(
            ContractPaymentMilestone.contract_id.in_(contract_ids)
        ),
    )

    invoices = await _scalars(
        session, select(Invoice).where(Invoice.customer_id == customer_id)
    )
    invoice_ids = [i.id for i in invoices] or [None]
    invoice_items = await _scalars(
        session,
        select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids)),
    )

    payments = await _scalars(
        session, select(Payment).where(Payment.customer_id == customer_id)
    )

    shipments = await _scalars(
        session, select(Shipment).where(Shipment.customer_id == customer_id)
    )
    shipment_ids = [s.id for s in shipments] or [None]
    shipment_items = await _scalars(
        session,
        select(ShipmentItem).where(ShipmentItem.shipment_id.in_(shipment_ids)),
    )

    product_requirements = await _scalars(
        session,
        select(ProductRequirement).where(ProductRequirement.customer_id == customer_id),
    )

    # Customer-scoped products: anything referenced by this customer's
    # requirements / invoice items / shipment items.
    product_ids: set = set()
    for r in product_requirements:
        if r.product_id is not None:
            product_ids.add(r.product_id)
    for it in invoice_items:
        if it.product_id is not None:
            product_ids.add(it.product_id)
    for it in shipment_items:
        if it.product_id is not None:
            product_ids.add(it.product_id)
    products: list[Product] = []
    if product_ids:
        products = await _scalars(
            session, select(Product).where(Product.id.in_(list(product_ids)))
        )

    journal_items = await _scalars(
        session,
        select(CustomerJournalItem)
        .where(CustomerJournalItem.customer_id == customer_id)
        .order_by(
            CustomerJournalItem.occurred_at.desc().nullslast(),
            CustomerJournalItem.created_at.desc(),
        ),
    )

    tasks = await _scalars(
        session,
        select(CustomerTask)
        .where(CustomerTask.customer_id == customer_id)
        .order_by(
            CustomerTask.due_date.asc().nullslast(),
            CustomerTask.created_at.desc(),
        ),
    )

    # Source documents: direct customer assignments + anything referenced by
    # journal items / tasks / product requirements.
    document_ids: set = set()
    for j in journal_items:
        if j.document_id is not None:
            document_ids.add(j.document_id)
    for t in tasks:
        if t.document_id is not None:
            document_ids.add(t.document_id)
    for r in product_requirements:
        if r.source_document_id is not None:
            document_ids.add(r.source_document_id)
    assigned_docs = await _scalars(
        session,
        select(Document).where(Document.assigned_customer_id == customer_id),
    )
    for d in assigned_docs:
        document_ids.add(d.id)
    source_documents: list[Document] = []
    if document_ids:
        source_documents = await _scalars(
            session, select(Document).where(Document.id.in_(list(document_ids)))
        )

    return {
        **_customer_dict(c),
        "contacts": [_contact_dict(ct) for ct in contacts],
        "orders": [_order_dict(o) for o in orders],
        "contracts": [_contract_dict(k) for k in contracts],
        "contract_payment_milestones": [_milestone_dict(m) for m in milestones],
        "invoices": [_invoice_dict(i) for i in invoices],
        "invoice_items": [_invoice_item_dict(it) for it in invoice_items],
        "payments": [_payment_dict(p) for p in payments],
        "shipments": [_shipment_dict(s) for s in shipments],
        "shipment_items": [_shipment_item_dict(it) for it in shipment_items],
        "products": [_product_dict(p) for p in products],
        "product_requirements": [
            _product_requirement_dict(r) for r in product_requirements
        ],
        "journal_items": [_journal_item_dict(j) for j in journal_items],
        "tasks": [_task_dict(t) for t in tasks],
        "source_documents": [_document_ref_dict(d) for d in source_documents],
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
    ).scalar_one_or_none() if k.order_id else None
    customer: Customer | None = None
    if k.customer_id is not None:
        customer = (
            await session.execute(select(Customer).where(Customer.id == k.customer_id))
        ).scalar_one_or_none()
    elif order is not None:
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
                "review_action": p.review_action,
                "source_refs": p.source_refs,
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
