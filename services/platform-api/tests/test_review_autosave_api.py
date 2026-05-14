from __future__ import annotations

from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():
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


async def _seed_extraction(engine) -> DocumentExtraction:
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
            status=DocumentExtractionStatus.pending_review,
            review_version=0,
        )
        session.add(extraction)
        await session.flush()
        extraction.review_draft = _minimal_review_draft(extraction.id, document.id)
        await session.commit()
        await session.refresh(extraction)
        return extraction


async def _acquire_lock(ac, extraction_id, user: str) -> dict:
    res = await ac.post(
        f"/api/win/ingest/extractions/{extraction_id}/review/lock",
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_autosave_requires_matching_lock_and_version():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, extraction.id, "user_a")
            res = await ac.patch(
                f"/api/win/ingest/extractions/{extraction.id}/review",
                headers={"X-User-Id": "user_a"},
                json={
                    "lock_token": lock["lock_token"],
                    "base_version": 99,
                    "cell_patches": [],
                    "row_patches": [],
                },
            )
            assert res.status_code == 409, res.text
            assert "review_version mismatch" in res.json()["detail"]
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_autosave_rejects_wrong_lock_token():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            await _acquire_lock(ac, extraction.id, "user_a")
            res = await ac.patch(
                f"/api/win/ingest/extractions/{extraction.id}/review",
                headers={"X-User-Id": "user_a"},
                json={
                    "lock_token": str(uuid4()),
                    "base_version": 0,
                    "cell_patches": [],
                    "row_patches": [],
                },
            )
            assert res.status_code == 409, res.text
            assert "lock token mismatch" in res.json()["detail"]
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_autosave_updates_cell_and_increments_version():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, extraction.id, "user_a")
            res = await ac.patch(
                f"/api/win/ingest/extractions/{extraction.id}/review",
                headers={"X-User-Id": "user_a"},
                json={
                    "lock_token": lock["lock_token"],
                    "base_version": 0,
                    "cell_patches": [
                        {
                            "table_name": "customers",
                            "client_row_id": "customers:0",
                            "field_name": "short_name",
                            "value": "测试",
                        }
                    ],
                    "row_patches": [],
                },
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["review_version"] == 1
            cells = {
                c["field_name"]: c
                for c in body["review_draft"]["tables"][0]["rows"][0]["cells"]
            }
            assert cells["short_name"]["value"] == "测试"
            assert cells["short_name"]["status"] == "edited"
            assert cells["short_name"]["source"] == "edited"

        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == extraction.id
                    )
                )
            ).scalar_one()
            assert row.review_version == 1
            persisted_cells = {
                c["field_name"]: c
                for c in row.review_draft["tables"][0]["rows"][0]["cells"]
            }
            assert persisted_cells["short_name"]["value"] == "测试"
            assert persisted_cells["short_name"]["status"] == "edited"
            assert row.last_reviewed_by == "user_a"
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_autosave_updates_row_decision_and_current_step():
    engine = await _make_engine()
    extraction = await _seed_extraction(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, extraction.id, "user_a")
            target_entity = uuid4()
            res = await ac.patch(
                f"/api/win/ingest/extractions/{extraction.id}/review",
                headers={"X-User-Id": "user_a"},
                json={
                    "lock_token": lock["lock_token"],
                    "base_version": 0,
                    "cell_patches": [],
                    "row_patches": [
                        {
                            "table_name": "customers",
                            "client_row_id": "customers:0",
                            "operation": "update",
                            "selected_entity_id": str(target_entity),
                            "match_level": "strong",
                            "match_keys": ["tax_id"],
                            "reason": "user picked the existing customer",
                        }
                    ],
                    "current_step": "contacts",
                },
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["review_draft"]["current_step"] == "contacts"
            row = body["review_draft"]["tables"][0]["rows"][0]
            assert row["row_decision"]["operation"] == "update"
            assert row["row_decision"]["selected_entity_id"] == str(target_entity)
            assert row["row_decision"]["match_level"] == "strong"
            assert row["entity_id"] == str(target_entity)
            assert row["is_writable"] is True

        async with AsyncSession(engine, expire_on_commit=False) as session:
            persisted = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == extraction.id
                    )
                )
            ).scalar_one()
            assert persisted.review_draft["current_step"] == "contacts"
            assert (
                persisted.review_draft["tables"][0]["rows"][0]["row_decision"][
                    "operation"
                ]
                == "update"
            )
    finally:
        await engine.dispose()
        await dispose_all()
