"""光天 · AI 库存管家 — API + 业务规则端到端测试 (SQLite, 无需 PG/Redis).

覆盖: SKU 列表/派生状态/详情 · 出入库 · 库存不足 · 缺货预警触发+解除 ·
订单缺口/可发率 · AI 补产建议规则引擎 · 采纳幂等 · 老板问数意图 · KPI · 日报.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest
from httpx import ASGITransport


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — override the PG-truncating autouse fixture
    yield


@pytest.fixture
def _sqlite_tenant_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("COOKIE_SECRET", "gt-cookie-secret-32-bytes-padding=====")
    import yunwei_win.db as db

    monkeypatch.setattr(db, "_engines", {}, raising=False)
    monkeypatch.setattr(db, "_provisioned", set(), raising=False)
    monkeypatch.setattr(db, "_provisioned_ingest_tables", set(), raising=False)
    monkeypatch.setattr(db, "_provisioned_schema_ingest_tables", set(), raising=False)
    from yunwei_win.config import settings

    monkeypatch.setattr(settings, "database_url", os.environ["DATABASE_URL"])
    yield tmp_path


def _make_app(tenant: str):
    from fastapi import FastAPI, Request

    from yunwei_win.routes import router as win_router

    app = FastAPI()

    @app.middleware("http")
    async def stamp(request: Request, call_next):
        request.state.enterprise_id = tenant
        request.state.actor = "tester"
        return await call_next(request)

    app.include_router(win_router, prefix="/api/win")
    return app


async def _client(tenant: str):
    from yunwei_win.db import ensure_schema_ingest_tables_for, get_engine_for
    from yunwei_win.services.guangtian_seed import seed_guangtian_demo

    await ensure_schema_ingest_tables_for(tenant)
    engine = await get_engine_for(tenant)
    await seed_guangtian_demo(engine)
    app = _make_app(tenant)
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t"), engine


def _tag(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


B = "/api/win/guangtian"


# ----------------------------- seed + list -----------------------------


@pytest.mark.asyncio
async def test_seed_creates_eight_skus(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        skus = (await client.get(f"{B}/skus")).json()
    assert len(skus) == 8
    codes = {s["code"] for s in skus}
    assert "JT-HLZ-230-114-65" in codes and "JT-GZB-AL90" in codes


@pytest.mark.asyncio
async def test_seed_is_idempotent(_sqlite_tenant_root):
    from yunwei_win.services.guangtian_seed import seed_guangtian_demo

    tag = _tag("gt")
    client, engine = await _client(tag)
    async with client:
        again = await seed_guangtian_demo(engine)
        assert again is False  # already seeded
        skus = (await client.get(f"{B}/skus")).json()
        assert len(skus) == 8


@pytest.mark.asyncio
async def test_derived_status_anomaly_out_low_normal(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        skus = {s["code"]: s for s in (await client.get(f"{B}/skus")).json()}
    assert skus["JT-GZB-AL80"]["status"] == "anomaly"  # 手工标记
    assert skus["JT-JZL-JC16"]["status"] == "out"       # balance 0
    assert skus["JT-HLZ-T3-150"]["status"] == "normal"  # 6800 > 1500
    # M70: below safety AND has open order gap → shortage_risk wins
    assert skus["JT-MLS-M70"]["status"] == "shortage_risk"


@pytest.mark.asyncio
async def test_get_sku_404(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        r = await client.get(f"{B}/skus/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_kpi_shape(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        kpi = (await client.get(f"{B}/briefing/kpi")).json()
    assert kpi["sku_total"] == 8
    assert kpi["out_of_stock_count"] == 1
    assert kpi["shortage_order_count"] == 3
    assert kpi["skus_with_open_gap"] >= 2


# ----------------------------- inbound / outbound -----------------------


@pytest.mark.asyncio
async def test_inbound_increases_balance_and_writes_movement(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-MLS-M70"][0]
        before = float(sku["last_balance"])
        r = await client.post(f"{B}/inbound", json={"sku_id": sku["id"], "quantity": 500, "source_ref": "SC-2026-0521"})
        assert r.status_code == 200
        assert float(r.json()["balance_after"]) == before + 500
        after = [s for s in (await client.get(f"{B}/skus")).json() if s["id"] == sku["id"]][0]
        assert float(after["last_balance"]) == before + 500
        movs = (await client.get(f"{B}/stock-movements", params={"sku_id": sku["id"]})).json()
        assert any(m["op"] == "inbound" and float(m["quantity"]) == 500 for m in movs)


@pytest.mark.asyncio
async def test_outbound_decreases_balance(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-HLZ-T3-150"][0]
        before = float(sku["last_balance"])
        r = await client.post(f"{B}/outbound", json={"sku_id": sku["id"], "quantity": 200, "customer": "宜兴华能", "order_no": "SO-X"})
        assert r.status_code == 200
        assert float(r.json()["balance_after"]) == before - 200


@pytest.mark.asyncio
async def test_outbound_insufficient_stock_400(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-JZL-JC16"][0]
        r = await client.post(f"{B}/outbound", json={"sku_id": sku["id"], "quantity": 50})
    assert r.status_code == 400
    assert "库存不足" in r.json()["detail"]


@pytest.mark.asyncio
async def test_inbound_negative_qty_400(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = (await client.get(f"{B}/skus")).json()[0]
        r = await client.post(f"{B}/inbound", json={"sku_id": sku["id"], "quantity": -5})
    assert r.status_code == 400


# ----------------------------- shortage alerts --------------------------


@pytest.mark.asyncio
async def test_outbound_below_safety_triggers_alert(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        # AL90: balance 78, safety 200 — already low; outbound 78 → 0 → out alert
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-GZB-AL90"][0]
        r = await client.post(f"{B}/outbound", json={"sku_id": sku["id"], "quantity": 78})
        assert r.json()["alert_id"] is not None
        alerts = (await client.get(f"{B}/stock-alerts", params={"only_open": True})).json()
        assert any(a["sku_id"] == sku["id"] and a["level"] == "out" for a in alerts)


@pytest.mark.asyncio
async def test_inbound_resolves_open_alert(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-GZB-AL90"][0]
        await client.post(f"{B}/outbound", json={"sku_id": sku["id"], "quantity": 78})  # triggers
        # inbound 500 → back above safety 200 → resolve
        r = await client.post(f"{B}/inbound", json={"sku_id": sku["id"], "quantity": 500})
        assert r.json()["resolved_alerts"] >= 1
        open_alerts = (await client.get(f"{B}/stock-alerts", params={"only_open": True})).json()
        assert all(a["sku_id"] != sku["id"] for a in open_alerts)


# ----------------------------- customer orders --------------------------


@pytest.mark.asyncio
async def test_customer_order_fulfillment(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        orders = {o["order_no"]: o for o in (await client.get(f"{B}/customer-orders")).json()}
    assert orders["SO-20260519-002"]["fulfillment_pct"] == 100  # JC18-LR 300 of 540
    assert orders["SO-20260519-001"]["fulfillment_pct"] < 100   # JC16 out + M70 short
    al90_item = [it for it in orders["SO-20260519-003"]["items"] if it["sku_code"] == "JT-GZB-AL90"][0]
    assert float(al90_item["gap"]) == 72  # needed 150 - stock 78


# ----------------------------- replenishment engine ---------------------


@pytest.mark.asyncio
async def test_generate_replenishments_covers_short_skus(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        res = (await client.post(f"{B}/replenishments/generate")).json()
        assert len(res["created"]) >= 3
        reps = (await client.get(f"{B}/replenishments")).json()
        by_sku = {r["sku_id"]: r for r in reps}
        # JC16 out → high priority, suggest covers gap
        jc16 = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-JZL-JC16"][0]
        assert by_sku[jc16["id"]]["priority"] == "high"
        assert float(by_sku[jc16["id"]]["suggest_qty"]) >= 200


@pytest.mark.asyncio
async def test_generate_replenishments_skips_existing(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        await client.post(f"{B}/replenishments/generate")
        second = (await client.post(f"{B}/replenishments/generate")).json()
        assert second["created"] == []
        assert second["skipped_existing"] >= 3


@pytest.mark.asyncio
async def test_replenishment_source_is_ai_autodraft_unverified(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        await client.post(f"{B}/replenishments/generate")
        reps = (await client.get(f"{B}/replenishments")).json()
    assert all(r["source"] == "ai_autodraft" for r in reps)
    assert all(r["status"] == "suggested" for r in reps)


@pytest.mark.asyncio
async def test_adopt_replenishment_sets_work_order(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        await client.post(f"{B}/replenishments/generate")
        rep = (await client.get(f"{B}/replenishments")).json()[0]
        r = await client.post(f"{B}/replenishments/{rep['id']}/adopt")
        assert r.status_code == 200
        assert r.json()["work_order_no"].startswith("SC-")
        adopted = [x for x in (await client.get(f"{B}/replenishments")).json() if x["id"] == rep["id"]][0]
        assert adopted["status"] == "adopted"
        assert adopted["work_order_no"]


@pytest.mark.asyncio
async def test_adopt_twice_is_409_style_400(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        await client.post(f"{B}/replenishments/generate")
        rep = (await client.get(f"{B}/replenishments")).json()[0]
        await client.post(f"{B}/replenishments/{rep['id']}/adopt")
        r2 = await client.post(f"{B}/replenishments/{rep['id']}/adopt")
    assert r2.status_code == 400


# ----------------------------- 老板问数 --------------------------------


@pytest.mark.asyncio
async def test_ask_priority_production(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        ans = (await client.post(f"{B}/ask", json={"question": "明天应该优先生产什么？"})).json()
    assert ans["engine"] == "demo-mock"
    assert "优先生产" in ans["conclusion"]
    assert any(lk["target"] == "replenish" for lk in ans["links"])


@pytest.mark.asyncio
async def test_ask_shortage_and_fallback(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        shortage = (await client.post(f"{B}/ask", json={"question": "现在哪些缺货？"})).json()
        assert "缺货" in shortage["conclusion"]
        fallback = (await client.post(f"{B}/ask", json={"question": "你好呀"})).json()
        assert "库存总览" in fallback["conclusion"]


# ----------------------------- daily report -----------------------------


@pytest.mark.asyncio
async def test_inbound_voucher_confirm_apply_endpoint_404(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        r = await client.post(f"{B}/inbound-vouchers/{uuid.uuid4()}/confirm-and-apply")
    assert r.status_code == 400  # not found → GuangtianRuleError → 400


@pytest.mark.asyncio
async def test_movements_carry_confidence_and_confirmed(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-MLS-M70"][0]
        await client.post(f"{B}/inbound", json={"sku_id": sku["id"], "quantity": 100, "confidence": 96})
        movs = (await client.get(f"{B}/stock-movements", params={"sku_id": sku["id"]})).json()
    fresh = [m for m in movs if m["reference_no"] and m["reference_no"].startswith("IN-")]
    assert fresh and fresh[0]["confidence"] == 96 and fresh[0]["confirmed"] is True


@pytest.mark.asyncio
async def test_daily_report_after_movement(_sqlite_tenant_root):
    client, _ = await _client(_tag("gt"))
    async with client:
        sku = [s for s in (await client.get(f"{B}/skus")).json() if s["code"] == "JT-HLZ-T3-150"][0]
        await client.post(f"{B}/outbound", json={"sku_id": sku["id"], "quantity": 100})
        report = (await client.get(f"{B}/daily-report")).json()
    assert len(report["sections"]) == 3
    assert "出库 1 笔" in report["summary"] or "出库" in report["summary"]
