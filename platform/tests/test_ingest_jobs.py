"""Tests for the async RQ-backed /api/ingest/jobs API (Agent A surface).

We don't actually start an RQ worker; we stub ``enqueue_ingest_job`` so the
API can demonstrate enqueue-on-success / failure-on-redis-down without
touching Redis or the worker module (Agent B). Postgres is faked with the
same in-memory SQLite + ``Base.metadata.create_all`` pattern used by
``test_ingest_auto_flow.py``.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only override
    yield


import yinhu_brain.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yinhu_brain import router as yinhu_router  # noqa: E402
from yinhu_brain.db import Base, get_session  # noqa: E402
from yinhu_brain.models.ingest_job import (  # noqa: E402
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yinhu_brain.services.ingest import job_queue as job_queue_module  # noqa: E402


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


def _stub_queue(monkeypatch):
    """Replace enqueue/Redis to avoid Redis dependency. Captures all calls."""
    calls: list[tuple[str, int]] = []

    def fake_enqueue(job_id: str, *, attempt: int) -> str:
        calls.append((job_id, attempt))
        return f"rq:{job_id}:a{attempt}"

    monkeypatch.setattr(job_queue_module, "enqueue_ingest_job", fake_enqueue)
    # The api module imported the helper by name — patch the bound reference too.
    from yinhu_brain.api import ingest as ingest_api

    monkeypatch.setattr(ingest_api, "enqueue_ingest_job", fake_enqueue)
    return calls


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
    # Mirrors platform_app/main.py: yinhu router is mounted at /win.
    app.include_router(yinhu_router, prefix="/win")
    return app


# ---------- POST /jobs ---------------------------------------------------


@pytest.mark.asyncio
async def test_create_jobs_returns_batch_id_and_persists_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    calls = _stub_queue(monkeypatch)
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                "/win/api/ingest/jobs",
                files=[("files", ("a.pdf", b"%PDF-fake", "application/pdf"))],
                data={"source_hint": "file"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert "batch_id" in body
            assert len(body["jobs"]) == 1
            j = body["jobs"][0]
            assert j["status"] == "queued"
            assert j["original_filename"] == "a.pdf"
            assert calls == [(j["id"], 1)]

        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (await session.execute(select(IngestJob))).scalar_one()
            assert row.enterprise_id == "tenant_test"
            assert row.attempts == 1
            assert row.rq_job_id == f"rq:{j['id']}:a1"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_jobs_supports_text_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                "/win/api/ingest/jobs",
                data={"text": "hello world", "source_hint": "pasted_text"},
            )
            assert res.status_code == 200, res.text
            jobs = res.json()["jobs"]
            assert len(jobs) == 1
            assert jobs[0]["original_filename"] == "note.txt"
            assert jobs[0]["source_hint"] == "pasted_text"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_jobs_rejects_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                "/win/api/ingest/jobs", data={"source_hint": "file"}
            )
            assert res.status_code == 400
    finally:
        await engine.dispose()


# ---------- GET /jobs (list + by id) -------------------------------------


@pytest.mark.asyncio
async def test_list_jobs_split_by_active_and_history(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        session.add(IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="run.pdf", source_hint="file",
            status=IngestJobStatus.running, stage=IngestJobStage.extract,
            attempts=1,
        ))
        session.add(IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="old.pdf", source_hint="file",
            status=IngestJobStatus.confirmed, stage=IngestJobStage.done,
            attempts=1,
        ))
        await session.commit()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            active = (await ac.get("/win/api/ingest/jobs?status=active")).json()
            history = (await ac.get("/win/api/ingest/jobs?status=history")).json()
            assert [j["original_filename"] for j in active] == ["run.pdf"]
            assert [j["original_filename"] for j in history] == ["old.pdf"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_job_returns_result_json_for_extracted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        j = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="x.pdf", source_hint="file",
            status=IngestJobStatus.extracted, stage=IngestJobStage.done,
            attempts=1,
            result_json={"draft": {"customer": {"full_name": "ABC"}}, "plan": {}},
        )
        session.add(j)
        await session.commit()
        jid = str(j.id)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(f"/win/api/ingest/jobs/{jid}")
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "extracted"
            assert body["result_json"]["draft"]["customer"]["full_name"] == "ABC"
    finally:
        await engine.dispose()


# ---------- retry / cancel -----------------------------------------------


@pytest.mark.asyncio
async def test_retry_failed_job_reenqueues(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    calls = _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        j = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="bad.pdf", source_hint="file",
            status=IngestJobStatus.failed, stage=IngestJobStage.ocr,
            attempts=1, error_message="upstream 500",
        )
        session.add(j)
        await session.commit()
        jid = str(j.id)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(f"/win/api/ingest/jobs/{jid}/retry")
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "queued"
            assert body["attempts"] == 2
            assert calls == [(jid, 2)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancel_queued_job_marks_canceled(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        j = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="q.pdf", source_hint="file",
            status=IngestJobStatus.queued, stage=IngestJobStage.received,
            attempts=0,
        )
        session.add(j)
        await session.commit()
        jid = str(j.id)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(f"/win/api/ingest/jobs/{jid}/cancel")
            assert res.status_code == 200, res.text
            assert res.json()["status"] == "canceled"
    finally:
        await engine.dispose()


# ---------- RQ id format ----------------------------------------------


def test_rq_id_uses_only_letters_digits_dashes_underscores():
    """RQ rejects job ids with any char outside [A-Za-z0-9_-]. Regression
    for the colon-separated format that shipped in commit be56aee and
    failed every real enqueue with 'Job ID must only contain letters,
    numbers, underscores and dashes'. SCYN250620合同.pdf surfaced it."""
    import re
    from yinhu_brain.services.ingest.job_queue import _rq_id_for

    rid = _rq_id_for("abc12345-6789-4def-0123-456789abcdef", 3)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", rid), rid
    # Encodes the attempt so retries don't collide
    assert rid.endswith("-a3")
    # Encodes the business job id (UUID) verbatim
    assert "abc12345-6789-4def-0123-456789abcdef" in rid
