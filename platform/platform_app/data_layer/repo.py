"""DB accessors for ``bronze_files`` and ``silver_mappings``.

Kept separate from ``platform_app/db.py`` so the data layer can be added /
removed as a unit (see docs/data-layer.md M1).
"""
from __future__ import annotations
import json
import time
import uuid
from .. import db


def insert_bronze_file(
    *,
    client_id: str,
    source_type: str,
    bronze_path: str,
    original_filename: str | None,
    sheet_name: str | None,
    row_count: int,
    checksum_sha256: str | None,
    uploaded_by: str | None,
    meta: dict,
) -> str:
    """Insert one bronze parquet record. Returns the new id."""
    file_id = uuid.uuid4().hex
    db.main().execute(
        "INSERT INTO bronze_files "
        "(id, client_id, source_type, bronze_path, original_filename, sheet_name, "
        " row_count, checksum_sha256, uploaded_by, ingested_at, meta_json) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            file_id, client_id, source_type, bronze_path, original_filename,
            sheet_name, row_count, checksum_sha256, uploaded_by,
            int(time.time()), json.dumps(meta, ensure_ascii=False),
        ),
    )
    return file_id


def find_by_checksum(client_id: str, checksum: str) -> dict | None:
    return db.main().execute(
        "SELECT * FROM bronze_files "
        "WHERE client_id=%s AND checksum_sha256=%s AND deleted_at IS NULL "
        "LIMIT 1",
        (client_id, checksum),
    ).fetchone()


def list_bronze_files(client_id: str, source_type: str | None = None) -> list[dict]:
    if source_type:
        rows = db.main().execute(
            "SELECT * FROM bronze_files "
            "WHERE client_id=%s AND source_type=%s AND deleted_at IS NULL "
            "ORDER BY ingested_at DESC",
            (client_id, source_type),
        ).fetchall()
    else:
        rows = db.main().execute(
            "SELECT * FROM bronze_files "
            "WHERE client_id=%s AND deleted_at IS NULL "
            "ORDER BY ingested_at DESC",
            (client_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def soft_delete_bronze_file(file_id: str) -> None:
    db.main().execute(
        "UPDATE bronze_files SET deleted_at=%s WHERE id=%s",
        (int(time.time()), file_id),
    )


def insert_silver_mapping(
    *,
    client_id: str,
    source_type: str,
    filename_pattern: str,
    sheet_pattern: str | None,
    silver_table: str,
    column_map: dict[str, str],
    bronze_columns_snapshot: list[str],
    created_by: str | None,
) -> str:
    mapping_id = uuid.uuid4().hex
    db.main().execute(
        "INSERT INTO silver_mappings "
        "(id, client_id, source_type, filename_pattern, sheet_pattern, "
        " silver_table, column_map, bronze_columns_snapshot, created_at, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            mapping_id, client_id, source_type, filename_pattern, sheet_pattern,
            silver_table, json.dumps(column_map, ensure_ascii=False),
            json.dumps(bronze_columns_snapshot, ensure_ascii=False),
            int(time.time()), created_by,
        ),
    )
    return mapping_id


def list_silver_mappings(client_id: str, source_type: str | None = None) -> list[dict]:
    if source_type:
        rows = db.main().execute(
            "SELECT * FROM silver_mappings "
            "WHERE client_id=%s AND source_type=%s AND status='active' "
            "ORDER BY created_at DESC",
            (client_id, source_type),
        ).fetchall()
    else:
        rows = db.main().execute(
            "SELECT * FROM silver_mappings "
            "WHERE client_id=%s AND status='active' "
            "ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
    return [dict(r) for r in rows]
