"""锦泰 财务三表 / 进销存台账 / 折旧 / 成本拆分 测试.

Pattern: in-memory SQLite + Base.metadata.create_all + httpx.AsyncClient.
覆盖:
  * chart_of_accounts seed + listing
  * /finance/balance-sheet 会企01 (期初 + 实时聚合 = 期末; 资产 = 负债 + 权益)
  * /finance/pnl-distribution 会企02 (收入 - 成本 - 费用 = 利润; 税 + 分配)
  * /finance/cashflow 会企03 (经营/投资/筹资三段 + 净增加)
  * /finance/depreciation 折旧台账 (线性折旧, 累计封顶)
  * /finance/cost-breakdown 成本拆分 (按物料 / 按供应商)
  * /procurement/inventory-ledger 进销存 (期初 + 入 - 出 = 期末)
  * WAC 加权平均成本: receive PO 后 material.last_unit_cost 更新
  * auto-draft 升级: 近 3 月用量 + supplier 自动绑 + unit_price 回填
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    AccountClass,
    ChartOfAccount,
    DEFAULT_CHART_OF_ACCOUNTS,
    FixedAsset,
    FixedAssetCategory,
    Material,
    PeriodOpeningBalance,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
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
    app.dependency_overrides[get_session] = _override_session
    return app


async def _seed_period_openings(engine, period: str, openings: dict[str, str]) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            for code, amount in openings.items():
                s.add(
                    PeriodOpeningBalance(
                        period=period,
                        account_code=code,
                        opening_amount=Decimal(amount),
                        created_by="seed",
                        updated_by="seed",
                    )
                )


# ============================== chart of accounts ======================


@pytest.mark.asyncio
async def test_chart_of_accounts_seeds_on_first_call() -> None:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select, func

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/finance/chart-of-accounts")
            assert resp.status_code == 200
            rows = resp.json()
            assert len(rows) == len(DEFAULT_CHART_OF_ACCOUNTS)

        async with AsyncSession(engine) as s:
            count = (await s.execute(select(func.count()).select_from(ChartOfAccount))).scalar_one()
            assert count == len(DEFAULT_CHART_OF_ACCOUNTS)

        # second call is idempotent (still same count)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/finance/chart-of-accounts")
            assert resp.status_code == 200
            assert len(resp.json()) == len(DEFAULT_CHART_OF_ACCOUNTS)
    finally:
        await engine.dispose()


# ============================== balance sheet ==========================


@pytest.mark.asyncio
async def test_balance_sheet_balances_with_seed_data() -> None:
    """资产 = 负债 + 所有者权益."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        period = "2026-05"
        # opening 已含 inventory; 不放 FA (FA 折旧需要流入 PNL 才能保持借贷平衡,
        # 那块逻辑非 demo 最小可用范围 — 折旧由 /finance/depreciation 单独出表).
        await _seed_period_openings(engine, period, {
            "1001": "100000",    # 库存现金
            "1002": "4950000",   # 银行存款 (= 5000000 - 50000 inv 历史购入)
            "1122": "1200000",   # 应收账款
            "1405": "50000",     # 库存商品 (期初 = 期末, demo 简化)
            "2001": "1000000",   # 短期借款
            "2202": "0",         # 用 payables 表实时算
            "4001": "5000000",   # 实收资本
            "4104": "300000",    # 未分配利润 期初
            "6601": "0", "6602": "0", "6603": "0",
        })
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="MAT-A", name="物料A", unit="kg",
                             safety_stock=Decimal("100"),
                             last_balance=Decimal("1000"),
                             last_unit_cost=Decimal("50"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m)
                sup = Supplier(name="供应商 A", payment_terms_days=60,
                               created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup)

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get(f"/finance/balance-sheet?period={period}")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["statement"] == "会企01 资产负债表"
            assert body["unit"] == "元"
            assert body["currency"] == "CNY"
            # 存货 = 1000 × 50 = 50000
            inventory = next(r for r in body["assets"] if r["name"] == "库存商品")
            assert Decimal(inventory["ending"]) == Decimal("50000.00")
            # 总账平衡
            totals = body["totals"]
            assert totals["balanced"] is True, (
                f"assets {totals['assets']} != L+E {totals['liabilities_plus_equity']}"
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_balance_sheet_period_invalid_400() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/finance/balance-sheet?period=BAD")
            assert resp.status_code == 400
            assert "YYYY-MM" in resp.text
    finally:
        await engine.dispose()


# ============================== PNL ====================================


@pytest.mark.asyncio
async def test_pnl_calculation_revenue_cost_distribution() -> None:
    """收入 - 成本 - 费用 = 营业利润; net = 营利 × (1 - 税率); 分配 + retained."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        period = "2026-05"
        # Seed: 期间内 stock_movement out (营业成本来源)
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="MAT-X", name="X", unit="kg",
                             safety_stock=Decimal("0"),
                             last_balance=Decimal("1000"),
                             last_unit_cost=Decimal("100"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m)
                await s.flush()
                # 期内出库 200 kg → COGS = 200 × 100 = 20000
                s.add(StockMovement(
                    material_id=m.id,
                    direction=StockMovementDirection.out,
                    quantity=Decimal("200"),
                    balance_after=Decimal("800"),
                    reference_type=StockMovementReferenceType.adjustment,
                    reference_id=None,
                    occurred_at=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc),
                    created_by="seed", updated_by="seed",
                ))

        # 期初费用
        await _seed_period_openings(engine, period, {
            "6601": "5000",   # 销售费用
            "6602": "3000",   # 管理费用
            "6603": "1000",   # 财务费用
            "4104": "0",
        })

        # 期初 invoice (营业收入). Invoice 需要 customer_id FK.
        from yunwei_win.models import Customer, Invoice
        async with AsyncSession(engine) as s:
            async with s.begin():
                cust = Customer(full_name="测试客户", created_by="seed", updated_by="seed",
                                 human_verified=True)
                s.add(cust)
                await s.flush()
                inv = Invoice(
                    customer_id=cust.id,
                    amount_total=Decimal("100000"),
                    issue_date=date(2026, 5, 10),
                    human_verified=True,
                    created_by="seed", updated_by="seed",
                )
                s.add(inv)

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get(f"/finance/pnl-distribution?period={period}")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["statement"] == "会企02 利润及利润分配表"
            assert body["unit"] == "元"
            # 营业利润 = 100000 - 20000 - 5000 - 3000 - 1000 = 71000
            assert Decimal(body["totals"]["operating_profit"]) == Decimal("71000.00")
            # 净利润 = 71000 × (1 - 0.25) = 53250
            assert Decimal(body["totals"]["net_profit"]) == Decimal("53250.00")
            # 营业收入行
            rev_row = next(r for r in body["rows"] if r["name"] == "一、营业收入")
            assert Decimal(rev_row["amount"]) == Decimal("100000.00")
    finally:
        await engine.dispose()


# ============================== cashflow ===============================


@pytest.mark.asyncio
async def test_cashflow_structure_present() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/finance/cashflow?period=2026-05")
            assert resp.status_code == 200
            body = resp.json()
            assert body["statement"] == "会企03 现金流量表"
            assert len(body["operating"]) >= 5  # 5 个常用行
            assert len(body["investing"]) >= 1
            assert len(body["financing"]) >= 1
            assert "net_increase" in body["totals"]
    finally:
        await engine.dispose()


# ============================== depreciation ===========================


@pytest.mark.asyncio
async def test_depreciation_straight_line_calculation() -> None:
    """累计折旧 = monthly × months; 净值 = original - 累计."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                s.add(FixedAsset(
                    asset_no="FA-LINE",
                    name="某设备",
                    category=FixedAssetCategory.machinery,
                    acquired_date=date(2024, 1, 1),
                    original_cost=Decimal("120000"),
                    salvage_value=Decimal("0"),
                    useful_life_months=60,
                    created_by="seed", updated_by="seed", human_verified=True,
                ))

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 折旧到 2024-06 = 6 个月 × 2000 = 12000
            resp = await c.get("/finance/depreciation?period=2024-06")
            body = resp.json()
            assert resp.status_code == 200
            row = body["rows"][0]
            assert Decimal(row["monthly_depreciation"]) == Decimal("2000.00")
            assert row["months_depreciated_through_period"] == 6
            assert Decimal(row["accumulated_depreciation"]) == Decimal("12000.00")
            assert Decimal(row["net_book_value"]) == Decimal("108000.00")

            # 折旧到 5 年后 (60 月) — accumulated 封顶 (120000 - 0 = 120000)
            resp2 = await c.get("/finance/depreciation?period=2028-12")
            body2 = resp2.json()
            row2 = body2["rows"][0]
            assert row2["months_depreciated_through_period"] == 60
            assert Decimal(row2["accumulated_depreciation"]) == Decimal("120000.00")
            assert Decimal(row2["net_book_value"]) == Decimal("0.00")

            # 6 年后, 折旧不会超过 120000 (没残值)
            resp3 = await c.get("/finance/depreciation?period=2029-12")
            body3 = resp3.json()
            row3 = body3["rows"][0]
            assert Decimal(row3["accumulated_depreciation"]) == Decimal("120000.00")
            assert Decimal(row3["current_period_depreciation"]) == Decimal("0.00")
    finally:
        await engine.dispose()


