"""Procurement & briefing listing endpoints — smoke tests.

Empty-state behaviour + filter parameters. The mutation paths and full
business-rule chain are covered in test_jintai_mainline_e2e.py.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    Material,
    Payable,
    PayableStatus,
    PurchaseOrder,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionSource,
    PurchaseRequisitionStatus,
    Supplier,
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

    from yunwei_win.api.briefing import router as briefing_router
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
        request.state.actor = "tester"
        return await call_next(request)

    app.include_router(procurement_router)
    app.include_router(briefing_router)
    app.dependency_overrides[get_session] = _override_session
    return app


@pytest.mark.asyncio
async def test_listings_empty_state() -> None:
    """All listing endpoints return [] / zero on a fresh DB without error."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for path in (
                "/procurement/materials",
                "/procurement/requisitions",
                "/procurement/purchase-orders",
                "/procurement/payables",
                "/procurement/stock-alerts",
                "/procurement/stock-movements",
            ):
                resp = await client.get(path)
                assert resp.status_code == 200, f"{path} -> {resp.status_code} {resp.text}"
                assert resp.json() == []
            kpi = await client.get("/briefing/kpi")
            assert kpi.status_code == 200
            body = kpi.json()
            assert body["payable_total"] == "0"  # Decimal serialized as string
            assert body["low_stock_count"] == 0
            assert body["pending_pr_count"] == 0
            assert body["open_po_count"] == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_materials_warning_levels() -> None:
    """list_materials maps last_balance vs safety_stock to ok/low/out."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                s.add_all([
                    Material(code="OK-1", name="OK", unit="kg",
                             safety_stock=Decimal("100"), last_balance=Decimal("500"),
                             created_by="seed", updated_by="seed", human_verified=True),
                    Material(code="LOW-1", name="Low", unit="kg",
                             safety_stock=Decimal("100"), last_balance=Decimal("50"),
                             created_by="seed", updated_by="seed", human_verified=True),
                    Material(code="OUT-1", name="Out", unit="kg",
                             safety_stock=Decimal("100"), last_balance=Decimal("0"),
                             created_by="seed", updated_by="seed", human_verified=True),
                ])
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/procurement/materials")
            assert resp.status_code == 200
            rows = {m["code"]: m["warning"] for m in resp.json()}
            assert rows == {"OK-1": "ok", "LOW-1": "low", "OUT-1": "out"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_payables_aging_filter() -> None:
    """aging=overdue/due_soon/future filters payables correctly."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        today = date.today()
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                sup = Supplier(name="X", payment_terms_days=30,
                               created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup)
                await s.flush()
                s.add_all([
                    Payable(supplier_id=sup.id, source_type="manual",
                            amount=Decimal("1000"), invoice_date=today - timedelta(days=90),
                            due_date=today - timedelta(days=30),  # overdue
                            status=PayableStatus.pending,
                            created_by="seed", updated_by="seed", human_verified=True),
                    Payable(supplier_id=sup.id, source_type="manual",
                            amount=Decimal("2000"), invoice_date=today - timedelta(days=10),
                            due_date=today + timedelta(days=15),  # due_soon
                            status=PayableStatus.pending,
                            created_by="seed", updated_by="seed", human_verified=True),
                    Payable(supplier_id=sup.id, source_type="manual",
                            amount=Decimal("3000"), invoice_date=today,
                            due_date=today + timedelta(days=90),  # future
                            status=PayableStatus.pending,
                            created_by="seed", updated_by="seed", human_verified=True),
                ])
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            full = (await client.get("/procurement/payables")).json()
            assert len(full) == 3
            overdue = (await client.get("/procurement/payables?aging=overdue")).json()
            assert len(overdue) == 1 and Decimal(overdue[0]["amount"]) == Decimal("1000")
            due_soon = (await client.get("/procurement/payables?aging=due_soon")).json()
            assert len(due_soon) == 1 and Decimal(due_soon[0]["amount"]) == Decimal("2000")
            future = (await client.get("/procurement/payables?aging=future")).json()
            assert len(future) == 1 and Decimal(future[0]["amount"]) == Decimal("3000")
            assert (await client.get("/procurement/payables?aging=BAD")).status_code == 422
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_requisitions_status_filter() -> None:
    """status=pending_approval / approved / rejected filters correctly."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                sup = Supplier(name="Y", payment_terms_days=30,
                               created_by="seed", updated_by="seed", human_verified=True)
                s.add(sup)
                await s.flush()
                s.add_all([
                    PurchaseRequisition(pr_no="PR-PEND-1",
                                        status=PurchaseRequisitionStatus.pending_approval,
                                        source=PurchaseRequisitionSource.ai_autodraft,
                                        supplier_id=sup.id, human_verified=False,
                                        created_by="seed", updated_by="seed"),
                    PurchaseRequisition(pr_no="PR-REJ-1",
                                        status=PurchaseRequisitionStatus.rejected,
                                        source=PurchaseRequisitionSource.manual,
                                        supplier_id=sup.id, human_verified=True,
                                        created_by="seed", updated_by="seed"),
                ])
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            all_resp = await client.get("/procurement/requisitions")
            assert all_resp.status_code == 200
            assert len(all_resp.json()) == 2
            pend = await client.get("/procurement/requisitions?status=pending_approval")
            assert pend.status_code == 200
            assert [p["pr_no"] for p in pend.json()] == ["PR-PEND-1"]
            bad = await client.get("/procurement/requisitions?status=BAD_STATUS")
            assert bad.status_code == 400
    finally:
        await engine.dispose()
