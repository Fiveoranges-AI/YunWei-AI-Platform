"""Schema-level guarantees for the customer-operations ontology (P0 task ①).

These tests don't need a live Postgres — they spin up an in-memory SQLite
engine, run ``Base.metadata.create_all``, then assert:

  - every new ontology table is registered with the mapper
  - every cross-cutting mixin column is present on every core entity
  - the new tables accept reasonable inserts and respect FK constraints
  - cross-tenant isolation: two distinct enterprise ids resolve to two
    distinct database URLs (the per-DB security boundary holds)

If these assertions fail, the ontology contract documented in
``docs/architecture/ontology.md`` has drifted and should be updated in
the same change.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from yunwei_win.db import Base, _build_tenant_url


@pytest.fixture(autouse=True)
def _clean_state():
    """Override the project-wide autouse fixture from ``conftest.py``.

    The default ``_clean_state`` truncates the platform Postgres + Redis
    between tests. These ontology tests are pure-Python — in-memory
    SQLite, no platform DB — so skip the cleanup and avoid forcing the
    test runner to have psycopg / Redis available.
    """
    yield


ONTOLOGY_FULL_MIXIN_COLUMNS = {
    "source_type",
    "source_ref",
    "source_span",
    "confidence",
    "extracted_by",
    "human_verified",
    "verified_by",
    "verified_at",
    "created_by",
    "updated_by",
    "owner_user_id",
    "team_id",
    "is_deleted",
}

ONTOLOGY_MIXIN_NO_CONFIDENCE = ONTOLOGY_FULL_MIXIN_COLUMNS - {"confidence"}

CORE_ENTITY_FULL = [
    "customers",
    "contacts",
    "contracts",
    "orders",
    "order_items",
    "products",
    "invoices",
    "invoice_items",
    "payments",
    "shipments",
    "shipment_items",
    "deliveries",
    "next_actions",
    # InvoicePaymentAllocation: full mixin set minus OwnershipMixin.
]

CORE_ENTITY_PARTIAL = {
    # table -> expected mixin column set
    "customer_risk_signals": ONTOLOGY_MIXIN_NO_CONFIDENCE,
    # allocations row inherits ownership from its parent invoice/payment.
    "invoice_payment_allocations": ONTOLOGY_FULL_MIXIN_COLUMNS
    - {"owner_user_id", "team_id"},
}

NEW_TABLES = [
    "order_items",
    "deliveries",
    "invoice_payment_allocations",
    "next_actions",
    "action_logs",
]


@pytest_asyncio.fixture
async def engine():
    # Importing yunwei_win.models registers every mapper against Base.metadata.
    import yunwei_win.models  # noqa: F401

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(eng.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.mark.asyncio
async def test_new_ontology_tables_exist(engine):
    """Every new operations-layer table is in the live schema."""

    async with engine.begin() as conn:
        existing = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))

    missing = set(NEW_TABLES) - existing
    assert not missing, f"new ontology tables missing from schema: {missing}"


@pytest.mark.asyncio
async def test_full_mixins_present_on_core_entities(engine):
    """Every "core business" table carries the full row-level mixin set."""

    async with engine.begin() as conn:
        inspector = await conn.run_sync(inspect)
        for table in CORE_ENTITY_FULL:
            cols = await conn.run_sync(
                lambda c, t=table: {c2["name"] for c2 in inspect(c).get_columns(t)}
            )
            missing = ONTOLOGY_FULL_MIXIN_COLUMNS - cols
            assert not missing, (
                f"{table} is missing ontology mixin columns: {sorted(missing)}"
            )


@pytest.mark.asyncio
async def test_partial_mixins_present(engine):
    """Tables that opt out of part of the mixin set still carry the rest."""

    async with engine.begin() as conn:
        for table, expected in CORE_ENTITY_PARTIAL.items():
            cols = await conn.run_sync(
                lambda c, t=table: {c2["name"] for c2 in inspect(c).get_columns(t)}
            )
            missing = expected - cols
            assert not missing, (
                f"{table} is missing partial mixin columns: {sorted(missing)}"
            )


@pytest.mark.asyncio
async def test_order_item_round_trip(engine):
    """OrderItem accepts an insert keyed on order_id and respects the FK."""

    from yunwei_win.models import Customer, Order, OrderItem

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="测试客户")
        session.add(cust)
        await session.flush()

        order = Order(
            id=uuid.uuid4(),
            customer_id=cust.id,
            order_no="PO-001",
            order_date=date(2026, 5, 21),
            amount_total=Decimal("100.00"),
        )
        session.add(order)
        await session.flush()

        item = OrderItem(
            order_id=order.id,
            description="Widget",
            quantity=Decimal("2"),
            unit_price=Decimal("50.0000"),
            amount=Decimal("100.0000"),
        )
        session.add(item)
        await session.commit()

        rows = (await session.execute(select(OrderItem))).scalars().all()
        assert len(rows) == 1
        assert rows[0].order_id == order.id
        # mixin defaults
        assert rows[0].human_verified is False
        assert rows[0].is_deleted is False


@pytest.mark.asyncio
async def test_invoice_payment_allocation_many_to_many(engine):
    """One payment clears two invoices; one invoice cleared by two payments."""

    from yunwei_win.models import (
        Customer,
        Invoice,
        InvoicePaymentAllocation,
        Payment,
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="C")
        session.add(cust)
        await session.flush()

        inv_a = Invoice(id=uuid.uuid4(), customer_id=cust.id, invoice_no="A")
        inv_b = Invoice(id=uuid.uuid4(), customer_id=cust.id, invoice_no="B")
        pay_1 = Payment(
            id=uuid.uuid4(), customer_id=cust.id, amount=Decimal("100")
        )
        pay_2 = Payment(
            id=uuid.uuid4(), customer_id=cust.id, amount=Decimal("50")
        )
        session.add_all([inv_a, inv_b, pay_1, pay_2])
        await session.flush()

        # pay_1 splits across inv_a and inv_b
        session.add(InvoicePaymentAllocation(
            invoice_id=inv_a.id, payment_id=pay_1.id, amount=Decimal("60"),
        ))
        session.add(InvoicePaymentAllocation(
            invoice_id=inv_b.id, payment_id=pay_1.id, amount=Decimal("40"),
        ))
        # inv_b further cleared by pay_2
        session.add(InvoicePaymentAllocation(
            invoice_id=inv_b.id, payment_id=pay_2.id, amount=Decimal("50"),
        ))
        await session.commit()

        allocs = (
            await session.execute(select(InvoicePaymentAllocation))
        ).scalars().all()
        assert len(allocs) == 3

        # Uniqueness: same (invoice_id, payment_id) twice should fail.
        async with AsyncSession(engine, expire_on_commit=False) as s2:
            s2.add(InvoicePaymentAllocation(
                invoice_id=inv_a.id, payment_id=pay_1.id,
                amount=Decimal("1"),
            ))
            with pytest.raises(IntegrityError):
                await s2.commit()


@pytest.mark.asyncio
async def test_next_action_targets_polymorphic(engine):
    """NextAction targets an order via the polymorphic pointer + denorm
    customer_id."""

    from yunwei_win.enums import ActionTargetType, NextActionType
    from yunwei_win.models import Customer, NextAction, Order

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="C")
        session.add(cust)
        await session.flush()
        order = Order(id=uuid.uuid4(), customer_id=cust.id)
        session.add(order)
        await session.flush()

        na = NextAction(
            target_entity_type=ActionTargetType.order,
            target_entity_id=order.id,
            customer_id=cust.id,
            action_type=NextActionType.chase_payment,
            title="催客户付尾款",
            talking_script="X总,合同付款节点已到,麻烦帮忙安排一下尾款。",
            due_at=datetime(2026, 5, 25, 9, 0, tzinfo=timezone.utc),
        )
        session.add(na)
        await session.commit()

        rows = (await session.execute(select(NextAction))).scalars().all()
        assert len(rows) == 1
        assert rows[0].target_entity_id == order.id
        assert rows[0].action_type == NextActionType.chase_payment
        assert rows[0].status.value == "suggested"  # default


@pytest.mark.asyncio
async def test_delivery_status_enum(engine):
    """Delivery rows accept the abnormal status path."""

    from yunwei_win.enums import DeliveryStatus
    from yunwei_win.models import Customer, Delivery, Order, Shipment

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="C")
        session.add(cust)
        await session.flush()
        order = Order(id=uuid.uuid4(), customer_id=cust.id)
        session.add(order)
        await session.flush()
        ship = Shipment(
            id=uuid.uuid4(), customer_id=cust.id, order_id=order.id
        )
        session.add(ship)
        await session.flush()

        deliv = Delivery(
            shipment_id=ship.id,
            delivery_date=date(2026, 5, 20),
            signed_by="张三",
            is_abnormal=True,
            abnormal_reason="数量短少 5 件",
            status=DeliveryStatus.abnormal,
        )
        session.add(deliv)
        await session.commit()

        rows = (await session.execute(select(Delivery))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == DeliveryStatus.abnormal
        assert rows[0].is_abnormal is True


@pytest.mark.asyncio
async def test_cross_tenant_isolation_via_db_url():
    """Per-enterprise database URLs diverge for distinct enterprise ids —
    this is the security boundary in lieu of row-level RLS."""

    import os

    # The function reads settings.database_url; ensure a deterministic base.
    os.environ.setdefault("DATABASE_URL", "postgresql://u:p@h/postgres")

    a = _build_tenant_url("acme")
    b = _build_tenant_url("globex")
    assert a != b
    assert "tenant_acme" in a
    assert "tenant_globex" in b


@pytest.mark.asyncio
async def test_soft_delete_default_and_set(engine):
    """is_deleted defaults to False; flipping it to True persists."""

    from yunwei_win.models import Customer

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="A")
        session.add(cust)
        await session.commit()

        assert cust.is_deleted is False

        cust.is_deleted = True
        await session.commit()

        fresh = await session.get(Customer, cust.id)
        assert fresh.is_deleted is True


@pytest.mark.asyncio
async def test_action_log_minimal_audit_only(engine):
    """ActionLog has no soft-delete / ownership / verification columns by
    design — it's append-only. Inserting one with the required fields
    works."""

    from yunwei_win.enums import ActionTargetType, NextActionType
    from yunwei_win.models import ActionLog, Customer

    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=uuid.uuid4(), full_name="C")
        session.add(cust)
        await session.flush()

        log = ActionLog(
            target_entity_type=ActionTargetType.customer,
            target_entity_id=cust.id,
            action_type=NextActionType.follow_up,
            actor="user:42",
            actor_kind="user",
            executed_at=datetime.now(timezone.utc),
            input_summary="电话 5 分钟",
            output_summary="客户口头确认延期一周",
        )
        session.add(log)
        await session.commit()

        rows = (await session.execute(select(ActionLog))).scalars().all()
        assert len(rows) == 1
        # ActionLog deliberately lacks these columns.
        assert not hasattr(rows[0], "is_deleted")
        assert not hasattr(rows[0], "owner_user_id")
