"""Upload pipeline: Excel/CSV → bronze parquet (docs/data-layer.md §4.2).

Steps for one upload:
1. Save the original blob to ``_uploads/<uuid><ext>`` for audit
2. Compute SHA-256; if ``bronze_files`` already has it for the tenant,
   short-circuit with a "duplicate" result (AC-D2)
3. Read each sheet via pandas, drop fully empty rows
4. Persist each sheet as a parquet at
   ``bronze/file_excel/<YYYY-MM-DD>/<stem>__<sheet>.parquet`` with a
   sibling ``_meta.json``
5. Insert a ``bronze_files`` row per sheet
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
import pandas as pd
from . import paths, repo

_SHEET_NAME_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class IngestedSheet:
    bronze_file_id: str
    bronze_path: str          # relative to data_root
    sheet_name: str
    row_count: int
    columns: list[str]


@dataclass(frozen=True)
class IngestResult:
    duplicate: bool
    checksum: str
    sheets: list[IngestedSheet]
    existing_file_ids: list[str]   # populated when duplicate=True


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(s: str) -> str:
    return _SHEET_NAME_SAFE.sub("_", s)[:64] or "sheet"


def ingest_excel(
    *,
    client_id: str,
    original_filename: str,
    file_bytes: bytes,
    uploaded_by: str | None,
) -> IngestResult:
    """Excel/CSV upload entry point. Idempotent on checksum."""
    paths.ensure_tenant_dirs(client_id)
    checksum = compute_sha256(file_bytes)

    # AC-D2: same file uploaded twice → return existing rows, do nothing
    existing = repo.find_by_checksum(client_id, checksum)
    if existing:
        same = [r for r in repo.list_bronze_files(client_id, "file_excel")
                if r["checksum_sha256"] == checksum]
        return IngestResult(
            duplicate=True, checksum=checksum, sheets=[],
            existing_file_ids=[r["id"] for r in same],
        )

    suffix = Path(original_filename).suffix.lower() or ".xlsx"
    upload_id = uuid.uuid4().hex
    upload_path = paths.uploads_dir(client_id) / f"{upload_id}{suffix}"
    upload_path.write_bytes(file_bytes)

    bronze_root = paths.bronze_dir(client_id, "file_excel")
    today = date.today().isoformat()
    day_dir = bronze_root / today
    day_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    sheets: list[IngestedSheet] = []
    file_stem = _slug(Path(original_filename).stem)
    try:
        if suffix == ".csv":
            sheet_iter: dict[str, pd.DataFrame] = {"Sheet1": pd.read_csv(upload_path)}
        else:
            # sheet_name=None → dict of {sheet: df}
            sheet_iter = pd.read_excel(upload_path, sheet_name=None, dtype=object)

        for sheet_name, df in sheet_iter.items():
            df = df.dropna(how="all")  # drop fully empty rows
            parquet_name = f"{file_stem}__{_slug(sheet_name)}.parquet"
            parquet_path = day_dir / parquet_name
            # Stringify all object columns — bronze is "preserve as-is";
            # silver transform handles type coercion.
            df = df.astype(object).where(pd.notna(df), None)
            df.to_parquet(parquet_path, index=False)
            written.append(parquet_path)

            rel = parquet_path.relative_to(paths.data_root()).as_posix()
            meta = {
                "source_type": "file_excel",
                "tenant": client_id,
                "ingested_at": int(time.time()),
                "ingested_by": uploaded_by,
                "original_filename": original_filename,
                "sheet_name": sheet_name,
                "row_count": int(len(df)),
                "checksum_sha256": checksum,
                "columns": [str(c) for c in df.columns],
            }
            (parquet_path.with_suffix(".json")).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2)
            )

            file_id = repo.insert_bronze_file(
                client_id=client_id,
                source_type="file_excel",
                bronze_path=rel,
                original_filename=original_filename,
                sheet_name=sheet_name,
                row_count=int(len(df)),
                checksum_sha256=checksum,
                uploaded_by=uploaded_by,
                meta=meta,
            )
            sheets.append(IngestedSheet(
                bronze_file_id=file_id,
                bronze_path=rel,
                sheet_name=sheet_name,
                row_count=int(len(df)),
                columns=[str(c) for c in df.columns],
            ))
    except Exception:
        # Best-effort cleanup of any parquet/_meta we managed to write,
        # then surface the error. DB rows for already-inserted sheets in
        # this batch stay; uploaders can retry — they'll dedupe by checksum.
        for p in written:
            try:
                p.unlink(missing_ok=True)
                p.with_suffix(".json").unlink(missing_ok=True)
            except OSError:
                pass
        upload_path.unlink(missing_ok=True)
        raise

    return IngestResult(duplicate=False, checksum=checksum,
                        sheets=sheets, existing_file_ids=[])


def read_bronze_preview(client_id: str, bronze_file_id: str, limit: int = 50) -> dict:
    """Return columns + first ``limit`` rows for the assistant preview pane."""
    row = next((r for r in repo.list_bronze_files(client_id)
                if r["id"] == bronze_file_id), None)
    if row is None:
        raise FileNotFoundError(bronze_file_id)
    parquet_path = paths.data_root() / row["bronze_path"]
    df = pd.read_parquet(parquet_path)
    head = df.head(limit)
    cols = [str(c) for c in head.columns]
    rows = [
        {c: (None if pd.isna(v) else _jsonable(v)) for c, v in zip(cols, r)}
        for r in head.itertuples(index=False, name=None)
    ]
    return {"columns": cols, "rows": rows, "total": int(len(df))}


def _jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)