# ============================== cost breakdown =========================


@pytest.mark.asyncio
async def test_cost_breakdown_by_material_and_supplier() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="供货1", payment_terms_days=30,
                               created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m1 = Material(code="M1", name="m1", unit="kg",
                              last_balance=Decimal("100"),
                              last_unit_cost=Decimal("50"),
                              created_by="seed", updated_by="seed", human_verified=True)
                m2 = Material(code="M2", name="m2", unit="kg",
                              last_balance=Decimal("100"),
                              last_unit_cost=Decimal("20"),
                              created_by="seed", updated_by="seed", human_verified=True)
                s.add_all([m1, m2]); await s.flush()
                # 2026-05 期内出库 (cogs)
                s.add(StockMovement(material_id=m1.id, direction=StockMovementDirection.out,
                                     quantity=Decimal("50"), balance_after=Decimal("50"),
                                     reference_type=StockMovementReferenceType.adjustment,
                                     occurred_at=datetime(2026, 5, 10, tzinfo=timezone.utc),
                                     created_by="seed", updated_by="seed"))
                s.add(StockMovement(material_id=m2.id, direction=StockMovementDirection.out,
                                     quantity=Decimal("30"), balance_after=Decimal("70"),
                                     reference_type=StockMovementReferenceType.adjustment,
                                     occurred_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
                                     created_by="seed", updated_by="seed"))
                # 2026-05 收到的 PO
                po = PurchaseOrder(po_no="PO-501", supplier_id=sup.id,
                                   status=PurchaseOrderStatus.closed,
                                   total_amount=Decimal("8000"),
                                   received_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
                                   created_by="seed", updated_by="seed", human_verified=True)
                s.add(po)

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get("/finance/cost-breakdown?period=2026-05")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            # by_material: M1 ranks higher (2500 > 600)
            assert [r["code"] for r in body["by_material"]] == ["M1", "M2"]
            assert Decimal(body["by_material"][0]["cost_amount"]) == Decimal("2500.00")  # 50×50
            assert Decimal(body["by_material"][1]["cost_amount"]) == Decimal("600.00")    # 30×20
            assert Decimal(body["totals"]["cogs_from_material_consumption"]) == Decimal("3100.00")
            # by_supplier: 供货1 8000
            assert len(body["by_supplier"]) == 1
            assert Decimal(body["by_supplier"][0]["received_amount"]) == Decimal("8000.00")
    finally:
        await engine.dispose()


