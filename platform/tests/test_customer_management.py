"""Tests for the customer-management endpoints (Win UI maintenance flows).

Covered surface:

- PATCH  /api/customers/{id}
- PUT    /api/customers/{id}/contacts
- DELETE /api/customers/{id}
- DELETE /api/customers?confirm=...

Uses the same in-memory SQLite pattern as ``test_ingest_auto_flow.py``: we
override the autouse Postgres-truncating fixture, enable SQLite foreign-key
enforcement (so RESTRICT / CASCADE bugs that fail in prod also fail here),
and hit the routes through ``httpx.AsyncClient(ASGITransport)``.
"""

from __future__ import annotations

from uuid import UUID

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    Contact,
    ContactRole,
    Contract,
    Customer,
    CustomerEvent,
    CustomerEventType,
    CustomerMemoryItem,
    Document,
    DocumentType,
    EntityType,
    FieldProvenance,
    MemoryKind,
    Order,
)


# ---------- helpers -------------------------------------------------------


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

    from yunwei_win.api.customer_management import router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _seed_customer(
    engine,
    *,
    full_name: str = "测试客户有限公司",
    short_name: str | None = "测试",
    address: str | None = "上海市",
    tax_id: str | None = None,
) -> UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        c = Customer(
            full_name=full_name,
            short_name=short_name,
            address=address,
            tax_id=tax_id,
        )
        session.add(c)
        await session.commit()
        return c.id


# ---------- PATCH /api/customers/{id} ------------------------------------


@pytest.mark.asyncio
async def test_patch_customer_updates_fields() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        customer_id = await _seed_customer(engine)
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                f"/api/customers/{customer_id}",
                json={
                    "full_name": "新名称有限公司",
                    "short_name": "新简称",
                    "address": "北京市",
                    "tax_id": "91310000XXXXXXXX",
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["full_name"] == "新名称有限公司"
            assert body["short_name"] == "新简称"
            assert body["address"] == "北京市"
            assert body["tax_id"] == "91310000XXXXXXXX"

        async with AsyncSession(engine, expire_on_commit=False) as session:
            c = (
                await session.execute(select(Customer).where(Customer.id == customer_id))
            ).scalar_one()
            assert c.full_name == "新名称有限公司"
            assert c.short_name == "新简称"
            assert c.address == "北京市"
            assert c.tax_id == "91310000XXXXXXXX"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_patch_customer_404_missing() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unknown = "00000000-0000-0000-0000-000000000000"
            resp = await client.patch(
                f"/api/customers/{unknown}",
                json={"full_name": "X"},
            )
            assert resp.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_patch_customer_rejects_empty_full_name() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        customer_id = await _seed_customer(engine)
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                f"/api/customers/{customer_id}",
                json={"full_name": ""},
            )
            assert resp.status_code == 400

        # Untouched.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            c = (
                await session.execute(select(Customer).where(Customer.id == customer_id))
            ).scalar_one()
            assert c.full_name == "测试客户有限公司"
    finally:
        await engine.dispose()


# ---------- PUT /api/customers/{id}/contacts -----------------------------


@pytest.mark.asyncio
async def test_put_contacts_creates_updates_deletes() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        customer_id = await _seed_customer(engine)

        # Seed two existing contacts and a provenance row for c2 (the one we
        # will delete) — that provenance row must also be cleaned up.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            c1 = Contact(
                customer_id=customer_id,
                name="王经理",
                role=ContactRole.buyer,
                mobile="13800000001",
            )
            c2 = Contact(
                customer_id=customer_id,
                name="李工",
                role=ContactRole.delivery,
                mobile="13800000002",
            )
            session.add_all([c1, c2])
            await session.flush()
            c1_id, c2_id = c1.id, c2.id

            # Need a Document for the provenance row's FK.
            doc = Document(
                type=DocumentType.business_card,
                file_url="/tmp/card.jpg",
                original_filename="card.jpg",
                file_sha256="a" * 64,
                file_size_bytes=10,
            )
            session.add(doc)
            await session.flush()

            prov = FieldProvenance(
                document_id=doc.id,
                entity_type=EntityType.contact,
                entity_id=c2_id,
                field_name="name",
                value="李工",
            )
            session.add(prov)
            await session.commit()

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/customers/{customer_id}/contacts",
                json={
                    "contacts": [
                        {
                            "id": str(c1_id),
                            "name": "王经理（更新）",
                            "role": "buyer",
                            "mobile": "13900000001",
                        },
                        {
                            "name": "赵工",
                            "role": "acceptance",
                            "mobile": "13800000003",
                        },
                    ]
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["customer_id"] == str(customer_id)
            names = sorted(c["name"] for c in body["contacts"])
            assert names == ["王经理（更新）", "赵工"]

        async with AsyncSession(engine, expire_on_commit=False) as session:
            contacts = (
                await session.execute(
                    select(Contact).where(Contact.customer_id == customer_id)
                )
            ).scalars().all()
            assert len(contacts) == 2
            by_name = {c.name: c for c in contacts}
            assert by_name["王经理（更新）"].id == c1_id
            assert by_name["王经理（更新）"].mobile == "13900000001"
            assert "赵工" in by_name
            # c2 is gone.
            removed = (
                await session.execute(select(Contact).where(Contact.id == c2_id))
            ).scalar_one_or_none()
            assert removed is None
            # And its provenance row is gone.
            orphan = (
                await session.execute(
                    select(FieldProvenance).where(
                        FieldProvenance.entity_type == EntityType.contact,
                        FieldProvenance.entity_id == c2_id,
                    )
                )
            ).scalars().all()
            assert orphan == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_contacts_rejects_empty_name() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        customer_id = await _seed_customer(engine)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            c1 = Contact(
                customer_id=customer_id,
                name="王经理",
                role=ContactRole.buyer,
            )
            session.add(c1)
            await session.commit()

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/customers/{customer_id}/contacts",
                json={
                    "contacts": [
                        {"name": "李工", "role": "buyer"},
                        {"name": "", "role": "buyer"},
                    ]
                },
            )
            assert resp.status_code == 400

        # DB unchanged: still exactly the one seeded contact.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (
                await session.execute(
                    select(Contact).where(Contact.customer_id == customer_id)
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].name == "王经理"
    finally:
        await engine.dispose()


