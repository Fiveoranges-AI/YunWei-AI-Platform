"""光天 · AI 库存管家 API.

Mounted under ``/api/win/guangtian``. 列表/详情只读 + 出入库/补产/采纳 写路径
(都包在单 ``session.begin()`` 事务) + 缺货预警 + 老板问数 + 库存日报 + KPI.

per-tenant DB 在首个写或 ``_ensure_tables`` 时 provision; 与锦泰物理隔离
(光天 tenant = ``guangtian_demo``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import ensure_schema_ingest_tables_for, get_session
from yunwei_win.models import (
    GuangtianCustomerOrder,
    GuangtianCustomerOrderItem,
    GuangtianInboundType,
    GuangtianMovementOp,
    GuangtianOutboundType,
    GuangtianReplenishment,
    GuangtianReplenishStatus,
    GuangtianSku,
    GuangtianStockAlert,
    GuangtianStockMovement,
    GuangtianVoucherStatus,
)
from yunwei_win.services.guangtian import (
    GuangtianRuleError,
    adopt_replenishment,
    apply_inbound_voucher,
    apply_outbound_voucher,
    derive_status,
    generate_replenishment_suggestions,
    open_order_gap_by_sku,
    record_inbound,
    record_outbound,
)
from yunwei_win.services.guangtian_ask import answer_inventory_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/guangtian")


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


class SkuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    spec: str | None = None
    category: str | None = None
    unit: str
    location: str | None = None
    safety_stock: Decimal
    last_balance: Decimal
    status: str  # 派生: normal|low|shortage_risk|out|anomaly
    last_in_at: date | None = None
    last_out_at: date | None = None


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku_id: UUID
    op: str
    quantity: Decimal
    balance_before: Decimal
    balance_after: Decimal
    reference_no: str | None = None
    operator: str | None = None
    occurred_at: datetime
    confidence: int | None = None
    confirmed: bool
    note: str | None = None


class InboundIn(BaseModel):
    sku_id: UUID
    quantity: Decimal
    unit: str | None = None
    batch: str | None = None
    location: str | None = None
    inbound_type: GuangtianInboundType = GuangtianInboundType.production
    source_ref: str | None = None
    operator: str | None = None
    confidence: int | None = None


class OutboundIn(BaseModel):
    sku_id: UUID
    quantity: Decimal
    unit: str | None = None
    outbound_type: GuangtianOutboundType = GuangtianOutboundType.sales
    customer: str | None = None
    order_no: str | None = None
    operator: str | None = None
    confidence: int | None = None


class MovementResultOut(BaseModel):
    sku_id: UUID
    voucher_id: UUID
    movement_id: UUID
    balance_before: Decimal
    balance_after: Decimal
    alert_id: UUID | None = None
    resolved_alerts: int = 0


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku_id: UUID
    level: str
    balance_at_trigger: Decimal
    safety_stock_at_trigger: Decimal
    triggered_at: datetime
    resolved_at: datetime | None = None
    note: str | None = None


class OrderItemOut(BaseModel):
    sku_id: UUID | None
    sku_code: str | None
    name: str | None
    needed: Decimal
    stock: Decimal
    gap: Decimal
    unit: str | None


class OrderOut(BaseModel):
    id: UUID
    order_no: str
    customer: str
    delivery_date: date | None
    delivery_note: str | None
    level: str
    total_value: Decimal | None
    ai_suggestion: str | None
    items: list[OrderItemOut]
    fulfillment_pct: int


class ReplenishmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku_id: UUID
    current_stock: Decimal
    safety_stock: Decimal
    suggest_qty: Decimal
    unit: str | None
    priority: str
    reason: str | None
    est_date: date | None
    status: str
    source: str
    work_order_no: str | None


class AskIn(BaseModel):
    question: str


# ============================== helpers =================================


async def _sku_code_map(session: AsyncSession) -> dict[UUID, GuangtianSku]:
    rows = (await session.execute(select(GuangtianSku))).scalars().all()
    return {s.id: s for s in rows}


# ============================== SKU =====================================


@router.get("/skus", response_model=list[SkuOut])
async def list_skus(
    request: Request, session: AsyncSession = Depends(get_session)
) -> list[SkuOut]:
    await _ensure_tables(request)
    gaps = await open_order_gap_by_sku(session)
    rows = (
        await session.execute(
            select(GuangtianSku).where(GuangtianSku.is_deleted.is_(False)).order_by(GuangtianSku.code)
        )
    ).scalars().all()
    out: list[SkuOut] = []
    for s in rows:
        status = derive_status(
            balance=Decimal(s.last_balance),
            safety=Decimal(s.safety_stock),
            override=s.status_override,
            has_open_gap=s.id in gaps,
        )
        out.append(
            SkuOut(
                id=s.id, code=s.code, name=s.name, spec=s.spec, category=s.category,
                unit=s.unit, location=s.location, safety_stock=s.safety_stock,
                last_balance=s.last_balance, status=status.value,
                last_in_at=s.last_in_at, last_out_at=s.last_out_at,
            )
        )
    return out


@router.get("/skus/{sku_id}", response_model=SkuOut)
async def get_sku(
    request: Request, sku_id: UUID, session: AsyncSession = Depends(get_session)
) -> SkuOut:
    await _ensure_tables(request)
    s = await session.get(GuangtianSku, sku_id)
    if s is None or s.is_deleted:
        raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
    gaps = await open_order_gap_by_sku(session)
    status = derive_status(
        balance=Decimal(s.last_balance), safety=Decimal(s.safety_stock),
        override=s.status_override, has_open_gap=s.id in gaps,
    )
    return SkuOut(
        id=s.id, code=s.code, name=s.name, spec=s.spec, category=s.category,
        unit=s.unit, location=s.location, safety_stock=s.safety_stock,
        last_balance=s.last_balance, status=status.value,
        last_in_at=s.last_in_at, last_out_at=s.last_out_at,
    )


# ============================== movements / 出入库 ========================


@router.get("/stock-movements", response_model=list[MovementOut])
async def list_movements(
    request: Request,
    session: AsyncSession = Depends(get_session),
    sku_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[MovementOut]:
    await _ensure_tables(request)
    stmt = select(GuangtianStockMovement).order_by(GuangtianStockMovement.occurred_at.desc()).limit(limit)
    if sku_id is not None:
        stmt = stmt.where(GuangtianStockMovement.sku_id == sku_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [MovementOut.model_validate(r) for r in rows]


@router.post("/inbound", response_model=MovementResultOut)
async def post_inbound(
    request: Request, payload: InboundIn, session: AsyncSession = Depends(get_session)
) -> MovementResultOut:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            res = await record_inbound(
                session=session, sku_id=payload.sku_id, quantity=payload.quantity,
                actor=actor, unit=payload.unit, batch=payload.batch,
                location=payload.location, inbound_type=payload.inbound_type,
                source_ref=payload.source_ref, operator=payload.operator,
                confidence=payload.confidence,
            )
    except GuangtianRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"unique-key conflict: {e.orig}") from e
    return MovementResultOut(**res.__dict__)


@router.post("/outbound", response_model=MovementResultOut)
async def post_outbound(
    request: Request, payload: OutboundIn, session: AsyncSession = Depends(get_session)
) -> MovementResultOut:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            res = await record_outbound(
                session=session, sku_id=payload.sku_id, quantity=payload.quantity,
                actor=actor, unit=payload.unit, outbound_type=payload.outbound_type,
                customer=payload.customer, order_no=payload.order_no,
                operator=payload.operator, confidence=payload.confidence,
            )
    except GuangtianRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"unique-key conflict: {e.orig}") from e
    return MovementResultOut(**res.__dict__)


@router.post("/inbound-vouchers/{voucher_id}/confirm-and-apply", response_model=MovementResultOut)
async def inbound_confirm_apply(
    request: Request, voucher_id: UUID, session: AsyncSession = Depends(get_session)
) -> MovementResultOut:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            res = await apply_inbound_voucher(session=session, voucher_id=voucher_id, actor=actor)
    except GuangtianRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MovementResultOut(**res.__dict__)


@router.post("/outbound-vouchers/{voucher_id}/confirm-and-apply", response_model=MovementResultOut)
async def outbound_confirm_apply(
    request: Request, voucher_id: UUID, session: AsyncSession = Depends(get_session)
) -> MovementResultOut:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            res = await apply_outbound_voucher(session=session, voucher_id=voucher_id, actor=actor)
    except GuangtianRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MovementResultOut(**res.__dict__)


# ============================== alerts / 缺货预警 =========================


@router.get("/stock-alerts", response_model=list[AlertOut])
async def list_alerts(
    request: Request,
    session: AsyncSession = Depends(get_session),
    only_open: bool = Query(default=False),
) -> list[AlertOut]:
    await _ensure_tables(request)
    stmt = select(GuangtianStockAlert).order_by(GuangtianStockAlert.triggered_at.desc())
    if only_open:
        stmt = stmt.where(GuangtianStockAlert.resolved_at.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]


# ============================== customer orders / 订单缺货 ================


@router.get("/customer-orders", response_model=list[OrderOut])
async def list_customer_orders(
    request: Request, session: AsyncSession = Depends(get_session)
) -> list[OrderOut]:
    await _ensure_tables(request)
    sku_map = await _sku_code_map(session)
    orders = (
        await session.execute(
            select(GuangtianCustomerOrder)
            .where(GuangtianCustomerOrder.is_deleted.is_(False))
            .order_by(GuangtianCustomerOrder.order_no)
        )
    ).scalars().all()
    items_rows = (
        await session.execute(
            select(GuangtianCustomerOrderItem)
            .where(GuangtianCustomerOrderItem.is_deleted.is_(False))
            .order_by(GuangtianCustomerOrderItem.sort_order)
        )
    ).scalars().all()
    items_by_order: dict[UUID, list[GuangtianCustomerOrderItem]] = {}
    for it in items_rows:
        items_by_order.setdefault(it.order_id, []).append(it)

    out: list[OrderOut] = []
    for o in orders:
        item_outs: list[OrderItemOut] = []
        total_needed = Decimal("0")
        total_fillable = Decimal("0")
        for it in items_by_order.get(o.id, []):
            sku = sku_map.get(it.sku_id) if it.sku_id else None
            stock = Decimal(sku.last_balance) if sku else Decimal("0")
            needed = Decimal(it.needed)
            gap = needed - stock
            gap = gap if gap > 0 else Decimal("0")
            total_needed += needed
            total_fillable += min(needed, stock)
            item_outs.append(
                OrderItemOut(
                    sku_id=it.sku_id,
                    sku_code=sku.code if sku else None,
                    name=sku.name if sku else None,
                    needed=needed, stock=stock, gap=gap, unit=it.unit or (sku.unit if sku else None),
                )
            )
        pct = int((total_fillable / total_needed * 100)) if total_needed > 0 else 100
        out.append(
            OrderOut(
                id=o.id, order_no=o.order_no, customer=o.customer,
                delivery_date=o.delivery_date, delivery_note=o.delivery_note,
                level=o.level.value, total_value=o.total_value,
                ai_suggestion=o.ai_suggestion, items=item_outs, fulfillment_pct=pct,
            )
        )
    return out


# ============================== replenishment / AI 补产建议 ===============


@router.get("/replenishments", response_model=list[ReplenishmentOut])
async def list_replenishments(
    request: Request,
    session: AsyncSession = Depends(get_session),
    status: GuangtianReplenishStatus | None = Query(default=None),
) -> list[ReplenishmentOut]:
    await _ensure_tables(request)
    stmt = select(GuangtianReplenishment).where(GuangtianReplenishment.is_deleted.is_(False))
    if status is not None:
        stmt = stmt.where(GuangtianReplenishment.status == status)
    rows = (await session.execute(stmt.order_by(GuangtianReplenishment.created_at.desc()))).scalars().all()
    return [ReplenishmentOut.model_validate(r) for r in rows]


@router.post("/replenishments/generate")
async def gen_replenishments(
    request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    async with session.begin():
        res = await generate_replenishment_suggestions(session=session, actor=actor)
    return {"created": [str(i) for i in res.created], "skipped_existing": res.skipped_existing}


@router.post("/replenishments/{replenishment_id}/adopt")
async def adopt_replenishment_ep(
    request: Request, replenishment_id: UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    await _ensure_tables(request)
    actor = _actor_from_request(request)
    try:
        async with session.begin():
            work_order_no = await adopt_replenishment(
                session=session, replenishment_id=replenishment_id, actor=actor
            )
    except GuangtianRuleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"work_order_no": work_order_no}


# ============================== 老板问数 ==================================


@router.post("/ask")
async def ask(
    request: Request, payload: AskIn, session: AsyncSession = Depends(get_session)
) -> dict:
    await _ensure_tables(request)
    return await answer_inventory_question(session=session, question=payload.question)


# ============================== KPI / 日报 ===============================


def _today_range() -> tuple[datetime, datetime]:
    now = datetime.now(tz=timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


@router.get("/briefing/kpi")
async def briefing_kpi(
    request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await _ensure_tables(request)
    skus = (await session.execute(select(GuangtianSku).where(GuangtianSku.is_deleted.is_(False)))).scalars().all()
    gaps = await open_order_gap_by_sku(session)
    total = len(skus)
    low = sum(1 for s in skus if Decimal(s.safety_stock) > 0 and 0 < Decimal(s.last_balance) < Decimal(s.safety_stock))
    out_count = sum(1 for s in skus if Decimal(s.last_balance) <= 0)
    shortage_orders = (
        await session.execute(select(func.count()).select_from(GuangtianCustomerOrder).where(GuangtianCustomerOrder.is_deleted.is_(False)))
    ).scalar_one()
    start, now = _today_range()
    today_in = (
        await session.execute(
            select(func.count()).select_from(GuangtianStockMovement)
            .where(GuangtianStockMovement.op == GuangtianMovementOp.inbound)
            .where(GuangtianStockMovement.occurred_at >= start)
        )
    ).scalar_one()
    today_out = (
        await session.execute(
            select(func.count()).select_from(GuangtianStockMovement)
            .where(GuangtianStockMovement.op == GuangtianMovementOp.outbound)
            .where(GuangtianStockMovement.occurred_at >= start)
        )
    ).scalar_one()
    open_alerts = (
        await session.execute(select(func.count()).select_from(GuangtianStockAlert).where(GuangtianStockAlert.resolved_at.is_(None)))
    ).scalar_one()
    return {
        "sku_total": total,
        "low_stock_count": low,
        "out_of_stock_count": out_count,
        "shortage_order_count": shortage_orders,
        "skus_with_open_gap": len(gaps),
        "today_inbound": today_in,
        "today_outbound": today_out,
        "open_alerts": open_alerts,
    }


@router.get("/daily-report")
async def daily_report(
    request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await _ensure_tables(request)
    start, now = _today_range()
    movements = (
        await session.execute(
            select(GuangtianStockMovement).where(GuangtianStockMovement.occurred_at >= start)
        )
    ).scalars().all()
    in_count = sum(1 for m in movements if m.op == GuangtianMovementOp.inbound)
    out_count = sum(1 for m in movements if m.op == GuangtianMovementOp.outbound)
    net = sum((Decimal(m.quantity) for m in movements), Decimal("0"))
    open_alerts = (
        await session.execute(select(GuangtianStockAlert).where(GuangtianStockAlert.resolved_at.is_(None)))
    ).scalars().all()
    pending = (
        await session.execute(
            select(GuangtianReplenishment).where(GuangtianReplenishment.status == GuangtianReplenishStatus.suggested)
        )
    ).scalars().all()
    sku_map = await _sku_code_map(session)
    return {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "summary": f"今日入库 {in_count} 笔, 出库 {out_count} 笔, 净流入 {net}",
        "sections": [
            {"title": "今日流水", "items": [f"入库 {in_count} 笔 / 出库 {out_count} 笔 / 净 {net}"]},
            {
                "title": "风险与异常",
                "items": [
                    f"{sku_map[a.sku_id].code if a.sku_id in sku_map else a.sku_id} "
                    f"{a.level.value} 余量 {a.balance_at_trigger}/安全 {a.safety_stock_at_trigger}"
                    for a in open_alerts
                ] or ["无未解除预警"],
            },
            {
                "title": "AI 补产建议",
                "items": [
                    f"{sku_map[r.sku_id].code if r.sku_id in sku_map else r.sku_id} "
                    f"建议补 {r.suggest_qty} ({r.priority.value})"
                    for r in pending
                ] or ["无待处理建议"],
            },
        ],
    }
