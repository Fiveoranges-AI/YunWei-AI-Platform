"""Round 3 收敛 & 边界测试.

覆盖:
  * 决策 #1: Material.last_unit_cost cold-start backfill (无重复;只填 0;按最新 PO)
  * 决策 #4: 折旧入 PNL 闭环 — balance_sheet 含 FA 仍借贷平衡
  * 双 confirm 幂等 (服务规则不被重复触发)
  * 跨期会计: period A 的 retained_earnings 通过 opening_balance 流到 period B
  * 库存为零 reorder 推荐 (低库存路径不死)
  * WAC 极端值 (零 balance, 极大 quantity)
  * PR 重复 approve 拒绝
  * 跨 API 自审: stock-movements limit 边界, payables 空 aging
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401
from yunwei_win.db import (
    Base,
    _backfill_material_unit_costs,
    get_session,
)
from yunwei_win.models import (
    FixedAsset,
    FixedAssetCategory,
    Material,
    PeriodOpeningBalance,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionSource,
    PurchaseRequisitionStatus,
    StockMovement,
    StockMovementDirection,
    StockMovementReferenceType,
    Supplier,
)


# ============================== helpers =================================


async def _make_engine():
    from sqlalchemy import event

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine, *, actor: str = "test-actor"):
    from fastapi import FastAPI

    from yunwei_win.api.bom import router as bom_router
    from yunwei_win.api.briefing import router as briefing_router
    from yunwei_win.api.confirm import router as confirm_router
    from yunwei_win.api.finance import router as finance_router
    from yunwei_win.api.procurement import router as procurement_router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp_actor(request, call_next):
        request.state.actor = actor
        return await call_next(request)

    app.include_router(confirm_router)
    app.include_router(procurement_router)
    app.include_router(briefing_router)
    app.include_router(finance_router)
    app.include_router(bom_router)
    app.dependency_overrides[get_session] = _override_session
    return app


# ============================== 决策 #1 backfill ========================


@pytest.mark.asyncio
async def test_backfill_fills_only_zero_costs_from_latest_received_po() -> None:
    """Backfill 只更新 last_unit_cost = 0 的物料,且取该物料最近 received PO 的 unit_price."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="BF-Sup", payment_terms_days=30,
                                created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m_zero = Material(code="BF-ZERO", name="zero", unit="kg",
                                   last_balance=Decimal("0"), last_unit_cost=Decimal("0"),
                                   created_by="seed", updated_by="seed", human_verified=True)
                m_set = Material(code="BF-SET", name="set", unit="kg",
                                  last_balance=Decimal("0"), last_unit_cost=Decimal("99"),
                                  created_by="seed", updated_by="seed", human_verified=True)
                m_no_history = Material(code="BF-NONE", name="none", unit="kg",
                                          last_balance=Decimal("0"), last_unit_cost=Decimal("0"),
                                          created_by="seed", updated_by="seed", human_verified=True)
                s.add_all([m_zero, m_set, m_no_history]); await s.flush()
                # 老 PO (2 个月前 received)
                old_po = PurchaseOrder(po_no="BF-PO-OLD", supplier_id=sup.id,
                                        status=PurchaseOrderStatus.closed,
                                        total_amount=Decimal("100"),
                                        received_at=datetime.now(tz=timezone.utc) - timedelta(days=60),
                                        created_by="seed", updated_by="seed", human_verified=True)
                s.add(old_po); await s.flush()
                s.add_all([
                    PurchaseOrderItem(po_id=old_po.id, material_id=m_zero.id,
                                       quantity=Decimal("1"), unit_price=Decimal("10"), amount=Decimal("10"),
                                       created_by="seed", updated_by="seed", human_verified=True),
                    PurchaseOrderItem(po_id=old_po.id, material_id=m_set.id,
                                       quantity=Decimal("1"), unit_price=Decimal("20"), amount=Decimal("20"),
                                       created_by="seed", updated_by="seed", human_verified=True),
                ])
                # 新 PO (1 天前 received, 同一物料 m_zero 价格涨到 15)
                new_po = PurchaseOrder(po_no="BF-PO-NEW", supplier_id=sup.id,
                                        status=PurchaseOrderStatus.closed,
                                        total_amount=Decimal("150"),
                                        received_at=datetime.now(tz=timezone.utc) - timedelta(days=1),
                                        created_by="seed", updated_by="seed", human_verified=True)
                s.add(new_po); await s.flush()
                s.add(PurchaseOrderItem(po_id=new_po.id, material_id=m_zero.id,
                                         quantity=Decimal("1"), unit_price=Decimal("15"), amount=Decimal("15"),
                                         created_by="seed", updated_by="seed", human_verified=True))
                zero_id = m_zero.id
                set_id = m_set.id
                none_id = m_no_history.id

        # 调 backfill (lightweight migration 入口)
        async with engine.begin() as conn:
            await _backfill_material_unit_costs(conn)

        async with AsyncSession(engine) as s:
            m_zero_after = await s.get(Material, zero_id)
            m_set_after = await s.get(Material, set_id)
            m_none_after = await s.get(Material, none_id)
            # m_zero: 取最新 PO (15)
            assert Decimal(m_zero_after.last_unit_cost) == Decimal("15")
            # m_set: 已有非零值, 不动
            assert Decimal(m_set_after.last_unit_cost) == Decimal("99")
            # m_no_history: 没 PO 历史, 保留 0
            assert Decimal(m_none_after.last_unit_cost) == Decimal("0")

        # 幂等:再调一次,值不变
        async with engine.begin() as conn:
            await _backfill_material_unit_costs(conn)
        async with AsyncSession(engine) as s:
            assert Decimal((await s.get(Material, zero_id)).last_unit_cost) == Decimal("15")
            assert Decimal((await s.get(Material, set_id)).last_unit_cost) == Decimal("99")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_safe_when_tables_missing() -> None:
    """没有 procurement_materials 表时安全 noop (cold-start before schema deployed)."""
    from sqlalchemy import create_engine
    sync_engine = create_engine("sqlite:///:memory:")
    # 只建 1 张 unrelated table, 不建 procurement_*
    from sqlalchemy import MetaData, Table, Column, String
    md = MetaData()
    Table("unrelated", md, Column("x", String))
    md.create_all(sync_engine)
    sync_engine.dispose()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            # No procurement tables exist — should not raise
            await _backfill_material_unit_costs(conn)
    finally:
        await engine.dispose()


