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
from fastapi import APIRouter, Body, File, Form, HTTPException, Path, Query, Request, UploadFile
import duckdb
from .. import db
from ..api import _user_from_request
from . import ingest, paths, repo, silver_schema, transform

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


# ─── upload (M3 §4.2) ───────────────────────────────────────────

# Hard cap matches docs/data-layer.md §10 risk row "大 Excel 内存爆".
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@router.post("/upload")
async def upload(
    request: Request,
    client: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """Excel/CSV upload → bronze parquet (one row per sheet). Returns sheet
    previews so the assistant can render them in chat.
    """
    user = _user_from_request(request)
    _require_client_acl(user, client)

    blob = await file.read()
    if len(blob) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, {"error": "file_too_large",
                                  "limit_bytes": _MAX_UPLOAD_BYTES})

    suffix = (file.filename or "").lower().rsplit(".", 1)[-1]
    if suffix not in ("xlsx", "xls", "csv"):
        raise HTTPException(400, {"error": "unsupported_format",
                                  "message": "仅支持 .xlsx / .xls / .csv"})

    try:
        result = ingest.ingest_excel(
            client_id=client,
            original_filename=file.filename or "upload",
            file_bytes=blob,
            uploaded_by=user["id"],
        )
    except Exception as e:
        raise HTTPException(400, {"error": "ingest_failed", "message": str(e)})

    if result.duplicate:
        return {"duplicate": True, "checksum": result.checksum,
                "existing_file_ids": result.existing_file_ids}

    sheets_view = []
    for s in result.sheets:
        preview = ingest.read_bronze_preview(client, s.bronze_file_id, limit=50)
        sheets_view.append({
            "bronze_file_id": s.bronze_file_id,
            "sheet_name": s.sheet_name,
            "row_count": s.row_count,
            "columns": preview["columns"],
            "preview_rows": preview["rows"],
        })
    return {"duplicate": False, "checksum": result.checksum, "sheets": sheets_view}


@router.get("/bronze/{file_id}/preview")
def bronze_preview(
    request: Request,
    file_id: str = Path(..., pattern=r"^[a-f0-9]{32}$"),
    client: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    user = _user_from_request(request)
    _require_client_acl(user, client)
    try:
        return ingest.read_bronze_preview(client, file_id, limit=limit)
    except FileNotFoundError:
        raise HTTPException(404, {"error": "bronze_file_not_found"})


@router.delete("/bronze/{file_id}")
def bronze_delete(
    request: Request,
    file_id: str = Path(..., pattern=r"^[a-f0-9]{32}$"),
    client: str = Query(...),
) -> dict:
    """Soft-delete bronze + cascade silver rows that originated from it (AC-D7)."""
    user = _user_from_request(request)
    _require_client_acl(user, client)
    matching = [r for r in repo.list_bronze_files(client) if r["id"] == file_id]
    if not matching:
        raise HTTPException(404, {"error": "bronze_file_not_found"})
    silver_deleted = transform.cascade_delete_silver(client, file_id)
    repo.soft_delete_bronze_file(file_id)
    return {"ok": True, "silver_rows_deleted": silver_deleted}


# ─── mapping (M3 §5) ────────────────────────────────────────────

@router.post("/mapping")
def create_mapping(
    request: Request,
    body: dict = Body(...),
) -> dict:
    """Build a bronze→silver column mapping and immediately materialize.

    Body schema::

        {
          "client": "yinhu",
          "bronze_file_id": "...",          # source for the run + filename pattern
          "silver_table": "orders",
          "column_map": {"客户名": "customer_name_snapshot", ...}
        }
    """
    user = _user_from_request(request)
    client = body.get("client")
    bronze_file_id = body.get("bronze_file_id")
    silver_table = body.get("silver_table")
    column_map = body.get("column_map") or {}
    if not (client and bronze_file_id and silver_table and isinstance(column_map, dict)):
        raise HTTPException(400, {"error": "missing_fields"})
    _require_client_acl(user, client)

    if silver_table not in silver_schema.load().tables:
        raise HTTPException(400, {"error": "unknown_silver_table"})

    bronze_row = next(
        (r for r in repo.list_bronze_files(client) if r["id"] == bronze_file_id),
        None,
    )
    if bronze_row is None:
        raise HTTPException(404, {"error": "bronze_file_not_found"})

    bronze_columns = list(json.loads(bronze_row["meta_json"]).get("columns", []))
    mapping_id = repo.insert_silver_mapping(
        client_id=client,
        source_type=bronze_row["source_type"],
        filename_pattern=bronze_row["original_filename"] or "",
        sheet_pattern=bronze_row["sheet_name"],
        silver_table=silver_table,
        column_map=column_map,
        bronze_columns_snapshot=bronze_columns,
        created_by=user["id"],
    )

    # Auto-trigger transform after mapping created (§5.2).
    result = transform.materialize(
        client_id=client,
        bronze_file_id=bronze_file_id,
        silver_table=silver_table,
        column_map=column_map,
    )
    return {
        "mapping_id": mapping_id,
        "silver_table": result.silver_table,
        "rows_written": result.rows_written,
        "rows_skipped": result.rows_skipped,
    }


@router.get("/mappings")
def list_mappings(
    request: Request,
    client: str = Query(...),
    source_type: str | None = Query(None),
) -> dict:
    user = _user_from_request(request)
    _require_client_acl(user, client)
    rows = repo.list_silver_mappings(client, source_type)
    return {"mappings": [
        {
            "id": r["id"],
            "source_type": r["source_type"],
            "filename_pattern": r["filename_pattern"],
            "sheet_pattern": r["sheet_pattern"],
            "silver_table": r["silver_table"],
            "column_map": json.loads(r["column_map"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]}
