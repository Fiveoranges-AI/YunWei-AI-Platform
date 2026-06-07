"""Pre-OCR image preprocessing.

Uploaded photos are often sideways (EXIF orientation), huge, or weakly
compressed — all of which slow the parser/OCR and can hurt accuracy. This
normalizes an image's bytes BEFORE storage, so every downstream parser
(LandingAI today) reads a right-side-up, bounded, recompressed image.

Pure and defensive: anything it can't open or improve is returned unchanged,
so it can never break ingest. Format is preserved (no surprise png→jpeg), only
orientation / size / compression change.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

from PIL import Image, ImageOps

from yunwei_win.config import settings

logger = logging.getLogger(__name__)

_RASTER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
# Formats we can safely re-encode in place. Anything else (or animated) passes
# through untouched.
_REENCODABLE = {"JPEG", "PNG", "WEBP"}
_EXIF_ORIENTATION_TAG = 0x0112


@dataclass(frozen=True)
class PreprocessResult:
    data: bytes
    changed: bool
    rotated: bool
    resized: bool
    orig_bytes: int
    new_bytes: int
    note: str


def _looks_like_image(content_type: str | None, filename: str | None) -> bool:
    if content_type and content_type.lower().startswith("image/"):
        return True
    if filename:
        return os.path.splitext(filename)[1].lower() in _RASTER_EXTS
    return False


def preprocess_image_bytes(
    data: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> PreprocessResult:
    """Return cleaned image bytes — or the original, unchanged on any doubt."""

    n = len(data)
    unchanged = lambda note: PreprocessResult(data, False, False, False, n, n, note)  # noqa: E731

    if not settings.image_preprocess_enabled:
        return unchanged("disabled")
    if not _looks_like_image(content_type, filename):
        return unchanged("not_image")

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001 — never break ingest on a bad image
        return unchanged("open_failed")

    fmt = (img.format or "").upper()
    if fmt not in _REENCODABLE or getattr(img, "is_animated", False):
        return unchanged(f"skip:{fmt or 'unknown'}")

    # 1) Auto-rotate from EXIF, then let the saved file drop the (now applied)
    #    orientation tag so viewers don't double-rotate.
    exif = img.getexif()
    orientation = exif.get(_EXIF_ORIENTATION_TAG, 1) if exif else 1
    rotated = orientation not in (1, 0)
    img = ImageOps.exif_transpose(img) or img

    # 2) Bound the largest dimension.
    w, h = img.size
    resized = False
    limit = max(256, settings.image_max_dimension)
    if max(w, h) > limit:
        scale = limit / max(w, h)
        img = img.resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS
        )
        resized = True

    # 3) Re-encode in the same format.
    out = io.BytesIO()
    save_kwargs: dict[str, object] = {}
    if fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = max(1, min(100, settings.image_jpeg_quality))
        if fmt == "JPEG":
            save_kwargs["optimize"] = True
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
    elif fmt == "PNG":
        save_kwargs["optimize"] = True
    try:
        img.save(out, format=fmt, **save_kwargs)
    except Exception:  # noqa: BLE001
        return unchanged("encode_failed")
    new = out.getvalue()

    # Keep the result only when it helps: rotation/resize are correctness/size
    # wins; otherwise require a strictly smaller file so we never inflate.
    if rotated or resized or len(new) < n:
        return PreprocessResult(new, True, rotated, resized, n, len(new), "ok")
    return PreprocessResult(data, False, rotated, False, n, n, "no_gain")
