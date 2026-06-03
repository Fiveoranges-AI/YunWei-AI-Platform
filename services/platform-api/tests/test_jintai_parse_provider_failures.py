"""Round 11 — ClaudeProvider failure-mode regression tests (round 9 P1-6 deferred).

The /parse/upload endpoint falls back to DemoMockProvider when no
ANTHROPIC_API_KEY is set, but in production the real ClaudeProvider is
swapped in. This file locks down the behaviour of every failure mode
the real provider can produce, so prod doesn't surprise us:

  - upstream call_claude raises LLMCallFailed (timeout / 429 / 5xx)
        → 502 Bad Gateway (round 11 fix)
  - provider returns empty entities (LLM produced no extractable rows)
        → 200, candidate.entities == []
  - provider returns malformed JSON that the upstream parser silently
    flattens to entities=[] + warnings=[...]
        → 200, candidate.entities == [], warnings include the parser hint
  - generic provider exception (not LLMCallFailed)
        → 500 (existing behaviour, kept as fallback)

We don't test the real ClaudeProvider here (that needs respx + the
anthropic SDK). We patch ``_resolve_provider`` to return a stub
``ExtractionProvider`` for each scenario.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


_TMP_UPLOAD_ROOT = Path("/tmp/jintai-r11-uploads")


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


def _build_app(engine):
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
        request.state.actor = "r11-actor"
        return await call_next(request)

    app.include_router(parse_upload_router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _post_upload(client, filename, content, mime):
    return await client.post(
        "/parse/upload",
        files={"file": (filename, content, mime)},
    )


# ============================== stub providers ==============================


def _patch_provider(monkeypatch, stub_extract):
    """Replace _resolve_provider so the endpoint goes down the non-demo
    branch and calls our stub.extract()."""
    from yunwei_win.api import parse_upload as pu

    class _StubProvider:
        name = "stub"

        async def extract(self, payload):
            return await stub_extract(payload)

    monkeypatch.setattr(pu, "_resolve_provider", lambda: (_StubProvider(), "stub"))


# ============================== tests ==============================


@pytest.mark.asyncio
async def test_llm_call_failed_surfaces_as_502(monkeypatch) -> None:
    """LLMCallFailed (timeout / 429 / 5xx after 3 retries) must surface as
    502 Bad Gateway, not 500. Distinguishes upstream outage from our bug.
    """
    import httpx

    from yunwei_win.services.llm import LLMCallFailed

    async def _raise_llm_failure(_payload):
        raise LLMCallFailed("Claude call failed after 3 attempts: anthropic.APITimeoutError")

    _patch_provider(monkeypatch, _raise_llm_failure)

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "doc.pdf", b"%PDF-1.4\n%mock\n", "application/pdf")

    assert resp.status_code == 502, (
        f"LLMCallFailed should be 502 (upstream unavailable), got {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    assert "upstream LLM unavailable" in resp.text


@pytest.mark.asyncio
async def test_provider_returns_empty_entities_is_200(monkeypatch) -> None:
    """LLM produced 0 extractable entities (e.g. blurry image, OCR scrambled
    everything). This is NOT an error — return 200 with empty candidate so
    the user sees 'no fields detected, please retry / type manually'.
    """
    import httpx

    from yunwei_win.services.parse_pipeline.providers.base import ProviderResult

    async def _empty(_payload):
        return ProviderResult(entities=[], warnings=["LLM 找不到可抽取字段"], provider_name="stub")

    _patch_provider(monkeypatch, _empty)

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "blank.pdf", b"%PDF-1.4\n", "application/pdf")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate"]["entities"] == []
    # The pipeline layer surfaces warnings to the candidate response.
    warnings = body["candidate"].get("warnings", [])
    assert any("LLM" in w or "找不到" in w for w in warnings), (
        f"empty-result warnings should propagate, got {warnings}"
    )


@pytest.mark.asyncio
async def test_provider_returns_partial_json_is_200_with_warning(monkeypatch) -> None:
    """If we feed _parse_response_json a malformed payload directly, it
    flattens to entities=[] + warnings=['LLM 响应未能解析为 JSON']. Cover
    via the upstream pipeline so we're sure the endpoint surfaces it.
    """
    import httpx

    from yunwei_win.services.parse_pipeline.providers.claude import _parse_response_json

    # Verify the parser's contract first so the test is honest.
    pr = _parse_response_json("{ this is not closed ")
    assert pr.entities == []
    assert any("JSON" in w for w in pr.warnings)

    # Now exercise via the endpoint.
    async def _bad_json_provider(_payload):
        return _parse_response_json("{ broken")

    _patch_provider(monkeypatch, _bad_json_provider)

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "broken.pdf", b"%PDF-1.4\n", "application/pdf")
    assert resp.status_code == 200, resp.text
    warnings = resp.json()["candidate"].get("warnings", [])
    assert any("JSON" in w for w in warnings), (
        f"expected JSON-parse warning to surface, got {warnings}"
    )


@pytest.mark.asyncio
async def test_generic_provider_exception_still_500(monkeypatch) -> None:
    """A non-LLM exception inside provider.extract() (e.g. KeyError, ValueError
    because our adapter mis-shaped the payload) should remain a 500 — that
    really IS a bug on our side, monitoring should page.
    """
    import httpx

    async def _value_error(_payload):
        raise ValueError("provider adapter mis-shaped payload")

    _patch_provider(monkeypatch, _value_error)

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "doc.pdf", b"%PDF-1.4\n", "application/pdf")

    assert resp.status_code == 500, (
        f"non-LLM exception should remain 500 (it's our bug), got {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    assert "ValueError" in resp.text


@pytest.mark.asyncio
async def test_no_api_key_falls_back_to_demo_mock_provider(monkeypatch) -> None:
    """Sanity: without ANTHROPIC_API_KEY, _resolve_provider must pick
    DemoMockProvider — not raise, not 500. Locks down the demo path.
    """
    import httpx

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Re-import to re-evaluate _resolve_provider with the cleared env.
    import importlib

    from yunwei_win.api import parse_upload as pu

    importlib.reload(pu)
    provider, name = pu._resolve_provider()
    assert name == "demo-mock", (
        f"with no ANTHROPIC_API_KEY, expected demo-mock provider, got {name}"
    )

    engine = await _make_engine()
    app = _build_app(engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await _post_upload(client, "smoke.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider"] == "demo-mock"
