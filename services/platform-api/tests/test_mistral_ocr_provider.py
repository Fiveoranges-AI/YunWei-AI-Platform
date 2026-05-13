"""Tests for ``MistralOcrProvider``.

The provider wraps the existing ``mistral_ocr_client`` helpers so the
ingest orchestrator does not branch per modality. These tests monkeypatch
the upstream functions on the provider module so no live network call is
made; the goal is to verify modality routing, PDF native-text fast-path,
and OCR-unavailable → warning conversion match the previous behavior that
used to live in ``evidence.py``.
"""

from __future__ import annotations

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yunwei_win.services import pdf as pdf_utils
from yunwei_win.services.mistral_ocr_client import MistralOCRUnavailable
from yunwei_win.services.ocr.base import OcrInput
from yunwei_win.services.ocr.mistral import MistralOcrProvider


@pytest.mark.asyncio
async def test_image_modality_calls_image_ocr(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    captured: dict = {}

    async def fake_image(data, filename, content_type):
        captured["data"] = data
        captured["filename"] = filename
        captured["content_type"] = content_type
        return "image markdown"

    async def boom_pdf(*a, **k):
        raise AssertionError("pdf OCR must not run for image modality")

    async def boom_doc(*a, **k):
        raise AssertionError("document OCR must not run for image modality")

    monkeypatch.setattr(mistral_module, "parse_image_to_markdown", fake_image)
    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", boom_pdf)
    monkeypatch.setattr(mistral_module, "parse_document_to_markdown", boom_doc)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"image-bytes",
            stored_path="/tmp/card.png",
            filename="card.png",
            content_type="image/png",
            modality="image",
            source_hint="file",
        )
    )

    assert result.markdown == "image markdown"
    assert result.provider == "mistral"
    assert result.warnings == []
    assert captured["filename"] == "card.png"
    assert captured["content_type"] == "image/png"
    assert captured["data"] == b"image-bytes"


@pytest.mark.asyncio
async def test_pdf_native_text_skips_ocr(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    monkeypatch.setattr(
        mistral_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [
            pdf_utils.PageText(page_num=1, text="甲方：测试客户有限公司"),
            pdf_utils.PageText(page_num=2, text="金额：120000"),
        ],
    )

    async def boom_pdf(*a, **k):
        raise AssertionError("OCR fallback must not run when native text exists")

    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", boom_pdf)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"%PDF-1.4 native",
            stored_path="/tmp/native.pdf",
            filename="native.pdf",
            content_type="application/pdf",
            modality="pdf",
            source_hint="file",
        )
    )

    assert "测试客户有限公司" in result.markdown
    assert result.provider == "mistral"
    assert result.metadata.get("pdf_text_source") == "native"
    assert result.warnings == []


@pytest.mark.asyncio
async def test_pdf_scanned_falls_back_to_mistral_ocr(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    monkeypatch.setattr(
        mistral_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [pdf_utils.PageText(page_num=1, text="")],
    )

    captured: dict = {}

    async def fake_pdf(data, filename):
        captured["data"] = data
        captured["filename"] = filename
        return "scanned markdown"

    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", fake_pdf)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"%PDF scanned",
            stored_path="/tmp/scan.pdf",
            filename="scan.pdf",
            content_type="application/pdf",
            modality="pdf",
            source_hint="file",
        )
    )

    assert result.markdown == "scanned markdown"
    assert result.provider == "mistral"
    assert result.metadata.get("pdf_text_source") == "mistral_ocr"
    assert captured["filename"] == "scan.pdf"
    assert captured["data"] == b"%PDF scanned"


@pytest.mark.asyncio
async def test_office_modality_calls_document_ocr(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    captured: dict = {}

    async def fake_doc(data, filename, content_type=None):
        captured["data"] = data
        captured["filename"] = filename
        captured["content_type"] = content_type
        return "office markdown"

    monkeypatch.setattr(mistral_module, "parse_document_to_markdown", fake_doc)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"PK\x03\x04",
            stored_path="/tmp/doc.docx",
            filename="proposal.docx",
            content_type=None,
            modality="office",
            source_hint="file",
        )
    )

    assert result.markdown == "office markdown"
    assert result.provider == "mistral"
    assert captured["filename"] == "proposal.docx"


@pytest.mark.asyncio
async def test_image_ocr_unavailable_becomes_warning(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    async def explode(*a, **k):
        raise MistralOCRUnavailable("mistral ocr unreachable: ConnectError")

    monkeypatch.setattr(mistral_module, "parse_image_to_markdown", explode)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"img",
            stored_path="/tmp/card.jpg",
            filename="card.jpg",
            content_type="image/jpeg",
            modality="image",
            source_hint="file",
        )
    )

    assert result.markdown == ""
    assert result.provider == "mistral"
    assert any("Mistral OCR unavailable" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_pdf_scanned_ocr_unavailable_becomes_warning(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    monkeypatch.setattr(
        mistral_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [pdf_utils.PageText(page_num=1, text="")],
    )

    async def explode(*a, **k):
        raise MistralOCRUnavailable("mistral ocr 5xx 500: down")

    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", explode)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"%PDF",
            stored_path="/tmp/scan.pdf",
            filename="scan.pdf",
            content_type="application/pdf",
            modality="pdf",
            source_hint="file",
        )
    )

    assert result.markdown == ""
    assert any("Mistral OCR unavailable" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_office_ocr_unavailable_becomes_warning(monkeypatch) -> None:
    from yunwei_win.services.ocr import mistral as mistral_module

    async def explode(*a, **k):
        raise MistralOCRUnavailable("mistral down")

    monkeypatch.setattr(mistral_module, "parse_document_to_markdown", explode)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"PK",
            stored_path="/tmp/doc.docx",
            filename="doc.docx",
            content_type=None,
            modality="office",
            source_hint="file",
        )
    )

    assert result.markdown == ""
    assert any("Mistral OCR unavailable" in w for w in result.warnings)
