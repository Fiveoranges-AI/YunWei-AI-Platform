from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from yunwei_win.models.contact import Contact  # noqa: E402
from yunwei_win.models.customer import Customer  # noqa: E402
from yunwei_win.models.document import Document, DocumentType  # noqa: E402
from yunwei_win.models.document_extraction import (  # noqa: E402
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.models.document_parse import DocumentParse  # noqa: E402
from yunwei_win.models.field_provenance import FieldProvenance  # noqa: E402
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


# --- draft fixture builders -------------------------------------------------


def _cell(field_name: str, *, label: str, data_type: str = "text", value=None,
          source: str = "ai", status: str | None = None,
          confidence: float | None = 0.9, source_refs=None, required: bool = False):
    if status is None:
        status = "missing" if value in (None, "") else "extracted"
    if status == "missing":
        source = "empty"
    return {
        "field_name": field_name,
        "label": label,
        "data_type": data_type,
        "required": required,
        "is_array": False,
        "value": value,
        "display_value": "" if value in (None, "") else str(value),
        "status": status,
        "source": source,
        "confidence": confidence if value not in (None, "") else None,
        "source_refs": source_refs or [],
        "review_visible": True,
        "explicit_clear": False,
    }


def _row(client_row_id: str, *, cells: list[dict], operation: str = "create",
         is_writable: bool = True, entity_id: UUID | None = None,
         selected_entity_id: UUID | None = None,
         match_level: str | None = None):
    return {
        "client_row_id": client_row_id,
        "entity_id": str(entity_id) if entity_id else None,
        "operation": "update" if operation == "update" else "create",
        "is_writable": is_writable,
        "row_decision": {
            "operation": operation,
            "selected_entity_id": str(selected_entity_id) if selected_entity_id else None,
            "candidate_entities": [],
            "match_keys": [],
            "match_level": match_level,
        },
        "cells": cells,
    }


def _table(table_name: str, *, label: str, rows: list[dict],
           is_array: bool = False, presentation: str = "card",
           review_step: str | None = None):
    return {
        "table_name": table_name,
        "label": label,
        "is_array": is_array,
        "rows": rows,
        "presentation": presentation,
        "review_step": review_step,
    }


def _draft(*, extraction_id: UUID, document_id: UUID, parse_id: UUID | None,
           tables: list[dict], review_version: int = 0):
    return {
        "extraction_id": str(extraction_id),
        "document_id": str(document_id),
        "parse_id": str(parse_id) if parse_id else None,
        "schema_version": 1,
        "status": "pending_review",
        "review_version": review_version,
        "current_step": "summary",
        "document": {"filename": "doc.txt", "summary": None, "source_text": None},
        "route_plan": {"selected_pipelines": []},
        "steps": [],
        "tables": tables,
        "schema_warnings": [],
        "general_warnings": [],
    }


# --- seeds -----------------------------------------------------------------


async def _seed_extraction(
    engine,
    *,
    draft_tables_builder,
    parse_artifact_present: bool = True,
) -> dict:
    """Create one Document + DocumentParse + DocumentExtraction with a draft.

    ``draft_tables_builder`` is a callable that returns the list of table dicts
    once we know the extraction.id (so child rows can reference their parent
    row's client_row_id without race).
    """

    async with AsyncSession(engine, expire_on_commit=False) as session:
        document = Document(
            type=DocumentType.text_note,
            file_url="memory://doc.txt",
            file_sha256="deadbeef" * 8,
            file_size_bytes=42,
            original_filename="doc.txt",
            content_type="text/plain",
        )
        session.add(document)
        await session.flush()

        parse_id = None
        if parse_artifact_present:
            parse = DocumentParse(
                document_id=document.id,
                provider="text",
                model="stub",
                artifact={"markdown": "stub"},
            )
            session.add(parse)
            await session.flush()
            parse_id = parse.id

        extraction = DocumentExtraction(
            document_id=document.id,
            parse_id=parse_id,
            status=DocumentExtractionStatus.pending_review,
            review_version=0,
        )
        session.add(extraction)
        await session.flush()

        tables = draft_tables_builder()
        extraction.review_draft = _draft(
            extraction_id=extraction.id,
            document_id=document.id,
            parse_id=parse_id,
            tables=tables,
        )
        await session.commit()
        await session.refresh(extraction)
        return {
            "extraction_id": extraction.id,
            "document_id": document.id,
            "parse_id": parse_id,
        }


async def _acquire_lock(ac, extraction_id, user: str) -> dict:
    res = await ac.post(
        f"/api/win/ingest/extractions/{extraction_id}/review/lock",
        headers={"X-User-Id": user},
    )
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# 1. Lock / version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_requires_valid_lock_token_and_latest_version():
    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        cells=[
                            _cell("full_name", label="公司全称", value="测试有限公司",
                                  required=True),
                        ],
                    )
                ],
            ),
        ]

    engine = await _make_engine()
    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={
                    "lock_token": lock["lock_token"],
                    "base_version": 99,  # stale
                },
            )
            assert res.status_code == 409, res.text
            assert "review_version mismatch" in res.json()["detail"]
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 2. Customer + child link
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_writes_customer_then_child_system_links():
    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        cells=[
                            _cell("full_name", label="公司全称", value="测试有限公司",
                                  required=True),
                        ],
                    )
                ],
            ),
            _table(
                "contacts",
                label="联系人",
                is_array=True,
                rows=[
                    _row(
                        "contacts:0",
                        cells=[
                            _cell("name", label="姓名", value="张三", required=True),
                            _cell("mobile", label="手机", value="13800000000"),
                        ],
                    )
                ],
            ),
        ]

    engine = await _make_engine()
    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "confirmed"
            assert len(body["written_rows"]["customers"]) == 1
            assert len(body["written_rows"]["contacts"]) == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            customer = (await session.execute(select(Customer))).scalar_one()
            assert customer.full_name == "测试有限公司"
            contact = (await session.execute(select(Contact))).scalar_one()
            assert contact.customer_id == customer.id
            assert contact.name == "张三"
            assert contact.mobile == "13800000000"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 3. Default-only / non-writable rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_skips_default_only_rows():
    def _tables():
        # An orders row with no AI values, is_writable=false, ignore decision.
        return [
            _table(
                "orders",
                label="订单",
                rows=[
                    {
                        "client_row_id": "orders:0",
                        "entity_id": None,
                        "operation": "create",
                        "is_writable": False,
                        "row_decision": {
                            "operation": "ignore",
                            "selected_entity_id": None,
                            "candidate_entities": [],
                            "match_keys": [],
                            "match_level": "none",
                        },
                        "cells": [
                            _cell("amount_currency", label="币种", value="CNY",
                                  source="default", status="missing"),
                        ],
                    }
                ],
            ),
        ]

    engine = await _make_engine()
    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "confirmed"
            assert "orders" not in body["written_rows"]
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models.order import Order
            rows = (await session.execute(select(Order))).scalars().all()
            assert rows == []
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 4. AI null does not overwrite existing DB value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_does_not_overwrite_existing_value_with_ai_null():
    # Pre-seed an existing customer with address.
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        existing = Customer(full_name="测试有限公司", address="旧地址")
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        existing_id = existing.id

    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        operation="update",
                        selected_entity_id=existing_id,
                        match_level="strong",
                        cells=[
                            _cell("full_name", label="公司全称",
                                  value="测试有限公司", required=True),
                            # AI gave us no address — must NOT clobber DB.
                            _cell("address", label="地址", value=None),
                        ],
                    )
                ],
            ),
        ]

    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customer = (
                await session.execute(select(Customer).where(Customer.id == existing_id))
            ).scalar_one()
            assert customer.address == "旧地址"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 5. Provenance carries parse_id / extraction_id / source_refs / review_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_writes_final_value_provenance_with_parse_and_source_refs():
    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        cells=[
                            _cell("full_name", label="公司全称",
                                  value="测试有限公司", required=True),
                            _cell(
                                "short_name",
                                label="简称",
                                value="测试",
                                source_refs=[
                                    {"ref_type": "chunk", "ref_id": "chunk:1"}
                                ],
                            ),
                        ],
                    )
                ],
            ),
        ]

    engine = await _make_engine()
    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (
                await session.execute(
                    select(FieldProvenance).where(
                        FieldProvenance.field_name == "short_name",
                    )
                )
            ).scalar_one()
            assert row.extraction_id == seed["extraction_id"]
            assert row.parse_id == seed["parse_id"]
            assert row.review_action == "ai"
            assert row.source_refs[0]["ref_id"] == "chunk:1"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 6. Lock release
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_releases_review_lock():
    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        cells=[
                            _cell("full_name", label="公司全称",
                                  value="测试有限公司", required=True),
                        ],
                    )
                ],
            ),
        ]

    engine = await _make_engine()
    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
        async with AsyncSession(engine, expire_on_commit=False) as session:
            ext = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == seed["extraction_id"]
                    )
                )
            ).scalar_one()
            assert ext.lock_token is None
            assert ext.locked_by is None
            assert ext.lock_expires_at is None
            assert ext.status == DocumentExtractionStatus.confirmed
            assert ext.confirmed_by == "user_a"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 7. link_existing parent supplies FK to child create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_link_existing_parent_for_child():
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        existing = Customer(full_name="测试有限公司")
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        existing_id = existing.id

    def _tables():
        return [
            _table(
                "customers",
                label="客户",
                rows=[
                    _row(
                        "customers:0",
                        operation="link_existing",
                        selected_entity_id=existing_id,
                        match_level="strong",
                        cells=[
                            _cell("full_name", label="公司全称",
                                  value="测试有限公司", required=True),
                        ],
                    )
                ],
            ),
            _table(
                "contacts",
                label="联系人",
                is_array=True,
                rows=[
                    _row(
                        "contacts:0",
                        cells=[
                            _cell("name", label="姓名", value="李四", required=True),
                        ],
                    )
                ],
            ),
        ]

    seed = await _seed_extraction(engine, draft_tables_builder=_tables)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            lock = await _acquire_lock(ac, seed["extraction_id"], "user_a")
            res = await ac.post(
                f"/api/win/ingest/extractions/{seed['extraction_id']}/confirm",
                headers={"X-User-Id": "user_a"},
                json={"lock_token": lock["lock_token"], "base_version": 0},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            # No new customer row should be written (link_existing).
            assert "customers" not in body["written_rows"]
            assert len(body["written_rows"]["contacts"]) == 1
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1  # the pre-existing one
            assert customers[0].id == existing_id
            contact = (await session.execute(select(Contact))).scalar_one()
            assert contact.customer_id == existing_id
            assert contact.name == "李四"
    finally:
        await engine.dispose()
        await dispose_all()
