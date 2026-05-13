"""Materialize the canonical 5 silver tables into ``silver-live.duckdb``.

Idempotent: ``ensure_silver_tables`` may be called repeatedly; CREATE TABLE
IF NOT EXISTS is used throughout. The DDL is derived from
``silver-canonical.yaml`` so schema growth in the kernel propagates after
``ops/sync_silver_canonical.py`` is run.
"""
from __future__ import annotations
import duckdb
from . import paths, silver_schema
from .silver_schema import Column


def _yaml_type_to_duckdb(c: Column) -> str:
    t = c.type
    if t == "string" or t == "enum":
        return "VARCHAR"
    if t == "date":
        return "DATE"
    if t == "datetime":
        return "TIMESTAMP"
    if t == "boolean":
        return "BOOLEAN"
    if t == "json":
        return "JSON"
    if t.startswith("decimal"):
        return t.upper()
    return "VARCHAR"


def _column_ddl(c: Column) -> str:
    sql_type = _yaml_type_to_duckdb(c)
    null_sql = "" if c.nullable else " NOT NULL"
    return f'"{c.name}" {sql_type}{null_sql}'


def open_silver(client_id: str, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open silver-live.duckdb. Creates parent dirs if needed."""
    paths.ensure_tenant_dirs(client_id)
    return duckdb.connect(str(paths.silver_live_path(client_id)), read_only=read_only)


def ensure_silver_tables(client_id: str) -> None:
    """Create the 5 canonical silver tables if absent. Idempotent."""
    schema = silver_schema.load()
    con = open_silver(client_id)
    try:
        for tname, table in schema.tables.items():
            cols_ddl = ", ".join(_column_ddl(c) for c in table.columns)
            pk = ", ".join(f'"{c}"' for c in table.primary_key)
            con.execute(
                f'CREATE TABLE IF NOT EXISTS "{tname}" ({cols_ddl}, PRIMARY KEY ({pk}))'
            )
    finally:
        con.close()
