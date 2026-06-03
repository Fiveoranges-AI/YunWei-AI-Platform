"""Tests for the P0 task ③ confirm-card endpoint + writer.

Covered surface:

  * POST /confirm/entities — writes ontology rows with full audit stamps
    + emits one ActionLog per entity.
  * was_edited fields drop their per-field confidence + are recorded in
    the ActionLog input_summary.
  * Relationships (Customer-has-Contact, Customer-has-Order) resolve
    parent FKs after the parent row flushes.
  * "associate with existing" branch skips re-insertion but still emits
    an ActionLog.
  * Invalid date / numeric values produce HTTP 400.

Same in-memory SQLite pattern as ``test_customer_management.py``: the
project-level Postgres autouse fixture is overridden, FKs are enabled,
and the API is hit through ``httpx.AsyncClient(ASGITransport)``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    Contact,
    Customer,
    Order,
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


def _build_app(engine, *, actor: str = "test-user"):
    from fastapi import FastAPI

    from yunwei_win.api.confirm import router

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

    app.include_router(router)
    app.dependency_overrides[get_session] = _override_session
    return app


def _customer_field(name: str, value, confidence: float = 0.9, **kw):
    return {
        "name": name,
        "value": value,
        "confidence": confidence,
        "was_edited": kw.get("was_edited", False),
        "source_span": kw.get(
            "source_span", {"page": 1, "text": f"sample-{name}"}
        ),
    }


# ---------- happy path ---------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_creates_customer_with_audit_stamps() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine, actor="alice")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-001",
                    "source_type": "contract",
                    "source_ref": "storage://test/contract.pdf",
                    "entities": [
                        {
                            "entity_type": "Customer",
                            "temp_id": "c1",
                            "fields": [
                                _customer_field("full_name", "测试客户有限公司"),
                                _customer_field("short_name", "测试", confidence=0.7),
                                _customer_field("tax_id", "91310000XXXXXXXX", confidence=0.85),
                            ],
                        }
                    ],
                    "relationships": [],
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body["written"]) == 1
            written = body["written"][0]
            assert written["entity_type"] == "Customer"
            assert written["created"] is True
            assert written["human_verified"] is True
            assert written["verified_by"] == "alice"
            customer_id = UUID(written["entity_id"])
            assert len(body["action_log_ids"]) == 1

        # Verify DB row: audit stamps + confidence (lowest surviving field).
        async with AsyncSession(engine, expire_on_commit=False) as session:
            c = (
                await session.execute(select(Customer).where(Customer.id == customer_id))
            ).scalar_one()
            assert c.full_name == "测试客户有限公司"
            assert c.short_name == "测试"
            assert c.tax_id == "91310000XXXXXXXX"
            assert c.human_verified is True
            assert c.verified_by == "alice"
            assert c.verified_at is not None
            assert c.source_type == "contract"
            assert c.source_ref == "storage://test/contract.pdf"
            assert c.source_span is not None
            assert "fields" in c.source_span
            assert c.created_by == "alice"
            assert c.updated_by == "alice"
            assert c.confidence == Decimal("0.70")  # min surviving confidence

            log = (
                await session.execute(
                    select(ActionLog).where(ActionLog.target_entity_id == customer_id)
                )
            ).scalar_one()
            assert log.target_entity_type == ActionTargetType.customer
            assert log.actor == "alice"
            assert log.actor_kind == "user"
            assert log.succeeded is True
            assert log.input_summary is not None
            assert "ingestion=ing-001" in log.input_summary
            assert "entity=Customer" in log.input_summary
    finally:
        await engine.dispose()


# ---------- edit branch --------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_edited_field_clears_confidence_and_logs() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine, actor="bob")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-002",
                    "source_type": "wechat_screenshot",
                    "source_ref": "storage://test/chat.png",
                    "entities": [
                        {
                            "entity_type": "Customer",
                            "temp_id": "c1",
                            "fields": [
                                _customer_field("full_name", "AI 写错的名", confidence=0.4, was_edited=True),
                                _customer_field("short_name", "简称", confidence=0.9),
                            ],
                        }
                    ],
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["written"][0]["edited_field_count"] == 1
            customer_id = UUID(body["written"][0]["entity_id"])

        async with AsyncSession(engine, expire_on_commit=False) as session:
            c = (
                await session.execute(select(Customer).where(Customer.id == customer_id))
            ).scalar_one()
            assert c.human_verified is True
            # Only the unedited field's confidence survives; that becomes row confidence.
            assert c.confidence == Decimal("0.90")

            log = (
                await session.execute(
                    select(ActionLog).where(ActionLog.target_entity_id == customer_id)
                )
            ).scalar_one()
            assert "edited=1" in (log.input_summary or "")
            assert "edited_fields=full_name" in (log.input_summary or "")
    finally:
        await engine.dispose()


# ---------- relationship resolution --------------------------------------


@pytest.mark.asyncio
async def test_confirm_resolves_customer_has_contact_relationship() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-003",
                    "source_type": "contract",
                    "source_ref": "storage://test/contract.pdf",
                    "entities": [
                        {
                            "entity_type": "Customer",
                            "temp_id": "c1",
                            "fields": [_customer_field("full_name", "Acme Co.")],
                        },
                        {
                            "entity_type": "Contact",
                            "temp_id": "p1",
                            "fields": [
                                _customer_field("name", "张三"),
                                _customer_field("phone", "13800000000"),
                            ],
                        },
                    ],
                    "relationships": [
                        {
                            "from_temp_id": "c1",
                            "to_temp_id": "p1",
                            "type": "Customer-has-Contact",
                        }
                    ],
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body["written"]) == 2
            assert len(body["action_log_ids"]) == 2
            written_by_temp = {w["temp_id"]: w for w in body["written"]}
            customer_id = UUID(written_by_temp["c1"]["entity_id"])
            contact_id = UUID(written_by_temp["p1"]["entity_id"])

        async with AsyncSession(engine, expire_on_commit=False) as session:
            contact = (
                await session.execute(select(Contact).where(Contact.id == contact_id))
            ).scalar_one()
            assert contact.customer_id == customer_id
            assert contact.human_verified is True
            assert contact.source_type == "contract"
    finally:
        await engine.dispose()


# ---------- existing-entity branch ---------------------------------------


@pytest.mark.asyncio
async def test_confirm_associate_existing_skips_insert_but_logs() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        # Pre-seed an existing customer the user is going to associate to.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            existing = Customer(full_name="既有客户")
            session.add(existing)
            await session.commit()
            existing_id = existing.id

        app = _build_app(engine, actor="carol")
        transport = ASGITransport(app=app)
        from httpx import AsyncClient as Client
        async with Client(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-004",
                    "source_type": "excel",
                    "source_ref": "storage://test/sheet.xlsx",
                    "entities": [
                        {
                            "entity_type": "Customer",
                            "temp_id": "c1",
                            "existing_entity_id": str(existing_id),
                            "fields": [
                                _customer_field("full_name", "AI 推荐重复名"),
                            ],
                        },
                        {
                            "entity_type": "Order",
                            "temp_id": "o1",
                            "fields": [
                                _customer_field("amount_total", "10000.50"),
                                _customer_field("order_date", "2026-05-01"),
                            ],
                        },
                    ],
                    "relationships": [
                        {
                            "from_temp_id": "c1",
                            "to_temp_id": "o1",
                            "type": "Customer-has-Order",
                        }
                    ],
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            customer_written = next(w for w in body["written"] if w["temp_id"] == "c1")
            order_written = next(w for w in body["written"] if w["temp_id"] == "o1")
            assert customer_written["created"] is False
            assert UUID(customer_written["entity_id"]) == existing_id
            assert order_written["created"] is True

        async with AsyncSession(engine, expire_on_commit=False) as session:
            # Existing customer was NOT replaced — full_name still "既有客户".
            c = (
                await session.execute(select(Customer).where(Customer.id == existing_id))
            ).scalar_one()
            assert c.full_name == "既有客户"

            order = (
                await session.execute(
                    select(Order).where(Order.id == UUID(order_written["entity_id"]))
                )
            ).scalar_one()
            assert order.customer_id == existing_id
            assert order.amount_total == Decimal("10000.5000")
            assert order.order_date.isoformat() == "2026-05-01"
            assert order.human_verified is True
            assert order.verified_by == "carol"

            logs = list(
                (
                    await session.execute(
                        select(ActionLog).order_by(ActionLog.executed_at)
                    )
                ).scalars()
            )
            # One log per entity (existing + created).
            assert len(logs) == 2
    finally:
        await engine.dispose()


# ---------- validation ---------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_invalid_date_returns_400() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        # Need a parent customer for the order FK.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            existing = Customer(full_name="x")
            session.add(existing)
            await session.commit()
            existing_id = existing.id

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-bad",
                    "source_type": "contract",
                    "source_ref": "",
                    "entities": [
                        {
                            "entity_type": "Customer",
                            "temp_id": "c1",
                            "existing_entity_id": str(existing_id),
                            "fields": [],
                        },
                        {
                            "entity_type": "Order",
                            "temp_id": "o1",
                            "fields": [
                                _customer_field("order_date", "not-a-date"),
                            ],
                        },
                    ],
                    "relationships": [
                        {
                            "from_temp_id": "c1",
                            "to_temp_id": "o1",
                            "type": "Customer-has-Order",
                        }
                    ],
                },
            )
            assert resp.status_code == 400, resp.text
            assert "order_date" in resp.text or "date" in resp.text.lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_confirm_empty_entities_returns_400() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/confirm/entities",
                json={
                    "ingestion_id": "ing-empty",
                    "source_type": "contract",
                    "source_ref": "",
                    "entities": [],
                    "relationships": [],
                },
            )
            assert resp.status_code == 400, resp.text
            assert "empty" in resp.text.lower()
    finally:
        await engine.dispose()