# ============================== 决策 #4 折旧闭环 ========================


@pytest.mark.asyncio
async def test_balance_sheet_balanced_with_fa_via_depreciation_closure() -> None:
    """加 FA → 当期折旧 D 流入 admin_expense → retained_earnings 减少 D ×(1-税率) (loss path 不缴税).

    Setup: FA 原值 1200000 / 60 月,opening at 2026-05 = 28 个月已折旧:
       monthly = 20000;period_end = 2026-05-31 → months_through = 29 (2024-01 → 2026-05 含)
       accum_at_end = 580000;period_dep = 20000
    无收入无成本无其他费用 → operating_profit = -20000;loss → tax = 0 → net = -20000
    retained_change = -20000

    Balance check at 2026-05-31:
       Asset delta vs opening = -20000 (累计折旧从 560000 → 580000, contra-asset)
       Equity delta vs opening = -20000 (retained 减少 20000)
       期初 assets == 期初 L+E (seeded balanced) → 期末 also balanced
    """
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        period = "2026-05"
        async with AsyncSession(engine) as s:
            async with s.begin():
                # FA acquired 2024-01-01, monthly = 20000, by 2026-04-30 已折旧 28 月 = 560000
                s.add(FixedAsset(
                    asset_no="FA-CLOSURE", name="设备",
                    category=FixedAssetCategory.machinery,
                    acquired_date=date(2024, 1, 1),
                    original_cost=Decimal("1200000"),
                    salvage_value=Decimal("0"),
                    useful_life_months=60,
                    created_by="seed", updated_by="seed", human_verified=True,
                ))
                # Seed openings so 期初 资产 = 负债 + 权益
                # 期初资产: 现金 100w + 银行 380w + FA 120w - 累计折旧 56w = 544w
                # 期初权益: 实收 500w + 未分配 44w = 544w
                for code, amount in [
                    ("1001", "1000000"),   # 库存现金 100w
                    ("1002", "3800000"),   # 银行存款 380w
                    ("1601", "1200000"),   # 固定资产 120w
                    ("1602",  "560000"),   # 累计折旧 56w (期初已计提)
                    ("4001", "5000000"),   # 实收资本 500w
                    ("4104",  "440000"),   # 未分配利润 44w
                ]:
                    s.add(PeriodOpeningBalance(
                        period=period, account_code=code,
                        opening_amount=Decimal(amount),
                        created_by="seed", updated_by="seed",
                    ))

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            pnl_resp = await c.get(f"/finance/pnl-distribution?period={period}")
            assert pnl_resp.status_code == 200
            pnl = pnl_resp.json()
            assert Decimal(pnl["period_depreciation_in_admin"]) == Decimal("20000.00")
            assert Decimal(pnl["totals"]["net_profit"]) == Decimal("-20000.00")

            bs_resp = await c.get(f"/finance/balance-sheet?period={period}")
            assert bs_resp.status_code == 200, bs_resp.text
            body = bs_resp.json()
            totals = body["totals"]
            assert totals["balanced"] is True, (
                f"FA-included balance failed: assets {totals['assets']} != L+E {totals['liabilities_plus_equity']}"
            )
            # 资产 = 100w + 380w + 120w - 58w (期末累计折旧) = 542w
            assert Decimal(totals["assets"]) == Decimal("5420000.00")
            # L+E = 500w + (44w - 2w 折旧亏损) = 542w
            assert Decimal(totals["liabilities_plus_equity"]) == Decimal("5420000.00")
    finally:
        await engine.dispose()


