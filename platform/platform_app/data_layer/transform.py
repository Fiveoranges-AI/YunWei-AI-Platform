"""bronze parquet × silver_mappings → silver upsert (docs/data-layer.md §5).

Transform invariants:
- **Idempotent** (§5.2): re-running a transform deletes any silver rows
  whose ``source_lineage.bronze_file_id`` matches the input bronze, then
  re-inserts. Same bronze + same mapping → identical silver state.
- **Permissive on missing columns**: required silver columns the user did
  not map are filled with conservative defaults so the user can iterate
  the mapping without churn. Domain-correct values come later when the
  assistant proposes better mappings.
- **source_lineage** is a JSON object ``{"bronze_file_id": ..., "row_index": n}``
  — used for cascade delete (AC-D7) and idempotent re-runs.
"""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import pandas as pd
from . import paths, repo, silver_db, silver_schema


@dataclass(frozen=True)
class TransformResult:
    silver_table: str
    rows_written: int
    rows_skipped: int


def _coerce(value: Any, sql_type: str):
    """Best-effort conversion from a bronze cell to a DuckDB-friendly value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if sql_type in ("VARCHAR",):
        return str(value)
    if sql_type == "DATE":
        if isinstance(value, date):
            return value
        try:
            return pd.to_datetime(value).date()
        except (ValueError, TypeError):
            return None
    if sql_type == "TIMESTAMP":
        if isinstance(value, datetime):
            return value
        try:
            return pd.to_datetime(value).to_pydatetime()
        except (ValueError, TypeError):
            return None
    if sql_type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        return s in ("true", "1", "yes", "y", "是", "t")
    if sql_type.startswith("DECIMAL"):
        try:
            return Decimal(str(value).replace(",", "").strip() or "0")
        except (InvalidOperation, ValueError):
            return Decimal("0")
    if sql_type == "JSON":
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    return value


def _column_default(col_name: str, sql_type: str, *, source_type: str,
                    bronze_file_id: str, row_index: int):
    """Defaults for required silver columns the user did not map."""
    if col_name == "source_type":
        return source_type
    if col_name == "source_lineage":
        return json.dumps({"bronze_file_id": bronze_file_id, "row_index": row_index})
    if col_name in ("created_at", "updated_at"):
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if col_name.endswith("_id") and sql_type == "VARCHAR":
        # Synthetic primary key when not mapped — domain key assignment
        # is the assistant's job in M3-assistant.
        return f"{bronze_file_id[:8]}_{row_index}"
    if col_name in ("display_name", "customer_name_snapshot"):
        return "(unnamed)"
    if col_name == "order_date":
        return date.today()
    if col_name == "payment_status":
        return "unknown"
    if col_name == "status":
        return "draft"
    # Decimals → 0; the rest fall back to NULL and we'll only use this
    # default if NOT NULL forces our hand.
    if sql_type.startswith("DECIMAL"):
        return Decimal("0")
    if sql_type == "BOOLEAN":
        return False
    if sql_type == "DATE":
        return date.today()
    if sql_type == "TIMESTAMP":
        return datetime.now(timezone.utc).replace(tzinfo=None)
    return None


def materialize(
    *,
    client_id: str,
    bronze_file_id: str,
    silver_table: str,
    column_map: dict[str, str],
) -> TransformResult:
    """Apply ``column_map`` to bronze parquet rows, upsert into silver.

    ``column_map`` is ``{bronze_column: silver_column}``.
    """
    schema = silver_schema.load()
    if silver_table not in schema.tables:
        raise ValueError(f"unknown silver_table: {silver_table}")
    table_schema = schema.tables[silver_table]
    # M3-pipeline supports only tables with source_lineage — without it we
    # can't dedupe on re-run (§5.2). order_items / order_source_records /
    # boss_query_logs are loaded later via different paths.
    if not any(c.name == "source_lineage" for c in table_schema.columns):
        raise ValueError(
            f"silver_table {silver_table!r} lacks source_lineage; "
            "cannot be a transform target"
        )

    # Reverse: silver_col → bronze_col (mapping is provided bronze→silver,
    # but we iterate silver columns to fill row dicts)
    silver_to_bronze: dict[str, str] = {v: k for k, v in column_map.items()}

    bronze_row = next(
        (r for r in repo.list_bronze_files(client_id) if r["id"] == bronze_file_id),
        None,
    )
    if bronze_row is None:
        raise FileNotFoundError(bronze_file_id)
    parquet_path = paths.data_root() / bronze_row["bronze_path"]
    df = pd.read_parquet(parquet_path)

    silver_db.ensure_silver_tables(client_id)
    con = silver_db.open_silver(client_id)
    rows_written = 0
    rows_skipped = 0
    try:
        # Idempotency (§5.2): drop any prior rows from this bronze file first.
        con.execute(
            f"DELETE FROM \"{silver_table}\" "
            "WHERE json_extract_string(source_lineage, '$.bronze_file_id') = ?",
            [bronze_file_id],
        )

        col_defs = [(c.name, _yaml_to_sql(c.type), c.nullable) for c in table_schema.columns]
        col_names_quoted = ", ".join(f'"{n}"' for n, _t, _nul in col_defs)
        placeholders = ", ".join("?" for _ in col_defs)

        for row_index, raw in enumerate(df.itertuples(index=False, name=None)):
            row_dict = dict(zip([str(c) for c in df.columns], raw))
            silver_row: list[Any] = []
            try:
                for cname, sql_type, nullable in col_defs:
                    bcol = silver_to_bronze.get(cname)
                    val = row_dict.get(bcol) if bcol else None
                    coerced = _coerce(val, sql_type)
                    if coerced is None:
                        if cname in ("source_type", "source_lineage",
                                     "created_at", "updated_at") or not nullable:
                            coerced = _column_default(
                                cname, sql_type,
                                source_type=bronze_row["source_type"],
                                bronze_file_id=bronze_file_id,
                                row_index=row_index,
                            )
                    silver_row.append(coerced)
                con.execute(
                    f'INSERT INTO "{silver_table}" ({col_names_quoted}) VALUES ({placeholders})',
                    silver_row,
                )
                rows_written += 1
            except Exception:
                # Bad rows shouldn't poison the whole file; skip + count.
                rows_skipped += 1
                continue
    finally:
        con.close()
    return TransformResult(
        silver_table=silver_table,
        rows_written=rows_written,
        rows_skipped=rows_skipped,
    )


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


def cascade_delete_silver(client_id: str, bronze_file_id: str) -> int:
    """Delete all silver rows whose source_lineage points at this bronze
    file. Returns the number of rows deleted across all silver tables (AC-D7).

    Only the "primary business tables" (customers, orders) carry
    source_lineage per silver-canonical.yaml — others (order_items,
    order_source_records, boss_query_logs) are skipped here since their
    lineage is via FK or is the source itself.
    """
    silver_db.ensure_silver_tables(client_id)
    schema = silver_schema.load()
    tables_with_lineage = [
        tname for tname, t in schema.tables.items()
        if any(c.name == "source_lineage" for c in t.columns)
    ]
    con = silver_db.open_silver(client_id)
    deleted = 0
    try:
        for tname in tables_with_lineage:
            res = con.execute(
                f"DELETE FROM \"{tname}\" "
                "WHERE json_extract_string(source_lineage, '$.bronze_file_id') = ? "
                "RETURNING 1",
                [bronze_file_id],
            ).fetchall()
            deleted += len(res)
    finally:
        con.close()
    return deleted
