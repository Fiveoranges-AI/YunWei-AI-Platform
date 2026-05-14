"""Confirm endpoint tests for the schema-first surface.

Each test synthesizes a ``DocumentExtraction.review_draft`` JSON and POSTs
``/api/win/ingest/extractions/{id}/confirm`` with patches. We don't
exercise the materializer — that's covered by ``test_schema_ingest_review_draft``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, get_session  # noqa: E402
from yunwei_win.models import (  # noqa: E402
    Customer,
    Document,
    DocumentReviewStatus,
    DocumentType,
    FieldProvenance,
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
    Order,
)
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


def _build_app(engine, monkeypatch) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_enterprise(request: Request, call_next):
        request.state.enterprise_id = "tenant_test"
        return await call_next(request)

    async def session_dep():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_dep

    # Bypass the per-enterprise ensure helpers — SQLite has every table.
    from yunwei_win.api import schema_ingest as schema_ingest_api

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(schema_ingest_api, "ensure_schema_ingest_tables_for", _noop)
    monkeypatch.setattr(schema_ingest_api, "ensure_ingest_job_tables_for", _noop)

    app.include_router(yinhu_router, prefix="/api/win")
    return app


def _draft_payload(
    *,
    extraction_id: uuid.UUID,
    document_id: uuid.UUID,
    tables: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "extraction_id": str(extraction_id),
        "document_id": str(document_id),
        "schema_version": 1,
        "status": "pending_review",
        "document": {"filename": "doc.pdf"},
        "route_plan": {"selected_pipelines": []},
        "tables": tables,
        "schema_warnings": [],
        "general_warnings": [],
    }


def _cell(
    field_name: str,
    label: str,
    data_type: str,
    *,
    value: Any = None,
    status: str = "extracted",
    source: str = "ai",
    required: bool = False,
    evidence: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "label": label,
        "data_type": data_type,
        "required": required,
        "is_array": False,
        "value": value,
        "display_value": "" if value is None else str(value),
        "status": status,
        "confidence": confidence,
        "evidence": evidence,
        "source": source,
    }


async def _seed_extraction(
    engine,
    *,
    extraction_id: uuid.UUID,
    document_id: uuid.UUID,
    review_draft: dict[str, Any],
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        extraction = DocumentExtraction(
            id=extraction_id,
            document_id=document_id,
            schema_version=1,
            provider="landingai",
            route_plan={},
            raw_pipeline_results=[],
            review_draft=review_draft,
            status=DocumentExtractionStatus.pending_review,
        )
        session.add(extraction)
        await session.commit()


async def _seed_document(engine, *, customer_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        cust = Customer(id=customer_id, full_name="测试客户")
        session.add(cust)
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/d.txt",
            original_filename="doc.pdf",
            file_sha256="0" * 64,
            file_size_bytes=10,
            ocr_text="text",
        )
        session.add(doc)
        await session.commit()
        return doc.id


# ---- test 1: orders row created + provenance written ------------------


@pytest.mark.asyncio
async def test_confirm_creates_orders_row_and_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell(
                            "full_name", "公司全称", "text",
                            value="测试客户", status="extracted", source="ai",
                            required=True,
                        ),
                    ],
                }
            ],
        },
        {
            "table_name": "orders",
            "label": "订单",
            "rows": [
                {
                    "client_row_id": "orders:0",
                    "entity_id": None,
                    "operation": "create",
                    "cells": [
                        _cell(
                            "customer_id", "客户", "uuid",
                            value=str(customer_id),
                            required=True,
                        ),
                        _cell(
                            "amount_total", "订单金额", "decimal",
                            value=30000,
                            evidence={"page": 1, "excerpt": "合同总价人民币叁万元整"},
                            confidence=0.91,
                        ),
                        _cell(
                            "amount_currency", "币种", "text",
                            value="CNY",
                        ),
                        _cell(
                            "delivery_promised_date", "承诺交期", "date",
                            value="2026-06-30",
                            evidence={"page": 1, "excerpt": "交付日期 2026-06-30"},
                        ),
                        _cell(
                            "delivery_address", "交付地址", "text",
                            status="missing", source="empty",
                        ),
                        _cell(
                            "description", "订单说明", "text",
                            value="测试订单",
                        ),
                    ],
                }
            ],
        },
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": []},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "confirmed"
            assert "orders" in body["written_rows"]
            assert len(body["written_rows"]["orders"]) == 1

        async with AsyncSession(engine, expire_on_commit=False) as session:
            orders = (await session.execute(select(Order))).scalars().all()
            assert len(orders) == 1
            o = orders[0]
            assert int(o.amount_total) == 30000
            assert o.customer_id == customer_id
            assert o.description == "测试订单"

            provs = (await session.execute(select(FieldProvenance))).scalars().all()
            # amount_total + delivery_promised_date have evidence → provenance.
            field_names = {p.field_name for p in provs}
            assert "amount_total" in field_names
            assert "delivery_promised_date" in field_names
    finally:
        await engine.dispose()


# ---- test 2: user-filled missing cell persists -----------------------


@pytest.mark.asyncio
async def test_confirm_uses_user_filled_missing_cells(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                    ],
                }
            ],
        },
        {
            "table_name": "orders",
            "label": "订单",
            "rows": [
                {
                    "client_row_id": "orders:0",
                    "operation": "create",
                    "cells": [
                        _cell("customer_id", "客户", "uuid",
                              value=str(customer_id), required=True),
                        _cell("amount_total", "订单金额", "decimal", value=100),
                        _cell("amount_currency", "币种", "text", value="CNY"),
                        _cell("delivery_promised_date", "承诺交期", "date",
                              value="2026-07-01"),
                        _cell("delivery_address", "交付地址", "text",
                              status="missing", source="empty"),
                        _cell("description", "订单说明", "text", value="x"),
                    ],
                }
            ],
        },
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            patches = [
                {
                    "table_name": "orders",
                    "client_row_id": "orders:0",
                    "field_name": "delivery_address",
                    "value": "北京市朝阳区某街道 1 号",
                    "status": "edited",
                }
            ]
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": patches},
            )
            assert res.status_code == 200, res.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            o = (await session.execute(select(Order))).scalar_one()
            assert o.delivery_address == "北京市朝阳区某街道 1 号"

            provs = (await session.execute(select(FieldProvenance))).scalars().all()
            assert any(p.field_name == "delivery_address" for p in provs)
    finally:
        await engine.dispose()


# ---- test 3: required cell missing returns 400 -----------------------


@pytest.mark.asyncio
async def test_confirm_rejects_when_required_cell_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    extraction_id = uuid.uuid4()
    # Document with no customer seeded — so create-mode customer must have full_name.
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/d.txt",
            original_filename="doc.pdf",
            file_sha256="0" * 64,
            file_size_bytes=10,
            ocr_text="text",
        )
        session.add(doc)
        await session.commit()
        document_id = doc.id

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": None,
                    "operation": "create",
                    "cells": [
                        _cell(
                            "full_name", "公司全称", "text",
                            value=None, status="missing", source="empty",
                            required=True,
                        ),
                    ],
                }
            ],
        }
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": []},
            )
            assert res.status_code == 400, res.text
            detail = res.json()["detail"]
            cells = detail["invalid_cells"]
            assert any(
                c["table_name"] == "customers" and c["field_name"] == "full_name"
                for c in cells
            )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            ext = (
                await session.execute(
                    select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
                )
            ).scalar_one()
            assert ext.status == DocumentExtractionStatus.pending_review
    finally:
        await engine.dispose()


# ---- test 4: rejected cells are skipped ------------------------------


@pytest.mark.asyncio
async def test_confirm_skips_rejected_cells(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                    ],
                }
            ],
        },
        {
            "table_name": "orders",
            "label": "订单",
            "rows": [
                {
                    "client_row_id": "orders:0",
                    "operation": "create",
                    "cells": [
                        _cell("customer_id", "客户", "uuid",
                              value=str(customer_id), required=True),
                        _cell("amount_total", "订单金额", "decimal", value=500),
                        _cell("amount_currency", "币种", "text", value="CNY"),
                        _cell("delivery_promised_date", "承诺交期", "date",
                              value="2026-07-01"),
                        # delivery_address rejected: should not be persisted.
                        _cell(
                            "delivery_address", "交付地址", "text",
                            value="原本错误的地址",
                            status="rejected",
                            source="ai",
                        ),
                        _cell("description", "订单说明", "text", value="d"),
                    ],
                }
            ],
        },
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": []},
            )
            assert res.status_code == 200, res.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            o = (await session.execute(select(Order))).scalar_one()
            assert o.delivery_address is None
    finally:
        await engine.dispose()


# ---- test 5: extraction + job status flip to confirmed ----------------


@pytest.mark.asyncio
async def test_confirm_marks_extraction_and_job_confirmed(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                    ],
                }
            ],
        }
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    # Seed extraction first so the IngestJob FK is satisfiable.
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        b = IngestBatch(enterprise_id="tenant_test", source="seed")
        session.add(b)
        await session.flush()
        job = IngestJob(
            batch_id=b.id, enterprise_id="tenant_test",
            original_filename="doc.pdf", source_hint="file",
            status=IngestJobStatus.extracted, stage=IngestJobStage.done,
            attempts=1,
            document_id=document_id,
            extraction_id=extraction_id,
        )
        session.add(job)
        await session.commit()

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": []},
            )
            assert res.status_code == 200, res.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            ext = (
                await session.execute(
                    select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
                )
            ).scalar_one()
            assert ext.status == DocumentExtractionStatus.confirmed
            assert ext.confirmed_at is not None

            j = (await session.execute(select(IngestJob))).scalar_one()
            assert j.status == IngestJobStatus.confirmed

            doc = (
                await session.execute(
                    select(Document).where(Document.id == document_id)
                )
            ).scalar_one()
            assert doc.review_status == DocumentReviewStatus.confirmed
    finally:
        await engine.dispose()


# ---- test 6: server-stored draft is authoritative --------------------


@pytest.mark.asyncio
async def test_confirm_uses_server_stored_draft_not_client_draft(monkeypatch, tmp_path):
    """The server reads the canonical draft from the DB. A client draft with
    an empty tables list must NOT short-circuit confirm — the server should
    still write what the DB-stored draft says."""

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    server_tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="服务器版本客户名", required=True),
                    ],
                }
            ],
        },
    ]
    server_draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=server_tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=server_draft,
    )

    # Client sends a draft with no tables (or a tampered name) — should NOT
    # change what the server writes.
    client_draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=[],
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": client_draft, "patches": []},
            )
            assert res.status_code == 200, res.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            cust = (
                await session.execute(
                    select(Customer).where(Customer.id == customer_id)
                )
            ).scalar_one()
            # The server-stored draft's value wins, not the empty client draft.
            assert cust.full_name == "服务器版本客户名"
    finally:
        await engine.dispose()


# ---- test 7: extraction_id mismatch in client draft -> 400 -----------


@pytest.mark.asyncio
async def test_confirm_rejects_when_extraction_id_mismatch_in_client_draft(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                    ],
                }
            ],
        }
    ]
    server_draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=server_draft,
    )

    # Client sends a draft with a DIFFERENT extraction_id.
    wrong_id = uuid.uuid4()
    client_draft = _draft_payload(
        extraction_id=wrong_id,
        document_id=document_id,
        tables=tables,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": client_draft, "patches": []},
            )
            assert res.status_code == 400, res.text
    finally:
        await engine.dispose()


# ---- test 8: patches for nonexistent rows are silently ignored -------


@pytest.mark.asyncio
async def test_confirm_ignores_patches_for_nonexistent_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                    ],
                }
            ],
        }
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            # Patch a row that doesn't exist in the server draft.
            patches = [
                {
                    "table_name": "customers",
                    "client_row_id": "ghost:99",
                    "field_name": "full_name",
                    "value": "应该被忽略",
                }
            ]
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"patches": patches},
            )
            assert res.status_code == 200, res.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            # Only the original customer row exists — no ghost row was created.
            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1
            assert customers[0].full_name == "测试客户"
    finally:
        await engine.dispose()


# ---- test 9: catalog field with no ORM destination -> 400 ------------


@pytest.mark.asyncio
async def test_confirm_reports_orm_destination_missing(monkeypatch, tmp_path):
    """A non-rejected, non-empty cell whose field_name has no ORM column on
    the table model must surface as ``catalog_field_has_no_orm_destination``.
    """

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    customer_id = uuid.uuid4()
    extraction_id = uuid.uuid4()
    document_id = await _seed_document(engine, customer_id=customer_id)

    # Customer has no ``imaginary_field`` column on the ORM but the catalog
    # cell points at it. We synthesize the cell directly into the stored
    # draft — the materializer normally wouldn't emit unknown fields.
    tables = [
        {
            "table_name": "customers",
            "label": "客户",
            "rows": [
                {
                    "client_row_id": "customers:0",
                    "entity_id": str(customer_id),
                    "operation": "update",
                    "cells": [
                        _cell("full_name", "公司全称", "text",
                              value="测试客户", required=True),
                        # Catalog claims this field exists, but the ORM doesn't.
                        _cell("imaginary_field", "imaginary", "text",
                              value="something"),
                    ],
                }
            ],
        }
    ]
    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=tables,
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    # Inject the imaginary field into the catalog by patching the company
    # schema service for the duration of this test.
    from yunwei_win.services import company_schema

    async def fake_get_company_schema(_session):
        cat = await _real_get_company_schema(_session)
        for table in cat.get("tables") or []:
            if table["table_name"] == "customers":
                table["fields"].append({
                    "field_name": "imaginary_field",
                    "label": "imaginary",
                    "data_type": "text",
                    "required": False,
                    "is_array": False,
                    "is_active": True,
                    "sort_order": 999,
                })
        return cat

    _real_get_company_schema = company_schema.get_company_schema
    from yunwei_win.services.schema_ingest import confirm as confirm_mod

    monkeypatch.setattr(confirm_mod, "get_company_schema", fake_get_company_schema)

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"patches": []},
            )
            assert res.status_code == 400, res.text
            cells = res.json()["detail"]["invalid_cells"]
            assert any(
                c["table_name"] == "customers"
                and c["field_name"] == "imaginary_field"
                and c["reason"] == "catalog_field_has_no_orm_destination"
                for c in cells
            ), cells
    finally:
        await engine.dispose()


# ---- test 10: ORM-required field missing from catalog -> 400 ---------


def test_check_orm_parity_fires_when_required_orm_column_lacks_catalog_field():
    """``_check_orm_parity`` must flag any NOT NULL ORM column with no
    default and no FK auto-fill that has no matching catalog field.

    We build a draft whose ``customers`` table has only ``short_name`` in
    its catalog (``full_name`` is NOT NULL on the Customer ORM with no
    default and no FK auto-fill — so it must be reported)."""

    from yunwei_win.services.schema_ingest.confirm import _check_orm_parity
    from yunwei_win.services.schema_ingest.schemas import (
        ReviewCell,
        ReviewDraft,
        ReviewDraftDocument,
        ReviewDraftRoutePlan,
        ReviewRow,
        ReviewTable,
    )

    draft = ReviewDraft(
        extraction_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document=ReviewDraftDocument(filename="doc.pdf"),
        route_plan=ReviewDraftRoutePlan(),
        tables=[
            ReviewTable(
                table_name="customers",
                label="客户",
                rows=[
                    ReviewRow(
                        client_row_id="customers:0",
                        cells=[
                            ReviewCell(
                                field_name="short_name",
                                label="简称",
                                data_type="text",
                                value="某客户",
                                status="extracted",
                                source="ai",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    catalog_by_table = {
        "customers": {"short_name": {"field_name": "short_name", "data_type": "text"}},
    }

    invalid = _check_orm_parity(draft, catalog_by_table)
    assert any(
        c["table_name"] == "customers"
        and c["field_name"] == "full_name"
        and c["reason"] == "orm_requires_field_missing_from_catalog"
        for c in invalid
    ), invalid


# ---- test 11: integer validation accepts integral floats -------------


def test_integer_validation_accepts_integral_floats():
    from yunwei_win.services.schema_ingest.confirm import _validate_value

    spec = {"data_type": "integer"}
    assert _validate_value(spec, "10.0") is True
    assert _validate_value(spec, "10") is True
    assert _validate_value(spec, 10) is True
    assert _validate_value(spec, "10.5") is False
    assert _validate_value(spec, "abc") is False
    assert _validate_value(spec, True) is False


@pytest.mark.asyncio
async def test_linked_fk_passes_validation_when_parent_in_draft(monkeypatch, tmp_path):
    """A required FK cell marked ``source="linked"`` does not trigger
    ``missing_required`` so long as a same-confirm parent row will actually
    be written. Confirm writeback fills the UUID after the parent inserts.
    """
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    extraction_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.text_note,
            file_url="file:///tmp/d.png",
            original_filename="card.png",
            file_sha256="0" * 64,
            file_size_bytes=10,
            ocr_text="名片 OCR",
        )
        session.add(doc)
        await session.commit()
        document_id = doc.id

    draft = _draft_payload(
        extraction_id=extraction_id,
        document_id=document_id,
        tables=[
            {
                "table_name": "customers",
                "label": "客户",
                "is_array": False,
                "rows": [
                    {
                        "client_row_id": "customers:0",
                        "entity_id": None,
                        "operation": "create",
                        "cells": [
                            _cell(
                                "full_name", "客户名称", "text",
                                value="新客户", required=True,
                            ),
                        ],
                    }
                ],
            },
            {
                "table_name": "contacts",
                "label": "联系人",
                "is_array": True,
                "rows": [
                    {
                        "client_row_id": "contacts:0",
                        "entity_id": None,
                        "operation": "create",
                        "cells": [
                            _cell(
                                "customer_id", "客户", "uuid",
                                value=None, status="missing", source="linked",
                                required=True,
                            ),
                            _cell(
                                "name", "姓名", "text",
                                value="联系人A", required=True,
                            ),
                        ],
                    }
                ],
            },
        ],
    )
    await _seed_extraction(
        engine,
        extraction_id=extraction_id,
        document_id=document_id,
        review_draft=draft,
    )

    app = _build_app(engine, monkeypatch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.post(
                f"/api/win/ingest/extractions/{extraction_id}/confirm",
                json={"review_draft": draft, "patches": []},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["status"] == "confirmed"
            # Writeback chose the just-created customer's UUID for the
            # contact's FK; surface it via written_rows for sanity.
            assert len(body["written_rows"].get("customers", [])) == 1
            assert len(body["written_rows"].get("contacts", [])) == 1
    finally:
        await engine.dispose()
