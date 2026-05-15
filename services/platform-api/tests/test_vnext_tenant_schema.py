from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

import yunwei_win.models  # noqa: F401
from yunwei_win.db import Base, ensure_schema_ingest_tables
from yunwei_win.models.company_schema import CompanySchemaField
from yunwei_win.models.document_extraction import DocumentExtraction
from yunwei_win.models.document_parse import DocumentParse
from yunwei_win.models.field_provenance import FieldProvenance
from yunwei_win.services.company_schema import (
    DEFAULT_COMPANY_SCHEMA,
    ensure_default_company_schema,
    get_company_schema,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


def test_vnext_models_are_registered():
    assert "document_parses" in Base.metadata.tables
    assert "document_extractions" in Base.metadata.tables
    assert "company_schema_fields" in Base.metadata.tables
    assert "field_provenance" in Base.metadata.tables


def test_document_parse_model_has_artifact_columns():
    cols = DocumentParse.__table__.columns
    assert {
        "document_id",
        "provider",
        "model",
        "status",
        "artifact",
        "raw_metadata",
        "warnings",
        "error_message",
    }.issubset(cols.keys())


def test_document_extraction_model_has_vnext_review_columns():
    cols = DocumentExtraction.__table__.columns
    assert {
        "document_id",
        "parse_id",
        "provider",
        "model",
        "selected_tables",
        "extraction",
        "extraction_metadata",
        "validation_warnings",
        "entity_resolution",
        "review_draft",
        "review_version",
        "locked_by",
        "lock_token",
        "lock_expires_at",
        "last_reviewed_by",
        "last_reviewed_at",
        "confirmed_by",
        "confirmed_at",
    }.issubset(cols.keys())


def test_company_schema_fields_have_roles_and_visibility():
    cols = CompanySchemaField.__table__.columns
    assert "field_role" in cols.keys()
    assert "review_visible" in cols.keys()


@pytest.mark.asyncio
async def test_ensure_schema_ingest_tables_migrates_legacy_company_schema_fields():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE company_schema_tables (
                        id CHAR(32) PRIMARY KEY,
                        table_name VARCHAR(128) NOT NULL,
                        label VARCHAR(255) NOT NULL,
                        purpose TEXT,
                        category VARCHAR(32) NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_company_schema_table_version
                            UNIQUE (table_name, version)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE company_schema_fields (
                        id CHAR(32) PRIMARY KEY,
                        table_id CHAR(32) NOT NULL,
                        field_name VARCHAR(128) NOT NULL,
                        label VARCHAR(255) NOT NULL,
                        data_type VARCHAR(32) NOT NULL,
                        required BOOLEAN NOT NULL DEFAULT 0,
                        is_array BOOLEAN NOT NULL DEFAULT 0,
                        enum_values JSON,
                        default_value JSON,
                        description TEXT,
                        extraction_hint TEXT,
                        validation JSON,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_company_schema_field_name
                            UNIQUE (table_id, field_name),
                        FOREIGN KEY(table_id)
                            REFERENCES company_schema_tables(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
            await conn.run_sync(Base.metadata.create_all)

        await ensure_schema_ingest_tables(engine)

        async with engine.begin() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: {
                    col["name"]: col
                    for col in inspect(sync_conn).get_columns(
                        "company_schema_fields"
                    )
                }
            )
        assert "field_role" in columns
        assert "review_visible" in columns
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await ensure_default_company_schema(session)
            catalog = await get_company_schema(session)
        fields = {
            (table["table_name"], field["field_name"]): field
            for table in catalog["tables"]
            for field in table["fields"]
        }
        assert fields[("customers", "full_name")]["field_role"] == "identity_key"
        assert fields[("orders", "customer_id")]["review_visible"] is False
    finally:
        await engine.dispose()


def test_field_provenance_records_parse_extraction_and_review_action():
    cols = FieldProvenance.__table__.columns
    assert {"parse_id", "extraction_id", "source_refs", "review_action"}.issubset(cols.keys())


@pytest.mark.asyncio
async def test_default_catalog_classifies_system_fields_as_hidden():
    engine, session = await _session()
    try:
        await ensure_default_company_schema(session)
        catalog = await get_company_schema(session)
        fields = {
            (table["table_name"], field["field_name"]): field
            for table in catalog["tables"]
            for field in table["fields"]
        }
        assert fields[("orders", "customer_id")]["field_role"] == "system_link"
        assert fields[("orders", "customer_id")]["review_visible"] is False
        assert fields[("customers", "full_name")]["field_role"] == "identity_key"
        assert fields[("customers", "full_name")]["review_visible"] is True
        assert fields[("contacts", "title")]["field_role"] == "extractable"
        assert ("contacts", "needs_review") not in fields
        assert fields[("customer_tasks", "assignee")]["field_role"] == "extractable"
        assert ("customer_tasks", "owner") not in fields
    finally:
        await session.close()
        await engine.dispose()


def test_default_catalog_contains_only_vnext_target_tables():
    names = {entry["table_name"] for entry in DEFAULT_COMPANY_SCHEMA}
    assert names == {
        "customers",
        "contacts",
        "products",
        "product_requirements",
        "orders",
        "contracts",
        "contract_payment_milestones",
        "invoices",
        "invoice_items",
        "payments",
        "shipments",
        "shipment_items",
        "customer_journal_items",
        "customer_tasks",
    }
