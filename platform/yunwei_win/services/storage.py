"""Storage backend for uploaded originals.

Two backends, selected by ``STORAGE_BACKEND`` env:

- ``local`` (default) — writes to ``$DATA_ROOT/files/<uuid>.ext``. The
  ``StoredFile.path`` returned is a ``file://`` URL so callers don't
  have to special-case local vs remote.
- ``s3`` — writes to an S3-compatible bucket (AWS S3, Cloudflare R2,
  MinIO, ...). ``StoredFile.path`` is ``s3://bucket/key``. Env vars:
  ``S3_BUCKET``, ``S3_ENDPOINT_URL`` (optional, for R2/MinIO),
  ``S3_REGION`` (default ``auto``), ``S3_ACCESS_KEY_ID`` /
  ``S3_SECRET_ACCESS_KEY`` (or rely on instance role / Railway service
  env).

The ``path`` field is opaque to most callers. Use ``open_for_read`` to
get bytes back, or ``materialize_to_local`` when a downstream library
(pypdf) needs a real ``Path``.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.parse import urlparse


class StoredFile(NamedTuple):
    path: str       # url; file:// for local, s3:// for s3
    sha256: str
    size: int


def _backend() -> str:
    return os.environ.get("STORAGE_BACKEND", "local").strip().lower() or "local"


# ---------- local backend ----------------------------------------------

def _data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", "/data")) / "files"


def _store_local(content: bytes, filename: str, default_ext: str) -> StoredFile:
    root = _data_root()
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or default_ext
    out = root / f"{uuid.uuid4().hex}{ext}"
    out.write_bytes(content)
    return StoredFile(
        path=f"file://{out.absolute()}",
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


# ---------- s3 backend -------------------------------------------------

def _s3_client():
    import boto3
    kwargs = {
        "region_name": os.environ.get("S3_REGION", "auto"),
    }
    endpoint = os.environ.get("S3_ENDPOINT_URL", "").strip()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    ak = os.environ.get("S3_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("S3_SECRET_ACCESS_KEY", "").strip()
    if ak and sk:
        kwargs["aws_access_key_id"] = ak
        kwargs["aws_secret_access_key"] = sk
    return boto3.client("s3", **kwargs)


def _s3_bucket() -> str:
    bucket = os.environ.get("S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET env var")
    return bucket


def _store_s3(content: bytes, filename: str, default_ext: str) -> StoredFile:
    bucket = _s3_bucket()
    ext = Path(filename).suffix or default_ext
    key = f"files/{uuid.uuid4().hex}{ext}"
    client = _s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=content)
    return StoredFile(
        path=f"s3://{bucket}/{key}",
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )


# ---------- public API -------------------------------------------------

def store_upload(
    content: bytes,
    original_filename: str,
    *,
    default_ext: str = "",
) -> StoredFile:
    """Persist ``content`` and return a descriptor whose ``path`` is a URL."""
    backend = _backend()
    if backend == "s3":
        return _store_s3(content, original_filename, default_ext)
    return _store_local(content, original_filename, default_ext)


def open_for_read(stored_path: str) -> bytes:
    """Read the bytes back regardless of backend."""
    parsed = urlparse(stored_path)
    if parsed.scheme in ("", "file"):
        # Tolerate legacy bare-path values that pre-date the URL convention.
        path = parsed.path if parsed.scheme == "file" else stored_path
        return Path(path).read_bytes()
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        client = _s3_client()
        obj = client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    raise ValueError(f"unknown storage scheme: {parsed.scheme!r}")


def local_path_for(stored_path: str) -> Optional[Path]:
    """Return a filesystem Path when the URL is local, else None."""
    parsed = urlparse(stored_path)
    if parsed.scheme == "" and stored_path.startswith("/"):
        return Path(stored_path)
    if parsed.scheme == "file":
        return Path(parsed.path)
    return None


def materialize_to_local(stored_path: str) -> Path:
    """Return a real filesystem path for any URL.

    For local URLs this is a no-op. For s3:// it downloads to a temp file
    and returns that path. Caller is responsible for cleanup if needed;
    the temp file lives until process exit.
    """
    local = local_path_for(stored_path)
    if local is not None:
        return local
    data = open_for_read(stored_path)
    parsed = urlparse(stored_path)
    suffix = Path(parsed.path).suffix or ".bin"
    fd, name = tempfile.mkstemp(prefix="ingest-", suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return Path(name)
