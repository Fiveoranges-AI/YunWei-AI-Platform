"""Slice ③ — image preprocessing + model-id resolution (DB-free unit tests)."""

import io

import pytest
from PIL import Image

from yunwei_win.config import settings
from yunwei_win.services.image_preprocess import preprocess_image_bytes
from yunwei_win.services.schema_ingest.model_ids import (
    extraction_model_id,
    parse_model_id,
)


@pytest.fixture(autouse=True)
def _clean_state():
    # Override conftest's table-truncating autouse fixture (same name) — these
    # are pure unit tests that never touch the database / redis.
    yield


def _jpeg(w: int, h: int, *, exif: bytes | None = None) -> bytes:
    img = Image.new("RGB", (w, h), (120, 130, 140))
    buf = io.BytesIO()
    if exif is not None:
        img.save(buf, format="JPEG", quality=95, exif=exif)
    else:
        img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_oversized_image_is_downscaled():
    res = preprocess_image_bytes(
        _jpeg(4000, 3000), content_type="image/jpeg", filename="big.jpg"
    )
    assert res.changed and res.resized
    out = Image.open(io.BytesIO(res.data))
    assert max(out.size) <= settings.image_max_dimension
    assert res.new_bytes < res.orig_bytes


def test_exif_orientation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° — landscape should become portrait
    res = preprocess_image_bytes(
        _jpeg(800, 400, exif=exif.tobytes()),
        content_type="image/jpeg",
        filename="rot.jpg",
    )
    assert res.rotated and res.changed
    out = Image.open(io.BytesIO(res.data))
    assert out.size == (400, 800)  # dimensions swapped
    assert out.getexif().get(0x0112, 1) in (0, 1)  # tag cleared


def test_non_image_passes_through():
    data = b"%PDF-1.7 not an image"
    res = preprocess_image_bytes(
        data, content_type="application/pdf", filename="x.pdf"
    )
    assert not res.changed and res.data == data


def test_unopenable_bytes_pass_through():
    data = b"\x00\x01\x02 not a real image"
    res = preprocess_image_bytes(
        data, content_type="image/jpeg", filename="bad.jpg"
    )
    assert not res.changed and res.data == data


def test_small_image_is_not_inflated():
    data = _jpeg(64, 64)
    res = preprocess_image_bytes(
        data, content_type="image/jpeg", filename="tiny.jpg"
    )
    assert len(res.data) <= len(data)


def test_model_id_resolution():
    assert parse_model_id("landingai") == settings.landingai_parse_model
    assert parse_model_id("text") is None
    assert extraction_model_id("landingai") == settings.landingai_extract_model
    assert extraction_model_id("deepseek") == settings.model_parse
    # A model surfaced in response metadata wins over the configured fallback.
    assert extraction_model_id("deepseek", {"model": "ds-actual"}) == "ds-actual"
    assert extraction_model_id("text") is None
