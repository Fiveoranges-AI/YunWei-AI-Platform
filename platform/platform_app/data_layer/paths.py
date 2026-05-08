"""Per-tenant data directory layout (docs/data-layer.md §2).

```
<DATA_ROOT>/tenants/<client_id>/
├─ bronze/{erp_kingdee,erp_yongyou,file_excel,file_pdf,manual_ui}/
├─ _uploads/                       # original-file audit copies
├─ silver-live.duckdb              # customer agent reads this
└─ silver-snapshot-<date>.duckdb   # kernel evaluator copies
```

Date-bucketed sub-dirs (`<YYYY-MM-DD>`) are created lazily by writers,
not here.
"""
from __future__ import annotations
import re
from pathlib import Path
from ..settings import settings

# bronze source_type ⇆ on-disk bucket. Add new source types here.
SOURCE_TYPES: tuple[str, ...] = (
    "erp_kingdee",
    "erp_yongyou",
    "file_excel",
    "file_pdf",
    "manual_ui",
)

_CLIENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _validate_client_id(client_id: str) -> None:
    # Defense-in-depth: client_id flows from the URL path; this prevents path
    # traversal even if a caller forgets to validate upstream.
    if not _CLIENT_ID_RE.match(client_id):
        raise ValueError(f"invalid client_id: {client_id!r}")


def data_root() -> Path:
    return Path(settings.data_root).resolve()


def tenant_root(client_id: str) -> Path:
    _validate_client_id(client_id)
    return data_root() / "tenants" / client_id


def bronze_dir(client_id: str, source_type: str) -> Path:
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unknown source_type: {source_type!r}")
    return tenant_root(client_id) / "bronze" / source_type


def uploads_dir(client_id: str) -> Path:
    return tenant_root(client_id) / "_uploads"


def silver_live_path(client_id: str) -> Path:
    return tenant_root(client_id) / "silver-live.duckdb"


def silver_snapshot_path(client_id: str, date_iso: str) -> Path:
    return tenant_root(client_id) / f"silver-snapshot-{date_iso}.duckdb"


def ensure_tenant_dirs(client_id: str) -> Path:
    """Create the full bronze/* + _uploads layout. Idempotent."""
    root = tenant_root(client_id)
    (root / "_uploads").mkdir(parents=True, exist_ok=True)
    bronze_root = root / "bronze"
    for source_type in SOURCE_TYPES:
        (bronze_root / source_type).mkdir(parents=True, exist_ok=True)
    return root
