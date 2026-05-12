"""Storage backend smoke tests.

Local backend uses tmp_path. S3 backend is exercised via a moto-style
stub patched onto `boto3.client` so the test never hits real network.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def test_local_backend_returns_file_url(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    from yinhu_brain.services.storage import store_upload, open_for_read

    out = store_upload(b"hello", "note.txt")
    assert out.path.startswith("file://")
    assert out.size == 5
    # File is reachable via open_for_read regardless of scheme.
    assert open_for_read(out.path) == b"hello"


def test_local_backend_materialize_returns_same_disk_path(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    from yinhu_brain.services.storage import store_upload, materialize_to_local

    out = store_upload(b"%PDF-data", "doc.pdf")
    local = materialize_to_local(out.path)
    assert local.exists()
    assert local.read_bytes() == b"%PDF-data"


def test_open_for_read_accepts_legacy_bare_filesystem_path(monkeypatch, tmp_path):
    """Pre-Agent-B IngestJob rows may carry bare /data/... paths.
    open_for_read should still read those, not crash on the missing
    scheme."""
    from yinhu_brain.services.storage import open_for_read

    target = tmp_path / "legacy.bin"
    target.write_bytes(b"legacy")
    assert open_for_read(str(target)) == b"legacy"


def test_s3_backend_uses_boto3_put_object(monkeypatch):
    """STORAGE_BACKEND=s3 routes writes through boto3, returns s3:// URL."""
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_REGION", "auto")

    calls = []

    class FakeS3:
        def put_object(self, *, Bucket, Key, Body):
            calls.append({"bucket": Bucket, "key": Key, "size": len(Body)})

    import yinhu_brain.services.storage as storage_module

    def fake_client(service_name, **kw):
        assert service_name == "s3"
        return FakeS3()

    # boto3 is only imported inside _s3_client; patch it there.
    import boto3
    monkeypatch.setattr(boto3, "client", fake_client)

    out = storage_module.store_upload(b"payload", "a.pdf")
    assert out.path.startswith("s3://test-bucket/files/")
    assert out.path.endswith(".pdf")
    assert out.size == 7
    assert len(calls) == 1
    assert calls[0]["bucket"] == "test-bucket"


def test_s3_backend_open_for_read(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")

    class FakeBody:
        def read(self):
            return b"remote-bytes"

    class FakeS3:
        def get_object(self, *, Bucket, Key):
            assert Bucket == "test-bucket"
            assert Key == "files/abc.pdf"
            return {"Body": FakeBody()}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: FakeS3())

    from yinhu_brain.services.storage import open_for_read

    assert open_for_read("s3://test-bucket/files/abc.pdf") == b"remote-bytes"


def test_s3_backend_missing_bucket_raises(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    from yinhu_brain.services.storage import store_upload

    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        store_upload(b"x", "x.bin")