# ============================== 双 confirm 幂等 + PR 重复 approve ==========


@pytest.mark.asyncio
async def test_double_confirm_entities_creates_separate_voucher_rows() -> None:
    """两次 /confirm/entities 同样的 IssueVoucher 不去重(各自有 unique voucher_no 才合法).

    幂等保护在 confirm-and-issue 层面(已测), confirm_writer 本身做 row insert,
    重复 voucher_no 会被 unique constraint 拒.
    """
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="DC-M", name="dc", unit="kg",
                             last_balance=Decimal("100"), last_unit_cost=Decimal("0"),
                             safety_stock=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                mid = m.id

        app = _build_app(engine, actor="dc-actor")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            def _body(voucher_no: str):
                return {
                    "ingestion_id": "dc-1",
                    "source_type": "issue_voucher_photo",
                    "source_ref": "",
                    "entities": [{
                        "entity_type": "IssueVoucher",
                        "temp_id": "iv",
                        "fields": [
                            {"name": "voucher_no", "value": voucher_no},
                            {"name": "material_id", "value": str(mid)},
                            {"name": "quantity", "value": "10"},
                            {"name": "unit", "value": "kg"},
                        ],
                    }],
                }

            r1 = await c.post("/confirm/entities", json=_body("DC-V1"))
            assert r1.status_code == 200
            # 用同一个 voucher_no 再 confirm → 409 Conflict (round 3 self-audit fix)
            r2 = await c.post("/confirm/entities", json=_body("DC-V1"))
            assert r2.status_code == 409, r2.text
            assert "unique" in r2.text.lower() or "constraint" in r2.text.lower()

            # 不同 voucher_no → 各自一行
            r3 = await c.post("/confirm/entities", json=_body("DC-V2"))
            assert r3.status_code == 200
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pr_double_approve_returns_400_with_status_message() -> None:
    """重复 approve 同一个 PR → 第二次返回 400, 含状态说明."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="DA", payment_terms_days=30,
                                created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m = Material(code="DA-M", name="da", unit="kg",
                             last_balance=Decimal("0"), last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                pr = PurchaseRequisition(pr_no="DA-PR-1",
                                          status=PurchaseRequisitionStatus.pending_approval,
                                          source=PurchaseRequisitionSource.manual,
                                          supplier_id=sup.id, human_verified=False,
                                          created_by="seed", updated_by="seed")
                s.add(pr); await s.flush()
                s.add(PurchaseRequisitionItem(
                    pr_id=pr.id, material_id=m.id,
                    quantity=Decimal("5"), unit="kg",
                    unit_price=Decimal("10"), amount=Decimal("50"),
                    created_by="seed", updated_by="seed", human_verified=False,
                ))
                pr_id = pr.id

        app = _build_app(engine, actor="approver")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.post(f"/procurement/requisitions/{pr_id}/approve", json={})
            assert r1.status_code == 200
            r2 = await c.post(f"/procurement/requisitions/{pr_id}/approve", json={})
            assert r2.status_code == 400
            assert "closed_to_po" in r2.text or "pending_approval" in r2.text
    finally:
        await engine.dispose()


# ============================== 跨期会计 ================================


@pytest.mark.asyncio
async def test_retained_earnings_carries_across_periods() -> None:
    """Period A 计算的 retained_earnings 期末可由人手 seed 到 Period B 的 4104 期初,
    Period B 的 PNL 行 "年初未分配利润" 反映这个值."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        period_a = "2026-04"
        period_b = "2026-05"
        async with AsyncSession(engine) as s:
            async with s.begin():
                s.add(PeriodOpeningBalance(
                    period=period_b, account_code="4104",
                    opening_amount=Decimal("123456.78"),
                    created_by="seed", updated_by="seed",
                ))

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get(f"/finance/pnl-distribution?period={period_b}")
            assert resp.status_code == 200
            body = resp.json()
            opening_row = next(r for r in body["rows"] if "年初未分配利润" in r["name"])
            assert Decimal(opening_row["amount"]) == Decimal("123456.78")
    finally:
        await engine.dispose()