# ---------- DELETE /api/customers/{id} -----------------------------------


@pytest.mark.asyncio
async def test_delete_single_customer_cascades() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        # Build a customer with the full graph: contact, order, contract,
        # event, memory_item, provenance, document pointing at customer.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customer = Customer(full_name="客户A有限公司", short_name="A")
            session.add(customer)
            await session.flush()
            cid = customer.id

            contact = Contact(customer_id=cid, name="王经理", role=ContactRole.buyer)
            session.add(contact)

            order = Order(customer_id=cid, amount_total=100000, amount_currency="CNY")
            session.add(order)
            await session.flush()

            contract = Contract(
                order_id=order.id,
                contract_no_external="T-001",
                payment_milestones=[],
            )
            session.add(contract)

            event = CustomerEvent(
                customer_id=cid,
                title="签约",
                event_type=CustomerEventType.contract_signed,
            )
            session.add(event)

            memory = CustomerMemoryItem(
                customer_id=cid,
                content="偏好周一沟通",
                kind=MemoryKind.preference,
            )
            session.add(memory)

            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/c.pdf",
                original_filename="c.pdf",
                file_sha256="a" * 64,
                file_size_bytes=10,
                assigned_customer_id=cid,
                detected_customer_id=cid,
            )
            session.add(doc)
            await session.flush()

            prov = FieldProvenance(
                document_id=doc.id,
                entity_type=EntityType.customer,
                entity_id=cid,
                field_name="full_name",
                value="客户A有限公司",
            )
            session.add(prov)
            await session.commit()
            doc_id = doc.id

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/customers/{cid}")
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["customer_id"] == str(cid)
            assert body["deleted"] is True
            counts = body["deleted_counts"]
            assert counts["contacts"] == 1
            assert counts["orders"] == 1
            assert counts["contracts"] == 1
            assert counts["events"] == 1
            assert counts["memory_items"] == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            assert (
                await session.execute(select(Customer).where(Customer.id == cid))
            ).scalar_one_or_none() is None
            assert (
                await session.execute(select(Contact).where(Contact.customer_id == cid))
            ).scalars().all() == []
            assert (
                await session.execute(select(Order).where(Order.customer_id == cid))
            ).scalars().all() == []
            assert (
                await session.execute(select(Contract))
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(CustomerEvent).where(CustomerEvent.customer_id == cid)
                )
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(CustomerMemoryItem).where(CustomerMemoryItem.customer_id == cid)
                )
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(FieldProvenance).where(
                        FieldProvenance.entity_type == EntityType.customer,
                        FieldProvenance.entity_id == cid,
                    )
                )
            ).scalars().all() == []
            # Document is preserved; pointers nulled.
            d = (
                await session.execute(select(Document).where(Document.id == doc_id))
            ).scalar_one()
            assert d.assigned_customer_id is None
            assert d.detected_customer_id is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_customer_404() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unknown = "00000000-0000-0000-0000-000000000000"
            resp = await client.delete(f"/api/customers/{unknown}")
            assert resp.status_code == 404
    finally:
        await engine.dispose()


# ---------- DELETE /api/customers (bulk) ---------------------------------


@pytest.mark.asyncio
async def test_delete_all_requires_confirm() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        cid = await _seed_customer(engine)

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing confirm
            resp = await client.delete("/api/customers")
            assert resp.status_code == 400
            # Wrong confirm
            resp = await client.delete("/api/customers?confirm=nope")
            assert resp.status_code == 400
            # Right confirm
            resp = await client.delete(
                "/api/customers?confirm=DELETE_ALL_IMPORTED_CUSTOMERS"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["deleted_customers"] == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (await session.execute(select(Customer))).scalars().all()
            assert rows == []
            # Sanity: the originally-seeded customer is gone.
            assert (
                await session.execute(select(Customer).where(Customer.id == cid))
            ).scalar_one_or_none() is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_all_clears_multiple() -> None:
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        # Three customers, each with one contact + one order.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            ids = []
            for i in range(3):
                c = Customer(full_name=f"客户{i}", short_name=f"{i}")
                session.add(c)
                await session.flush()
                ids.append(c.id)
                session.add(
                    Contact(
                        customer_id=c.id,
                        name=f"联系人{i}",
                        role=ContactRole.buyer,
                    )
                )
                session.add(
                    Order(
                        customer_id=c.id,
                        amount_total=1000 + i,
                        amount_currency="CNY",
                    )
                )
            await session.commit()

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                "/api/customers?confirm=DELETE_ALL_IMPORTED_CUSTOMERS"
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["deleted_customers"] == 3
            assert body["deleted_counts"]["contacts"] == 3
            assert body["deleted_counts"]["orders"] == 3

        async with AsyncSession(engine, expire_on_commit=False) as session:
            assert (
                (await session.execute(select(Customer))).scalars().all()
            ) == []
            assert (
                (await session.execute(select(Contact))).scalars().all()
            ) == []
            assert (
                (await session.execute(select(Order))).scalars().all()
            ) == []
    finally:
        await engine.dispose()
