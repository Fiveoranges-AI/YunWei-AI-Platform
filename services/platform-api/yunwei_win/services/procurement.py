"""锦泰 主线业务规则 — 出库 / 缺料预警 / AI auto-draft PR / 审批转 PO / 入库.

This service is the "what happens AFTER an entity is confirmed via
confirm_writer". The confirm path stays pure (writes the row + ActionLog);
the business rules here mutate stock, create alerts, auto-draft PRs,
flip statuses, generate POs, write receipts, and append payables.

Every public function is callable in two ways:

  * Directly from the FastAPI handler (which provides the AsyncSession
    bound to the caller's per-tenant DB and is responsible for the
    enclosing transaction).
  * From the E2E integration test (which uses an in-memory SQLite session).

The service is intentionally NOT async-locking; concurrent issues on
the same material would race ``Material.last_balance`` but the demo
workload is single-tenant single-operator so we accept that.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    GoodsReceipt,
    IssueVoucher,
    IssueVoucherStatus,
    Material,
    NextActionType,
    Payable,
    PayableStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionSource,
    PurchaseRequisitionStatus,
    StockAlert,
    StockAlertLevel,
    StockMovement,
    StockMovementDirection,
    StockMovementReferenceType,
    Supplier,
)


logger = logging.getLogger(__name__)


# Rule constants. Kept as module-level so tests can monkeypatch.
DEFAULT_REORDER_MULTIPLIER = Decimal("2.0")  # fallback: reorder qty = safety_stock × N − balance
USAGE_LOOKBACK_DAYS = 90                     # 近 3 月用量
USAGE_REORDER_COVER_MONTHS = Decimal("2.0")  # 备 2 个月用量
AI_AUTODRAFT_ACTOR = "system:rule-engine"


# ============================== exceptions ==============================


class ProcurementRuleError(ValueError):
    """Raised when a procurement rule precondition fails (bad status, etc.)."""


# ============================== result types ============================


@dataclass
class IssueAndDecrementResult:
    voucher_id: uuid.UUID
    material_id: uuid.UUID
    movement_id: uuid.UUID
    balance_after: Decimal
    alert_id: uuid.UUID | None = None
    auto_drafted_pr_id: uuid.UUID | None = None
    auto_drafted_pr_no: str | None = None


@dataclass
class ApprovePrResult:
    pr_id: uuid.UUID
    po_id: uuid.UUID
    po_no: str
    total_amount: Decimal


@dataclass
class ReceivePoResult:
    po_id: uuid.UUID
    receipt_id: uuid.UUID
    receipt_no: str
    payable_id: uuid.UUID
    payable_due_date: date
    stock_movements: list[uuid.UUID] = field(default_factory=list)
    resolved_alert_ids: list[uuid.UUID] = field(default_factory=list)


# ============================== helpers =================================


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _next_seq(session: AsyncSession, model, column, prefix: str) -> str:
    """Generate the next sequential number with format ``<prefix>-<6-digit>``.

    Numbering is per-tenant (we live inside one DB) and starts at
    000001 if no rows exist. The format matches the front-end demo seed
    data (PR-2026-017, PO-2026-009 etc.) closely enough for review.
    """
    today = date.today()
    year = today.year
    # find max existing for this year
    like = f"{prefix}-{year}-%"
    stmt = select(column).where(column.like(like)).order_by(column.desc()).limit(1)
    latest = (await session.execute(stmt)).scalar_one_or_none()
    if latest is None:
        next_n = 1
    else:
        try:
            next_n = int(str(latest).rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_n = 1
    return f"{prefix}-{year}-{next_n:03d}"


async def _emit_action_log(
    session: AsyncSession,
    *,
    target_entity_id: uuid.UUID,
    actor: str,
    actor_kind: str,
    action_type: NextActionType,
    input_summary: str,
    output_summary: str,
    succeeded: bool = True,
    error_message: str | None = None,
) -> uuid.UUID:
    log = ActionLog(
        target_entity_type=ActionTargetType.other,
        target_entity_id=target_entity_id,
        action_type=action_type,
        actor=actor,
        actor_kind=actor_kind,
        input_summary=input_summary,
        output_summary=output_summary,
        executed_at=_now(),
        succeeded=succeeded,
        error_message=error_message,
        created_by=actor,
        updated_by=actor,
    )
    session.add(log)
    await session.flush()
    return log.id


def _compute_reorder_qty(
    *, safety_stock: Decimal, balance: Decimal,
    multiplier: Decimal = DEFAULT_REORDER_MULTIPLIER,
) -> Decimal:
    """fallback target = safety_stock × multiplier; reorder = target - balance, ≥0."""
    target = safety_stock * multiplier
    reorder = target - balance
    return reorder if reorder > 0 else Decimal("0")


@dataclass
class ReorderRecommendation:
    qty: Decimal
    source: str  # "usage_3mo_avg" | "safety_fallback"
    monthly_avg_usage: Decimal | None = None
    months_of_history: Decimal | None = None
    note: str = ""


async def _compute_reorder_recommendation(
    *,
    session: AsyncSession,
    material: Material,
    balance: Decimal,
    lookback_days: int = USAGE_LOOKBACK_DAYS,
    cover_months: Decimal = USAGE_REORDER_COVER_MONTHS,
) -> ReorderRecommendation:
    """Try "近 3 月平均月用量 × cover_months";落到 safety_stock × N − balance."""
    cutoff = _now() - timedelta(days=lookback_days)
    total_out = (
        await session.execute(
            select(func.sum(StockMovement.quantity)).where(
                StockMovement.material_id == material.id,
                StockMovement.direction == StockMovementDirection.out,
                StockMovement.occurred_at >= cutoff,
            )
        )
    ).scalar_one() or Decimal("0")
    total_out = Decimal(total_out)
    months = Decimal(lookback_days) / Decimal(30)
    if total_out > 0 and months > 0:
        monthly_avg = total_out / months
        target = monthly_avg * cover_months
        reorder = target - balance
        if reorder > 0:
            return ReorderRecommendation(
                qty=reorder.quantize(Decimal("0.0001")),
                source="usage_3mo_avg",
                monthly_avg_usage=monthly_avg.quantize(Decimal("0.0001")),
                months_of_history=months,
                note=(
                    f"按近 {lookback_days} 天累计用量 {total_out} ÷ {months} 月 = "
                    f"{monthly_avg.quantize(Decimal('0.01'))}/月,备 {cover_months} 个月扣 balance"
                ),
            )
    # fallback
    qty = _compute_reorder_qty(
        safety_stock=Decimal(material.safety_stock), balance=balance,
    )
    return ReorderRecommendation(
        qty=qty,
        source="safety_fallback",
        note=f"无 {lookback_days} 天用量历史 → 按 safety_stock × {DEFAULT_REORDER_MULTIPLIER} − balance 兜底",
    )


async def _last_supplier_for_material(
    *, session: AsyncSession, material_id,
) -> Supplier | None:
    """Find the supplier of the most recent received PO containing this material."""
    stmt = (
        select(Supplier)
        .select_from(PurchaseOrderItem)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(
            PurchaseOrderItem.material_id == material_id,
            PurchaseOrder.received_at.is_not(None),
        )
        .order_by(PurchaseOrder.received_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _last_unit_price_for_material(
    *, session: AsyncSession, material_id, supplier_id=None,
) -> Decimal | None:
    """Look up the last unit_price on a PO item for this material (optionally same supplier)."""
    stmt = (
        select(PurchaseOrderItem.unit_price)
        .select_from(PurchaseOrderItem)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id)
        .where(
            PurchaseOrderItem.material_id == material_id,
            PurchaseOrderItem.unit_price.is_not(None),
        )
        .order_by(PurchaseOrder.created_at.desc())
        .limit(1)
    )
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    return (await session.execute(stmt)).scalar_one_or_none()


# ============================== rule: confirm-and-issue =================


async def confirm_and_issue(
    *,
    voucher_id: uuid.UUID,
    actor: str,
    session: AsyncSession,
    auto_draft_when_low: bool = True,
) -> IssueAndDecrementResult:
    """领料单 → 扣库存 (+ 缺料预警 + AI auto-draft PR).

    Idempotency: if voucher.status is already ``confirmed`` we raise; callers
    should treat that as a duplicate-click 409. We do NOT silently no-op so
    the audit log stays honest about what was attempted.
    """
    # Atomic status transition: only one concurrent caller wins. Without
    # this, two simultaneous confirm-and-issue calls on the same voucher
    # both pass the status check, both decrement Material.last_balance,
    # and we write duplicate StockMovement rows. Round 9 P0-4 fix.
    transition = await session.execute(
        update(IssueVoucher)
        .where(IssueVoucher.id == voucher_id)
        .where(IssueVoucher.status == IssueVoucherStatus.draft)
        .values(status=IssueVoucherStatus.confirmed, updated_by=actor)
    )
    if transition.rowcount == 0:
        voucher = await session.get(IssueVoucher, voucher_id)
        if voucher is None:
            raise ProcurementRuleError(f"issue voucher {voucher_id} not found")
        if voucher.status == IssueVoucherStatus.confirmed:
            raise ProcurementRuleError(
                f"issue voucher {voucher.voucher_no} already confirmed"
            )
        if voucher.status == IssueVoucherStatus.cancelled:
            raise ProcurementRuleError(
                f"issue voucher {voucher.voucher_no} is cancelled"
            )
        raise ProcurementRuleError(
            f"issue voucher {voucher.voucher_no} unexpected status "
            f"{voucher.status.value}"
        )

    voucher = await session.get(IssueVoucher, voucher_id)
    material = await session.get(Material, voucher.material_id)
    if material is None:
        raise ProcurementRuleError(
            f"material {voucher.material_id} not found for voucher "
            f"{voucher.voucher_no}"
        )

    qty = Decimal(voucher.quantity)
    new_balance = Decimal(material.last_balance) - qty
    occurred_at = _now()

    movement = StockMovement(
        material_id=material.id,
        direction=StockMovementDirection.out,
        quantity=qty,
        balance_after=new_balance,
        reference_type=StockMovementReferenceType.issue_voucher,
        reference_id=voucher.id,
        occurred_at=occurred_at,
        source_type="issue_voucher",
        source_ref=voucher.voucher_no,
        extracted_by="system",
        created_by=actor,
        updated_by=actor,
    )
    session.add(movement)

    material.last_balance = new_balance
    # voucher.status was already set to `confirmed` by the atomic
    # conditional UPDATE above (P0-4 race guard).
    await session.flush()

    result = IssueAndDecrementResult(
        voucher_id=voucher.id,
        material_id=material.id,
        movement_id=movement.id,
        balance_after=new_balance,
    )

    log_summary = (
        f"voucher={voucher.voucher_no} material={material.code} "
        f"qty=-{qty} balance_after={new_balance}"
    )
    await _emit_action_log(
        session,
        target_entity_id=voucher.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.other,
        input_summary=f"action=issue_voucher_confirm {log_summary}",
        output_summary=f"stock_movement_id={movement.id}",
    )

    safety = Decimal(material.safety_stock)
    if safety > 0 and new_balance < safety:
        level = StockAlertLevel.out if new_balance <= 0 else StockAlertLevel.low
        alert = StockAlert(
            material_id=material.id,
            level=level,
            balance_at_trigger=new_balance,
            safety_stock_at_trigger=safety,
            triggered_at=occurred_at,
            triggered_by_kind="issue_voucher",
            triggered_by_id=voucher.id,
            note=(
                f"领料 {voucher.voucher_no} 扣减后余量 {new_balance} 跌破安全线 {safety}"
            ),
            created_by=actor,
            updated_by=actor,
        )
        session.add(alert)
        await session.flush()
        result.alert_id = alert.id
        await _emit_action_log(
            session,
            target_entity_id=alert.id,
            actor=AI_AUTODRAFT_ACTOR,
            actor_kind="system",
            action_type=NextActionType.escalate,
            input_summary=(
                f"action=stock_alert_trigger material={material.code} "
                f"level={level.value} balance={new_balance} safety={safety}"
            ),
            output_summary=f"stock_alert_id={alert.id}",
        )

        if auto_draft_when_low:
            pr = await _ai_autodraft_requisition(
                session=session,
                material=material,
                triggering_voucher=voucher,
                balance=new_balance,
                related_alert=alert,
            )
            if pr is not None:
                result.auto_drafted_pr_id = pr.id
                result.auto_drafted_pr_no = pr.pr_no

    return result


async def _ai_autodraft_requisition(
    *,
    session: AsyncSession,
    material: Material,
    triggering_voucher: IssueVoucher,
    balance: Decimal,
    related_alert: StockAlert,
) -> PurchaseRequisition | None:
    """AI 规则版 auto-draft (升级):
      1. 优先按近 3 月平均月用量 × 2 推荐 qty (fallback 到 safety×2 − balance)
      2. 按"该物料最近成交 supplier"自动绑(若有)
      3. 按"该物料最近 unit_price"回填 (若有)
    真正调 LLM 留给后续 task.
    """
    rec = await _compute_reorder_recommendation(
        session=session, material=material, balance=balance,
    )
    if rec.qty <= 0:
        return None

    supplier = await _last_supplier_for_material(
        session=session, material_id=material.id,
    )
    supplier_id = supplier.id if supplier else None
    unit_price = await _last_unit_price_for_material(
        session=session, material_id=material.id, supplier_id=supplier_id,
    )
    if unit_price is None:
        unit_price = await _last_unit_price_for_material(
            session=session, material_id=material.id,
        )

    pr_no = await _next_seq(
        session, PurchaseRequisition, PurchaseRequisition.pr_no, "PR",
    )
    today = date.today()
    source_note_parts = [
        f"AI 检测到 {material.name} 跌破安全线 {material.safety_stock}",
        f"(余量 {balance})",
        f"· qty 来源: {rec.source}",
    ]
    if supplier is not None:
        source_note_parts.append(f"· supplier 自动绑: {supplier.name} (按最近成交)")
    if unit_price is not None:
        source_note_parts.append(f"· unit_price 回填: ¥{unit_price} (按历史)")
    pr = PurchaseRequisition(
        pr_no=pr_no,
        dept=triggering_voucher.workshop,
        applicant=triggering_voucher.applicant,
        apply_date=today,
        supplier_id=supplier_id,
        status=PurchaseRequisitionStatus.pending_approval,
        source=PurchaseRequisitionSource.ai_autodraft,
        source_note=" ".join(source_note_parts),
        # AI auto-draft — human has NOT verified yet (approve flips this).
        human_verified=False,
        source_type="ai_autodraft",
        source_ref=triggering_voucher.voucher_no,
        extracted_by="llm:rule-engine",
        confidence=Decimal("0.80"),
        created_by=AI_AUTODRAFT_ACTOR,
        updated_by=AI_AUTODRAFT_ACTOR,
    )
    session.add(pr)
    await session.flush()

    item_amount = (
        (Decimal(unit_price) * rec.qty) if unit_price is not None else None
    )
    pr_item = PurchaseRequisitionItem(
        pr_id=pr.id,
        material_id=material.id,
        quantity=rec.qty,
        unit=material.unit,
        arrive_date=today + timedelta(days=10),
        unit_price=Decimal(unit_price) if unit_price is not None else None,
        amount=item_amount,
        note=rec.note,
        human_verified=False,
        source_type="ai_autodraft",
        extracted_by="llm:rule-engine",
        created_by=AI_AUTODRAFT_ACTOR,
        updated_by=AI_AUTODRAFT_ACTOR,
    )
    session.add(pr_item)

    related_alert.related_pr_id = pr.id
    await session.flush()

    await _emit_action_log(
        session,
        target_entity_id=pr.id,
        actor=AI_AUTODRAFT_ACTOR,
        actor_kind="system",
        action_type=NextActionType.other,
        input_summary=(
            f"action=ai_autodraft_pr material={material.code} "
            f"reorder_qty={rec.qty} qty_source={rec.source} "
            f"supplier={supplier.name if supplier else 'unbound'} "
            f"unit_price={unit_price if unit_price is not None else 'unknown'} "
            f"triggered_by_voucher={triggering_voucher.voucher_no} "
            f"triggered_by_alert={related_alert.id}"
        ),
        output_summary=f"purchase_requisition_id={pr.id} pr_no={pr.pr_no}",
    )
    return pr


# ============================== rule: approve PR ========================


async def approve_requisition(
    *,
    pr_id: uuid.UUID,
    actor: str,
    session: AsyncSession,
    supplier_id: uuid.UUID | None = None,
    unit_prices: dict[uuid.UUID, Decimal] | None = None,
) -> ApprovePrResult:
    """张主管批准 PR → 自动生成 PO.

    ``supplier_id`` 可选: 如 PR 本身没绑 supplier (AI auto-draft 没填),必须在
    approve 时传入。``unit_prices`` 可选: 按 PR item id 覆盖单价 (AI auto-draft
    没填价时由审批人补)。
    """
    # Atomic status transition: prevent concurrent approve_requisition
    # from creating duplicate POs for the same PR. Round 9 P0-4 fix.
    transition = await session.execute(
        update(PurchaseRequisition)
        .where(PurchaseRequisition.id == pr_id)
        .where(PurchaseRequisition.status == PurchaseRequisitionStatus.pending_approval)
        .values(
            status=PurchaseRequisitionStatus.approved,
            updated_by=actor,
        )
    )
    if transition.rowcount == 0:
        pr = await session.get(PurchaseRequisition, pr_id)
        if pr is None:
            raise ProcurementRuleError(f"requisition {pr_id} not found")
        raise ProcurementRuleError(
            f"requisition {pr.pr_no} is in status {pr.status.value}, "
            "expected pending_approval"
        )

    pr = await session.get(PurchaseRequisition, pr_id)

    final_supplier_id = supplier_id or pr.supplier_id
    if final_supplier_id is None:
        raise ProcurementRuleError(
            f"requisition {pr.pr_no} has no supplier; supplier_id required"
        )
    supplier = await session.get(Supplier, final_supplier_id)
    if supplier is None:
        raise ProcurementRuleError(f"supplier {final_supplier_id} not found")

    items_stmt = select(PurchaseRequisitionItem).where(
        PurchaseRequisitionItem.pr_id == pr.id
    )
    pr_items = (await session.execute(items_stmt)).scalars().all()
    if not pr_items:
        raise ProcurementRuleError(f"requisition {pr.pr_no} has no items")

    po_no = await _next_seq(session, PurchaseOrder, PurchaseOrder.po_no, "PO")
    now = _now()
    today = date.today()

    # compute total + materialize per-item prices
    po_total = Decimal("0")
    resolved_items: list[tuple[PurchaseRequisitionItem, Decimal | None, Decimal | None]] = []
    for item in pr_items:
        override = (unit_prices or {}).get(item.id)
        unit_price = override if override is not None else item.unit_price
        if unit_price is None:
            amount = None
        else:
            amount = Decimal(unit_price) * Decimal(item.quantity)
            po_total += amount
        resolved_items.append((item, unit_price, amount))

    po = PurchaseOrder(
        po_no=po_no,
        supplier_id=supplier.id,
        from_pr_id=pr.id,
        status=PurchaseOrderStatus.open,
        delivery_date=max(
            (i.arrive_date for i in pr_items if i.arrive_date is not None),
            default=None,
        ),
        total_amount=po_total,
        currency="CNY",
        human_verified=True,
        verified_by=actor,
        verified_at=now,
        source_type="approval",
        source_ref=pr.pr_no,
        extracted_by="user",
        created_by=actor,
        updated_by=actor,
    )
    session.add(po)
    await session.flush()

    for item, unit_price, amount in resolved_items:
        session.add(
            PurchaseOrderItem(
                po_id=po.id,
                material_id=item.material_id,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=unit_price,
                amount=amount,
                human_verified=True,
                verified_by=actor,
                verified_at=now,
                source_type="approval",
                source_ref=pr.pr_no,
                extracted_by="user",
                created_by=actor,
                updated_by=actor,
            )
        )

    pr.status = PurchaseRequisitionStatus.closed_to_po
    pr.approver = actor
    pr.approved_at = now
    pr.human_verified = True
    pr.verified_by = actor
    pr.verified_at = now
    pr.po_ref = po.po_no
    pr.supplier_id = supplier.id
    pr.updated_by = actor

    await session.flush()

    await _emit_action_log(
        session,
        target_entity_id=pr.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.other,
        input_summary=(
            f"action=approve_requisition pr={pr.pr_no} supplier={supplier.name} "
            f"items={len(pr_items)} total={po_total}"
        ),
        output_summary=f"purchase_order_id={po.id} po_no={po.po_no}",
    )

    return ApprovePrResult(
        pr_id=pr.id, po_id=po.id, po_no=po.po_no, total_amount=po_total,
    )


async def reject_requisition(
    *,
    pr_id: uuid.UUID,
    actor: str,
    reason: str | None,
    session: AsyncSession,
) -> uuid.UUID:
    # Atomic status transition: prevent a concurrent reject (or a reject
    # racing an approve) from both passing a read-then-check and double-writing
    # the decision. Mirrors approve_requisition (Round 9 P0-4). The reason /
    # approver / timestamp are set inside the same conditional UPDATE.
    transition = await session.execute(
        update(PurchaseRequisition)
        .where(PurchaseRequisition.id == pr_id)
        .where(PurchaseRequisition.status == PurchaseRequisitionStatus.pending_approval)
        .values(
            status=PurchaseRequisitionStatus.rejected,
            rejected_reason=reason,
            approver=actor,
            approved_at=_now(),
            updated_by=actor,
        )
    )
    if transition.rowcount == 0:
        pr = await session.get(PurchaseRequisition, pr_id)
        if pr is None:
            raise ProcurementRuleError(f"requisition {pr_id} not found")
        raise ProcurementRuleError(
            f"requisition {pr.pr_no} is in status {pr.status.value}, "
            "expected pending_approval"
        )

    pr = await session.get(PurchaseRequisition, pr_id)
    await _emit_action_log(
        session,
        target_entity_id=pr.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.other,
        input_summary=f"action=reject_requisition pr={pr.pr_no} reason={reason!r}",
        output_summary=f"pr_status=rejected",
    )
    return pr.id


# ============================== rule: receive PO ========================


async def receive_purchase_order(
    *,
    po_id: uuid.UUID,
    warehouse: str,
    actor: str,
    session: AsyncSession,
    receipt_no: str | None = None,
    invoice_date: date | None = None,
) -> ReceivePoResult:
    """PO 入库 → 写 GoodsReceipt + StockMovement+ + 应付账款.

    Stock movements are created one per PO item (which is one per material).
    Resolves any open StockAlert for the same materials if balance recovers
    above safety_stock.
    """
    # Atomic status transition: prevent concurrent receive_purchase_order
    # from creating duplicate goods receipts / payables. Round 9 P0-4 fix.
    transition = await session.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == po_id)
        .where(PurchaseOrder.status.in_(
            (PurchaseOrderStatus.open, PurchaseOrderStatus.in_transit)
        ))
        .values(status=PurchaseOrderStatus.closed, updated_by=actor)
    )
    if transition.rowcount == 0:
        po = await session.get(PurchaseOrder, po_id)
        if po is None:
            raise ProcurementRuleError(f"purchase order {po_id} not found")
        raise ProcurementRuleError(
            f"purchase order {po.po_no} is in status {po.status.value}, "
            "cannot receive"
        )

    po = await session.get(PurchaseOrder, po_id)
    supplier = await session.get(Supplier, po.supplier_id)
    if supplier is None:
        raise ProcurementRuleError(f"supplier {po.supplier_id} not found")

    items_stmt = select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id)
    po_items = (await session.execute(items_stmt)).scalars().all()
    if not po_items:
        raise ProcurementRuleError(f"purchase order {po.po_no} has no items")

    now = _now()
    today = invoice_date or date.today()

    if receipt_no is None:
        receipt_no = await _next_seq(
            session, GoodsReceipt, GoodsReceipt.receipt_no, "GR",
        )

    receipt = GoodsReceipt(
        receipt_no=receipt_no,
        po_id=po.id,
        warehouse=warehouse,
        received_at=now,
        received_by=actor,
        human_verified=True,
        verified_by=actor,
        verified_at=now,
        source_type="receive",
        source_ref=po.po_no,
        extracted_by="user",
        created_by=actor,
        updated_by=actor,
    )
    session.add(receipt)
    await session.flush()

    movement_ids: list[uuid.UUID] = []
    resolved_alerts: list[uuid.UUID] = []
    for item in po_items:
        material = await session.get(Material, item.material_id)
        if material is None:
            raise ProcurementRuleError(
                f"material {item.material_id} on PO {po.po_no} not found"
            )
        old_balance = Decimal(material.last_balance)
        old_cost = Decimal(material.last_unit_cost)
        new_balance = old_balance + Decimal(item.quantity)
        # 加权平均成本 (WAC):receipt 携带 unit_price 才参与;无价时不影响 last_unit_cost.
        if item.unit_price is not None and new_balance > 0:
            received_cost = Decimal(item.unit_price)
            material.last_unit_cost = (
                (old_balance * old_cost + Decimal(item.quantity) * received_cost)
                / new_balance
            ).quantize(Decimal("0.0001"))
        movement = StockMovement(
            material_id=material.id,
            direction=StockMovementDirection.in_,
            quantity=Decimal(item.quantity),
            balance_after=new_balance,
            reference_type=StockMovementReferenceType.goods_receipt,
            reference_id=receipt.id,
            occurred_at=now,
            source_type="goods_receipt",
            source_ref=receipt.receipt_no,
            extracted_by="system",
            created_by=actor,
            updated_by=actor,
        )
        session.add(movement)
        material.last_balance = new_balance
        await session.flush()
        movement_ids.append(movement.id)

        safety = Decimal(material.safety_stock)
        if safety > 0 and new_balance >= safety:
            stmt = select(StockAlert).where(
                StockAlert.material_id == material.id,
                StockAlert.resolved_at.is_(None),
            )
            open_alerts = (await session.execute(stmt)).scalars().all()
            for alert in open_alerts:
                alert.resolved_at = now
                resolved_alerts.append(alert.id)
            await session.flush()

    payable = Payable(
        supplier_id=supplier.id,
        source_type="po",
        source_ref=po.po_no,
        source_po_id=po.id,
        amount=Decimal(po.total_amount),
        paid_amount=Decimal("0"),
        currency=po.currency,
        invoice_date=today,
        due_date=today + timedelta(days=supplier.payment_terms_days),
        status=PayableStatus.pending,
        human_verified=True,
        verified_by=actor,
        verified_at=now,
        extracted_by="user",
        created_by=actor,
        updated_by=actor,
    )
    session.add(payable)

    # po.status was already set to `closed` by the atomic conditional UPDATE
    # at the top of this function (P0-4 race guard).
    po.warehouse = warehouse
    po.received_at = now
    po.updated_by = actor
    await session.flush()

    await _emit_action_log(
        session,
        target_entity_id=po.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.other,
        input_summary=(
            f"action=receive_po po={po.po_no} warehouse={warehouse} "
            f"items={len(po_items)} amount={po.total_amount}"
        ),
        output_summary=(
            f"receipt_id={receipt.id} payable_id={payable.id} "
            f"stock_movements={len(movement_ids)} "
            f"resolved_alerts={len(resolved_alerts)}"
        ),
    )

    return ReceivePoResult(
        po_id=po.id,
        receipt_id=receipt.id,
        receipt_no=receipt.receipt_no,
        payable_id=payable.id,
        payable_due_date=payable.due_date,
        stock_movements=movement_ids,
        resolved_alert_ids=resolved_alerts,
    )
