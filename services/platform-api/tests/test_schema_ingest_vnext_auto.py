from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override Postgres+Redis fixture
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, dispose_all  # noqa: E402
from yunwei_win.models.document import Document  # noqa: E402
from yunwei_win.models.document_extraction import DocumentExtraction  # noqa: E402
from yunwei_win.models.document_parse import DocumentParse  # noqa: E402
from yunwei_win.services.schema_ingest import auto as auto_module  # noqa: E402
from yunwei_win.services.schema_ingest.auto import auto_ingest  # noqa: E402
from yunwei_win.services.schema_ingest.extraction_normalize import (  # noqa: E402
    NormalizedExtraction,
    NormalizedFieldValue,
    NormalizedRow,
)
from yunwei_win.services.schema_ingest.table_router import (  # noqa: E402
    SelectedTable,
    TableRouteResult,
)


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


def _patch_router(monkeypatch, *, selected: list[str], warnings: list[str] | None = None):
    async def fake_route(*, parse_artifact, catalog, llm=None):
        return TableRouteResult(
            selected_tables=[SelectedTable(table_name=name) for name in selected],
            rejected_tables=[],
            document_summary="测试摘要",
            needs_human_attention=False,
            warnings=list(warnings or []),
        )

    monkeypatch.setattr(auto_module.router_module, "route_tables", fake_route)


def _patch_extractor(monkeypatch, *, tables: dict[str, list[NormalizedRow]]):
    async def fake_extract(*, parse_artifact, selected_tables, catalog, provider, session=None, llm=None):
        return NormalizedExtraction(
            provider="deepseek" if provider == "deepseek" else "landingai",
            tables=tables,
            metadata={},
        )

    monkeypatch.setattr(
        auto_module.extractors_module, "extract_from_parse_artifact", fake_extract
    )


def _patch_validator(monkeypatch, *, warnings: list[str]):
    def fake_validate(normalized, *, selected_tables, catalog, parse_artifact):
        return list(warnings)

    monkeypatch.setattr(
        auto_module.validation_module,
        "validate_normalized_extraction",
        fake_validate,
    )


@pytest.mark.asyncio
async def test_auto_ingest_text_persists_parse_extraction_and_review(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(
        monkeypatch,
        tables={
            "customers": [
                NormalizedRow(
                    client_row_id="customers:0",
                    fields={
                        "full_name": NormalizedFieldValue(
                            value="测试有限公司", confidence=0.91
                        )
                    },
                )
            ]
        },
    )

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="客户：测试有限公司",
                original_filename="note.txt",
                content_type="text/plain",
                source_hint="pasted_text",
                uploader="tester",
            )
            await session.commit()

            parse = (
                await session.execute(
                    select(DocumentParse).where(DocumentParse.id == result.parse_id)
                )
            ).scalar_one()
            assert parse.provider == "text"
            assert parse.document_id == result.document_id

            extraction = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == result.extraction_id
                    )
                )
            ).scalar_one()
            assert extraction.parse_id == result.parse_id
            assert extraction.document_id == result.document_id
            assert result.selected_tables[0]["table_name"] == "customers"
            assert result.review_draft is not None
            assert result.review_draft.steps[0].key == "customer"
            assert result.review_draft.parse_id == result.parse_id
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_auto_ingest_rejects_unsupported_file_type(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            with pytest.raises(ValueError, match="unsupported file type"):
                await auto_ingest(
                    session=session,
                    file_bytes=b"PK\x03\x04 zip-bytes",
                    original_filename="archive.zip",
                    content_type="application/zip",
                    source_hint="file",
                )
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_auto_ingest_stores_validation_warnings(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(
        monkeypatch,
        tables={
            "customers": [
                NormalizedRow(
                    client_row_id="customers:0",
                    fields={
                        "full_name": NormalizedFieldValue(value="测试有限公司")
                    },
                )
            ]
        },
    )
    _patch_validator(monkeypatch, warnings=["source ref chunk:99 not found"])

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="客户：测试有限公司",
                source_hint="pasted_text",
            )
            await session.commit()

            extraction = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == result.extraction_id
                    )
                )
            ).scalar_one()
            assert extraction.validation_warnings is not None
            assert any(
                "source ref chunk:99 not found" in w
                for w in extraction.validation_warnings
            )
    finally:
        await engine.dispose()
        await dispose_all()
