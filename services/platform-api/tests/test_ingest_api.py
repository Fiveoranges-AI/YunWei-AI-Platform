"""Tests for the schema-first ingest API (/api/win/ingest/*).

Mirrors the V1 ``test_ingest_jobs.py`` pattern: in-memory SQLite,
``_stub_queue`` to bypass Redis, FastAPI dependency override for the
session. We don't run the worker here — these tests cover the API surface
(create / list / get / patch / ignore).
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only override
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, get_session  # noqa: E402
from yunwei_win.models import (  # noqa: E402
    Document,
    DocumentType,
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yunwei_win.models.document_extraction import (  # noqa: E402
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.routes import router as yinhu_router  # noqa: E402
from yunwei_win.services.ingest import job_queue as job_queue_module  # noqa: E402


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
    calls: list[tuple[str, int, str]] = []

    def fake_enqueue(job_id: str, *, attempt: int, enterprise_id: str) -> str:
        calls.append((job_id, attempt, enterprise_id))
        return f"rq:{job_id}:a{attempt}"

    monkeypatch.setattr(job_queue_module, "enqueue_ingest_job", fake_enqueue)
    from yunwei_win.api import schema_ingest as schema_ingest_api

    monkeypatch.setattr(schema_ingest_api, "enqueue_ingest_job", fake_enqueue)
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
    app.include_router(yinhu_router, prefix="/api/win")
    return app


def _stub_ensure_helpers(monkeypatch):
    """Skip the per-enterprise table-ensure helpers; in-memory SQLite already
    has every table from ``Base.metadata.create_all``."""
    from yunwei_win.api import schema_ingest as schema_ingest_api

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(schema_ingest_api, "ensure_schema_ingest_tables_for", _noop)
    monkeypatch.setattr(schema_ingest_api, "ensure_ingest_job_tables_for", _noop)


# ---------- POST /jobs ---------------------------------------------------


@pytest.mark.asyncio
async def test_create_schema_jobs_returns_review_job(monkeypatch, tmp_path):
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
            j = body["jobs"][0]
            assert "workflow_version" not in j
            assert j["extraction_id"] is None
            assert j["status"] == "queued"
            assert len(calls) == 1
            assert calls[0][0] == j["id"]
    finally:
        await engine.dispose()


# ---------- GET /jobs ----------------------------------------------------


@pytest.mark.asyncio
async def test_list_schema_jobs_returns_active_jobs(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        session.add(IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="a.pdf", source_hint="file",
            status=IngestJobStatus.running, stage=IngestJobStage.extract,
            attempts=1,
        ))
        session.add(IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="schema.pdf", source_hint="file",
            status=IngestJobStatus.queued, stage=IngestJobStage.received,
            attempts=0,
        ))
        await session.commit()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get("/api/win/ingest/jobs?status=active")
            assert res.status_code == 200, res.text
            rows = res.json()
            assert [r["original_filename"] for r in rows] == ["schema.pdf", "a.pdf"]
    finally:
        await engine.dispose()


# ---------- GET /jobs/{id} (with + without extraction) ------------------


@pytest.mark.asyncio
async def test_get_schema_job_without_extraction_returns_null_draft(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        job = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="x.pdf", source_hint="file",
            status=IngestJobStatus.queued, stage=IngestJobStage.received,
            attempts=0,
        )
        session.add(job)
        await session.commit()
        jid = str(job.id)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(f"/api/win/ingest/jobs/{jid}")
            assert res.status_code == 200, res.text
            body = res.json()
            assert "workflow_version" not in body
            assert body["review_draft"] is None
            assert body["extraction"] is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_schema_job_with_extraction_embeds_review_draft(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/x.txt",
            original_filename="x.pdf",
            file_sha256="0" * 64,
            file_size_bytes=10,
            ocr_text="some text",
        )
        session.add(doc)
        await session.flush()
        draft_payload = {
            "extraction_id": str(uuid.uuid4()),
            "document_id": str(doc.id),
            "schema_version": 1,
            "status": "pending_review",
            "document": {"filename": "x.pdf"},
            "route_plan": {"selected_pipelines": []},
            "tables": [],
        }
        extraction = DocumentExtraction(
            document_id=doc.id,
            schema_version=1,
            provider="landingai",
            route_plan={},
            raw_pipeline_results=[],
            review_draft=draft_payload,
            status=DocumentExtractionStatus.pending_review,
        )
        session.add(extraction)
        await session.flush()
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        job = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="x.pdf", source_hint="file",
            status=IngestJobStatus.extracted, stage=IngestJobStage.done,
            attempts=1,
            document_id=doc.id,
            extraction_id=extraction.id,
            result_json=draft_payload,
        )
        session.add(job)
        await session.commit()
        jid = str(job.id)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(f"/api/win/ingest/jobs/{jid}")
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["review_draft"] == draft_payload
            assert body["extraction"]["status"] == "pending_review"
    finally:
        await engine.dispose()


# ---------- PATCH /extractions/{id} -------------------------------------


@pytest.mark.asyncio
async def test_patch_extraction_updates_review_draft(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/x.txt",
            original_filename="y.pdf",
            file_sha256="1" * 64,
            file_size_bytes=10,
            ocr_text="t",
        )
        session.add(doc)
        await session.flush()
        ex_id = uuid.uuid4()
        extraction = DocumentExtraction(
            id=ex_id,
            document_id=doc.id,
            schema_version=1,
            review_draft={
                "extraction_id": str(ex_id),
                "document_id": str(doc.id),
                "schema_version": 1,
                "status": "pending_review",
                "document": {"filename": "y.pdf"},
                "route_plan": {"selected_pipelines": []},
                "tables": [],
            },
            status=DocumentExtractionStatus.pending_review,
        )
        session.add(extraction)
        await session.commit()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            new_draft = {
                "extraction_id": str(ex_id),
                "document_id": str(doc.id),
                "schema_version": 1,
                "status": "pending_review",
                "document": {"filename": "y.pdf"},
                "route_plan": {"selected_pipelines": []},
                "tables": [
                    {
                        "table_name": "orders",
                        "label": "订单",
                        "rows": [
                            {
                                "client_row_id": "orders:0",
                                "operation": "create",
                                "cells": [
                                    {
                                        "field_name": "amount_total",
                                        "label": "订单金额",
                                        "data_type": "decimal",
                                        "value": 12345,
                                        "display_value": "12345",
                                        "status": "edited",
                                        "source": "edited",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            res = await ac.patch(
                f"/api/win/ingest/extractions/{ex_id}",
                json={"review_draft": new_draft},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["review_draft"]["tables"][0]["rows"][0]["cells"][0]["value"] == 12345
    finally:
        await engine.dispose()


# ---------- POST /extractions/{id}/ignore -------------------------------


@pytest.mark.asyncio
async def test_ignore_extraction_marks_status_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _stub_ensure_helpers(monkeypatch)
    _stub_queue(monkeypatch)
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/x.txt",
            original_filename="z.pdf",
            file_sha256="2" * 64,
            file_size_bytes=10,
            ocr_text="t",
        )
        session.add(doc)
        await session.flush()
        ex_id = uuid.uuid4()
        extraction = DocumentExtraction(
            id=ex_id,
            document_id=doc.id,
            schema_version=1,
            review_draft={},
            status=DocumentExtractionStatus.pending_review,
        )
        session.add(extraction)
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        job = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="z.pdf", source_hint="file",
            status=IngestJobStatus.extracted, stage=IngestJobStage.done,
            attempts=1,
            extraction_id=ex_id,
        )
        session.add(job)
        await session.commit()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(f"/api/win/ingest/extractions/{ex_id}/ignore")
            assert res.status_code == 200, res.text
            assert res.json()["status"] == "ignored"

        async with AsyncSession(engine, expire_on_commit=False) as session:
            ext = (
                await session.execute(
                    select(DocumentExtraction).where(DocumentExtraction.id == ex_id)
                )
            ).scalar_one()
            assert ext.status == DocumentExtractionStatus.ignored
            jrow = (await session.execute(select(IngestJob))).scalar_one()
            assert jrow.status == IngestJobStatus.canceled
    finally:
        await engine.dispose()