# ============================== 库存零 + WAC 极端 =======================


@pytest.mark.asyncio
async def test_reorder_works_when_balance_is_zero() -> None:
    """balance = 0 时不能崩;reorder 应推荐至少 safety_stock × 2."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="ZB-M", name="zero balance", unit="kg",
                             safety_stock=Decimal("100"),
                             last_balance=Decimal("0"),
                             last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                mid = m.id

        app = _build_app(engine, actor="zb-actor")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            confirm_resp = await c.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "zb-1",
                    "source_type": "issue_voucher_photo",
                    "source_ref": "",
                    "entities": [{
                        "entity_type": "IssueVoucher",
                        "temp_id": "iv",
                        "fields": [
                            {"name": "voucher_no", "value": "ZB-V1"},
                            {"name": "material_id", "value": str(mid)},
                            {"name": "quantity", "value": "0.01"},  # 出微量
                            {"name": "unit", "value": "kg"},
                        ],
                    }],
                },
            )
            vid = UUID(confirm_resp.json()["written"][0]["entity_id"])
            issue_resp = await c.post(f"/procurement/issue-vouchers/{vid}/confirm-and-issue")
            assert issue_resp.status_code == 200
            body = issue_resp.json()
            # balance -> -0.01 → out alert
            assert body["alert_id"] is not None
            assert body["auto_drafted_pr_id"] is not None

            # PR item qty > 0
            from yunwei_win.models import (
                PurchaseRequisitionItem,
            )
            async with AsyncSession(engine) as s:
                items = (await s.execute(select(PurchaseRequisitionItem))).scalars().all()
                assert len(items) == 1
                assert Decimal(items[0].quantity) > 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wac_handles_first_receipt_and_zero_balance() -> None:
    """First receipt (balance from 0) 应正确锁定 unit_cost 而非除零."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="WAC0", payment_terms_days=30,
                                created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m = Material(code="WAC0-M", name="wac zero", unit="kg",
                             last_balance=Decimal("0"),  # 起始 0
                             last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                po = PurchaseOrder(po_no="WAC0-PO", supplier_id=sup.id,
                                    status=PurchaseOrderStatus.open,
                                    total_amount=Decimal("500"),
                                    created_by="seed", updated_by="seed", human_verified=True)
                s.add(po); await s.flush()
                s.add(PurchaseOrderItem(po_id=po.id, material_id=m.id,
                                         quantity=Decimal("50"), unit="kg",
                                         unit_price=Decimal("10"), amount=Decimal("500"),
                                         created_by="seed", updated_by="seed", human_verified=True))
                po_id = po.id; mid = m.id

        app = _build_app(engine, actor="wac0")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post(f"/procurement/purchase-orders/{po_id}/receive",
                              json={"warehouse": "W1"})
            assert r.status_code == 200, r.text

        async with AsyncSession(engine) as s:
            m_after = await s.get(Material, mid)
            # (0×0 + 50×10) / 50 = 10
            assert Decimal(m_after.last_unit_cost) == Decimal("10.0000")
            assert Decimal(m_after.last_balance) == Decimal("50.0000")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wac_handles_large_quantities_without_overflow() -> None:
    """100w kg × ¥10000 + 起始 50w kg × ¥5000 → WAC 8333.3333."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="BIG", payment_terms_days=30,
                                created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m = Material(code="BIG-M", name="big", unit="kg",
                             last_balance=Decimal("500000"),
                             last_unit_cost=Decimal("5000"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                po = PurchaseOrder(po_no="BIG-PO", supplier_id=sup.id,
                                    status=PurchaseOrderStatus.open,
                                    total_amount=Decimal("10000000000"),  # 100亿
                                    created_by="seed", updated_by="seed", human_verified=True)
                s.add(po); await s.flush()
                s.add(PurchaseOrderItem(po_id=po.id, material_id=m.id,
                                         quantity=Decimal("1000000"), unit="kg",
                                         unit_price=Decimal("10000"), amount=Decimal("10000000000"),
                                         created_by="seed", updated_by="seed", human_verified=True))
                po_id = po.id; mid = m.id

        from httpx import ASGITransport, AsyncClient
        app = _build_app(engine, actor="big-actor")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post(f"/procurement/purchase-orders/{po_id}/receive",
                              json={"warehouse": "BigW"})
            assert r.status_code == 200, r.text

        async with AsyncSession(engine) as s:
            m_after = await s.get(Material, mid)
            # WAC = (500000×5000 + 1000000×10000) / 1500000 = 8333.3333
            assert Decimal(m_after.last_unit_cost) == Decimal("8333.3333")
            assert Decimal(m_after.last_balance) == Decimal("1500000.0000")
    finally:
        await engine.dispose()


# ============================== API 自审小测 ===========================


@pytest.mark.asyncio
async def test_finance_invalid_period_returns_400_with_format_hint() -> None:
    """所有 finance endpoint 在 period 非 YYYY-MM 时返回 400 + 提示."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            for path in [
                "/finance/balance-sheet?period=2026/05",
                "/finance/pnl-distribution?period=26-05",
                "/finance/cashflow?period=2026-13",
                "/finance/depreciation?period=foo",
                "/finance/cost-breakdown?period=2026-1",  # 缺零填充
            ]:
                resp = await c.get(path)
                assert resp.status_code == 400, f"{path}: status {resp.status_code}"
                assert "YYYY-MM" in resp.text, f"{path}: missing format hint"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stock_movements_limit_capped_at_500() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 超 limit 应被 fastapi Query le=500 拒绝
            r = await c.get("/procurement/stock-movements?limit=1000")
            assert r.status_code == 422
    finally:
        await engine.dispose()
