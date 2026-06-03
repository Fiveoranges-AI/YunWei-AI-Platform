"""Per-enterprise async SQLAlchemy engine pool.

Each enterprise gets its own Postgres database (e.g. tenant_yinhu, tenant_acme).
The pool keeps one async engine per enterprise; engines are created lazily on
first access and the database is provisioned (CREATE DATABASE + create_all) if
it does not yet exist.

Routes use this via the standard FastAPI dependency::

    @router.get("/customers")
    async def list_customers(session: AsyncSession = Depends(get_session)):
        ...

The dependency reads the enterprise_id that platform middleware stamped onto
``request.state.enterprise_id`` before the route handler runs. See
``platform_app/main.py`` for the middleware that does the cookie → user →
enterprise lookup.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, Request
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from yunwei_win.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by every per-tenant database."""


def _tenant_db_name(enterprise_id: str) -> str:
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in enterprise_id.lower())
    return f"tenant_{safe}"


def _ensure_async_driver(url: str) -> str:
    """Promote a plain ``postgresql://`` URL to ``postgresql+asyncpg://``.

    Platform-side code (psycopg) wants the bare URL; SQLAlchemy needs an
    explicit driver tag. Accepting both keeps the env-var contract simple.
    """
    if url.startswith("postgresql+") or url.startswith("postgres+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


def _build_tenant_url(enterprise_id: str) -> str:
    """Derive the per-tenant database URL from settings.database_url.

    The base URL points at the platform postgres (typically the ``postgres``
    or ``platform`` database). We swap the database name to the tenant DB.
    """
    base = _ensure_async_driver(settings.database_url)
    if base.startswith("sqlite"):
        return f"sqlite+aiosqlite:///./yinhu_{_tenant_db_name(enterprise_id)}.db"
    parts = urlsplit(base)
    new_path = "/" + _tenant_db_name(enterprise_id)
    return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))


def _admin_url() -> str:
    """A URL pointing at the postgres admin DB so we can CREATE DATABASE."""
    base = _ensure_async_driver(settings.database_url)
    if base.startswith("sqlite"):
        return base
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))


_engines: dict[str, AsyncEngine] = {}
_provisioned: set[str] = set()
_provisioned_ingest_tables: set[str] = set()
_provisioned_schema_ingest_tables: set[str] = set()
_engine_lock = asyncio.Lock()


async def _ensure_database(enterprise_id: str) -> None:
    """Create the per-tenant database if it does not exist, then create_all."""
    if enterprise_id in _provisioned:
        return
    async with _engine_lock:
        if enterprise_id in _provisioned:
            return
        db_name = _tenant_db_name(enterprise_id)
        if not settings.database_url.startswith("sqlite"):
            admin_engine = create_async_engine(_admin_url(), isolation_level="AUTOCOMMIT")
            try:
                async with admin_engine.connect() as conn:
                    exists = await conn.scalar(
                        text("SELECT 1 FROM pg_database WHERE datname = :n").bindparams(n=db_name)
                    )
                    if not exists:
                        await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            finally:
                await admin_engine.dispose()
        # Now run create_all on the tenant DB. Importing models registers them
        # against Base.metadata so create_all sees every table.
        import yunwei_win.models  # noqa: F401  — register mappers

        engine = _get_engine_unlocked(enterprise_id)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _run_lightweight_tenant_migrations(conn)
        _provisioned.add(enterprise_id)


def _get_engine_unlocked(enterprise_id: str) -> AsyncEngine:
    if enterprise_id in _engines:
        return _engines[enterprise_id]
    engine = create_async_engine(
        _build_tenant_url(enterprise_id),
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    _engines[enterprise_id] = engine
    return engine


async def _get_engine(enterprise_id: str) -> AsyncEngine:
    if enterprise_id in _engines:
        return _engines[enterprise_id]
    async with _engine_lock:
        return _get_engine_unlocked(enterprise_id)


async def get_engine_for(enterprise_id: str) -> AsyncEngine:
    """Public: return the engine bound to ``enterprise_id``, provisioning the
    database on first access. Used by the metrics endpoint and any code that
    needs a raw engine instead of a session."""
    await _ensure_database(enterprise_id)
    return await _get_engine(enterprise_id)


async def ensure_ingest_job_tables(engine: AsyncEngine) -> None:
    """Idempotently create ingest_batches + ingest_jobs on an existing tenant
    engine. Safe to call from API request handlers — uses CREATE TABLE IF
    NOT EXISTS via Base.metadata.create_all on the two specific tables.
    """
    import yunwei_win.models  # noqa: F401 — register mappers
    from yunwei_win.models.ingest_job import IngestBatch, IngestJob

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[IngestBatch.__table__, IngestJob.__table__],
                checkfirst=True,
            )
        )


