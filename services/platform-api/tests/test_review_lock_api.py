from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override the project-level fixture that wants Postgres+Redis
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, dispose_all, get_session  # noqa: E402
from yunwei_win.models.document import Document, DocumentType  # noqa: E402
from yunwei_win.models.document_extraction import (  # noqa: E402
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.routes import router as yinhu_router  # noqa: E402


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
    app.include_router(yinhu_router, prefix="/api/win")
    return app


def _minimal_review_draft(extraction_id: UUID, document_id: UUID) -> dict:
    return {
        "extraction_id": str(extraction_id),
        "document_id": str(document_id),
        "schema_version": 1,
        "status": "pending_review",
        "review_version": 0,
        "current_step": "customer",
        "document": {"filename": "profile.txt", "summary": None, "source_text": None},
        "route_plan": {"selected_pipelines": []},
        "steps": [
            {
                "key": "customer",
                "label": "客户",
                "table_names": ["customers"],
                "status": "in_progress",
            }
        ],
        "tables": [
            {
                "table_name": "customers",
                "label": "客户",
                "is_array": False,
                "rows": [
                    {
                        "client_row_id": "customers:0",
                        "operation": "create",
                        "is_writable": True,
                        "row_decision": {
                            "operation": "create",
                            "candidate_entities": [],
                            "match_keys": [],
                        },
                        "cells": [
                            {
                                "field_name": "full_name",
                                "label": "公司全称",
                                "data_type": "text",
                                "value": "测试有限公司",
                                "display_value": "测试有限公司",
                                "status": "extracted",
                                "source": "ai",
                                "source_refs": [],
                                "review_visible": True,
                            },
                            {
                                "field_name": "short_name",
                                "label": "简称",
                                "data_type": "text",
                                "value": None,
                                "display_value": "",
                                "status": "missing",
                                "source": "empty",
                                "source_refs": [],
                                "review_visible": True,
                            },
                        ],
                    }
                ],
                "presentation": "card",
                "review_step": "customer",
            }
        ],
        "schema_warnings": [],
        "general_warnings": [],
    }


async def _seed_extraction(
    engine,
    *,
    lock_token: UUID | None = None,
    locked_by: str | None = None,
    lock_expires_at: datetime | None = None,
    status: DocumentExtractionStatus = DocumentExtractionStatus.pending_review,
) -> DocumentExtraction:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        document = Document(
            type=DocumentType.text_note,
            file_url="memory://profile.txt",
            file_sha256="deadbeef" * 8,
            file_size_bytes=10,
            original_filename="profile.txt",
            content_type="text/plain",
        )
        session.add(document)
        await session.flush()
        extraction = DocumentExtraction(
            document_id=document.id,
            status=status,
            review_version=0,
            lock_token=lock_token,
            locked_by=locked_by,
            lock_expires_at=lock_expires_at,
        )
        extraction.review_draft = _minimal_review_draft(uuid4(), document.id)
        # Patch the draft's IDs to match the row we're inserting so a later
        # GET roundtrip lines up with the persisted ids.
        session.add(extraction)
        await session.flush()
        extraction.review_draft = _minimal_review_draft(extraction.id, document.id)
        await session.commit()
        await session.refresh(extraction)
        return extraction


@pytest.mark.asyncio
async def test_get_review_returns_vnext_draft_and_version():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(
                f"/api/win/ingest/extractions/{extraction.id}/review"
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["id"] == str(extraction.id)
            assert body["review_version"] == 0
            assert body["review_draft"]["tables"][0]["table_name"] == "customers"
            assert body["lock"]["locked_by"] is None
            assert body["lock"]["lock_expires_at"] is None
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_acquire_lock_returns_token_for_unlocked_pending_review():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_a"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["mode"] == "edit"
            assert body["locked_by"] == "user_a"
            assert body["lock_token"]
            assert body["review_version"] == 0
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_acquire_lock_by_same_user_refreshes_edit_lock():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            first = await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_a"},
            )
            assert first.status_code == 200, first.text
            second = await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_a"},
            )
            assert second.status_code == 200, second.text
            assert first.json()["mode"] == "edit"
            assert second.json()["mode"] == "edit"
            assert first.json()["locked_by"] == "user_a"
            assert second.json()["locked_by"] == "user_a"
            # Same user reacquires → same token, just refreshed expiry.
            assert first.json()["lock_token"] == second.json()["lock_token"]
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_acquire_lock_by_other_user_returns_read_only():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_a"},
            )
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_b"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["mode"] == "read_only"
            assert body["locked_by"] == "user_a"
            assert body["lock_token"] is None
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_expired_lock_can_be_reacquired_by_other_user():
    engine = await _make_engine()
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    extraction = await _seed_extraction(
        engine,
        lock_token=uuid4(),
        locked_by="user_a",
        lock_expires_at=expired,
    )
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction.id}/review/lock",
                headers={"X-User-Id": "user_b"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["mode"] == "edit"
            assert body["locked_by"] == "user_b"
            assert body["lock_token"]
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == extraction.id
                    )
                )
            ).scalar_one()
            assert row.locked_by == "user_b"
    finally:
        await engine.dispose()
        await dispose_all()
