from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override Postgres+Redis fixture
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from pathlib import Path  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.db import Base, dispose_all  # noqa: E402
from yunwei_win.models.document import Document  # noqa: E402
from yunwei_win.models.document_extraction import DocumentExtraction  # noqa: E402
from yunwei_win.models.document_parse import DocumentParse, DocumentParseStatus  # noqa: E402
from yunwei_win.services import storage as storage_module  # noqa: E402
from yunwei_win.services.schema_ingest import auto as auto_module  # noqa: E402
from yunwei_win.services.schema_ingest.auto import auto_ingest  # noqa: E402
from yunwei_win.services.schema_ingest.extraction_normalize import (  # noqa: E402
    NormalizedExtraction,
    NormalizedFieldValue,
    NormalizedRow,
)
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact  # noqa: E402
from yunwei_win.services.schema_ingest.table_router import (  # noqa: E402
    SelectedTable,
    TableRouteResult,
)
from yunwei_win.services.schema_ingest.upload import PreStoredFile  # noqa: E402


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


def _patch_router(
    monkeypatch,
    *,
    selected: list[str],
    warnings: list[str] | None = None,
    capture: dict | None = None,
):
    async def fake_route(*, parse_artifact, catalog, llm=None):
        if capture is not None:
            capture["router_llm"] = llm
        return TableRouteResult(
            selected_tables=[SelectedTable(table_name=name) for name in selected],
            rejected_tables=[],
            document_summary="测试摘要",
            needs_human_attention=False,
            warnings=list(warnings or []),
        )

    monkeypatch.setattr(auto_module.router_module, "route_tables", fake_route)


def _patch_extractor(
    monkeypatch,
    *,
    tables: dict[str, list[NormalizedRow]],
    capture: dict | None = None,
):
    async def fake_extract(*, parse_artifact, selected_tables, catalog, provider, session=None, llm=None):
        if capture is not None:
            capture["extractor_provider"] = provider
            capture["extractor_llm"] = llm
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
async def test_auto_ingest_injects_complete_json_llm_into_router_and_extractor(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    captured: dict = {}
    _patch_router(monkeypatch, selected=["customers"], capture=captured)
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
        capture=captured,
    )

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await auto_ingest(
                session=session,
                text_content="客户：测试有限公司",
                source_hint="pasted_text",
            )
            await session.commit()
        router_llm = captured["router_llm"]
        extractor_llm = captured["extractor_llm"]
        assert router_llm is not None
        assert hasattr(router_llm, "complete_json")
        # text → DeepSeek extractor → same adapter instance
        assert captured["extractor_provider"] == "deepseek"
        assert extractor_llm is router_llm
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


