"""Manual entry — double-write to bronze + silver (docs/data-layer.md §4.4).

The user-entered row goes both to:
1. ``bronze/manual_ui/<YYYY-MM-DD>/<entry_id>.parquet`` (audit trail)
2. ``silver-live.duckdb`` directly (no transform — this is the only
   "short-circuit" path; bronze still mandatory for audit)

Re-entry of the same primary key is **upsert**: silver replaces, bronze
appends another audit copy (so we keep the full history of edits).
"""
from __future__ import annotations
import json
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import pandas as pd
from . import paths, repo, silver_db, silver_schema


_SUPPORTED_TABLES = {"customers", "orders", "order_items",
                     "order_source_records", "boss_query_logs"}


def _coerce_for_silver(value: Any, sql_type: str):
    """Looser-than-transform coercion — manual UI provides clean values
    most of the time but we still defend against typos."""
    if value is None or value == "":
        return None
    if sql_type in ("VARCHAR",):
        return str(value)
    if sql_type == "DATE":
        if isinstance(value, date):
            return value
        try:
            return pd.to_datetime(str(value)).date()
        except Exception:
            return None
    if sql_type == "TIMESTAMP":
        try:
            return pd.to_datetime(str(value)).to_pydatetime()
        except Exception:
            return None
    if sql_type == "BOOLEAN":
        return str(value).strip().lower() in ("true", "1", "yes", "y", "是", "t")
    if sql_type.startswith("DECIMAL"):
        try:
            return Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return None
    if sql_type == "JSON":
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    return value


def _yaml_to_sql(t: str) -> str:
    if t in ("string", "enum"):
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


def _system_default(col_name: str, sql_type: str, *, entry_id: str):
    if col_name == "source_type":
        return "manual_ui"
    if col_name == "source_lineage":
        return json.dumps({"manual_entry_id": entry_id})
    if col_name in ("created_at", "updated_at"):
        return datetime.now(timezone.utc).replace(tzinfo=None)
    return None


def schema_for_form(silver_table: str) -> dict:
    """Return the column list for the assistant / form renderer.
    Marks system-managed columns so the UI / assistant doesn't ask the
    user for them."""
    if silver_table not in _SUPPORTED_TABLES:
        raise ValueError(f"unknown silver_table: {silver_table}")
    schema = silver_schema.load()
    table = schema.tables[silver_table]
    system_cols = {"source_type", "source_lineage", "created_at", "updated_at"}
    fields = []
    for c in table.columns:
        fields.append({
            "name": c.name,
            "type": c.type,
            "nullable": c.nullable,
            "values": list(c.values) if c.values else None,
            "description": c.description,
            "system_managed": c.name in system_cols,
            "is_primary_key": c.name in table.primary_key,
        })
    return {
        "table": silver_table,
        "primary_key": list(table.primary_key),
        "fields": fields,
    }


def record_manual_entry(
    *,
    client_id: str,
    silver_table: str,
    fields: dict,
    user_id: str | None,
) -> dict:
    """Double-write one row: bronze parquet (audit) + silver upsert.

    Returns ``{bronze_file_id, silver_table, primary_key, primary_key_value}``.
    """
    if silver_table not in _SUPPORTED_TABLES:
        raise ValueError(f"unknown silver_table: {silver_table}")
    schema = silver_schema.load()
    table = schema.tables[silver_table]
    entry_id = uuid.uuid4().hex

    # Build the silver row dict, applying coercion + system defaults.
    silver_row: dict[str, Any] = {}
    for c in table.columns:
        sql_type = _yaml_to_sql(c.type)
        raw = fields.get(c.name)
        coerced = _coerce_for_silver(raw, sql_type)
        if coerced is None:
            coerced = _system_default(c.name, sql_type, entry_id=entry_id)
        if coerced is None and not c.nullable and c.name in table.primary_key:
            # Auto-generate PK if missing (e.g. customer_id from display_name)
            coerced = f"manual_{entry_id[:12]}"
        if c.name == "source_type":
            coerced = "manual_ui"
        if c.name == "source_lineage":
            coerced = json.dumps({"manual_entry_id": entry_id})
        silver_row[c.name] = coerced

    # 1) Bronze audit copy.
    paths.ensure_tenant_dirs(client_id)
    bronze_root = paths.bronze_dir(client_id, "manual_ui")
    today = date.today().isoformat()
    day_dir = bronze_root / today
    day_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = day_dir / f"{silver_table}__{entry_id}.parquet"
    df = pd.DataFrame([silver_row])
    # Cast all values to JSON-friendly types for parquet.
    df.to_parquet(parquet_path, index=False)
    rel = parquet_path.relative_to(paths.data_root()).as_posix()
    meta = {
        "source_type": "manual_ui",
        "tenant": client_id,
        "ingested_at": int(time.time()),
        "ingested_by": user_id,
        "silver_table": silver_table,
        "manual_entry_id": entry_id,
        "row_count": 1,
        "fields_user_provided": list(fields.keys()),
    }
    parquet_path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )
    bronze_file_id = repo.insert_bronze_file(
        client_id=client_id,
        source_type="manual_ui",
        bronze_path=rel,
        original_filename=None,
        sheet_name=silver_table,
        row_count=1,
        checksum_sha256=None,
        uploaded_by=user_id,
        meta=meta,
    )

    # 2) Silver upsert. INSERT OR REPLACE handles re-entry of same PK.
    silver_db.ensure_silver_tables(client_id)
    con = silver_db.open_silver(client_id)
    try:
        col_names = [c.name for c in table.columns]
        placeholders = ", ".join("?" for _ in col_names)
        # DuckDB INSERT OR REPLACE → single-statement upsert keyed on PK
        con.execute(
            f"INSERT OR REPLACE INTO \"{silver_table}\" "
            f"({', '.join(f'\"{n}\"' for n in col_names)}) "
            f"VALUES ({placeholders})",
            [silver_row[n] for n in col_names],
        )
    finally:
        con.close()

    pk_col = table.primary_key[0]
    return {
        "bronze_file_id": bronze_file_id,
        "silver_table": silver_table,
        "primary_key": pk_col,
        "primary_key_value": silver_row[pk_col],
    }
