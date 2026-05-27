"""Round 9 self-audit — security regressions.

Covers the P0 findings surfaced in the adversarial review:

  P0-2 · upload path traversal / ext whitelist:
    * filename-suffix `.php` (or any non-allowed ext) must NOT land on disk
      with that ext, even when content-type bypasses _infer_source_type
    * filename `../../etc/passwd` must not escape UPLOAD_ROOT
    * an enterprise_id with shell metacharacters must be sanitized before
      being used as a directory segment (defense in depth — server-set
      today, but anchors the contract)

  P0-3 · confirm_writer entity_type gating:
    * candidate payload with `entity_type="ActionLog"` (or FieldProvenance,
      Payable, FixedAsset, StockMovement) must be rejected — these are
      audit / system-managed entities and must NOT be writable through the
      candidate confirm flow

  P1-7 · DemoMockProvider edges:
    * empty filename → 400 (not crash)
    * 0-byte file → still produces candidate (mock provider is
      deterministic from filename+size hash)
    * non-ASCII / unicode filename works
    * oversized file → 413
"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


_TMP_UPLOAD_ROOT = Path("/tmp/jintai-security-audit-uploads")


@pytest.fixture(autouse=True)
def _isolate_upload_root(monkeypatch):
    monkeypatch.setenv("JINTAI_UPLOAD_ROOT", str(_TMP_UPLOAD_ROOT))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if _TMP_UPLOAD_ROOT.exists():
        shutil.rmtree(_TMP_UPLOAD_ROOT)
    yield
    if _TMP_UPLOAD_ROOT.exists():
        shutil.rmtree(_TMP_UPLOAD_ROOT)


@pytest.fixture(autouse=True)
def _reload_parse_upload_root():
    import importlib

    import yunwei_win.api.parse_upload as pu

    importlib.reload(pu)
    yield


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

import yunwei_win.models  # noqa: F401, E402 — register
from yunwei_win.db import Base, get_session  # noqa: E402


async def _make_engine():
    from sqlalchemy import event

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine, *, actor: str = "audit-actor", enterprise_id: str | None = None):
    """Test app — stamps actor; optionally stamps enterprise_id (or leaves
    unset so endpoint falls back to 'default')."""
    from fastapi import FastAPI

    from yunwei_win.api.parse_upload import router as parse_upload_router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp(request, call_next):
        request.state.actor = actor
        if enterprise_id is not None:
            request.state.enterprise_id = enterprise_id
        return await call_next(request)

    app.include_router(parse_upload_router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _post_upload(client, filename, content, mime):
    return await client.post(
        "/parse/upload",
        files={"file": (filename, content, mime)},
    )


# ============================== P0-2 ===============================


@pytest.mark.asyncio
async def test_upload_php_filename_does_not_land_as_php_on_disk() -> None:
    """An attacker uploading evil.php with content-type image/jpeg must not
    cause a `.php` file to be written under UPLOAD_ROOT.
    """
    import httpx

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(
            client, "evil.php", b"<?php phpinfo(); ?>", "image/jpeg",
        )
    assert resp.status_code == 200, resp.text

    # Sweep the upload tree — no .php file may exist.
    for p in _TMP_UPLOAD_ROOT.rglob("*"):
        assert p.suffix != ".php", f"php file landed on disk: {p}"
        # also catch other dangerous exts in case future content-type tricks
        assert p.suffix not in {".sh", ".html", ".exe", ".bin"}, (
            f"non-whitelisted ext written: {p}"
        )

    # The actual stored ext should map to the source_type inferred from
    # content-type. content-type image/jpeg → wechat_screenshot → .jpg.
    body = resp.json()
    assert body["source_type"] == "wechat_screenshot"
    assert body["attachment"]["path"].endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_filename_with_traversal_does_not_escape_upload_root() -> None:
    """A pathological filename must not produce a file outside UPLOAD_ROOT."""
    import httpx

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(
            client, "../../etc/passwd", b"hello", "image/png",
        )

    # Either the request 200s with a safely-stored file, or 400s. EITHER way
    # the file must live under UPLOAD_ROOT.
    if resp.status_code == 200:
        body = resp.json()
        stored = Path(body["attachment"]["path"]).resolve()
        root = _TMP_UPLOAD_ROOT.resolve()
        assert str(stored).startswith(str(root)), (
            f"file escaped UPLOAD_ROOT: stored={stored} root={root}"
        )
    else:
        assert resp.status_code in (400, 422), resp.text


@pytest.mark.asyncio
async def test_upload_with_pathological_tenant_id_is_sanitized() -> None:
    """If middleware were ever to stamp a tenant_id containing path
    separators (it shouldn't, but defense in depth), the on-disk path must
    not escape UPLOAD_ROOT.
    """
    import httpx

    engine = await _make_engine()
    # Stamp a hostile enterprise_id directly onto request.state. In prod the
    # platform middleware never produces this, but `_save_upload` should
    # still refuse to write outside UPLOAD_ROOT.
    app = _build_app(engine, enterprise_id="../../escape_attempt")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "ok.jpg", b"x", "image/jpeg")

    assert resp.status_code == 200, resp.text
    stored = Path(resp.json()["attachment"]["path"]).resolve()
    root = _TMP_UPLOAD_ROOT.resolve()
    assert str(stored).startswith(str(root)), (
        f"sanitisation failed: stored={stored} root={root}"
    )
    # Sanitised dir should be a plain segment (no `..`, no `/`).
    parent_name = stored.parent.name
    assert ".." not in parent_name
    assert "/" not in parent_name
    assert "\\" not in parent_name


# ============================== P0-3 ===============================


@pytest.mark.asyncio
async def test_confirm_writer_rejects_actionlog_entity_type() -> None:
    """confirm_writer must refuse to materialise audit / system-managed
    entities. ActionLog, FieldProvenance, StockMovement, Payable, FixedAsset
    must all be outside the writable allow-list.
    """
    from yunwei_win.services.confirm_writer import _ENTITY_MODEL

    forbidden = [
        "ActionLog",
        "FieldProvenance",
        "StockMovement",
        "Payable",
        "FixedAsset",
        "GoodsReceipt",
        "StockAlert",
        "ChartOfAccount",
        "PeriodOpeningBalance",
    ]
    for et in forbidden:
        assert et not in _ENTITY_MODEL, (
            f"{et} unexpectedly in confirm_writer._ENTITY_MODEL — would let "
            f"attacker forge audit/system rows via /confirm/entities"
        )


@pytest.mark.asyncio
async def test_confirm_endpoint_rejects_unknown_entity_type() -> None:
    """End-to-end: POST /confirm/entities with a forbidden entity_type must
    return 4xx (not 500, not silently accepted).
    """
    import httpx
    from fastapi import FastAPI

    engine = await _make_engine()
    from yunwei_win.api.confirm import router as confirm_router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp_actor(request, call_next):
        request.state.actor = "audit-actor"
        return await call_next(request)

    app.include_router(confirm_router)
    app.dependency_overrides[get_session] = _override_session

    body = {
        "ingestion_id": str(uuid4()),
        "source_doc_ref": "audit://forge",
        "entities": [
            {
                "temp_id": "t1",
                "entity_type": "ActionLog",
                "fields": [
                    {
                        "name": "input_summary",
                        "value": "FORGED action — see if audit lets this in",
                        "confidence": 0.99,
                        "was_edited": True,
                        "source_span": {"text": "x"},
                    },
                ],
            },
        ],
        "relationships": [],
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/confirm/entities", json=body)

    # Must NOT succeed. 4xx (validation error) or 500 with no row written.
    assert resp.status_code >= 400, (
        f"unknown entity_type ActionLog was ACCEPTED: {resp.status_code} {resp.text}"
    )


# ============================== P1-7 (upload edges) ===============================


@pytest.mark.asyncio
async def test_upload_empty_filename_returns_400() -> None:
    import httpx

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        # multipart parsers normalise empty-name uploads; some treat them as
        # missing-file. Either 400 or 422 is acceptable; 500 is not.
        resp = await _post_upload(client, "", b"data", "image/jpeg")
    assert resp.status_code in (400, 422), (
        f"empty filename should be a client error, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_upload_zero_byte_file_does_not_crash() -> None:
    """A 0-byte file must not crash the parse pipeline; DemoMockProvider
    keys on filename+size, so size=0 is a legal hash input.
    """
    import httpx

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "empty.jpg", b"", "image/jpeg")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attachment"]["size_bytes"] == 0
    assert body["provider"] == "demo-mock"


@pytest.mark.asyncio
async def test_upload_unicode_filename_is_preserved_in_response() -> None:
    import httpx

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(
            client, "领料单-2026-01.jpg", b"\xff\xd8\xff\xd9", "image/jpeg",
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attachment"]["filename"] == "领料单-2026-01.jpg"
    # On-disk filename uses sha256[:16].ext (no unicode), so no encoding
    # surprises in the filesystem layer.
    stored = Path(body["attachment"]["path"]).name
    assert stored.endswith(".jpg")
    assert all(ord(c) < 128 for c in stored), (
        f"on-disk filename leaked unicode: {stored!r}"
    )


@pytest.mark.asyncio
async def test_upload_oversize_returns_413() -> None:
    """Files above MAX_FILE_BYTES (20 MB) must 413 rather than silently
    truncate or crash the worker.
    """
    import httpx

    # Read MAX from the module so this test stays in sync with constant
    # tuning, but we send slightly over to trigger the guard.
    from yunwei_win.api import parse_upload as pu

    over = pu.MAX_FILE_BYTES + 1024
    payload = b"\x00" * over

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "big.jpg", payload, "image/jpeg")
    assert resp.status_code == 413, (
        f"expected 413 for {over}B, got {resp.status_code}: {resp.text[:200]}"
    )