@pytest.mark.asyncio
async def test_auto_ingest_degrades_parser_failure_into_review_draft(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))

    async def fail_parse(**_kwargs):
        raise RuntimeError("VISION_AGENT_API_KEY is not configured")

    monkeypatch.setattr(auto_module, "parse_file_factory", fail_parse)
    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(monkeypatch, tables={})

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF-1.4 placeholder",
                original_filename="quote.pdf",
                content_type="application/pdf",
                source_hint="file",
            )
            await session.commit()

            parse = (
                await session.execute(
                    select(DocumentParse).where(DocumentParse.id == result.parse_id)
                )
            ).scalar_one()
            assert parse.status == DocumentParseStatus.failed
            assert "VISION_AGENT_API_KEY" in (parse.error_message or "")
            assert parse.artifact["metadata"]["parse_failed"] is True

            extraction = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == result.extraction_id
                    )
                )
            ).scalar_one()
            assert result.review_draft is not None
            assert any(
                "parse failed: RuntimeError" in warning
                for warning in (extraction.validation_warnings or [])
            )
            assert not any(
                "API_KEY" in warning
                for warning in (extraction.validation_warnings or [])
            )
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_auto_ingest_falls_back_when_parse_artifact_model_dump_fails(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))

    class MockValSerArtifact(ParseArtifact):
        def model_dump(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise TypeError(
                "'MockValSer' object is not an instance of 'SchemaSerializer'"
            )

    async def fake_parse_factory(*, detected, path, filename, content_type):
        return MockValSerArtifact(
            provider=detected.parser_provider,
            source_type=detected.source_type,
            markdown="parsed-ok",
            metadata={"filename": filename, "content_type": content_type},
        )

    monkeypatch.setattr(auto_module, "parse_file_factory", fake_parse_factory)
    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(monkeypatch, tables={})

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF-1.4 placeholder",
                original_filename="quote.pdf",
                content_type="application/pdf",
                source_hint="file",
            )
            await session.commit()

            parse = (
                await session.execute(
                    select(DocumentParse).where(DocumentParse.id == result.parse_id)
                )
            ).scalar_one()
            assert parse.status == DocumentParseStatus.parsed
            assert parse.artifact["markdown"] == "parsed-ok"
            assert parse.artifact["metadata"]["filename"] == "quote.pdf"
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_auto_ingest_jsonifies_landingai_metadata_warnings(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    from landingai_ade.types.extract_response import MetadataWarning

    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(
        monkeypatch,
        tables={},
    )

    warning = MetadataWarning(
        code="nonconformant_output",
        msg="schema warning from LandingAI",
    )

    async def fake_parse_factory(*, detected, path, filename, content_type):
        return ParseArtifact(
            provider=detected.parser_provider,
            source_type=detected.source_type,
            markdown="parsed-ok",
            metadata={"filename": filename},
        )

    async def fake_extract(*, parse_artifact, selected_tables, catalog, provider, session=None, llm=None):
        return NormalizedExtraction(
            provider="landingai",
            tables={},
            metadata={"landingai_metadata": {"warnings": [warning]}},
        )

    monkeypatch.setattr(auto_module, "parse_file_factory", fake_parse_factory)
    monkeypatch.setattr(
        auto_module.extractors_module, "extract_from_parse_artifact", fake_extract
    )

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF-1.4 placeholder",
                original_filename="quote.pdf",
                content_type="application/pdf",
                source_hint="file",
            )
            await session.commit()

            extraction = (
                await session.execute(
                    select(DocumentExtraction).where(
                        DocumentExtraction.id == result.extraction_id
                    )
                )
            ).scalar_one()
            assert extraction.extraction_metadata["landingai_metadata"]["warnings"] == [
                {
                    "code": "nonconformant_output",
                    "msg": "schema warning from LandingAI",
                }
            ]
    finally:
        await engine.dispose()
        await dispose_all()


@pytest.mark.asyncio
async def test_auto_ingest_materializes_s3_pre_stored_path_for_parser(
    monkeypatch, tmp_path
):
    """Regression: when pre_stored.path is an s3:// URL, the parser must
    receive a real local file path. Naively wrapping the URL in Path()
    collapses ``s3://`` to ``s3:/`` and the parser then errors with
    ``[Errno 2] No such file or directory: 's3:/...'``."""

    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    pdf_bytes = b"%PDF-1.4 fake-bytes-for-test"
    s3_url = "s3://yunwei-ingest/files/abc123.pdf"

    def fake_open_for_read(stored_path: str) -> bytes:
        assert stored_path == s3_url, f"unexpected read of {stored_path!r}"
        return pdf_bytes

    monkeypatch.setattr(storage_module, "open_for_read", fake_open_for_read)

    captured: dict = {}

    async def fake_parse_factory(*, detected, path, filename, content_type):
        captured["path"] = path
        captured["bytes"] = Path(path).read_bytes()
        return ParseArtifact(
            provider=detected.parser_provider,
            source_type=detected.source_type,
            markdown="parsed-ok",
            metadata={"filename": filename},
        )

    monkeypatch.setattr(auto_module, "parse_file_factory", fake_parse_factory)
    _patch_router(monkeypatch, selected=["customers"])
    _patch_extractor(
        monkeypatch,
        tables={
            "customers": [
                NormalizedRow(
                    client_row_id="customers:0",
                    fields={"full_name": NormalizedFieldValue(value="测试")},
                )
            ]
        },
    )

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await auto_ingest(
                session=session,
                pre_stored=PreStoredFile(
                    path=s3_url,
                    sha256="d" * 64,
                    size=len(pdf_bytes),
                    original_filename="invoice.pdf",
                    content_type="application/pdf",
                ),
                original_filename="invoice.pdf",
                content_type="application/pdf",
                source_hint="file",
            )
            await session.commit()

        path = captured["path"]
        assert "s3:/" not in str(path), (
            f"parser received mangled S3 URL as Path: {path!r}"
        )
        assert Path(path).exists(), f"parser path does not exist: {path!r}"
        assert captured["bytes"] == pdf_bytes
    finally:
        await engine.dispose()
        await dispose_all()
