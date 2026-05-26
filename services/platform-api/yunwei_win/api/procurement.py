"""锦泰 主线 procurement API.

Mounted under ``/api/win/procurement``. Read-only listing endpoints +
the three business-rule mutations (confirm-and-issue, approve PR,
receive PO). All write paths wrap the rule call in a single
``session.begin()`` transaction so the multi-row mutation is atomic.

The endpoints assume the per-tenant DB is already provisioned (the
``confirm`` endpoint or the schema_ingest path provisions the
procurement tables on first hit; an idempotent ensure call here covers
the listing path that may run before any write).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.models import (
    GoodsReceipt,
    IssueVoucher,
    Material,
    Payable,
    PayableStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionStatus,
    StockAlert,
    StockMovement,
    Supplier,
)
from yunwei_win.services.procurement import (
    ProcurementRuleError,
    approve_requisition,
    confirm_and_issue,
    receive_purchase_order,
    reject_requisition,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/procurement")


def _actor_from_request(request: Request) -> str:
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, str) and actor:
        return actor
    user = getattr(request.state, "user", None)
    if isinstance(user, dict):
        for key in ("id", "username", "display_name"):
            val = user.get(key)
            if isinstance(val, str) and val:
                return val
    return "unknown"


async def _ensure_tables(request: Request) -> None:
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if enterprise_id:
        await ensure_schema_ingest_tables_for(enterprise_id)


# ============================== schemas =================================


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    spec: str | None = None
    unit: str
    safety_stock: Decimal
    last_balance: Decimal
    warning: str  # "ok" | "low" | "out"


class StockAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    material_id: UUID
    level: str
    balance_at_trigger: Decimal
    safety_stock_at_trigger: Decimal
    triggered_at: datetime
    resolved_at: datetime | None
    related_pr_id: UUID | None


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    material_id: UUID
    direction: str
    quantity: Decimal
    balance_after: Decimal
    reference_type: str
    reference_id: UUID | None
    occurred_at: datetime
    source_ref: str | None


class PurchaseRequisitionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    material_id: UUID
    quantity: Decimal
    unit: str | None
    arrive_date: date | None
    unit_price: Decimal | None
    amount: Decimal | None
    note: str | None


class PurchaseRequisitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pr_no: str
    dept: str | None
    applicant: str | None
    apply_date: date | None
    supplier_id: UUID | None
    status: str
    source: str
    source_note: str | None
    approver: str | None
    approved_at: datetime | None
    rejected_reason: str | None
    po_ref: str | None
    human_verified: bool
    items: list[PurchaseRequisitionItemOut] = Field(default_factory=list)


class PurchaseOrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    material_id: UUID
    quantity: Decimal
    unit: str | None
    unit_price: Decimal | None
    amount: Decimal | None


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    po_no: str
    supplier_id: UUID
    from_pr_id: UUID | None
    status: str
    delivery_date: date | None
    total_amount: Decimal
    currency: str
    warehouse: str | None
    received_at: datetime | None
    items: list[PurchaseOrderItemOut] = Field(default_factory=list)


class PayableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    source_type: str
    source_ref: str | None
    amount: Decimal
    paid_amount: Decimal
    invoice_date: date
    due_date: date
    status: str
    days_to_due: int  # negative if overdue
    aging_bucket: str  # "overdue" | "due_soon" | "future"


def _aging_for(due_date: date) -> tuple[int, str]:
    delta = (due_date - date.today()).days
    if delta < 0:
        bucket = "overdue"
    elif delta <= 30:
        bucket = "due_soon"
    else:
        bucket = "future"
    return delta, bucket


def _material_warning(balance: Decimal, safety: Decimal) -> str:
    if balance <= 0:
        return "out"
    if safety > 0 and balance < safety:
        return "low"
    return "ok"


# ============================== listings ================================


@router.get("/materials", response_model=list[MaterialOut])
async def list_materials(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[MaterialOut]:
    await _ensure_tables(request)
    rows = (await session.execute(select(Material).order_by(Material.code))).scalars().all()
    return [
        MaterialOut(
            id=m.id,
            code=m.code,
            name=m.name,
            spec=m.spec,
            unit=m.unit,
            safety_stock=m.safety_stock,
            last_balance=m.last_balance,
            warning=_material_warning(m.last_balance, m.safety_stock),
        )
        for m in rows
    ]


@router.get("/requisitions", response_model=list[PurchaseRequisitionOut])
async def list_requisitions(
    request: Request,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseRequisitionOut]:
    await _ensure_tables(request)
    stmt = select(PurchaseRequisition).order_by(PurchaseRequisition.created_at.desc())
    if status:
        try:
            stmt = stmt.where(PurchaseRequisition.status == PurchaseRequisitionStatus(status))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from e
    prs = (await session.execute(stmt)).scalars().all()
    items_by_pr: dict[UUID, list[PurchaseRequisitionItem]] = {}
    if prs:
        items_stmt = select(PurchaseRequisitionItem).where(
            PurchaseRequisitionItem.pr_id.in_([p.id for p in prs])
        ).order_by(PurchaseRequisitionItem.sort_order)
        items = (await session.execute(items_stmt)).scalars().all()
        for it in items:
            items_by_pr.setdefault(it.pr_id, []).append(it)
    return [
        PurchaseRequisitionOut(
            id=pr.id,
            pr_no=pr.pr_no,
            dept=pr.dept,
            applicant=pr.applicant,
            apply_date=pr.apply_date,
            supplier_id=pr.supplier_id,
            status=pr.status.value,
            source=pr.source.value,
            source_note=pr.source_note,
            approver=pr.approver,
            approved_at=pr.approved_at,
            rejected_reason=pr.rejected_reason,
            po_ref=pr.po_ref,
            human_verified=pr.human_verified,
            items=[
                PurchaseRequisitionItemOut.model_validate(i)
                for i in items_by_pr.get(pr.id, [])
            ],
        )
        for pr in prs
    ]


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
async def list_purchase_orders(
    request: Request,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseOrderOut]:
    await _ensure_tables(request)
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc())
    if status:
        try:
            stmt = stmt.where(PurchaseOrder.status == PurchaseOrderStatus(status))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from e
    pos = (await session.execute(stmt)).scalars().all()
    items_by_po: dict[UUID, list[PurchaseOrderItem]] = {}
    if pos:
        items_stmt = select(PurchaseOrderItem).where(
            PurchaseOrderItem.po_id.in_([p.id for p in pos])
        ).order_by(PurchaseOrderItem.sort_order)
        items = (await session.execute(items_stmt)).scalars().all()
        for it in items:
            items_by_po.setdefault(it.po_id, []).append(it)
    return [
        PurchaseOrderOut(
            id=po.id,
            po_no=po.po_no,
            supplier_id=po.supplier_id,
            from_pr_id=po.from_pr_id,
            status=po.status.value,
            delivery_date=po.delivery_date,
            total_amount=po.total_amount,
            currency=po.currency,
            warehouse=po.warehouse,
            received_at=po.received_at,
            items=[PurchaseOrderItemOut.model_validate(i) for i in items_by_po.get(po.id, [])],
        )
        for po in pos
    ]


@router.get("/payables", response_model=list[PayableOut])
async def list_payables(
    request: Request,
    aging: str | None = Query(default=None, pattern="^(overdue|due_soon|future)$"),
    session: AsyncSession = Depends(get_session),
) -> list[PayableOut]:
    await _ensure_tables(request)
    stmt = select(Payable).order_by(Payable.due_date)
    rows = (await session.execute(stmt)).scalars().all()
    out: list[PayableOut] = []
    for p in rows:
        days, bucket = _aging_for(p.due_date)
        if aging and bucket != aging:
            continue
        out.append(
            PayableOut(
                id=p.id,
                supplier_id=p.supplier_id,
                source_type=p.source_type,
                source_ref=p.source_ref,
                amount=p.amount,
                paid_amount=p.paid_amount,
                invoice_date=p.invoice_date,
                due_date=p.due_date,
                status=p.status.value,
                days_to_due=days,
                aging_bucket=bucket,
            )
        )
    return out


@router.get("/stock-alerts", response_model=list[StockAlertOut])
async def list_stock_alerts(
    request: Request,
    open_only: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[StockAlertOut]:
    await _ensure_tables(request)
    stmt = select(StockAlert).order_by(StockAlert.triggered_at.desc())
    if open_only:
        stmt = stmt.where(StockAlert.resolved_at.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    return [
        StockAlertOut(
            id=a.id,
            material_id=a.material_id,
            level=a.level.value,
            balance_at_trigger=a.balance_at_trigger,
            safety_stock_at_trigger=a.safety_stock_at_trigger,
            triggered_at=a.triggered_at,
            resolved_at=a.resolved_at,
            related_pr_id=a.related_pr_id,
        )
        for a in rows
    ]


@router.get("/stock-movements", response_model=list[StockMovementOut])
async def list_stock_movements(
    request: Request,
    material_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[StockMovementOut]:
    await _ensure_tables(request)
    stmt = (
        select(StockMovement).order_by(StockMovement.occurred_at.desc()).limit(limit)
    )
    if material_id:
        stmt = stmt.where(StockMovement.material_id == material_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        StockMovementOut(
            id=m.id,
            material_id=m.material_id,
            direction=m.direction.value,
            quantity=m.quantity,
            balance_after=m.balance_after,
            reference_type=m.reference_type.value,
            reference_id=m.reference_id,
            occurred_at=m.occurred_at,
            source_ref=m.source_ref,
        )
        for m in rows
    ]


@router.get("/inventory-ledger")
async def inventory_ledger(
    request: Request,
    material_id: UUID = Query(...),
    period: str = Query(..., description="YYYY-MM"),
    session: AsyncSession = Depends(get_session),
):
    """进销存台账: 期初 / 入 / 出 / 期末 + 期内流水明细 (按物料 × 期)."""
    from yunwei_win.services.finance import compute_inventory_ledger, period_bounds

    await _ensure_tables(request)
    try:
        period_bounds(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        return await compute_inventory_ledger(
            material_id=material_id, period=period, session=session,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ============================== mutations ===============================


class IssueVoucherConfirmResponse(BaseModel):
    voucher_id: UUID
    material_id: UUID
    movement_id: UUID
    balance_after: Decimal
    alert_id: UUID | None
    auto_drafted_pr_id: UUID | None
    auto_drafted_pr_no: str | None


@router.post(
    "/issue-vouchers/{voucher_id}/confirm-and-issue",
    response_model=IssueVoucherConfirmResponse,
)
async def issue_voucher_confirm_and_issue(
    request: Request,
    voucher_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> IssueVoucherConfirmResponse:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            result = await confirm_and_issue(
                voucher_id=voucher_id, actor=actor, session=session,
            )
    except ProcurementRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IssueVoucherConfirmResponse(
        voucher_id=result.voucher_id,
        material_id=result.material_id,
        movement_id=result.movement_id,
        balance_after=result.balance_after,
        alert_id=result.alert_id,
        auto_drafted_pr_id=result.auto_drafted_pr_id,
        auto_drafted_pr_no=result.auto_drafted_pr_no,
    )


class ApproveRequisitionPayload(BaseModel):
    supplier_id: UUID | None = None
    unit_prices: dict[UUID, Decimal] | None = None


class ApproveRequisitionResponse(BaseModel):
    pr_id: UUID
    po_id: UUID
    po_no: str
    total_amount: Decimal


@router.post(
    "/requisitions/{pr_id}/approve", response_model=ApproveRequisitionResponse,
)
async def approve_requisition_endpoint(
    request: Request,
    pr_id: UUID,
    payload: ApproveRequisitionPayload | None = None,
    session: AsyncSession = Depends(get_session),
) -> ApproveRequisitionResponse:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    payload = payload or ApproveRequisitionPayload()
    try:
        async with session.begin():
            result = await approve_requisition(
                pr_id=pr_id,
                actor=actor,
                session=session,
                supplier_id=payload.supplier_id,
                unit_prices=payload.unit_prices,
            )
    except ProcurementRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ApproveRequisitionResponse(
        pr_id=result.pr_id,
        po_id=result.po_id,
        po_no=result.po_no,
        total_amount=result.total_amount,
    )


class RejectRequisitionPayload(BaseModel):
    reason: str | None = None


@router.post("/requisitions/{pr_id}/reject")
async def reject_requisition_endpoint(
    request: Request,
    pr_id: UUID,
    payload: RejectRequisitionPayload | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    reason = payload.reason if payload else None
    try:
        async with session.begin():
            pr_id_out = await reject_requisition(
                pr_id=pr_id, actor=actor, reason=reason, session=session,
            )
    except ProcurementRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"pr_id": str(pr_id_out), "status": "rejected"}


class ReceivePoPayload(BaseModel):
    warehouse: str
    receipt_no: str | None = None
    invoice_date: date | None = None


class ReceivePoResponse(BaseModel):
    po_id: UUID
    receipt_id: UUID
    receipt_no: str
    payable_id: UUID
    payable_due_date: date
    stock_movement_ids: list[UUID]
    resolved_alert_ids: list[UUID]


@router.post(
    "/purchase-orders/{po_id}/receive", response_model=ReceivePoResponse,
)
async def purchase_order_receive(
    request: Request,
    po_id: UUID,
    payload: ReceivePoPayload,
    session: AsyncSession = Depends(get_session),
) -> ReceivePoResponse:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            result = await receive_purchase_order(
                po_id=po_id,
                warehouse=payload.warehouse,
                actor=actor,
                session=session,
                receipt_no=payload.receipt_no,
                invoice_date=payload.invoice_date,
            )
    except ProcurementRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ReceivePoResponse(
        po_id=result.po_id,
        receipt_id=result.receipt_id,
        receipt_no=result.receipt_no,
        payable_id=result.payable_id,
        payable_due_date=result.payable_due_date,
        stock_movement_ids=result.stock_movements,
        resolved_alert_ids=result.resolved_alert_ids,
    )