async def ensure_ingest_job_tables_for(enterprise_id: str) -> None:
    """Per-enterprise cached wrapper around ``ensure_ingest_job_tables``.

    API handlers call this once per request before touching the new tables;
    after the first call for an enterprise, the cache short-circuits the
    create_all roundtrip.
    """
    if enterprise_id in _provisioned_ingest_tables:
        return
    engine = await get_engine_for(enterprise_id)
    await ensure_ingest_job_tables(engine)
    _provisioned_ingest_tables.add(enterprise_id)


async def ensure_schema_ingest_tables(engine: AsyncEngine) -> None:
    """Idempotently create the schema-first ingest tables on a tenant engine.

    Covers:
      - schema catalog (company_schema_*, schema_change_proposals)
      - company data foundation (products, invoices, payments, shipments, ...)
      - document_extractions
      - IngestJob.extraction_id

    Safe to call repeatedly. Uses ``CREATE TABLE IF NOT EXISTS`` for tables
    and ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` (Postgres only) for the
    IngestJob extraction link. SQLite test paths get the column via
    ``create_all`` because the IngestJob mapper declares it.
    """
    import yunwei_win.models  # noqa: F401 — register mappers
    from yunwei_win.models.company_schema import (
        CompanySchemaField,
        CompanySchemaTable,
        SchemaChangeProposal,
    )
    from yunwei_win.models.company_data import (
        ContractPaymentMilestone,
        CustomerJournalItem,
        Invoice,
        InvoiceItem,
        Payment,
        Product,
        ProductRequirement,
        Shipment,
        ShipmentItem,
    )
    from yunwei_win.models.document_extraction import DocumentExtraction
    from yunwei_win.models.document_parse import DocumentParse
    from yunwei_win.models.operations import (
        ActionLog,
        Delivery,
        InvoicePaymentAllocation,
        NextAction,
        OrderItem,
    )
    from yunwei_win.models.procurement import (
        GoodsReceipt,
        IssueVoucher,
        Material,
        Payable,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseRequisition,
        PurchaseRequisitionItem,
        StockAlert,
        StockMovement,
        Supplier,
    )
    from yunwei_win.models.finance import (
        ChartOfAccount,
        FixedAsset,
        PeriodOpeningBalance,
    )
    from yunwei_win.models.bom import (
        BillOfMaterials,
        BillOfMaterialsLine,
    )

    new_tables = [
        CompanySchemaTable.__table__,
        CompanySchemaField.__table__,
        SchemaChangeProposal.__table__,
        Product.__table__,
        ProductRequirement.__table__,
        ContractPaymentMilestone.__table__,
        Invoice.__table__,
        InvoiceItem.__table__,
        Payment.__table__,
        Shipment.__table__,
        ShipmentItem.__table__,
        CustomerJournalItem.__table__,
        DocumentParse.__table__,
        DocumentExtraction.__table__,
        # Customer-operations ontology (P0 task ①)
        OrderItem.__table__,
        Delivery.__table__,
        InvoicePaymentAllocation.__table__,
        NextAction.__table__,
        ActionLog.__table__,
        # Procurement / inventory ontology (锦泰 主线)
        Supplier.__table__,
        Material.__table__,
        StockMovement.__table__,
        IssueVoucher.__table__,
        PurchaseRequisition.__table__,
        PurchaseRequisitionItem.__table__,
        PurchaseOrder.__table__,
        PurchaseOrderItem.__table__,
        GoodsReceipt.__table__,
        Payable.__table__,
        StockAlert.__table__,
        # Finance (会企 01/02/03)
        ChartOfAccount.__table__,
        PeriodOpeningBalance.__table__,
        FixedAsset.__table__,
        # BOM (配料单)
        BillOfMaterials.__table__,
        BillOfMaterialsLine.__table__,
    ]

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=new_tables, checkfirst=True,
            )
        )
        await _run_lightweight_tenant_migrations(conn)
        await _backfill_material_unit_costs(conn)
        if conn.dialect.name == "postgresql":
            # Existing tenant DBs were provisioned before extraction_id
            # existed on ingest_jobs. ALTER ... IF NOT EXISTS
            # is idempotent so this is safe on every cold start.
            await conn.execute(text(
                "ALTER TABLE ingest_jobs "
                "ADD COLUMN IF NOT EXISTS extraction_id UUID"
            ))
            # Schema-first contracts: customer_id direct on contract,
            # amount_total / amount_currency captured at contract level,
            # order_id relaxed to nullable so contracts can be ingested
            # without a same-confirm order parent.
            if await _column_exists(conn, "contracts", "order_id"):
                await conn.execute(
                    text("ALTER TABLE contracts ALTER COLUMN order_id DROP NOT NULL")
                )


