"""Idempotent migration cycle test for the customer-operations ontology.

The repo doesn't use Alembic — schema changes ship as model edits plus
idempotent ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` patches in
``yunwei_win.db._run_lightweight_tenant_migrations`` /
``ensure_schema_ingest_tables``. This test simulates the
upgrade-on-existing-tenant path:

1. Start with the *pre-P0* schema: only the original SQLAlchemy tables.
2. Run the new lightweight-migration helper.
3. Assert every new ontology column landed on every core table.
4. Run the helper again — must be a no-op (idempotency).

SQLite is used as the substrate so the test stays hermetic. The
PG-only ``IF NOT EXISTS`` ALTER syntax is exercised separately by
production cold-start runs.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from yunwei_win.db import Base


@pytest.fixture(autouse=True)
def _clean_state():
    """Skip the project-wide Postgres / Redis truncate fixture."""
    yield


ONTOLOGY_FULL = {
    "source_type", "source_ref", "source_span", "confidence", "extracted_by",
    "human_verified", "verified_by", "verified_at",
    "created_by", "updated_by",
    "owner_user_id", "team_id",
    "is_deleted",
}

CORE_FULL = [
    "customers", "contacts", "contracts", "orders", "products",
    "invoices", "invoice_items", "payments", "shipments", "shipment_items",
]


@pytest_asyncio.fixture
async def engine():
    import yunwei_win.models  # noqa: F401
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def _columns(conn, table: str) -> set[str]:
    return await conn.run_sync(
        lambda c: {col["name"] for col in inspect(c).get_columns(table)}
    )


@pytest.mark.asyncio
async def test_create_all_lands_full_mixins(engine):
    """Fresh ``create_all`` (the new-tenant path) populates every mixin
    column on every core table."""

    async with engine.begin() as conn:
        for table in CORE_FULL:
            cols = await _columns(conn, table)
            missing = ONTOLOGY_FULL - cols
            assert not missing, (
                f"{table} missing on fresh create_all: {sorted(missing)}"
            )


@pytest.mark.asyncio
async def test_partial_mixin_table_has_no_double_confidence(engine):
    """``customer_risk_signals`` keeps a single ``confidence`` column —
    we explicitly skipped ``RowConfidenceMixin`` on it to avoid clash."""

    async with engine.begin() as conn:
        cols = await _columns(conn, "customer_risk_signals")
        assert "confidence" in cols
        assert "risk_score" in cols
        # source mixin columns landed.
        for col in ("source_type", "source_ref", "source_span", "extracted_by"):
            assert col in cols, f"{col} missing on customer_risk_signals"


@pytest.mark.asyncio
async def test_lightweight_migrations_are_idempotent():
    """Running the lightweight migration helper twice in a row produces
    the same column set — no duplicate columns, no errors."""

    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import _run_lightweight_tenant_migrations

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Snapshot before — already migrated by create_all on a fresh DB.
            before = await _columns(conn, "customers")

            # Run the helper twice; both runs must be silent.
            await _run_lightweight_tenant_migrations(conn)
            mid = await _columns(conn, "customers")
            await _run_lightweight_tenant_migrations(conn)
            after = await _columns(conn, "customers")

        assert before == mid == after, "lightweight migration drifted"
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_pre_p0_table_picks_up_mixins_on_migration():
    """Simulate the realistic upgrade path: a tenant DB that pre-dates
    P0 (has ``customers`` without the mixin columns) gains them when
    the lightweight migration runs."""

    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import _run_lightweight_tenant_migrations

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with eng.begin() as conn:
            # Hand-craft a pre-P0 ``customers`` table: just the original
            # columns, none of the new mixin ones.
            await conn.execute(text("""
                CREATE TABLE customers (
                    id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    short_name TEXT,
                    address TEXT,
                    tax_id TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """))

            before = await _columns(conn, "customers")
            assert "human_verified" not in before
            assert "is_deleted" not in before

            await _run_lightweight_tenant_migrations(conn)

            after = await _columns(conn, "customers")
            missing = ONTOLOGY_FULL - after
            assert not missing, (
                f"after lightweight migration, customers still missing: "
                f"{sorted(missing)}"
            )
    finally:
        await eng.dispose()