# ============================== inventory ledger =======================


@pytest.mark.asyncio
async def test_inventory_ledger_opening_in_out_ending() -> None:
    """期初 + 入 - 出 = 期末. 期初 = 期外最近一条 movement 的 balance_after."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="LED-M", name="台账M", unit="kg",
                             last_balance=Decimal("700"),
                             last_unit_cost=Decimal("10"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                # 期外: 2026-04-30 入 500, balance 500
                s.add(StockMovement(material_id=m.id, direction=StockMovementDirection.in_,
                                     quantity=Decimal("500"), balance_after=Decimal("500"),
                                     reference_type=StockMovementReferenceType.opening,
                                     occurred_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
                                     created_by="seed", updated_by="seed"))
                # 期内: 2026-05-05 入 300, balance 800
                s.add(StockMovement(material_id=m.id, direction=StockMovementDirection.in_,
                                     quantity=Decimal("300"), balance_after=Decimal("800"),
                                     reference_type=StockMovementReferenceType.goods_receipt,
                                     occurred_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
                                     created_by="seed", updated_by="seed"))
                # 期内: 2026-05-20 出 100, balance 700
                s.add(StockMovement(material_id=m.id, direction=StockMovementDirection.out,
                                     quantity=Decimal("100"), balance_after=Decimal("700"),
                                     reference_type=StockMovementReferenceType.issue_voucher,
                                     occurred_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
                                     created_by="seed", updated_by="seed"))
                mid = m.id

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get(
                f"/procurement/inventory-ledger?material_id={mid}&period=2026-05"
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert Decimal(body["opening_balance"]) == Decimal("500.00")
            assert Decimal(body["in_qty"]) == Decimal("300.00")
            assert Decimal(body["out_qty"]) == Decimal("100.00")
            assert Decimal(body["ending_balance"]) == Decimal("700.00")
            assert len(body["movements"]) == 2  # 期内 2 条
            assert Decimal(body["ending_value"]) == Decimal("7000.00")  # 700 × 10

            # bad period
            resp_bad = await c.get(
                f"/procurement/inventory-ledger?material_id={mid}&period=BAD"
            )
            assert resp_bad.status_code == 400

            # missing material
            resp_404 = await c.get(
                f"/procurement/inventory-ledger?material_id={uuid4()}&period=2026-05"
            )
            assert resp_404.status_code == 404
    finally:
        await engine.dispose()


# ============================== WAC =====================================


@pytest.mark.asyncio
async def test_receive_po_updates_last_unit_cost_via_wac() -> None:
    """receive PO with unit_price → material.last_unit_cost 按加权平均更新."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                sup = Supplier(name="WAC-Sup", payment_terms_days=30,
                               created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup); await s.flush()
                m = Material(code="WAC-M", name="WAC物料", unit="kg",
                             last_balance=Decimal("100"),
                             last_unit_cost=Decimal("20"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                # 准备一个 open PO, 单价 ¥30, 数量 100
                po = PurchaseOrder(po_no="PO-WAC-1", supplier_id=sup.id,
                                   status=PurchaseOrderStatus.open,
                                   total_amount=Decimal("3000"),
                                   created_by="seed", updated_by="seed",
                                   human_verified=True)
                s.add(po); await s.flush()
                s.add(PurchaseOrderItem(
                    po_id=po.id, material_id=m.id,
                    quantity=Decimal("100"), unit="kg",
                    unit_price=Decimal("30"), amount=Decimal("3000"),
                    created_by="seed", updated_by="seed", human_verified=True,
                ))
                po_id = po.id
                mid = m.id

        app = _build_app(engine, actor="tester")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post(
                f"/procurement/purchase-orders/{po_id}/receive",
                json={"warehouse": "A-1"},
            )
            assert resp.status_code == 200, resp.text

        async with AsyncSession(engine) as s:
            m_after = await s.get(Material, mid)
            # WAC = (100 × 20 + 100 × 30) / 200 = 25
            assert Decimal(m_after.last_unit_cost) == Decimal("25.0000")
            assert Decimal(m_after.last_balance) == Decimal("200.0000")
    finally:
        await engine.dispose()


# ============================== auto-draft upgrade ======================


@pytest.mark.asyncio
async def test_auto_draft_uses_recent_supplier_and_unit_price() -> None:
    """When prior PO exists for the material, auto-draft binds supplier + back-fills unit_price."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                # 历史: 供应商A, 卖过这物料 ¥24/kg
                sup_a = Supplier(name="Sup-A", payment_terms_days=30,
                                 created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup_a); await s.flush()
                m = Material(code="HIST-M", name="历史物料", unit="kg",
                             safety_stock=Decimal("100"),
                             last_balance=Decimal("80"),  # 当前已低于 safety
                             last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                # 历史 PO (已 received)
                old_po = PurchaseOrder(
                    po_no="PO-OLD-1", supplier_id=sup_a.id,
                    status=PurchaseOrderStatus.closed,
                    total_amount=Decimal("2400"),
                    received_at=datetime.now(tz=timezone.utc) - timedelta(days=30),
                    created_by="seed", updated_by="seed", human_verified=True,
                )
                s.add(old_po); await s.flush()
                s.add(PurchaseOrderItem(
                    po_id=old_po.id, material_id=m.id,
                    quantity=Decimal("100"), unit="kg",
                    unit_price=Decimal("24"), amount=Decimal("2400"),
                    created_by="seed", updated_by="seed", human_verified=True,
                ))
                mid = m.id
                sup_a_id = sup_a.id

        app = _build_app(engine, actor="王仓管")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 创建一个 issue voucher 触发 auto-draft (issue qty 不重要; balance 已经 < safety)
            confirm_resp = await c.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-hist",
                    "source_type": "issue_voucher_photo",
                    "source_ref": "",
                    "entities": [
                        {
                            "entity_type": "IssueVoucher",
                            "temp_id": "iv",
                            "fields": [
                                {"name": "voucher_no", "value": "BL-HIST"},
                                {"name": "material_id", "value": str(mid)},
                                {"name": "quantity", "value": "10"},
                                {"name": "unit", "value": "kg"},
                            ],
                        }
                    ],
                },
            )
            assert confirm_resp.status_code == 200
            vid = UUID(confirm_resp.json()["written"][0]["entity_id"])
            issue_resp = await c.post(f"/procurement/issue-vouchers/{vid}/confirm-and-issue")
            assert issue_resp.status_code == 200
            body = issue_resp.json()
            assert body["auto_drafted_pr_id"] is not None

        # 查 PR: 应已绑 supplier + 有 unit_price
        async with AsyncSession(engine) as s:
            from yunwei_win.models import (
                PurchaseRequisition, PurchaseRequisitionItem,
            )
            from sqlalchemy import select
            pr_id = UUID(body["auto_drafted_pr_id"])
            pr = await s.get(PurchaseRequisition, pr_id)
            assert pr.supplier_id == sup_a_id, "supplier 应被自动绑"
            items = (await s.execute(
                select(PurchaseRequisitionItem).where(
                    PurchaseRequisitionItem.pr_id == pr_id
                )
            )).scalars().all()
            assert len(items) == 1
            assert items[0].unit_price == Decimal("24"), "unit_price 应被回填"
            assert items[0].amount is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_draft_uses_3mo_usage_when_history_present() -> None:
    """有近 3 月用量历史 → reorder 按用量推荐而非 safety fallback."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="USE-M", name="用量物料", unit="kg",
                             safety_stock=Decimal("50"),
                             last_balance=Decimal("40"),
                             last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                # 近 90 天累计出库 600 → 月均 200 → reorder = 200×2 - 40 = 360
                for days_ago, qty in [(80, 100), (50, 200), (20, 300)]:
                    s.add(StockMovement(
                        material_id=m.id, direction=StockMovementDirection.out,
                        quantity=Decimal(qty), balance_after=Decimal("0"),
                        reference_type=StockMovementReferenceType.adjustment,
                        occurred_at=datetime.now(tz=timezone.utc) - timedelta(days=days_ago),
                        created_by="seed", updated_by="seed",
                    ))
                mid = m.id

        app = _build_app(engine, actor="tester")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            confirm_resp = await c.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-usg",
                    "source_type": "issue_voucher_photo",
                    "source_ref": "",
                    "entities": [{
                        "entity_type": "IssueVoucher",
                        "temp_id": "iv",
                        "fields": [
                            {"name": "voucher_no", "value": "BL-USG-1"},
                            {"name": "material_id", "value": str(mid)},
                            {"name": "quantity", "value": "5"},
                            {"name": "unit", "value": "kg"},
                        ],
                    }],
                },
            )
            vid = UUID(confirm_resp.json()["written"][0]["entity_id"])
            issue_resp = await c.post(f"/procurement/issue-vouchers/{vid}/confirm-and-issue")
            body = issue_resp.json()
            assert body["auto_drafted_pr_id"] is not None

        async with AsyncSession(engine) as s:
            from yunwei_win.models import (
                PurchaseRequisition, PurchaseRequisitionItem,
            )
            from sqlalchemy import select
            pr_id = UUID(body["auto_drafted_pr_id"])
            pr = await s.get(PurchaseRequisition, pr_id)
            assert "usage_3mo_avg" in (pr.source_note or "")
            items = (await s.execute(
                select(PurchaseRequisitionItem).where(
                    PurchaseRequisitionItem.pr_id == pr_id
                )
            )).scalars().all()
            # qty: monthly avg = 600 / 3 = 200, target = 200×2 = 400, reorder = 400 - 35 = 365
            # balance after issuing 5 from 40 = 35
            assert items[0].quantity > Decimal("300")
    finally:
        await engine.dispose()