async def _run_lightweight_tenant_migrations(conn) -> None:
    """Patch existing tenant DBs after SQLAlchemy ``create_all``.

    ``create_all(checkfirst=True)`` creates missing tables but never adds
    columns to tables that already exist. vNext added several nullable/defaulted
    columns to long-lived tenant tables, so every cold start needs a small
    idempotent column migration before ORM queries touch those mappers.
    """

    # Cross-cutting columns added by the customer-operations ontology (P0
    # task ①). The same shape lands on every "core business" table: row-level
    # provenance / human verification / audit / ownership / soft delete.
    # ``RowProvenanceMixin.confidence`` is omitted from tables that already
    # have their own ``confidence`` column (e.g. customer_risk_signals).
    ONTOLOGY_FULL_MIXINS: dict[str, str] = {
        "source_type": "VARCHAR(32)",
        "source_ref": "VARCHAR(255)",
        "source_span": "JSON",
        "confidence": "NUMERIC(3, 2)",
        "extracted_by": "VARCHAR(64)",
        "human_verified": "BOOLEAN NOT NULL DEFAULT FALSE",
        "verified_by": "VARCHAR(128)",
        "verified_at": "TIMESTAMP WITH TIME ZONE",
        "created_by": "VARCHAR(128)",
        "updated_by": "VARCHAR(128)",
        "owner_user_id": "VARCHAR(128)",
        "team_id": "VARCHAR(128)",
        "is_deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    # Same set with ``confidence`` stripped — for tables that already have a
    # ``confidence`` column (e.g. customer_risk_signals) we keep the existing
    # column and add only the source / verification / audit / ownership /
    # soft-delete columns. See ``yunwei_win/models/_mixins.py``.
    ONTOLOGY_MIXINS_NO_CONFIDENCE: dict[str, str] = {
        k: v for k, v in ONTOLOGY_FULL_MIXINS.items() if k != "confidence"
    }

    migrations: dict[str, dict[str, str]] = {
        "company_schema_fields": {
            "field_role": "VARCHAR(32) NOT NULL DEFAULT 'extractable'",
            "review_visible": "BOOLEAN NOT NULL DEFAULT TRUE",
        },
        "customers": {
            "industry": "VARCHAR",
            "notes": "TEXT",
            **ONTOLOGY_FULL_MIXINS,
        },
        "contacts": {
            "title": "VARCHAR",
            "phone": "VARCHAR",
            "address": "VARCHAR",
            "wechat_id": "VARCHAR",
            "needs_review": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_key_decision_maker": "BOOLEAN NOT NULL DEFAULT FALSE",
            **ONTOLOGY_FULL_MIXINS,
        },
        "contracts": {
            "customer_id": "UUID",
            "amount_total": "NUMERIC(18, 4)",
            "amount_currency": "VARCHAR(8)",
            "delivery_terms": "TEXT",
            "penalty_terms": "TEXT",
            "payment_terms": "TEXT",
            "status": "VARCHAR(32)",
            **ONTOLOGY_FULL_MIXINS,
        },
        "orders": {
            "order_no": "VARCHAR(128)",
            "contract_id": "UUID",
            "order_date": "DATE",
            "status": "VARCHAR(32)",
            **ONTOLOGY_FULL_MIXINS,
        },
        "products": {
            "reference_unit_price": "NUMERIC(18, 4)",
            **ONTOLOGY_FULL_MIXINS,
        },
        "invoices": {
            "buyer_tax_id": "VARCHAR(32)",
            "contract_id": "UUID",
            **ONTOLOGY_FULL_MIXINS,
        },
        "invoice_items": {
            **ONTOLOGY_FULL_MIXINS,
        },
        "payments": {
            "amount_due": "NUMERIC(18, 4)",
            "due_date": "DATE",
            "status": "VARCHAR(32)",
            **ONTOLOGY_FULL_MIXINS,
        },
        "shipments": {
            **ONTOLOGY_FULL_MIXINS,
        },
        "shipment_items": {
            **ONTOLOGY_FULL_MIXINS,
        },
        "customer_risk_signals": {
            "risk_score": "NUMERIC(5, 2)",
            "target_entity_type": "VARCHAR(32)",
            "target_entity_id": "UUID",
            **ONTOLOGY_MIXINS_NO_CONFIDENCE,
        },
        "customer_tasks": {
            "document_id": "UUID",
            "assignee": "VARCHAR(128)",
            "priority": "VARCHAR(16) NOT NULL DEFAULT 'normal'",
            "status": "VARCHAR(16) NOT NULL DEFAULT 'open'",
        },
        "document_extractions": {
            "parse_id": "UUID",
            "provider": "VARCHAR(64)",
            "model": "VARCHAR(128)",
            "selected_tables": "JSON",
            "extraction": "JSON",
            "extraction_metadata": "JSON",
            "validation_warnings": "JSON",
            "entity_resolution": "JSON",
            "review_version": "INTEGER NOT NULL DEFAULT 0",
            "locked_by": "VARCHAR(128)",
            "lock_token": "UUID",
            "lock_expires_at": "TIMESTAMP WITH TIME ZONE",
            "last_reviewed_by": "VARCHAR(128)",
            "last_reviewed_at": "TIMESTAMP WITH TIME ZONE",
            "confirmed_by": "VARCHAR(64)",
            "confirmed_at": "TIMESTAMP WITH TIME ZONE",
        },
        "field_provenance": {
            "parse_id": "UUID",
            "extraction_id": "UUID",
            "source_refs": "JSON",
            "review_action": "VARCHAR(32)",
        },
        "ingest_jobs": {
            "extraction_id": "UUID",
        },
        # Procurement / inventory (锦泰 主线 — finance reports 加 last_unit_cost)
        "procurement_materials": {
            "last_unit_cost": "NUMERIC(18, 4) NOT NULL DEFAULT 0",
        },
    }

    for table_name, columns in migrations.items():
        if not await _table_exists(conn, table_name):
            continue
        for column_name, ddl in columns.items():
            await _add_column_if_missing(conn, table_name, column_name, ddl)


async def _table_exists(conn, table_name: str) -> bool:
    return await conn.run_sync(
        lambda sync_conn: inspect(sync_conn).has_table(table_name)
    )


async def _add_column_if_missing(
    conn,
    table_name: str,
    column_name: str,
    column_ddl: str,
) -> None:
    exists = await _column_exists(conn, table_name, column_name)
    if not exists:
        await conn.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")
        )


