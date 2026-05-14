"""Tests for the schema catalog + company data foundation.

Mirrors the in-memory SQLite + ASGI pattern from ``test_ingest_jobs.py``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only override
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, get_session  # noqa: E402
from yunwei_win.models.company_schema import CompanySchemaTable  # noqa: E402
from yunwei_win.routes import router as yinhu_router  # noqa: E402
from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA  # noqa: E402


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_enterprise(request: Request, call_next):
        request.state.enterprise_id = "tenant_test"
        return await call_next(request)

    async def session_dep():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_dep
    app.include_router(yinhu_router, prefix="/api/win")
    return app


# ---------- model registration ----------------------------------------


def test_company_schema_models_are_registered():
    assert "company_schema_tables" in Base.metadata.tables
    assert "company_schema_fields" in Base.metadata.tables
    assert "schema_change_proposals" in Base.metadata.tables


def test_company_data_models_are_registered():
    expected = {
        "products",
        "product_requirements",
        "contract_payment_milestones",
        "invoices",
        "invoice_items",
        "payments",
        "shipments",
        "shipment_items",
        "customer_journal_items",
    }
    assert expected.issubset(set(Base.metadata.tables))


# ---------- GET /company-schema ---------------------------------------


@pytest.mark.asyncio
async def test_get_company_schema_seeds_default_catalog():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get("/api/win/company-schema")
            assert res.status_code == 200, res.text
            body = res.json()
            table_names = [t["table_name"] for t in body["tables"]]
            assert "orders" in table_names
            orders = next(t for t in body["tables"] if t["table_name"] == "orders")
            fields = [f["field_name"] for f in orders["fields"]]
            assert fields[:6] == [
                "customer_id",
                "amount_total",
                "amount_currency",
                "delivery_promised_date",
                "delivery_address",
                "description",
            ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_company_schema_seed_is_idempotent():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            assert (await ac.get("/api/win/company-schema")).status_code == 200
            assert (await ac.get("/api/win/company-schema")).status_code == 200
        async with AsyncSession(engine, expire_on_commit=False) as session:
            table_count = await session.scalar(
                select(func.count()).select_from(CompanySchemaTable)
            )
            assert table_count == len(DEFAULT_COMPANY_SCHEMA)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approve_add_field_proposal_adds_field():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            # Seed first so the table exists.
            assert (await ac.get("/api/win/company-schema")).status_code == 200

            proposal = await ac.post(
                "/api/win/company-schema/change-proposals",
                json={
                    "proposal_type": "add_field",
                    "table_name": "orders",
                    "field_name": "external_po_no",
                    "proposed_payload": {
                        "label": "外部采购单号",
                        "data_type": "text",
                        "required": False,
                        "description": "客户侧采购单号",
                    },
                    "reason": "Document mentions PO No.",
                    "created_by": "ai",
                },
            )
            assert proposal.status_code == 200, proposal.text
            pid = proposal.json()["id"]

            approved = await ac.post(
                f"/api/win/company-schema/change-proposals/{pid}/approve"
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "applied"

            schema = (await ac.get("/api/win/company-schema")).json()
            orders = next(t for t in schema["tables"] if t["table_name"] == "orders")
            assert "external_po_no" in [f["field_name"] for f in orders["fields"]]
    finally:
        await engine.dispose()
