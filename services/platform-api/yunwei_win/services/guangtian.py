"""光天 · AI 库存管家 — 业务规则 service 层.

与 ``confirm_writer`` 分工一致 (沿用锦泰范式): confirm 路径只写实体 (草稿单 +
ActionLog); 过账/扣减/预警/规则引擎在这里, 都包在调用方的 ``session.begin()``
单事务里. 并发幂等用原子条件 UPDATE (锦泰 round 9 P0-4 同款).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    GuangtianCustomerOrder,
    GuangtianCustomerOrderItem,
    GuangtianInboundType,
    GuangtianInboundVoucher,
    GuangtianMovementOp,
    GuangtianMovementRefType,
    GuangtianOutboundType,
    GuangtianOutboundVoucher,
    GuangtianReplenishment,
    GuangtianReplenishPriority,
    GuangtianReplenishStatus,
    GuangtianSku,
    GuangtianStockAlert,
    GuangtianStockAlertLevel,
    GuangtianStockMovement,
    GuangtianStockStatus,
    GuangtianVoucherStatus,
    NextActionType,
)

AI_ACTOR = "ai:guangtian-autodraft"


class GuangtianRuleError(ValueError):
    """业务规则违例 → API 层转 HTTP 400."""


# ============================== helpers ===================================


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _next_seq(session: AsyncSession, column, prefix: str) -> str:
    """生成 ``<prefix>-<YYYYMMDD>-<3 位>`` 单号 (per-tenant)."""
    today = date.today()
    stamp = today.strftime("%Y%m%d")
    like = f"{prefix}-{stamp}-%"
    stmt = select(column).where(column.like(like)).order_by(column.desc()).limit(1)
    latest = (await session.execute(stmt)).scalar_one_or_none()
    if latest is None:
        next_n = 1
    else:
        try:
            next_n = int(str(latest).rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_n = 1
    return f"{prefix}-{stamp}-{next_n:03d}"


async def _emit_action_log(
    session: AsyncSession,
    *,
    target_entity_id: uuid.UUID,
    actor: str,
    actor_kind: str,
    action_type: NextActionType,
    input_summary: str,
    output_summary: str,
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
        succeeded=True,
        created_by=actor,
        updated_by=actor,
    )
    session.add(log)
    await session.flush()
    return log.id


def derive_status(
    *,
    balance: Decimal,
    safety: Decimal,
    override: GuangtianStockStatus | None = None,
    has_open_gap: bool = False,
) -> GuangtianStockStatus:
    """SKU 状态派生 (前端 SkuCatalogPanel 同款逻辑).

    手工 ``anomaly`` 覆盖优先; 否则: 余量<=0 已缺货; 有未满足订单缺口 缺货风险;
    余量<安全线 低库存; 其余正常.
    """
    if override is GuangtianStockStatus.anomaly:
        return GuangtianStockStatus.anomaly
    if balance <= 0:
        return GuangtianStockStatus.out
    if has_open_gap:
        return GuangtianStockStatus.shortage_risk
    if safety > 0 and balance < safety:
        return GuangtianStockStatus.low
    return GuangtianStockStatus.normal


async def _resolve_open_alerts(
    session: AsyncSession, *, sku_id: uuid.UUID, balance: Decimal, safety: Decimal
) -> int:
    """库存回补到安全线之上 → 关闭该 SKU 未解除的预警. 返回关闭条数."""
    if not (safety <= 0 or balance >= safety):
        return 0
    res = await session.execute(
        update(GuangtianStockAlert)
        .where(GuangtianStockAlert.sku_id == sku_id)
        .where(GuangtianStockAlert.resolved_at.is_(None))
        .values(resolved_at=_now())
    )
    return res.rowcount or 0


async def _maybe_trigger_alert(
    session: AsyncSession,
    *,
    sku: GuangtianSku,
    balance: Decimal,
    actor: str,
    triggered_by_kind: str,
    triggered_by_id: uuid.UUID,
    note: str,
) -> uuid.UUID | None:
    safety = Decimal(sku.safety_stock)
    if safety <= 0 or balance >= safety:
        return None
    level = (
        GuangtianStockAlertLevel.out if balance <= 0 else GuangtianStockAlertLevel.low
    )
    alert = GuangtianStockAlert(
        sku_id=sku.id,
        level=level,
        balance_at_trigger=balance,
        safety_stock_at_trigger=safety,
        triggered_at=_now(),
        triggered_by_kind=triggered_by_kind,
        triggered_by_id=triggered_by_id,
        note=note,
        created_by=actor,
        updated_by=actor,
    )
    session.add(alert)
    await session.flush()
    await _emit_action_log(
        session,
        target_entity_id=alert.id,
        actor=AI_ACTOR,
        actor_kind="system",
        action_type=NextActionType.escalate,
        input_summary=(
            f"action=guangtian_stock_alert sku={sku.code} level={level.value} "
            f"balance={balance} safety={safety}"
        ),
        output_summary=f"alert_id={alert.id}",
    )
    return alert.id


# ============================== results ===================================


@dataclass
class MovementResult:
    sku_id: uuid.UUID
    voucher_id: uuid.UUID
    movement_id: uuid.UUID
    balance_before: Decimal
    balance_after: Decimal
    alert_id: uuid.UUID | None = None
    resolved_alerts: int = 0


@dataclass
class ReplenishResult:
    created: list[uuid.UUID] = field(default_factory=list)
    skipped_existing: int = 0


# ============================== inbound ===================================


async def record_inbound(
    *,
    session: AsyncSession,
    sku_id: uuid.UUID,
    quantity: Decimal,
    actor: str,
    unit: str | None = None,
    batch: str | None = None,
    location: str | None = None,
    inbound_type: GuangtianInboundType = GuangtianInboundType.production,
    source_ref: str | None = None,
    operator: str | None = None,
    confidence: int | None = None,
    voucher_no: str | None = None,
) -> MovementResult:
    """直接入库登记 (前端 addInbound): 建已过账入库单 + 写流水 + 加库存 + 解预警."""
    if quantity <= 0:
        raise GuangtianRuleError("入库数量必须 > 0")
    sku = await session.get(GuangtianSku, sku_id)
    if sku is None:
        raise GuangtianRuleError(f"SKU {sku_id} 不存在")

    qty = Decimal(quantity)
    before = Decimal(sku.last_balance)
    after = before + qty
    occurred = _now()
    vno = voucher_no or await _next_seq(session, GuangtianInboundVoucher.voucher_no, "IN")

    voucher = GuangtianInboundVoucher(
        voucher_no=vno,
        sku_id=sku.id,
        quantity=qty,
        unit=unit or sku.unit,
        batch=batch,
        location=location or sku.location,
        inbound_type=inbound_type,
        source_ref=source_ref,
        operator=operator or actor,
        occurred_at=occurred,
        status=GuangtianVoucherStatus.applied,
        confidence=confidence,
        human_verified=True,
        verified_by=actor,
        verified_at=occurred,
        created_by=actor,
        updated_by=actor,
    )
    session.add(voucher)
    await session.flush()

    movement = GuangtianStockMovement(
        sku_id=sku.id,
        op=GuangtianMovementOp.inbound,
        quantity=qty,
        balance_before=before,
        balance_after=after,
        reference_type=GuangtianMovementRefType.inbound_voucher,
        reference_id=voucher.id,
        reference_no=vno,
        operator=operator or actor,
        occurred_at=occurred,
        confidence=confidence,
        confirmed=True,
        note=source_ref,
        source_type="inbound_voucher",
        source_ref=vno,
        extracted_by="system",
        created_by=actor,
        updated_by=actor,
    )
    session.add(movement)
    sku.last_balance = after
    sku.last_in_at = occurred.date()
    await session.flush()

    resolved = await _resolve_open_alerts(
        session, sku_id=sku.id, balance=after, safety=Decimal(sku.safety_stock)
    )
    await _emit_action_log(
        session,
        target_entity_id=voucher.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.create_profile,
        input_summary=(
            f"action=guangtian_inbound sku={sku.code} qty=+{qty} "
            f"balance_after={after} ref={source_ref or vno}"
        ),
        output_summary=f"movement_id={movement.id} resolved_alerts={resolved}",
    )
    return MovementResult(
        sku_id=sku.id,
        voucher_id=voucher.id,
        movement_id=movement.id,
        balance_before=before,
        balance_after=after,
        resolved_alerts=resolved,
    )


# ============================== outbound ==================================


async def record_outbound(
    *,
    session: AsyncSession,
    sku_id: uuid.UUID,
    quantity: Decimal,
    actor: str,
    unit: str | None = None,
    outbound_type: GuangtianOutboundType = GuangtianOutboundType.sales,
    customer: str | None = None,
    order_no: str | None = None,
    operator: str | None = None,
    confidence: int | None = None,
    voucher_no: str | None = None,
) -> MovementResult:
    """直接出库登记 (前端 addOutbound): 校验库存→建已过账出库单 + 流水 + 扣库 + 触发预警.

    库存不足直接 raise (前端 addOutbound 返回 false 的后端对应), 不部分出库.
    """
    if quantity <= 0:
        raise GuangtianRuleError("出库数量必须 > 0")
    sku = await session.get(GuangtianSku, sku_id)
    if sku is None:
        raise GuangtianRuleError(f"SKU {sku_id} 不存在")

    qty = Decimal(quantity)
    before = Decimal(sku.last_balance)
    if before < qty:
        raise GuangtianRuleError(
            f"库存不足: {sku.code} 现有 {before}, 需出 {qty}"
        )
    after = before - qty
    occurred = _now()
    vno = voucher_no or await _next_seq(session, GuangtianOutboundVoucher.voucher_no, "OUT")

    voucher = GuangtianOutboundVoucher(
        voucher_no=vno,
        sku_id=sku.id,
        quantity=qty,
        unit=unit or sku.unit,
        outbound_type=outbound_type,
        customer=customer,
        order_no=order_no,
        operator=operator or actor,
        occurred_at=occurred,
        status=GuangtianVoucherStatus.applied,
        confidence=confidence,
        human_verified=True,
        verified_by=actor,
        verified_at=occurred,
        created_by=actor,
        updated_by=actor,
    )
    session.add(voucher)
    await session.flush()

    movement = GuangtianStockMovement(
        sku_id=sku.id,
        op=GuangtianMovementOp.outbound,
        quantity=-qty,
        balance_before=before,
        balance_after=after,
        reference_type=GuangtianMovementRefType.outbound_voucher,
        reference_id=voucher.id,
        reference_no=vno,
        operator=operator or actor,
        occurred_at=occurred,
        confidence=confidence,
        confirmed=True,
        note=f"{order_no or ''} {customer or ''}".strip() or None,
        source_type="outbound_voucher",
        source_ref=vno,
        extracted_by="system",
        created_by=actor,
        updated_by=actor,
    )
    session.add(movement)
    sku.last_balance = after
    sku.last_out_at = occurred.date()
    await session.flush()

    alert_id = await _maybe_trigger_alert(
        session,
        sku=sku,
        balance=after,
        actor=actor,
        triggered_by_kind="outbound_voucher",
        triggered_by_id=voucher.id,
        note=f"出库 {vno} 扣减后余量 {after} 跌破安全线 {sku.safety_stock}",
    )
    await _emit_action_log(
        session,
        target_entity_id=voucher.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.other,
        input_summary=(
            f"action=guangtian_outbound sku={sku.code} qty=-{qty} "
            f"balance_after={after} order={order_no or ''}"
        ),
        output_summary=f"movement_id={movement.id} alert_id={alert_id}",
    )
    return MovementResult(
        sku_id=sku.id,
        voucher_id=voucher.id,
        movement_id=movement.id,
        balance_before=before,
        balance_after=after,
        alert_id=alert_id,
    )


# ===================== apply draft voucher (AI-confirm path) ==============


async def apply_inbound_voucher(
    *, session: AsyncSession, voucher_id: uuid.UUID, actor: str
) -> MovementResult:
    """过账一张草稿入库单 (confirm_writer 写入的 draft → applied). 原子幂等."""
    transition = await session.execute(
        update(GuangtianInboundVoucher)
        .where(GuangtianInboundVoucher.id == voucher_id)
        .where(GuangtianInboundVoucher.status == GuangtianVoucherStatus.draft)
        .values(status=GuangtianVoucherStatus.applied, updated_by=actor)
    )
    if transition.rowcount == 0:
        v = await session.get(GuangtianInboundVoucher, voucher_id)
        if v is None:
            raise GuangtianRuleError(f"入库单 {voucher_id} 不存在")
        raise GuangtianRuleError(f"入库单 {v.voucher_no} 已过账或已取消 (status={v.status.value})")

    v = await session.get(GuangtianInboundVoucher, voucher_id)
    sku = await session.get(GuangtianSku, v.sku_id)
    if sku is None:
        raise GuangtianRuleError(f"SKU {v.sku_id} 不存在")
    qty = Decimal(v.quantity)
    before = Decimal(sku.last_balance)
    after = before + qty
    occurred = v.occurred_at or _now()
    movement = GuangtianStockMovement(
        sku_id=sku.id, op=GuangtianMovementOp.inbound, quantity=qty,
        balance_before=before, balance_after=after,
        reference_type=GuangtianMovementRefType.inbound_voucher, reference_id=v.id,
        reference_no=v.voucher_no, operator=v.operator or actor, occurred_at=occurred,
        confidence=v.confidence, confirmed=True, source_type="inbound_voucher",
        source_ref=v.voucher_no, extracted_by="system", created_by=actor, updated_by=actor,
    )
    session.add(movement)
    sku.last_balance = after
    sku.last_in_at = occurred.date()
    await session.flush()
    resolved = await _resolve_open_alerts(
        session, sku_id=sku.id, balance=after, safety=Decimal(sku.safety_stock)
    )
    await _emit_action_log(
        session, target_entity_id=v.id, actor=actor, actor_kind="user",
        action_type=NextActionType.create_profile,
        input_summary=f"action=guangtian_inbound_apply voucher={v.voucher_no} qty=+{qty} balance_after={after}",
        output_summary=f"movement_id={movement.id} resolved_alerts={resolved}",
    )
    return MovementResult(
        sku_id=sku.id, voucher_id=v.id, movement_id=movement.id,
        balance_before=before, balance_after=after, resolved_alerts=resolved,
    )


async def apply_outbound_voucher(
    *, session: AsyncSession, voucher_id: uuid.UUID, actor: str
) -> MovementResult:
    """过账一张草稿出库单. 原子幂等 + 库存校验."""
    transition = await session.execute(
        update(GuangtianOutboundVoucher)
        .where(GuangtianOutboundVoucher.id == voucher_id)
        .where(GuangtianOutboundVoucher.status == GuangtianVoucherStatus.draft)
        .values(status=GuangtianVoucherStatus.applied, updated_by=actor)
    )
    if transition.rowcount == 0:
        v = await session.get(GuangtianOutboundVoucher, voucher_id)
        if v is None:
            raise GuangtianRuleError(f"出库单 {voucher_id} 不存在")
        raise GuangtianRuleError(f"出库单 {v.voucher_no} 已过账或已取消 (status={v.status.value})")

    v = await session.get(GuangtianOutboundVoucher, voucher_id)
    sku = await session.get(GuangtianSku, v.sku_id)
    if sku is None:
        raise GuangtianRuleError(f"SKU {v.sku_id} 不存在")
    qty = Decimal(v.quantity)
    before = Decimal(sku.last_balance)
    if before < qty:
        # 回滚状态: 抛错让事务整体回滚 (status 改动一并撤销)
        raise GuangtianRuleError(f"库存不足: {sku.code} 现有 {before}, 需出 {qty}")
    after = before - qty
    occurred = v.occurred_at or _now()
    movement = GuangtianStockMovement(
        sku_id=sku.id, op=GuangtianMovementOp.outbound, quantity=-qty,
        balance_before=before, balance_after=after,
        reference_type=GuangtianMovementRefType.outbound_voucher, reference_id=v.id,
        reference_no=v.voucher_no, operator=v.operator or actor, occurred_at=occurred,
        confidence=v.confidence, confirmed=True, source_type="outbound_voucher",
        source_ref=v.voucher_no, extracted_by="system", created_by=actor, updated_by=actor,
    )
    session.add(movement)
    sku.last_balance = after
    sku.last_out_at = occurred.date()
    await session.flush()
    alert_id = await _maybe_trigger_alert(
        session, sku=sku, balance=after, actor=actor,
        triggered_by_kind="outbound_voucher", triggered_by_id=v.id,
        note=f"出库 {v.voucher_no} 扣减后余量 {after} 跌破安全线 {sku.safety_stock}",
    )
    await _emit_action_log(
        session, target_entity_id=v.id, actor=actor, actor_kind="user",
        action_type=NextActionType.other,
        input_summary=f"action=guangtian_outbound_apply voucher={v.voucher_no} qty=-{qty} balance_after={after}",
        output_summary=f"movement_id={movement.id} alert_id={alert_id}",
    )
    return MovementResult(
        sku_id=sku.id, voucher_id=v.id, movement_id=movement.id,
        balance_before=before, balance_after=after, alert_id=alert_id,
    )


# ===================== order gaps + shortage =============================


async def open_order_gap_by_sku(session: AsyncSession) -> dict[uuid.UUID, Decimal]:
    """聚合所有未删除订单的每 SKU 缺口 (needed - 现库存, 跨订单累加, ≥0)."""
    rows = (
        await session.execute(
            select(
                GuangtianCustomerOrderItem.sku_id,
                GuangtianCustomerOrderItem.needed,
            )
            .join(
                GuangtianCustomerOrder,
                GuangtianCustomerOrder.id == GuangtianCustomerOrderItem.order_id,
            )
            .where(GuangtianCustomerOrder.is_deleted.is_(False))
            .where(GuangtianCustomerOrderItem.is_deleted.is_(False))
            .where(GuangtianCustomerOrderItem.sku_id.is_not(None))
        )
    ).all()
    needed_by_sku: dict[uuid.UUID, Decimal] = {}
    for sku_id, needed in rows:
        needed_by_sku[sku_id] = needed_by_sku.get(sku_id, Decimal("0")) + Decimal(needed)
    gaps: dict[uuid.UUID, Decimal] = {}
    for sku_id, total_needed in needed_by_sku.items():
        sku = await session.get(GuangtianSku, sku_id)
        bal = Decimal(sku.last_balance) if sku else Decimal("0")
        gap = total_needed - bal
        if gap > 0:
            gaps[sku_id] = gap
    return gaps


# ===================== AI 补产建议 规则引擎 ================================


def _priority_for(balance: Decimal, safety: Decimal, gap: Decimal) -> GuangtianReplenishPriority:
    if balance <= 0 or gap > 0:
        return GuangtianReplenishPriority.high
    if safety > 0 and balance < safety * Decimal("0.5"):
        return GuangtianReplenishPriority.high
    if safety > 0 and balance < safety:
        return GuangtianReplenishPriority.medium
    return GuangtianReplenishPriority.low


async def generate_replenishment_suggestions(
    *, session: AsyncSession, actor: str
) -> ReplenishResult:
    """规则引擎: 扫低于安全线的 SKU + 未满足订单缺口, 生成补产建议.

    建议量 = max(安全线 - 现库存, 订单累计缺口). 已存在 ``suggested`` 建议的
    SKU 跳过 (避免重复刷). 全部 ``source=ai_autodraft`` + ``human_verified=False``.
    """
    result = ReplenishResult()
    gaps = await open_order_gap_by_sku(session)
    existing = set(
        (
            await session.execute(
                select(GuangtianReplenishment.sku_id).where(
                    GuangtianReplenishment.status == GuangtianReplenishStatus.suggested
                )
            )
        ).scalars().all()
    )
    skus = (await session.execute(select(GuangtianSku).where(GuangtianSku.is_deleted.is_(False)))).scalars().all()
    for sku in skus:
        bal = Decimal(sku.last_balance)
        safety = Decimal(sku.safety_stock)
        gap = gaps.get(sku.id, Decimal("0"))
        below_safety = safety > 0 and bal < safety
        if not below_safety and gap <= 0:
            continue
        if sku.id in existing:
            result.skipped_existing += 1
            continue
        suggest = max(safety - bal, gap, Decimal("0"))
        if suggest <= 0:
            continue
        reason_bits = []
        if bal <= 0:
            reason_bits.append("已缺货")
        elif below_safety:
            reason_bits.append(f"低于安全线({bal}/{safety})")
        if gap > 0:
            reason_bits.append(f"未满足订单缺口 {gap}")
        rep = GuangtianReplenishment(
            sku_id=sku.id,
            current_stock=bal,
            safety_stock=safety,
            suggest_qty=suggest,
            unit=sku.unit,
            priority=_priority_for(bal, safety, gap),
            reason="; ".join(reason_bits) or "补至安全线",
            status=GuangtianReplenishStatus.suggested,
            source="ai_autodraft",
            human_verified=False,
            extracted_by=AI_ACTOR,
            created_by=AI_ACTOR,
            updated_by=AI_ACTOR,
        )
        session.add(rep)
        await session.flush()
        await _emit_action_log(
            session,
            target_entity_id=rep.id,
            actor=AI_ACTOR,
            actor_kind="system",
            action_type=NextActionType.create_profile,
            input_summary=(
                f"action=guangtian_replenish_autodraft sku={sku.code} "
                f"suggest={suggest} priority={rep.priority.value}"
            ),
            output_summary=f"replenishment_id={rep.id}",
        )
        result.created.append(rep.id)
    return result


async def adopt_replenishment(
    *, session: AsyncSession, replenishment_id: uuid.UUID, actor: str
) -> uuid.UUID:
    """采纳一条补产建议 → 挂工艺组工单 + human_verified. 原子幂等."""
    work_order_no = await _next_seq(session, GuangtianReplenishment.work_order_no, "SC")
    transition = await session.execute(
        update(GuangtianReplenishment)
        .where(GuangtianReplenishment.id == replenishment_id)
        .where(GuangtianReplenishment.status == GuangtianReplenishStatus.suggested)
        .values(
            status=GuangtianReplenishStatus.adopted,
            work_order_no=work_order_no,
            human_verified=True,
            verified_by=actor,
            verified_at=_now(),
            updated_by=actor,
        )
    )
    if transition.rowcount == 0:
        rep = await session.get(GuangtianReplenishment, replenishment_id)
        if rep is None:
            raise GuangtianRuleError(f"补产建议 {replenishment_id} 不存在")
        raise GuangtianRuleError(f"补产建议已处理 (status={rep.status.value})")
    rep = await session.get(GuangtianReplenishment, replenishment_id)
    await _emit_action_log(
        session,
        target_entity_id=rep.id,
        actor=actor,
        actor_kind="user",
        action_type=NextActionType.follow_up,
        input_summary=f"action=guangtian_replenish_adopt id={rep.id} qty={rep.suggest_qty}",
        output_summary=f"work_order_no={work_order_no}",
    )
    return work_order_no
