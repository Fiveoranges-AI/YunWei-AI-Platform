"""BOM (配料单) 测试.

锦泰 demo "配料单 D" 后端对应物:
  * GET /procurement/boms — list
  * GET /procurement/boms/{id} — head + lines
  * POST /procurement/boms/{id}/explode — 按 batch_quantity 爆开,返回每条
    材料 required_qty / current_balance / shortage / available
"""

from __future__ import annotations

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
    BillOfMaterials,
    BillOfMaterialsLine,
    BomStatus,
    Material,
)


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


def _build_app(engine):
    from fastapi import FastAPI

    from yunwei_win.api.bom import router as bom_router
    from yunwei_win.api.confirm import router as confirm_router

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
        request.state.actor = "tester"
        return await call_next(request)

    app.include_router(bom_router)
    app.include_router(confirm_router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _seed_bom_with_shortage(engine):
    """Seed: 1 BOM "承烧板" output_qty=1, with material A (per-output=5kg).
    Material A safety=200, balance=80 → for batch_qty=20, required=100, shortage=20."""
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            m_a = Material(code="MAT-A-BOM", name="A料",
                            unit="kg", safety_stock=Decimal("200"),
                            last_balance=Decimal("80"),
                            last_unit_cost=Decimal("10"),
                            created_by="seed", updated_by="seed", human_verified=True)
            m_b = Material(code="MAT-B-BOM", name="B料",
                            unit="kg", safety_stock=Decimal("0"),
                            last_balance=Decimal("5000"),
                            last_unit_cost=Decimal("5"),
                            created_by="seed", updated_by="seed", human_verified=True)
            s.add_all([m_a, m_b]); await s.flush()
            bom = BillOfMaterials(
                product_code="P-CSB-NCM",
                product_name="容百锂电承烧板",
                version="v1",
                output_quantity=Decimal("1"),
                output_unit="片",
                status=BomStatus.active,
                created_by="seed", updated_by="seed", human_verified=True,
            )
            s.add(bom); await s.flush()
            s.add_all([
                BillOfMaterialsLine(
                    bom_id=bom.id, material_id=m_a.id,
                    quantity_per_output=Decimal("5"), unit="kg",
                    scrap_rate=Decimal("0"), sort_order=1,
                    created_by="seed", updated_by="seed", human_verified=True,
                ),
                BillOfMaterialsLine(
                    bom_id=bom.id, material_id=m_b.id,
                    quantity_per_output=Decimal("2"), unit="kg",
                    scrap_rate=Decimal("0.05"),  # 5% 损耗
                    sort_order=2,
                    created_by="seed", updated_by="seed", human_verified=True,
                ),
            ])
            return bom.id, m_a.id, m_b.id


# ============================== tests ===================================


@pytest.mark.asyncio
async def test_list_and_get_bom() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        bom_id, _ma, _mb = await _seed_bom_with_shortage(engine)
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            list_resp = await c.get("/procurement/boms")
            assert list_resp.status_code == 200
            assert len(list_resp.json()) == 1
            assert list_resp.json()[0]["product_code"] == "P-CSB-NCM"

            detail_resp = await c.get(f"/procurement/boms/{bom_id}")
            assert detail_resp.status_code == 200
            body = detail_resp.json()
            assert len(body["lines"]) == 2

            list_active = await c.get("/procurement/boms?status=active")
            assert len(list_active.json()) == 1
            list_draft = await c.get("/procurement/boms?status=draft")
            assert list_draft.json() == []

            assert (await c.get(f"/procurement/boms/{uuid4()}")).status_code == 404
            assert (await c.get("/procurement/boms?status=BAD")).status_code == 400
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_explode_computes_required_and_shortage() -> None:
    """For batch_qty=20, output_qty=1 → batches=20:
       A required = 5×20 = 100; balance=80 → shortage 20 → not available
       B required = 2×20×1.05 = 42; balance=5000 → shortage 0 → available
       fully_available = False"""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        bom_id, ma_id, mb_id = await _seed_bom_with_shortage(engine)
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post(
                f"/procurement/boms/{bom_id}/explode",
                json={"batch_quantity": "20"},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["product_code"] == "P-CSB-NCM"
            assert Decimal(body["batch_quantity"]) == Decimal("20")
            assert body["fully_available"] is False

            lines = {l["code"]: l for l in body["lines"]}
            assert Decimal(lines["MAT-A-BOM"]["required_qty"]) == Decimal("100.0000")
            assert Decimal(lines["MAT-A-BOM"]["current_balance"]) == Decimal("80.0000")
            assert Decimal(lines["MAT-A-BOM"]["shortage"]) == Decimal("20.0000")
            assert lines["MAT-A-BOM"]["available"] is False

            # B: 2 × 20 × 1.05 = 42.0000
            assert Decimal(lines["MAT-B-BOM"]["required_qty"]) == Decimal("42.0000")
            assert Decimal(lines["MAT-B-BOM"]["shortage"]) == Decimal("0")
            assert lines["MAT-B-BOM"]["available"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_explode_smaller_batch_is_fully_available() -> None:
    """batch_qty=10 → A required=50, balance=80 → available"""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        bom_id, _ma, _mb = await _seed_bom_with_shortage(engine)
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post(
                f"/procurement/boms/{bom_id}/explode",
                json={"batch_quantity": "10"},
            )
            assert resp.status_code == 200
            assert resp.json()["fully_available"] is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_explode_bad_inputs_return_4xx() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        bom_id, _, _ = await _seed_bom_with_shortage(engine)
        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            assert (await c.post(
                f"/procurement/boms/{uuid4()}/explode", json={"batch_quantity": "10"}
            )).status_code == 404
            assert (await c.post(
                f"/procurement/boms/{bom_id}/explode", json={"batch_quantity": "0"}
            )).status_code == 400
            assert (await c.post(
                f"/procurement/boms/{bom_id}/explode", json={"batch_quantity": "-5"}
            )).status_code == 400
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bom_created_via_confirm_writer() -> None:
    """BOM head + lines 可以通过 /confirm/entities 走 AI 先填、人确认 路径写入."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        # seed materials only
        async with AsyncSession(engine) as s:
            async with s.begin():
                m = Material(code="BOM-CONF-M", name="conf 料", unit="kg",
                             last_balance=Decimal("0"), last_unit_cost=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True)
                s.add(m); await s.flush()
                mid = m.id

        app = _build_app(engine)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-bom-1",
                    "source_type": "bom_sheet",
                    "source_ref": "storage://bom.xlsx",
                    "entities": [
                        {
                            "entity_type": "BillOfMaterials",
                            "temp_id": "bom1",
                            "fields": [
                                {"name": "product_code", "value": "P-CONF-1", "confidence": 1.0},
                                {"name": "product_name", "value": "confirm 测试", "confidence": 1.0},
                                {"name": "version", "value": "v1", "confidence": 1.0},
                                {"name": "output_quantity", "value": "1", "confidence": 1.0},
                                {"name": "output_unit", "value": "kg", "confidence": 1.0},
                            ],
                        },
                        {
                            "entity_type": "BillOfMaterialsLine",
                            "temp_id": "line1",
                            "fields": [
                                {"name": "material_id", "value": str(mid), "confidence": 1.0},
                                {"name": "quantity_per_output", "value": "3", "confidence": 0.95},
                                {"name": "unit", "value": "kg", "confidence": 1.0},
                            ],
                        },
                    ],
                    "relationships": [
                        {"from_temp_id": "bom1", "to_temp_id": "line1",
                         "type": "BillOfMaterials-has-Line"},
                    ],
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body["written"]) == 2

            bom_id = next(UUID(w["entity_id"]) for w in body["written"] if w["entity_type"] == "BillOfMaterials")
            detail = await c.get(f"/procurement/boms/{bom_id}")
            assert detail.status_code == 200
            assert len(detail.json()["lines"]) == 1
            assert detail.json()["lines"][0]["material_id"] == str(mid)
    finally:
        await engine.dispose()
