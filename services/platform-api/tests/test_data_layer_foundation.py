"""M1 Foundation tests (docs/data-layer.md §8 M1).

Covers:
- bronze_files / silver_mappings tables created by migration 003
- repo.py CRUD + checksum dedup helper used by AC-D2
- paths.ensure_tenant_dirs creates the bronze/* + _uploads layout
- silver_schema loads canonical 5 tables
- shared duckdb_silver fixture works for downstream M2+ tests
"""
from __future__ import annotations
from pathlib import Path
import duckdb
import pytest
from platform_app import db
from platform_app.data_layer import paths, repo, silver_schema
from platform_app.settings import settings


# ─── fixtures ───────────────────────────────────────────────────

@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch) -> Path:
    """Override settings.data_root → an isolated tmp path for the test."""
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def duckdb_silver(tmp_data_root) -> Path:
    """Bootstrap an empty silver-live.duckdb for a synthetic tenant.

    Returned path can be opened by downstream M2+ tests; the file already
    has the canonical 5 silver tables created (no rows).
    """
    client = "test_tenant"
    paths.ensure_tenant_dirs(client)
    db_path = paths.silver_live_path(client)

    schema = silver_schema.load()
    con = duckdb.connect(str(db_path))
    try:
        for tname, table in schema.tables.items():
            cols_sql = ", ".join(_col_ddl(c) for c in table.columns)
            pk_sql = f", PRIMARY KEY ({', '.join(table.primary_key)})"
            con.execute(f"CREATE TABLE IF NOT EXISTS {tname} ({cols_sql}{pk_sql})")
    finally:
        con.close()
    return db_path


def _col_ddl(c) -> str:
    # Minimal yaml-type → DuckDB-type mapping; extended as M2+ needs land.
    t = c.type
    if t == "string":
        sql_type = "VARCHAR"
    elif t == "date":
        sql_type = "DATE"
    elif t == "datetime":
        sql_type = "TIMESTAMP"
    elif t == "boolean":
        sql_type = "BOOLEAN"
    elif t == "json":
        sql_type = "JSON"
    elif t == "enum":
        sql_type = "VARCHAR"  # enforce values at write time, not schema time
    elif t.startswith("decimal"):
        sql_type = t.upper()
    else:
        sql_type = "VARCHAR"
    null_sql = "" if c.nullable else " NOT NULL"
    return f"{c.name} {sql_type}{null_sql}"


# ─── 003 migration ──────────────────────────────────────────────

def test_migration_003_creates_data_layer_tables():
    db.init()
    rows = db.main().execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"bronze_files", "silver_mappings"} <= names


# ─── repo helpers ───────────────────────────────────────────────

def test_bronze_files_insert_and_lookup():
    db.init()
    fid = repo.insert_bronze_file(
        client_id="yinhu",
        source_type="file_excel",
        bronze_path="bronze/file_excel/2026-05-06/sales__Sheet1.parquet",
        original_filename="sales.xlsx",
        sheet_name="Sheet1",
        row_count=42,
        checksum_sha256="abc123",
        uploaded_by="user_eason",
        meta={"sheet_name": "Sheet1", "row_count": 42},
    )
    assert fid

    files = repo.list_bronze_files("yinhu")
    assert len(files) == 1
    assert files[0]["original_filename"] == "sales.xlsx"
    assert files[0]["row_count"] == 42

    # checksum dedup → AC-D2
    hit = repo.find_by_checksum("yinhu", "abc123")
    assert hit is not None and hit["id"] == fid


def test_bronze_files_filter_by_source_and_soft_delete():
    db.init()
    fid_excel = repo.insert_bronze_file(
        client_id="yinhu", source_type="file_excel",
        bronze_path="bronze/file_excel/x.parquet",
        original_filename="x.xlsx", sheet_name="A", row_count=1,
        checksum_sha256="aaa", uploaded_by=None, meta={},
    )
    repo.insert_bronze_file(
        client_id="yinhu", source_type="manual_ui",
        bronze_path="bronze/manual_ui/y.parquet",
        original_filename=None, sheet_name=None, row_count=2,
        checksum_sha256=None, uploaded_by=None, meta={},
    )

    excel_only = repo.list_bronze_files("yinhu", "file_excel")
    assert {r["source_type"] for r in excel_only} == {"file_excel"}

    repo.soft_delete_bronze_file(fid_excel)
    assert repo.list_bronze_files("yinhu", "file_excel") == []
    assert repo.find_by_checksum("yinhu", "aaa") is None


def test_silver_mapping_insert_and_list():
    db.init()
    mid = repo.insert_silver_mapping(
        client_id="yinhu",
        source_type="file_excel",
        filename_pattern="sales*.xlsx",
        sheet_pattern="Sheet1",
        silver_table="orders",
        column_map={"order_no": "order_number", "客户": "customer_name_snapshot"},
        bronze_columns_snapshot=["order_no", "客户", "金额"],
        created_by="user_eason",
    )
    assert mid

    rows = repo.list_silver_mappings("yinhu", "file_excel")
    assert len(rows) == 1
    assert rows[0]["silver_table"] == "orders"


# ─── paths ──────────────────────────────────────────────────────

def test_ensure_tenant_dirs_creates_full_layout(tmp_data_root):
    root = paths.ensure_tenant_dirs("yinhu")
    assert root.is_dir()
    assert (root / "_uploads").is_dir()
    for source_type in paths.SOURCE_TYPES:
        assert (root / "bronze" / source_type).is_dir(), source_type
    # Idempotent
    paths.ensure_tenant_dirs("yinhu")


def test_ensure_tenant_dirs_rejects_path_traversal(tmp_data_root):
    with pytest.raises(ValueError):
        paths.ensure_tenant_dirs("../escape")
    with pytest.raises(ValueError):
        paths.ensure_tenant_dirs("a/b")


def test_bronze_dir_rejects_unknown_source_type(tmp_data_root):
    with pytest.raises(ValueError):
        paths.bronze_dir("yinhu", "totally_made_up")


# ─── silver_schema ──────────────────────────────────────────────

def test_silver_schema_loads_five_canonical_tables():
    schema = silver_schema.reload()
    assert set(schema.tables) == {
        "customers", "orders", "order_items",
        "order_source_records", "boss_query_logs",
    }
    # Spec invariant: customers/orders carry source_type + source_lineage
    for tname in ("customers", "orders"):
        col_names = {c.name for c in schema.tables[tname].columns}
        assert "source_type" in col_names
        assert "source_lineage" in col_names


# ─── duckdb fixture ─────────────────────────────────────────────

def test_duckdb_silver_fixture_has_all_canonical_tables(duckdb_silver):
    con = duckdb.connect(str(duckdb_silver))
    try:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        ).fetchall()
    finally:
        con.close()
    names = {r[0] for r in rows}
    assert {"customers", "orders", "order_items",
            "order_source_records", "boss_query_logs"} <= names
