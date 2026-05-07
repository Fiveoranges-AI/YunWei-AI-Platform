"""Read-only API for the 数据中心 console (docs/data-layer.md M2 §3.2).

All endpoints require an authenticated session and validate that the user
has at least one user_tenant row for the requested ``client_id``.

Endpoints:
- GET /api/data/clients
- GET /api/data/health?client=<>
- GET /api/data/tables/<table>/rows?client=<>&limit=&offset=&q=
- GET /api/data/bronze?client=<>&source_type=

Write paths come in M3+ via the assistant; this file stays read-only.
"""
from __future__ import annotations
import json
from typing import Any
from fastapi import APIRouter, HTTPException, Path, Query, Request
import duckdb
from .. import db
from ..api import _user_from_request
from . import paths, repo, silver_schema

router = APIRouter(prefix="/api/data")

# Hard-coded for now; pulled from kernel yaml so it stays in sync if schema grows.
_CANONICAL_TABLES = tuple(silver_schema.load().tables.keys())

# Columns on which the table-browser ?q= ILIKE filter is applied. Avoids
# scanning JSON / decimal / date types that don't match raw substrings.
_SEARCHABLE_TYPES = {"string", "enum"}


# ─── helpers ────────────────────────────────────────────────────

def _user_clients(user_id: str) -> list[str]:
    rows = db.main().execute(
        "SELECT DISTINCT client_id FROM user_tenant WHERE user_id=%s",
        (user_id,),
    ).fetchall()
    return [r["client_id"] for r in rows]


def _require_client_acl(user: dict, client_id: str) -> None:
    if client_id not in _user_clients(user["id"]):
        raise HTTPException(403, {"error": "no_client_acl",
                                  "message": "无权访问该租户数据"})


def _open_silver(client_id: str) -> duckdb.DuckDBPyConnection | None:
    p = paths.silver_live_path(client_id)
    if not p.exists():
        return None
    # read_only avoids creating an empty file as a side effect of a probe.
    return duckdb.connect(str(p), read_only=True)


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='main' AND table_name=?",
        [table],
    ).fetchone()
    return row is not None


# ─── endpoints ──────────────────────────────────────────────────

@router.get("/clients")
def list_clients(request: Request) -> dict:
    """Lists client_ids visible to the current user; UI uses this to pick
    a default tenant + show a switcher when there are >1."""
    user = _user_from_request(request)
    return {"clients": _user_clients(user["id"])}


@router.get("/health")
def health(request: Request, client: str = Query(...)) -> dict:
    """Per-table row count + latest update timestamp + source distribution.

    Returns ``initialized=false`` when silver-live.duckdb does not yet
    exist for this tenant (new tenant w/ no data yet).
    """
    user = _user_from_request(request)
    _require_client_acl(user, client)

    con = _open_silver(client)
    if con is None:
        return {
            "initialized": False,
            "tables": {t: _empty_table_health() for t in _CANONICAL_TABLES},
        }
    try:
        return {
            "initialized": True,
            "tables": {t: _table_health(con, t) for t in _CANONICAL_TABLES},
        }
    finally:
        con.close()


def _empty_table_health() -> dict:
    return {"row_count": 0, "latest_updated_at": None, "by_source": {}}


def _table_health(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    if not _table_exists(con, table):
        return _empty_table_health()
    row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    cols = {c[0] for c in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='main' AND table_name=?",
        [table],
    ).fetchall()}
    latest = None
    if "updated_at" in cols:
        latest = con.execute(f"SELECT MAX(updated_at) FROM {table}").fetchone()[0]
    elif "created_at" in cols:
        latest = con.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]
    by_source: dict[str, int] = {}
    if "source_type" in cols:
        for src, n in con.execute(
            f"SELECT source_type, COUNT(*) FROM {table} GROUP BY source_type"
        ).fetchall():
            by_source[src or "unknown"] = n
    return {
        "row_count": row_count,
        "latest_updated_at": latest.isoformat() if latest else None,
        "by_source": by_source,
    }


@router.get("/tables/{table}/rows")
def table_rows(
    request: Request,
    table: str = Path(..., pattern=r"^[a-z_]+$"),
    client: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200),
) -> dict:
    """Paginated read-only table browse. ``q`` does ILIKE across string /
    enum columns; deliberately not full SQL — see §3.1."""
    user = _user_from_request(request)
    _require_client_acl(user, client)

    if table not in _CANONICAL_TABLES:
        raise HTTPException(404, {"error": "unknown_table"})

    con = _open_silver(client)
    if con is None or not _table_exists(con, table):
        if con:
            con.close()
        return {"columns": [], "rows": [], "total": 0}
    try:
        # The DuckDB table may have a subset of canonical columns (especially
        # mid-migration or in tests). Use the actual columns for SELECT and
        # only ILIKE on those that overlap with the canonical "string"/"enum"
        # set — otherwise we risk Binder errors on missing columns.
        actual_cols = [r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='main' AND table_name=? "
            "ORDER BY ordinal_position",
            [table],
        ).fetchall()]
        schema = silver_schema.load().tables[table]
        actual_set = set(actual_cols)
        searchable = [c.name for c in schema.columns
                      if c.type in _SEARCHABLE_TYPES and c.name in actual_set]

        where_sql = ""
        params: list[Any] = []
        if q and searchable:
            ors = " OR ".join(f"CAST({c} AS VARCHAR) ILIKE ?" for c in searchable)
            where_sql = f"WHERE {ors}"
            params = [f"%{q}%"] * len(searchable)

        total = con.execute(
            f"SELECT COUNT(*) FROM {table} {where_sql}", params
        ).fetchone()[0]

        rows_raw = con.execute(
            f"SELECT * FROM {table} {where_sql} "
            f"ORDER BY 1 LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        rows = [_row_to_jsonable(actual_cols, r) for r in rows_raw]
        return {"columns": actual_cols, "rows": rows, "total": total}
    finally:
        con.close()


def _row_to_jsonable(cols: list[str], row: tuple) -> dict:
    out: dict[str, Any] = {}
    for col, val in zip(cols, row):
        if val is None:
            out[col] = None
        elif hasattr(val, "isoformat"):
            out[col] = val.isoformat()
        elif isinstance(val, (str, int, float, bool)):
            out[col] = val
        else:
            # decimal, json-as-str, etc.
            out[col] = str(val)
    return out


@router.get("/bronze")
def bronze_files(
    request: Request,
    client: str = Query(...),
    source_type: str | None = Query(None),
) -> dict:
    """Bronze Files panel — list non-deleted bronze parquet records."""
    user = _user_from_request(request)
    _require_client_acl(user, client)

    if source_type and source_type not in paths.SOURCE_TYPES:
        raise HTTPException(400, {"error": "unknown_source_type"})

    files = repo.list_bronze_files(client, source_type)
    return {"files": [_bronze_row_view(f) for f in files]}


def _bronze_row_view(row: dict) -> dict:
    return {
        "id": row["id"],
        "source_type": row["source_type"],
        "original_filename": row["original_filename"],
        "sheet_name": row["sheet_name"],
        "row_count": row["row_count"],
        "uploaded_by": row["uploaded_by"],
        "ingested_at": row["ingested_at"],
        "bronze_path": row["bronze_path"],
    }
