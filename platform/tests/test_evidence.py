"""Tests for the unified ingest's Evidence collection step.

Evidence is the single OCR/normalization pass that produces a
``(Document row, ocr_text)`` for every downstream extractor. These tests
patch the storage / OCR / pdf helpers so we exercise the routing logic
without touching the network or the filesystem.

The project-wide autouse fixture wants Postgres + Redis; we override it
locally with a no-op because these tests use an in-memory SQLite engine,
mirroring ``test_yinhu_brain_contract_flow.py``.
"""

from __future__ import annotations

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yinhu_brain.models  # noqa: F401 - register SQLAlchemy mappers
from yinhu_brain.db import Base
from yinhu_brain.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
)
from yinhu_brain.services import pdf as pdf_utils
from yinhu_brain.services.ingest import evidence as evidence_module
from yinhu_brain.services.ingest.evidence import Evidence, collect_evidence
from yinhu_brain.services.mistral_ocr_client import MistralOCRUnavailable


# ---------- helpers -------------------------------------------------------


async def _make_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return session, engine


def _patch_store_upload(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Make ``store_upload`` deterministic and capture each call.

    Returns a list that gets appended to on every call so tests can assert
    what filename / extension flowed through.
    """
    calls: list[dict] = []

    def fake_store(content, original_filename, *, default_ext=""):
        from yinhu_brain.services.storage import StoredFile

        calls.append(
            {
                "size": len(content),
                "filename": original_filename,
                "default_ext": default_ext,
            }
        )
        suffix = (
            original_filename.rsplit(".", 1)[1]
            if "." in original_filename
            else default_ext.lstrip(".")
        )
        return StoredFile(
            path=f"/tmp/fake-{len(calls)}.{suffix or 'bin'}",
            sha256="a" * 64,
            size=len(content),
        )

    monkeypatch.setattr(evidence_module, "store_upload", fake_store)
    return calls


# ---------- text-content path --------------------------------------------


@pytest.mark.asyncio
async def test_text_content_does_not_call_ocr(monkeypatch) -> None:
    """A pasted text note becomes the ocr_text directly; no OCR helper fires."""
    store_calls = _patch_store_upload(monkeypatch)

    async def boom_image(*a, **k):
        raise AssertionError("parse_image_to_markdown must not be called for text")

    async def boom_pdf(*a, **k):
        raise AssertionError("parse_pdf_to_markdown must not be called for text")

    async def boom_doc(*a, **k):
        raise AssertionError("parse_document_to_markdown must not be called for text")

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", boom_image)
    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", boom_pdf)
    monkeypatch.setattr(evidence_module, "parse_document_to_markdown", boom_doc)

    session, engine = await _make_session()
    try:
        text = "客户王经理今天来电，确认 6 月底交付，金额 12 万。"
        result = await collect_evidence(
            session=session,
            text_content=text,
            source_hint="pasted_text",
            uploader="tester",
        )
        await session.commit()

        assert isinstance(result, Evidence)
        assert result.modality == "text"
        assert result.ocr_text == text  # already strip-clean
        assert result.warnings == []
        assert result.document.type == DocumentType.text_note
        assert result.document.processing_status == DocumentProcessingStatus.parsed
        assert result.document.review_status == DocumentReviewStatus.pending_review
        assert result.document.uploader == "tester"
        assert result.document.content_type == "text/plain"

        # store_upload should have run (text body persisted for audit).
        assert len(store_calls) == 1
        assert store_calls[0]["filename"] == "note.txt"
        assert store_calls[0]["default_ext"] == ".txt"

        # Document row is in the DB.
        doc = (
            await session.execute(select(Document).where(Document.id == result.document_id))
        ).scalar_one()
        assert doc.ocr_text == text
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_short_text_adds_warning_but_does_not_raise(monkeypatch) -> None:
    _patch_store_upload(monkeypatch)
    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            text_content="hi",  # 2 chars, well under the 20-char threshold
            source_hint="pasted_text",
        )
        await session.commit()

        assert result.modality == "text"
        assert result.ocr_text == "hi"
        assert any("too short" in w for w in result.warnings)
        # Still persisted with the warning attached
        assert any("too short" in w for w in (result.document.parse_warnings or []))
    finally:
        await session.close()
        await engine.dispose()


# ---------- image path ----------------------------------------------------


@pytest.mark.asyncio
async def test_image_bytes_trigger_image_ocr(monkeypatch) -> None:
    """Image bytes flow through ``parse_image_to_markdown`` and the markdown
    becomes ``ocr_text``."""
    store_calls = _patch_store_upload(monkeypatch)
    fake_md = "# Card\n\n王经理 13800000000 wang@example.com"

    captured: dict = {}

    async def fake_image(image_bytes, filename, content_type=None):
        captured["bytes_len"] = len(image_bytes)
        captured["filename"] = filename
        captured["content_type"] = content_type
        return fake_md

    async def boom_pdf(*a, **k):
        raise AssertionError("pdf OCR must not run for image inputs")

    async def boom_doc(*a, **k):
        raise AssertionError("document OCR must not run for image inputs")

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", fake_image)
    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", boom_pdf)
    monkeypatch.setattr(evidence_module, "parse_document_to_markdown", boom_doc)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"\x89PNG\r\n\x1a\nfake-image-bytes",
            original_filename="card.png",
            content_type="image/png",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "image"
        assert result.ocr_text == fake_md
        assert result.warnings == []
        assert result.document.type == DocumentType.business_card
        assert result.document.content_type == "image/png"
        assert captured["filename"] == "card.png"
        assert captured["content_type"] == "image/png"
        assert captured["bytes_len"] > 0
        # store_upload was called once with the original filename
        assert len(store_calls) == 1
        assert store_calls[0]["filename"] == "card.png"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_camera_capture_defaults_filename_and_content_type(monkeypatch) -> None:
    """Camera input usually arrives without a filename; we default to capture.jpg
    and image/jpeg so the OCR client picks the right media type."""
    store_calls = _patch_store_upload(monkeypatch)

    async def fake_image(image_bytes, filename, content_type=None):
        return "ocr text from camera"

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", fake_image)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"raw-jpeg-bytes",
            source_hint="camera",
        )
        await session.commit()

        assert result.modality == "image"
        assert result.document.original_filename == "capture.jpg"
        assert result.document.content_type == "image/jpeg"
        assert store_calls[0]["filename"] == "capture.jpg"
        assert store_calls[0]["default_ext"] == ".jpg"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_image_ocr_unavailable_warns_does_not_raise(monkeypatch) -> None:
    """Mistral down → ocr_text empty + warning, Document row still flushed."""
    _patch_store_upload(monkeypatch)

    async def explode(*a, **k):
        raise MistralOCRUnavailable("mistral ocr unreachable: ConnectError(...)")

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", explode)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"fake-image",
            original_filename="card.jpg",
            content_type="image/jpeg",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "image"
        assert result.ocr_text == ""
        assert any("Mistral OCR unavailable" in w for w in result.warnings)
        # Soft "too short" warning is also expected when OCR returns empty.
        assert any("too short" in w for w in result.warnings)
        # Document row is persisted with empty ocr_text and the warnings.
        doc = (
            await session.execute(select(Document).where(Document.id == result.document_id))
        ).scalar_one()
        assert doc.ocr_text == ""
        assert any("Mistral OCR unavailable" in w for w in (doc.parse_warnings or []))
    finally:
        await session.close()
        await engine.dispose()


# ---------- pdf path ------------------------------------------------------


@pytest.mark.asyncio
async def test_pdf_with_text_layer_uses_native_text_no_ocr(monkeypatch) -> None:
    """Born-digital PDF: pypdf returns plenty of text → no Mistral OCR call."""
    _patch_store_upload(monkeypatch)

    fake_pages = [
        pdf_utils.PageText(page_num=1, text="甲方：测试客户有限公司\n金额：120000 元"),
        pdf_utils.PageText(page_num=2, text="交付日期：2026-06-30"),
    ]
    monkeypatch.setattr(
        evidence_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: fake_pages,
    )

    async def boom_pdf(*a, **k):
        raise AssertionError("parse_pdf_to_markdown should not run for born-digital PDFs")

    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", boom_pdf)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"%PDF-1.4 fake bytes",
            original_filename="contract.pdf",
            content_type="application/pdf",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "pdf"
        assert "测试客户有限公司" in result.ocr_text
        assert "[page 1]" in result.ocr_text
        assert result.warnings == []
        assert result.document.type == DocumentType.contract
        assert result.document.content_type == "application/pdf"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_scanned_falls_back_to_mistral_ocr(monkeypatch) -> None:
    """Scanned PDF: pypdf returns ~nothing → Mistral OCR is called and used."""
    _patch_store_upload(monkeypatch)

    # is_scanned() returns True when total chars across pages < 50.
    fake_pages = [pdf_utils.PageText(page_num=1, text="")]
    monkeypatch.setattr(
        evidence_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: fake_pages,
    )

    fake_md = "# Scanned PDF\n\n甲方：测试客户有限公司\n金额：120000"
    captured: dict = {}

    async def fake_pdf_ocr(pdf_bytes, filename="doc.pdf"):
        captured["bytes_len"] = len(pdf_bytes)
        captured["filename"] = filename
        return fake_md

    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", fake_pdf_ocr)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"%PDF-1.4 scanned bytes",
            original_filename="scan.pdf",
            content_type="application/pdf",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "pdf"
        assert result.ocr_text == fake_md
        assert "测试客户有限公司" in result.ocr_text
        assert result.warnings == []
        assert captured["filename"] == "scan.pdf"
        assert captured["bytes_len"] > 0
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_ocr_unavailable_warns(monkeypatch) -> None:
    """Scanned PDF + OCR down → ocr_text stays empty, warning attached."""
    _patch_store_upload(monkeypatch)

    monkeypatch.setattr(
        evidence_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [pdf_utils.PageText(page_num=1, text="")],
    )

    async def explode(*a, **k):
        raise MistralOCRUnavailable("mistral ocr 5xx 500: down")

    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", explode)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"%PDF",
            original_filename="scan.pdf",
            content_type="application/pdf",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "pdf"
        assert result.ocr_text == ""
        assert any("Mistral OCR unavailable" in w for w in result.warnings)
    finally:
        await session.close()
        await engine.dispose()


# ---------- office path ---------------------------------------------------


@pytest.mark.asyncio
async def test_office_doc_routes_to_document_url_ocr(monkeypatch) -> None:
    """A .docx file goes through ``parse_document_to_markdown``."""
    _patch_store_upload(monkeypatch)

    fake_md = "# Word doc\n\n甲方：另一家测试客户公司"
    captured: dict = {}

    async def fake_doc_ocr(doc_bytes, filename="doc.pdf", content_type=None):
        captured["bytes_len"] = len(doc_bytes)
        captured["filename"] = filename
        captured["content_type"] = content_type
        return fake_md

    monkeypatch.setattr(evidence_module, "parse_document_to_markdown", fake_doc_ocr)

    async def boom_image(*a, **k):
        raise AssertionError("image OCR must not run for office files")

    async def boom_pdf(*a, **k):
        raise AssertionError("pdf OCR must not run for office files")

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", boom_image)
    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", boom_pdf)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"PK\x03\x04 docx bytes",
            original_filename="proposal.docx",
            source_hint="file",
        )
        await session.commit()

        assert result.modality == "office"
        assert result.ocr_text == fake_md
        assert captured["filename"] == "proposal.docx"
        assert result.document.type == DocumentType.contract
    finally:
        await session.close()
        await engine.dispose()


# ---------- error path ----------------------------------------------------


@pytest.mark.asyncio
async def test_empty_input_raises_value_error(monkeypatch) -> None:
    """Both inputs empty → caller bug → fast ValueError, no DB writes."""
    _patch_store_upload(monkeypatch)
    session, engine = await _make_session()
    try:
        with pytest.raises(ValueError, match="no input"):
            await collect_evidence(
                session=session,
                file_bytes=b"",
                text_content=None,
                source_hint="file",
            )
        # Nothing landed in the DB.
        rows = (await session.execute(select(Document))).scalars().all()
        assert rows == []
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_empty_text_and_no_bytes_raises(monkeypatch) -> None:
    """``text_content=""`` + no bytes is also "no input" — must raise."""
    _patch_store_upload(monkeypatch)
    session, engine = await _make_session()
    try:
        with pytest.raises(ValueError, match="no input"):
            await collect_evidence(
                session=session,
                text_content="   ",  # whitespace only
                source_hint="pasted_text",
            )
    finally:
        await session.close()
        await engine.dispose()


# ---------- progress callback --------------------------------------------


@pytest.mark.asyncio
async def test_progress_callback_emits_stages(monkeypatch) -> None:
    """The progress callback receives ``stored`` and ``ocr`` notifications."""
    _patch_store_upload(monkeypatch)

    async def fake_image(*a, **k):
        return "some markdown"

    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", fake_image)

    events: list[tuple[str, str]] = []

    async def progress(stage: str, message: str) -> None:
        events.append((stage, message))

    session, engine = await _make_session()
    try:
        await collect_evidence(
            session=session,
            file_bytes=b"jpeg-bytes",
            original_filename="card.jpg",
            content_type="image/jpeg",
            source_hint="file",
            progress=progress,
        )
        await session.commit()

        stages = [stage for stage, _ in events]
        assert "stored" in stages
        assert "ocr" in stages
    finally:
        await session.close()
        await engine.dispose()


