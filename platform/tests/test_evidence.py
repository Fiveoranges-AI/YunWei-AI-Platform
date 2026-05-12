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
from yinhu_brain.services.ingest import evidence as evidence_module
from yinhu_brain.services.ingest.evidence import Evidence, collect_evidence
from yinhu_brain.services.ocr.base import OcrInput, OcrResult


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


class _FakeOcrProvider:
    """Capture each ``parse`` call and return a pre-canned ``OcrResult``.

    Used to assert that ``collect_evidence`` forwards modality / filename /
    content_type through to whichever provider the factory returns.
    """

    def __init__(self, result: OcrResult) -> None:
        self.result = result
        self.inputs: list[OcrInput] = []

    async def parse(self, ocr_input: OcrInput) -> OcrResult:
        self.inputs.append(ocr_input)
        return self.result


def _install_provider(monkeypatch: pytest.MonkeyPatch, provider) -> None:
    """Patch ``get_ocr_provider`` so ``collect_evidence`` uses ``provider``."""
    monkeypatch.setattr(evidence_module, "get_ocr_provider", lambda: provider)


# ---------- text-content path --------------------------------------------


@pytest.mark.asyncio
async def test_text_content_does_not_call_ocr(monkeypatch) -> None:
    """A pasted text note becomes the ocr_text directly; no OCR provider fires."""
    store_calls = _patch_store_upload(monkeypatch)

    def boom_factory():
        raise AssertionError("OCR provider must not be requested for text input")

    monkeypatch.setattr(evidence_module, "get_ocr_provider", boom_factory)

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
    """Image bytes flow through the OCR provider and the markdown
    becomes ``ocr_text``."""
    store_calls = _patch_store_upload(monkeypatch)
    fake_md = "# Card\n\n王经理 13800000000 wang@example.com"

    provider = _FakeOcrProvider(OcrResult(markdown=fake_md, provider="fake"))
    _install_provider(monkeypatch, provider)

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
        # Provider received the correct OcrInput.
        assert len(provider.inputs) == 1
        ocr_input = provider.inputs[0]
        assert ocr_input.modality == "image"
        assert ocr_input.filename == "card.png"
        assert ocr_input.content_type == "image/png"
        assert ocr_input.source_hint == "file"
        assert len(ocr_input.file_bytes) > 0
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

    provider = _FakeOcrProvider(OcrResult(markdown="ocr text from camera", provider="fake"))
    _install_provider(monkeypatch, provider)

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
        # ``source_hint=camera`` should propagate to the provider input.
        assert provider.inputs[0].source_hint == "camera"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_image_ocr_unavailable_warns_does_not_raise(monkeypatch) -> None:
    """Provider returns empty markdown + warning → ocr_text empty,
    Document row still flushed, warning attached."""
    _patch_store_upload(monkeypatch)

    provider = _FakeOcrProvider(
        OcrResult(
            markdown="",
            provider="fake",
            warnings=["Mistral OCR unavailable: ConnectError(...)"],
        )
    )
    _install_provider(monkeypatch, provider)

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
async def test_pdf_routes_to_provider_with_pdf_modality(monkeypatch) -> None:
    """A PDF flows through the OCR provider with ``modality='pdf'``.

    The native-text / OCR-fallback decision now lives inside the provider, so
    the orchestrator-level test only verifies routing + result forwarding.
    """
    _patch_store_upload(monkeypatch)

    fake_md = "[page 1]\n甲方：测试客户有限公司\n金额：120000 元"
    provider = _FakeOcrProvider(
        OcrResult(
            markdown=fake_md,
            provider="fake",
            metadata={"pdf_text_source": "native"},
        )
    )
    _install_provider(monkeypatch, provider)

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
        assert result.ocr_text == fake_md
        assert result.warnings == []
        assert result.document.type == DocumentType.contract
        assert result.document.content_type == "application/pdf"
        assert provider.inputs[0].modality == "pdf"
        assert provider.inputs[0].filename == "contract.pdf"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_ocr_unavailable_warns(monkeypatch) -> None:
    """Provider's warning bubbles up as a Document parse_warning."""
    _patch_store_upload(monkeypatch)

    provider = _FakeOcrProvider(
        OcrResult(
            markdown="",
            provider="fake",
            warnings=["Mistral OCR unavailable: 5xx 500"],
        )
    )
    _install_provider(monkeypatch, provider)

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
async def test_office_doc_routes_to_provider_with_office_modality(monkeypatch) -> None:
    """A .docx file flows through the OCR provider with ``modality='office'``."""
    _patch_store_upload(monkeypatch)

    fake_md = "# Word doc\n\n甲方：另一家测试客户公司"
    provider = _FakeOcrProvider(OcrResult(markdown=fake_md, provider="fake"))
    _install_provider(monkeypatch, provider)

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
        assert provider.inputs[0].modality == "office"
        assert provider.inputs[0].filename == "proposal.docx"
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

    provider = _FakeOcrProvider(OcrResult(markdown="some markdown", provider="fake"))
    _install_provider(monkeypatch, provider)

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


