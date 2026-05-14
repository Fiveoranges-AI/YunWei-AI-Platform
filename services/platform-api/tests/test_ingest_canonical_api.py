"""Canonical schema-first ingest API tests.

The public Win ingest surface is unversioned: /api/win/ingest/*.
Versioned /ingest/v2 aliases should not remain once schema-first review is
the only supported upload/review workflow.
"""

from __future__ import annotations

import pytest

import yunwei_win.models  # noqa: F401 - register SQLAlchemy mappers
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from yunwei_win.db import Base, get_session
from yunwei_win.routes import router as win_router
from yunwei_win.services.ingest import job_queue as job_queue_module


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_enterprise(request: Request, call_next):
        request.state.enterprise_id = "tenant_test"
        return await call_next(request)

    async def session_dep():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_dep
    app.include_router(win_router, prefix="/api/win")
    return app


def _stub_queue(monkeypatch):
    calls: list[tuple[str, int, str]] = []

    def fake_enqueue(job_id: str, *, attempt: int, enterprise_id: str) -> str:
        calls.append((job_id, attempt, enterprise_id))
        return f"rq:{job_id}:a{attempt}"

    monkeypatch.setattr(job_queue_module, "enqueue_ingest_job", fake_enqueue)
    from yunwei_win.api import schema_ingest as schema_ingest_api

    monkeypatch.setattr(schema_ingest_api, "enqueue_ingest_job", fake_enqueue)
    return calls


def _stub_ensure_helpers(monkeypatch):
    from yunwei_win.api import schema_ingest as schema_ingest_api

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(schema_ingest_api, "ensure_schema_ingest_tables_for", _noop)
    monkeypatch.setattr(schema_ingest_api, "ensure_ingest_job_tables_for", _noop)


@pytest.mark.asyncio
async def test_create_canonical_ingest_job_returns_schema_review_job(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    calls = _stub_queue(monkeypatch)
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                "/api/win/ingest/jobs",
                files=[("files", ("a.pdf", b"%PDF-fake", "application/pdf"))],
                data={"source_hint": "file"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert len(body["jobs"]) == 1
            job = body["jobs"][0]
            assert "workflow_version" not in job
            assert "extraction_id" in job
            assert job["status"] == "queued"
            assert len(calls) == 1
            assert calls[0][0] == job["id"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_versioned_ingest_v2_jobs_route_is_removed(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get("/api/win/ingest/v2/jobs?status=active")
            assert res.status_code == 404
    finally:
        await engine.dispose()