async def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return await conn.run_sync(
        lambda sync_conn: column_name
        in {
            col["name"]
            for col in inspect(sync_conn).get_columns(table_name)
        }
    )


async def _backfill_material_unit_costs(conn) -> None:
    """Cold-start backfill: 把 ``procurement_materials.last_unit_cost = 0`` 的
    物料按它"最近一笔 received PO item.unit_price" 回填.

    Idempotent — 已有 unit_cost > 0 的物料不会被覆盖. Cross-dialect (用 Python
    端聚合最新值, 不依赖 ``DISTINCT ON`` / ``ROW_NUMBER``). 表/列缺失时安全返回.
    """
    if not await _table_exists(conn, "procurement_materials"):
        return
    if not await _table_exists(conn, "procurement_purchase_order_items"):
        return
    if not await _column_exists(conn, "procurement_materials", "last_unit_cost"):
        return

    rows = (await conn.execute(text("""
        SELECT m.id AS material_id, poi.unit_price, po.received_at
        FROM procurement_materials m
        JOIN procurement_purchase_order_items poi ON poi.material_id = m.id
        JOIN procurement_purchase_orders po ON po.id = poi.po_id
        WHERE (m.last_unit_cost IS NULL OR m.last_unit_cost = 0)
          AND poi.unit_price IS NOT NULL
          AND po.received_at IS NOT NULL
        ORDER BY po.received_at DESC
    """))).all()

    latest_by_material: dict = {}
    for row in rows:
        mid = row.material_id
        if mid not in latest_by_material:
            latest_by_material[mid] = row.unit_price

    for mid, price in latest_by_material.items():
        await conn.execute(
            text("UPDATE procurement_materials SET last_unit_cost = :p WHERE id = :id"),
            {"p": price, "id": mid},
        )


async def ensure_schema_ingest_tables_for(enterprise_id: str) -> None:
    """Per-enterprise cached wrapper around ``ensure_schema_ingest_tables``."""
    if enterprise_id in _provisioned_schema_ingest_tables:
        return
    engine = await get_engine_for(enterprise_id)
    await ensure_schema_ingest_tables(engine)
    _provisioned_schema_ingest_tables.add(enterprise_id)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session bound to the caller's enterprise.

    The enterprise_id is set on ``request.state`` by platform middleware after
    looking up the user from the ``app_session`` cookie. Routes that hit this
    without authentication get a 401.
    """
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if not enterprise_id:
        raise HTTPException(status_code=401, detail="not_authenticated")
    engine = await get_engine_for(enterprise_id)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


async def dispose_all() -> None:
    """Tear down every cached engine. Called on app shutdown."""
    for engine in list(_engines.values()):
        await engine.dispose()
    _engines.clear()
    _provisioned.clear()
    _provisioned_ingest_tables.clear()
    _provisioned_schema_ingest_tables.clear()
