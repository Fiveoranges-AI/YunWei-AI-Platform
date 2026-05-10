"""On-disk storage of uploaded originals.

Single source of truth for the file-layout convention: every uploaded
artifact lives under ``$DATA_ROOT/files/<uuid_hex><ext>``, with the original
extension preserved (or a caller-supplied default for rare cases like a
text note that arrives without a filename). The Document row records the
returned path + sha256 + size so audit / replay can find the original.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import NamedTuple


class StoredFile(NamedTuple):
    path: str
    sha256: str
    size: int


def _data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", "/data")) / "files"


def store_upload(
    content: bytes,
    original_filename: str,
    *,
    default_ext: str = "",
) -> StoredFile:
    """Persist ``content`` under DATA_ROOT/files and return its descriptor.

    ``default_ext`` is used when ``original_filename`` has no suffix. Pass
    e.g. ``".jpg"`` for image uploads or ``".bin"`` when nothing else fits.
    """
    root = _data_root()
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix or default_ext
    out = root / f"{uuid.uuid4().hex}{ext}"
    out.write_bytes(content)
    return StoredFile(
        path=str(out),
        sha256=hashlib.sha256(content).hexdigest(),
        size=len(content),
    )
