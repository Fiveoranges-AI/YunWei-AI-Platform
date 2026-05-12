# Modular OCR And Extractor Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split win ingest OCR and schema extraction into provider adapters, then add MinerU precise OCR and DeepSeek schema-routed extraction without changing the winapp response contract.

**Architecture:** Keep `/api/ingest/auto` as the stable orchestration boundary. `collect_evidence` stores input and calls an OCR provider for non-text uploads. `auto_ingest` routes schemas once, calls an extractor provider that returns `PipelineExtractResult[]`, normalizes those results into `UnifiedDraft`, and reuses existing Review/confirm flows.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Pydantic settings, `httpx`, existing Mistral OCR client, LandingAI ADE wrapper, DeepSeek through existing Anthropic-compatible `call_claude`, pytest/pytest-asyncio/respx.

---

## Design Review Against `coding-principle.md`

The design is sound with one required correction already applied to the spec:

- **High cohesion / low coupling:** OCR adapters own parsing API quirks; extractor adapters own model extraction quirks; business schemas and normalizer remain provider-neutral.
- **KISS:** The plan uses plain provider factories and dataclasses, not a dynamic plugin framework.
- **Cautious DRY:** Shared provider contracts are justified because Mistral/MinerU and LandingAI/DeepSeek are the same concepts and will change together at orchestration boundaries.
- **Explicit over implicit:** `ExtractionInput` now carries `AsyncSession` because DeepSeek and legacy extractors write `llm_calls`. No hidden global DB dependency.
- **Verifiability:** Every provider gets focused tests with no live network calls. Orchestrator tests verify provider composition end to end.

Implementation constraint: do not change winapp types, DB tables, confirm writeback, or the shape of `/win/api/ingest/auto`.

## File Structure

Create:

- `platform/yinhu_brain/services/ocr/__init__.py`  
  Public exports for OCR provider contracts and factory.
- `platform/yinhu_brain/services/ocr/base.py`  
  `OcrInput`, `OcrResult`, `OcrUnavailable`, `OcrProvider`.
- `platform/yinhu_brain/services/ocr/mistral.py`  
  Moves current Mistral OCR branching out of `evidence.py`.
- `platform/yinhu_brain/services/ocr/mineru.py`  
  MinerU precise signed-upload, polling, zip download, `full.md` extraction.
- `platform/yinhu_brain/services/ocr/factory.py`  
  `get_ocr_provider`.
- `platform/yinhu_brain/services/ingest/extractors/providers/__init__.py`  
  Public exports for extractor providers.
- `platform/yinhu_brain/services/ingest/extractors/providers/base.py`  
  `ExtractionInput`, `ExtractorProvider`.
- `platform/yinhu_brain/services/ingest/extractors/providers/landingai.py`  
  Wraps current LandingAI schema extraction.
- `platform/yinhu_brain/services/ingest/extractors/providers/legacy.py`  
  Preserves identity/commercial/ops behavior and warnings for unsupported schemas.
- `platform/yinhu_brain/services/ingest/extractors/providers/deepseek_schema.py`  
  New schema-routed DeepSeek extraction returning `PipelineExtractResult[]`.
- `platform/yinhu_brain/services/ingest/extractors/providers/factory.py`  
  `get_extractor_provider` and backwards-compatible provider resolution.
- `platform/prompts/schema_extraction.md`  
  Provider-neutral schema extraction prompt.
- `platform/tests/test_ocr_provider_factory.py`
- `platform/tests/test_mistral_ocr_provider.py`
- `platform/tests/test_mineru_ocr_provider.py`
- `platform/tests/test_extractor_provider_factory.py`
- `platform/tests/test_landingai_extractor_provider.py`
- `platform/tests/test_legacy_extractor_provider.py`
- `platform/tests/test_deepseek_schema_extractor_provider.py`

Modify:

- `platform/yinhu_brain/config.py`  
  Add OCR/extractor provider settings and MinerU settings.
- `platform/yinhu_brain/services/ingest/evidence.py`  
  Replace inline Mistral branches with OCR provider call.
- `platform/yinhu_brain/services/ingest/auto.py`  
  Replace provider-specific extraction branching with extractor provider call.
- `platform/tests/test_evidence.py`  
  Update monkeypatches from raw Mistral functions to OCR provider factory where needed.
- `platform/tests/test_ingest_auto_flow.py`  
  Update orchestrator tests to patch provider factory instead of old LandingAI function.

## Task 1: Settings And OCR Contracts

**Files:**
- Modify: `platform/yinhu_brain/config.py`
- Create: `platform/yinhu_brain/services/ocr/__init__.py`
- Create: `platform/yinhu_brain/services/ocr/base.py`
- Create: `platform/yinhu_brain/services/ocr/factory.py`
- Test: `platform/tests/test_ocr_provider_factory.py`

- [ ] **Step 1: Write failing OCR factory tests**

Create `platform/tests/test_ocr_provider_factory.py`:

```python
from __future__ import annotations

import pytest

from yinhu_brain.services.ocr.factory import get_ocr_provider
from yinhu_brain.services.ocr.mistral import MistralOcrProvider
from yinhu_brain.services.ocr.mineru import MineruPreciseOcrProvider


def test_get_ocr_provider_defaults_to_mistral(monkeypatch):
    from yinhu_brain.services.ocr import factory

    monkeypatch.setattr(factory.settings, "ocr_provider", "mistral")

    provider = get_ocr_provider()

    assert isinstance(provider, MistralOcrProvider)


def test_get_ocr_provider_can_select_mineru(monkeypatch):
    from yinhu_brain.services.ocr import factory

    monkeypatch.setattr(factory.settings, "ocr_provider", "mineru")

    provider = get_ocr_provider()

    assert isinstance(provider, MineruPreciseOcrProvider)


def test_get_ocr_provider_rejects_unknown_value():
    with pytest.raises(ValueError, match="unknown OCR provider"):
        get_ocr_provider("not-real")
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ocr_provider_factory.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'yinhu_brain.services.ocr'`.

- [ ] **Step 3: Add OCR settings**

In `platform/yinhu_brain/config.py`, add after `document_ai_provider`:

```python
    # ---- Modular ingest providers ----------------------------------------
    ocr_provider: Literal["mistral", "mineru"] = "mistral"
    extractor_provider: Literal["landingai", "deepseek", "legacy"] | None = None

    # ---- MinerU precise OCR ----------------------------------------------
    mineru_api_token: str = ""
    mineru_base_url: str = "https://mineru.net"
    mineru_model_version: Literal["pipeline", "vlm"] = "vlm"
    mineru_language: str = "ch"
    mineru_enable_table: bool = True
    mineru_enable_formula: bool = True
    mineru_is_ocr: bool = True
    mineru_poll_interval_seconds: float = 2.0
    mineru_timeout_seconds: int = 180
```

- [ ] **Step 4: Add OCR contract and factory**

Create `platform/yinhu_brain/services/ocr/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


OcrModality = Literal["image", "pdf", "office"]
OcrSourceHint = Literal["file", "camera"]


class OcrUnavailable(Exception):
    """Raised when an OCR provider is not configured or cannot parse input."""


@dataclass(frozen=True)
class OcrInput:
    file_bytes: bytes
    stored_path: str | None
    filename: str
    content_type: str | None
    modality: OcrModality
    source_hint: OcrSourceHint


@dataclass
class OcrResult:
    markdown: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class OcrProvider(Protocol):
    async def parse(self, input: OcrInput) -> OcrResult:
        """Parse a non-text upload into markdown."""
```

Create `platform/yinhu_brain/services/ocr/mistral.py` with a temporary class that will be replaced in Task 2:

```python
from __future__ import annotations

from yinhu_brain.services.ocr.base import OcrInput, OcrResult


class MistralOcrProvider:
    async def parse(self, input: OcrInput) -> OcrResult:
        raise NotImplementedError("MistralOcrProvider.parse is implemented in Task 2")
```

Create `platform/yinhu_brain/services/ocr/mineru.py` with a temporary class that will be replaced in Task 3:

```python
from __future__ import annotations

from yinhu_brain.services.ocr.base import OcrInput, OcrResult


class MineruPreciseOcrProvider:
    async def parse(self, input: OcrInput) -> OcrResult:
        raise NotImplementedError("MineruPreciseOcrProvider.parse is implemented in Task 3")
```

Create `platform/yinhu_brain/services/ocr/factory.py`:

```python
from __future__ import annotations

from typing import Literal

from yinhu_brain.config import settings
from yinhu_brain.services.ocr.base import OcrProvider
from yinhu_brain.services.ocr.mineru import MineruPreciseOcrProvider
from yinhu_brain.services.ocr.mistral import MistralOcrProvider


OcrProviderName = Literal["mistral", "mineru"]


def get_ocr_provider(name: OcrProviderName | str | None = None) -> OcrProvider:
    provider_name = name or settings.ocr_provider
    if provider_name == "mistral":
        return MistralOcrProvider()
    if provider_name == "mineru":
        return MineruPreciseOcrProvider()
    raise ValueError(f"unknown OCR provider: {provider_name!r}")
```

Create `platform/yinhu_brain/services/ocr/__init__.py`:

```python
from yinhu_brain.services.ocr.base import OcrInput, OcrProvider, OcrResult, OcrUnavailable
from yinhu_brain.services.ocr.factory import get_ocr_provider

__all__ = [
    "OcrInput",
    "OcrProvider",
    "OcrResult",
    "OcrUnavailable",
    "get_ocr_provider",
]
```

- [ ] **Step 5: Run test**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ocr_provider_factory.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add platform/yinhu_brain/config.py platform/yinhu_brain/services/ocr platform/tests/test_ocr_provider_factory.py
git commit -m "feat: add OCR provider contracts"
```

## Task 2: Mistral OCR Provider And Evidence Wiring

**Files:**
- Modify: `platform/yinhu_brain/services/ocr/mistral.py`
- Modify: `platform/yinhu_brain/services/ingest/evidence.py`
- Modify: `platform/tests/test_evidence.py`
- Test: `platform/tests/test_mistral_ocr_provider.py`

- [ ] **Step 1: Write failing Mistral provider tests**

Create `platform/tests/test_mistral_ocr_provider.py`:

```python
from __future__ import annotations

import pytest

from yinhu_brain.services import pdf as pdf_utils
from yinhu_brain.services.ocr.base import OcrInput
from yinhu_brain.services.ocr.mistral import MistralOcrProvider
from yinhu_brain.services.mistral_ocr_client import MistralOCRUnavailable


@pytest.mark.asyncio
async def test_mistral_provider_uses_image_ocr(monkeypatch):
    from yinhu_brain.services.ocr import mistral as mistral_module

    async def fake_image(data, filename, content_type):
        assert data == b"image"
        assert filename == "card.png"
        assert content_type == "image/png"
        return "image markdown"

    monkeypatch.setattr(mistral_module, "parse_image_to_markdown", fake_image)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"image",
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


@pytest.mark.asyncio
async def test_mistral_provider_uses_native_pdf_text_before_ocr(monkeypatch):
    from yinhu_brain.services.ocr import mistral as mistral_module

    monkeypatch.setattr(
        mistral_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [pdf_utils.PageText(page_num=1, text="甲方：测试客户有限公司")],
    )

    async def boom_pdf(*args, **kwargs):
        raise AssertionError("OCR fallback should not run when native text exists")

    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", boom_pdf)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"%PDF",
            stored_path="/tmp/native.pdf",
            filename="native.pdf",
            content_type="application/pdf",
            modality="pdf",
            source_hint="file",
        )
    )

    assert "测试客户有限公司" in result.markdown
    assert result.metadata["pdf_text_source"] == "native"


@pytest.mark.asyncio
async def test_mistral_provider_falls_back_for_scanned_pdf(monkeypatch):
    from yinhu_brain.services.ocr import mistral as mistral_module

    monkeypatch.setattr(
        mistral_module.pdf_utils,
        "extract_text_with_pages",
        lambda path: [pdf_utils.PageText(page_num=1, text="")],
    )

    async def fake_pdf(data, filename):
        assert data == b"%PDF"
        assert filename == "scan.pdf"
        return "scanned markdown"

    monkeypatch.setattr(mistral_module, "parse_pdf_to_markdown", fake_pdf)

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

    assert result.markdown == "scanned markdown"
    assert result.metadata["pdf_text_source"] == "mistral_ocr"


@pytest.mark.asyncio
async def test_mistral_provider_converts_ocr_unavailable_to_warning(monkeypatch):
    from yinhu_brain.services.ocr import mistral as mistral_module

    async def explode(*args, **kwargs):
        raise MistralOCRUnavailable("mistral down")

    monkeypatch.setattr(mistral_module, "parse_image_to_markdown", explode)

    result = await MistralOcrProvider().parse(
        OcrInput(
            file_bytes=b"image",
            stored_path="/tmp/card.jpg",
            filename="card.jpg",
            content_type="image/jpeg",
            modality="image",
            source_hint="file",
        )
    )

    assert result.markdown == ""
    assert any("Mistral OCR unavailable" in w for w in result.warnings)
```

- [ ] **Step 2: Run failing provider tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_mistral_ocr_provider.py -q
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement Mistral provider**

Replace `platform/yinhu_brain/services/ocr/mistral.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

from yinhu_brain.services import pdf as pdf_utils
from yinhu_brain.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_document_to_markdown,
    parse_image_to_markdown,
    parse_pdf_to_markdown,
)
from yinhu_brain.services.ocr.base import OcrInput, OcrResult

logger = logging.getLogger(__name__)


class MistralOcrProvider:
    async def parse(self, input: OcrInput) -> OcrResult:
        if input.modality == "image":
            return await self._parse_image(input)
        if input.modality == "pdf":
            return await self._parse_pdf(input)
        return await self._parse_office(input)

    async def _parse_image(self, input: OcrInput) -> OcrResult:
        try:
            markdown = await parse_image_to_markdown(
                input.file_bytes,
                input.filename,
                input.content_type,
            )
            return OcrResult(markdown=markdown or "", provider="mistral")
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral image OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])

    async def _parse_pdf(self, input: OcrInput) -> OcrResult:
        pages = pdf_utils.extract_text_with_pages(input.stored_path)
        native_text = pdf_utils.joined_text(pages)
        if native_text.strip():
            return OcrResult(
                markdown=native_text,
                provider="mistral",
                metadata={"pdf_text_source": "native"},
            )

        ocr_bytes = input.file_bytes
        if not ocr_bytes and input.stored_path:
            try:
                ocr_bytes = Path(input.stored_path).read_bytes()
            except FileNotFoundError as exc:
                msg = f"pre_stored pdf missing on fallback: {exc!s}"
                return OcrResult(markdown="", provider="mistral", warnings=[msg])

        try:
            markdown = await parse_pdf_to_markdown(ocr_bytes, input.filename)
            return OcrResult(
                markdown=markdown or "",
                provider="mistral",
                metadata={"pdf_text_source": "mistral_ocr"},
            )
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral pdf OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])

    async def _parse_office(self, input: OcrInput) -> OcrResult:
        try:
            markdown = await parse_document_to_markdown(
                input.file_bytes,
                input.filename,
                input.content_type,
            )
            return OcrResult(markdown=markdown or "", provider="mistral")
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral office OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])
```

- [ ] **Step 4: Run provider tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_mistral_ocr_provider.py -q
```

Expected: PASS.

- [ ] **Step 5: Rewire `collect_evidence`**

In `platform/yinhu_brain/services/ingest/evidence.py`:

Remove imports:

```python
from yinhu_brain.services import pdf as pdf_utils
from yinhu_brain.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_document_to_markdown,
    parse_image_to_markdown,
    parse_pdf_to_markdown,
)
```

Add imports:

```python
from yinhu_brain.services.ocr import OcrInput, OcrResult, get_ocr_provider
```

Replace the modality-specific OCR block with:

```python
    if modality == "text":
        assert text_content is not None
        ocr_text = text_content.strip()

    else:
        provider = get_ocr_provider()
        if modality == "image":
            await emit_progress(progress, "ocr", "正在识别图片文本")
        elif modality == "pdf":
            await emit_progress(progress, "ocr", "正在读取 PDF 文本")
        else:
            await emit_progress(progress, "ocr", "正在识别文档文本")

        result: OcrResult = await provider.parse(
            OcrInput(
                file_bytes=payload_bytes,
                stored_path=stored_path,
                filename=filename_for_store,
                content_type=ct_for_doc,
                modality=modality,
                source_hint="camera" if source_hint == "camera" else "file",
            )
        )
        ocr_text = result.markdown or ""
        warnings.extend(result.warnings)
```

- [ ] **Step 6: Update evidence tests to patch provider factory**

In `platform/tests/test_evidence.py`, add:

```python
from yinhu_brain.services.ocr.base import OcrResult
```

For tests that currently monkeypatch `evidence_module.parse_image_to_markdown`,
`parse_pdf_to_markdown`, `parse_document_to_markdown`, or `pdf_utils`, replace
those monkeypatches with a fake provider where the test only needs evidence
routing:

```python
class _FakeOcrProvider:
    def __init__(self, result: OcrResult):
        self.result = result
        self.inputs = []

    async def parse(self, input):
        self.inputs.append(input)
        return self.result
```

Example for `test_image_bytes_trigger_image_ocr`:

```python
    provider = _FakeOcrProvider(OcrResult(markdown=fake_md, provider="fake"))
    monkeypatch.setattr(evidence_module, "get_ocr_provider", lambda: provider)
```

Then assert:

```python
        assert provider.inputs[0].modality == "image"
        assert provider.inputs[0].filename == "card.png"
        assert provider.inputs[0].content_type == "image/png"
```

Keep the text-input tests asserting OCR is not called by monkeypatching:

```python
monkeypatch.setattr(
    evidence_module,
    "get_ocr_provider",
    lambda: pytest.fail("OCR provider must not be requested for text"),
)
```

- [ ] **Step 7: Run evidence and provider tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_mistral_ocr_provider.py tests/test_evidence.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add platform/yinhu_brain/services/ocr/mistral.py platform/yinhu_brain/services/ingest/evidence.py platform/tests/test_mistral_ocr_provider.py platform/tests/test_evidence.py
git commit -m "refactor: route evidence OCR through provider"
```

## Task 3: MinerU Precise OCR Provider

**Files:**
- Modify: `platform/yinhu_brain/services/ocr/mineru.py`
- Test: `platform/tests/test_mineru_ocr_provider.py`

- [ ] **Step 1: Write MinerU provider tests**

Create `platform/tests/test_mineru_ocr_provider.py`:

```python
from __future__ import annotations

import io
import zipfile

import httpx
import pytest

from yinhu_brain.services.ocr.base import OcrInput, OcrUnavailable
from yinhu_brain.services.ocr.mineru import MineruPreciseOcrProvider


def _zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_mineru_provider_uploads_polls_downloads_full_md(monkeypatch, respx_mock):
    from yinhu_brain.services.ocr import mineru as mineru_module

    monkeypatch.setattr(mineru_module.settings, "mineru_api_token", "token")
    monkeypatch.setattr(mineru_module.settings, "mineru_base_url", "https://mineru.net")
    monkeypatch.setattr(mineru_module.settings, "mineru_poll_interval_seconds", 0)
    monkeypatch.setattr(mineru_module.settings, "mineru_timeout_seconds", 5)

    apply_route = respx_mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "trace_id": "trace-1",
                "data": {
                    "batch_id": "batch-1",
                    "file_urls": ["https://upload.example.com/doc.pdf"],
                },
            },
        )
    )
    upload_route = respx_mock.put("https://upload.example.com/doc.pdf").mock(
        return_value=httpx.Response(200)
    )
    poll_route = respx_mock.get(
        "https://mineru.net/api/v4/extract-results/batch/batch-1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "trace_id": "trace-2",
                "data": {
                    "batch_id": "batch-1",
                    "extract_result": [
                        {
                            "file_name": "doc.pdf",
                            "state": "done",
                            "err_msg": "",
                            "full_zip_url": "https://cdn.example.com/result.zip",
                        }
                    ],
                },
            },
        )
    )
    zip_route = respx_mock.get("https://cdn.example.com/result.zip").mock(
        return_value=httpx.Response(200, content=_zip_bytes({"full.md": "# Parsed\n\n甲方"}))
    )

    result = await MineruPreciseOcrProvider().parse(
        OcrInput(
            file_bytes=b"%PDF",
            stored_path="/tmp/doc.pdf",
            filename="doc.pdf",
            content_type="application/pdf",
            modality="pdf",
            source_hint="file",
        )
    )

    assert result.provider == "mineru"
    assert result.markdown == "# Parsed\n\n甲方"
    assert result.metadata["batch_id"] == "batch-1"
    assert result.metadata["full_zip_url"] == "https://cdn.example.com/result.zip"
    assert apply_route.called
    assert upload_route.called
    assert poll_route.called
    assert zip_route.called


@pytest.mark.asyncio
async def test_mineru_provider_requires_token(monkeypatch):
    from yinhu_brain.services.ocr import mineru as mineru_module

    monkeypatch.setattr(mineru_module.settings, "mineru_api_token", "")

    with pytest.raises(OcrUnavailable, match="MINERU_API_TOKEN"):
        await MineruPreciseOcrProvider().parse(
            OcrInput(
                file_bytes=b"%PDF",
                stored_path="/tmp/doc.pdf",
                filename="doc.pdf",
                content_type="application/pdf",
                modality="pdf",
                source_hint="file",
            )
        )


@pytest.mark.asyncio
async def test_mineru_provider_raises_on_failed_state(monkeypatch, respx_mock):
    from yinhu_brain.services.ocr import mineru as mineru_module

    monkeypatch.setattr(mineru_module.settings, "mineru_api_token", "token")
    monkeypatch.setattr(mineru_module.settings, "mineru_poll_interval_seconds", 0)

    respx_mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "msg": "ok", "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example.com/doc.pdf"]}},
        )
    )
    respx_mock.put("https://upload.example.com/doc.pdf").mock(return_value=httpx.Response(200))
    respx_mock.get("https://mineru.net/api/v4/extract-results/batch/batch-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {"extract_result": [{"state": "failed", "err_msg": "bad file"}]},
            },
        )
    )

    with pytest.raises(OcrUnavailable, match="bad file"):
        await MineruPreciseOcrProvider().parse(
            OcrInput(
                file_bytes=b"%PDF",
                stored_path="/tmp/doc.pdf",
                filename="doc.pdf",
                content_type="application/pdf",
                modality="pdf",
                source_hint="file",
            )
        )


@pytest.mark.asyncio
async def test_mineru_provider_raises_when_zip_missing_full_md(monkeypatch, respx_mock):
    from yinhu_brain.services.ocr import mineru as mineru_module

    monkeypatch.setattr(mineru_module.settings, "mineru_api_token", "token")
    monkeypatch.setattr(mineru_module.settings, "mineru_poll_interval_seconds", 0)

    respx_mock.post("https://mineru.net/api/v4/file-urls/batch").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "msg": "ok", "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example.com/doc.pdf"]}},
        )
    )
    respx_mock.put("https://upload.example.com/doc.pdf").mock(return_value=httpx.Response(200))
    respx_mock.get("https://mineru.net/api/v4/extract-results/batch/batch-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {
                    "extract_result": [
                        {"state": "done", "full_zip_url": "https://cdn.example.com/result.zip"}
                    ]
                },
            },
        )
    )
    respx_mock.get("https://cdn.example.com/result.zip").mock(
        return_value=httpx.Response(200, content=_zip_bytes({"other.md": "no full"}))
    )

    with pytest.raises(OcrUnavailable, match="full.md"):
        await MineruPreciseOcrProvider().parse(
            OcrInput(
                file_bytes=b"%PDF",
                stored_path="/tmp/doc.pdf",
                filename="doc.pdf",
                content_type="application/pdf",
                modality="pdf",
                source_hint="file",
            )
        )
```

- [ ] **Step 2: Run failing MinerU tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_mineru_ocr_provider.py -q
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement MinerU provider**

Replace `platform/yinhu_brain/services/ocr/mineru.py`:

```python
from __future__ import annotations

import asyncio
import io
import time
import zipfile
from typing import Any

import httpx

from yinhu_brain.config import settings
from yinhu_brain.services.ocr.base import OcrInput, OcrResult, OcrUnavailable


class MineruPreciseOcrProvider:
    async def parse(self, input: OcrInput) -> OcrResult:
        token = settings.mineru_api_token.strip()
        if not token:
            raise OcrUnavailable("MINERU_API_TOKEN is not configured")

        base_url = settings.mineru_base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=120.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            batch_id, upload_url = await self._create_upload_task(
                client=client,
                base_url=base_url,
                headers=headers,
                filename=input.filename,
            )
            await self._upload_file(client=client, upload_url=upload_url, file_bytes=input.file_bytes)
            result = await self._poll_done(
                client=client,
                base_url=base_url,
                headers=headers,
                batch_id=batch_id,
            )
            full_zip_url = str(result.get("full_zip_url") or "")
            markdown = await self._download_full_markdown(client=client, full_zip_url=full_zip_url)

        return OcrResult(
            markdown=markdown,
            provider="mineru",
            metadata={
                "batch_id": batch_id,
                "full_zip_url": full_zip_url,
                "file_name": result.get("file_name"),
                "state": result.get("state"),
            },
        )

    async def _create_upload_task(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        filename: str,
    ) -> tuple[str, str]:
        payload = {
            "files": [{"name": filename}],
            "model_version": settings.mineru_model_version,
            "language": settings.mineru_language,
            "enable_table": settings.mineru_enable_table,
            "enable_formula": settings.mineru_enable_formula,
            "is_ocr": settings.mineru_is_ocr,
        }
        body = await self._request_json(
            client.post(f"{base_url}/api/v4/file-urls/batch", headers=headers, json=payload)
        )
        data = body.get("data") or {}
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls") or []
        upload_url = file_urls[0] if file_urls else None
        if not isinstance(batch_id, str) or not isinstance(upload_url, str):
            raise OcrUnavailable("MinerU upload task response missing batch_id or file_urls[0]")
        return batch_id, upload_url

    async def _upload_file(
        self,
        *,
        client: httpx.AsyncClient,
        upload_url: str,
        file_bytes: bytes,
    ) -> None:
        resp = await client.put(upload_url, content=file_bytes)
        if resp.status_code >= 400:
            raise OcrUnavailable(f"MinerU upload failed {resp.status_code}: {resp.text[:300]}")

    async def _poll_done(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        batch_id: str,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + float(settings.mineru_timeout_seconds)
        while True:
            body = await self._request_json(
                client.get(f"{base_url}/api/v4/extract-results/batch/{batch_id}", headers=headers)
            )
            data = body.get("data") or {}
            results = data.get("extract_result") or []
            result = results[0] if results else {}
            state = result.get("state")
            if state == "done":
                if not result.get("full_zip_url"):
                    raise OcrUnavailable("MinerU done result missing full_zip_url")
                return result
            if state == "failed":
                raise OcrUnavailable(f"MinerU parse failed: {result.get('err_msg') or 'unknown error'}")
            if time.monotonic() >= deadline:
                raise OcrUnavailable(f"MinerU parse timed out for batch {batch_id}")
            await asyncio.sleep(float(settings.mineru_poll_interval_seconds))

    async def _download_full_markdown(
        self,
        *,
        client: httpx.AsyncClient,
        full_zip_url: str,
    ) -> str:
        if not full_zip_url:
            raise OcrUnavailable("MinerU result missing full_zip_url")
        resp = await client.get(full_zip_url)
        if resp.status_code >= 400:
            raise OcrUnavailable(f"MinerU result zip download failed {resp.status_code}: {resp.text[:300]}")
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open("full.md") as f:
                    return f.read().decode("utf-8").strip()
        except KeyError as exc:
            raise OcrUnavailable("MinerU result zip missing full.md") from exc
        except zipfile.BadZipFile as exc:
            raise OcrUnavailable("MinerU result was not a valid zip file") from exc

    async def _request_json(self, awaitable) -> dict[str, Any]:
        try:
            resp = await awaitable
        except httpx.HTTPError as exc:
            raise OcrUnavailable(f"MinerU request failed: {exc!r}") from exc
        if resp.status_code >= 400:
            raise OcrUnavailable(f"MinerU HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            body = resp.json()
        except ValueError as exc:
            raise OcrUnavailable(f"MinerU non-JSON response: {resp.text[:200]}") from exc
        if body.get("code") != 0:
            trace_id = body.get("trace_id")
            raise OcrUnavailable(f"MinerU error {body.get('code')}: {body.get('msg')} trace_id={trace_id}")
        return body
```

- [ ] **Step 4: Run MinerU tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_mineru_ocr_provider.py tests/test_ocr_provider_factory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ocr/mineru.py platform/tests/test_mineru_ocr_provider.py
git commit -m "feat: add MinerU precise OCR provider"
```

## Task 4: Extractor Provider Contracts And Factory

**Files:**
- Create: `platform/yinhu_brain/services/ingest/extractors/providers/__init__.py`
- Create: `platform/yinhu_brain/services/ingest/extractors/providers/base.py`
- Create: `platform/yinhu_brain/services/ingest/extractors/providers/factory.py`
- Create temporary provider files: `landingai.py`, `legacy.py`, `deepseek_schema.py`
- Test: `platform/tests/test_extractor_provider_factory.py`

- [ ] **Step 1: Write failing factory tests**

Create `platform/tests/test_extractor_provider_factory.py`:

```python
from __future__ import annotations

import pytest

from yinhu_brain.services.ingest.extractors.providers.deepseek_schema import DeepSeekSchemaExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.factory import (
    get_extractor_provider,
    resolve_extractor_provider_name,
)
from yinhu_brain.services.ingest.extractors.providers.landingai import LandingAIExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.legacy import LegacyExtractorProvider


def test_resolve_extractor_provider_uses_explicit_setting(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", "deepseek")
    monkeypatch.setattr(factory.settings, "document_ai_provider", "landingai")

    assert resolve_extractor_provider_name() == "deepseek"


def test_resolve_extractor_provider_maps_legacy_document_ai_provider(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", None)
    monkeypatch.setattr(factory.settings, "document_ai_provider", "mistral")

    assert resolve_extractor_provider_name() == "legacy"


def test_resolve_extractor_provider_maps_landingai_document_ai_provider(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", None)
    monkeypatch.setattr(factory.settings, "document_ai_provider", "landingai")

    assert resolve_extractor_provider_name() == "landingai"


def test_get_extractor_provider_selects_each_provider():
    assert isinstance(get_extractor_provider("landingai"), LandingAIExtractorProvider)
    assert isinstance(get_extractor_provider("deepseek"), DeepSeekSchemaExtractorProvider)
    assert isinstance(get_extractor_provider("legacy"), LegacyExtractorProvider)


def test_get_extractor_provider_rejects_unknown_value():
    with pytest.raises(ValueError, match="unknown extractor provider"):
        get_extractor_provider("not-real")
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_extractor_provider_factory.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Add extractor provider contracts and factory**

Create `platform/yinhu_brain/services/ingest/extractors/providers/base.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult, PipelineSelection


@dataclass(frozen=True)
class ExtractionInput:
    document_id: uuid.UUID
    session: AsyncSession
    markdown: str
    selections: list[PipelineSelection]


class ExtractorProvider(Protocol):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        """Run selected schema pipelines and return provider-normalized results."""
```

Create temporary provider files:

```python
# platform/yinhu_brain/services/ingest/extractors/providers/landingai.py
from __future__ import annotations

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult


class LandingAIExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        raise NotImplementedError("LandingAIExtractorProvider is implemented in Task 5")
```

```python
# platform/yinhu_brain/services/ingest/extractors/providers/legacy.py
from __future__ import annotations

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult


class LegacyExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        raise NotImplementedError("LegacyExtractorProvider is implemented in Task 6")
```

```python
# platform/yinhu_brain/services/ingest/extractors/providers/deepseek_schema.py
from __future__ import annotations

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult


class DeepSeekSchemaExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        raise NotImplementedError("DeepSeekSchemaExtractorProvider is implemented in Task 7")
```

Create `platform/yinhu_brain/services/ingest/extractors/providers/factory.py`:

```python
from __future__ import annotations

from typing import Literal

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.extractors.providers.base import ExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.deepseek_schema import DeepSeekSchemaExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.landingai import LandingAIExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.legacy import LegacyExtractorProvider


ExtractorProviderName = Literal["landingai", "deepseek", "legacy"]


def resolve_extractor_provider_name() -> ExtractorProviderName:
    if settings.extractor_provider:
        return settings.extractor_provider
    if settings.document_ai_provider == "landingai":
        return "landingai"
    return "legacy"


def get_extractor_provider(
    name: ExtractorProviderName | str | None = None,
) -> ExtractorProvider:
    provider_name = name or resolve_extractor_provider_name()
    if provider_name == "landingai":
        return LandingAIExtractorProvider()
    if provider_name == "deepseek":
        return DeepSeekSchemaExtractorProvider()
    if provider_name == "legacy":
        return LegacyExtractorProvider()
    raise ValueError(f"unknown extractor provider: {provider_name!r}")
```

Create `platform/yinhu_brain/services/ingest/extractors/providers/__init__.py`:

```python
from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput, ExtractorProvider
from yinhu_brain.services.ingest.extractors.providers.factory import (
    get_extractor_provider,
    resolve_extractor_provider_name,
)

__all__ = [
    "ExtractionInput",
    "ExtractorProvider",
    "get_extractor_provider",
    "resolve_extractor_provider_name",
]
```

- [ ] **Step 4: Run factory tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_extractor_provider_factory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ingest/extractors/providers platform/tests/test_extractor_provider_factory.py
git commit -m "feat: add extractor provider contracts"
```

## Task 5: LandingAI Extractor Provider

**Files:**
- Modify: `platform/yinhu_brain/services/ingest/extractors/providers/landingai.py`
- Test: `platform/tests/test_landingai_extractor_provider.py`

- [ ] **Step 1: Write failing LandingAI provider test**

Create `platform/tests/test_landingai_extractor_provider.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.extractors.providers.landingai import LandingAIExtractorProvider
from yinhu_brain.services.ingest.unified_schemas import PipelineSelection


@pytest.mark.asyncio
async def test_landingai_provider_returns_pipeline_results(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import landingai as module

    calls = []

    async def fake_extract_with_schema(*, schema_json, markdown):
        calls.append((schema_json, markdown))
        from yinhu_brain.services.landingai_ade_client import LandingAIExtractResult

        return LandingAIExtractResult(
            extraction={"customer": {"full_name": "测试客户有限公司"}},
            extraction_metadata={"source": "landingai"},
            metadata={},
        )

    monkeypatch.setattr(module, "extract_with_schema", fake_extract_with_schema)
    monkeypatch.setattr(module, "load_schema_json", lambda name: f'{{"schema": "{name}"}}')

    result = await LandingAIExtractorProvider().extract_selected(
        ExtractionInput(
            document_id=uuid4(),
            session=SimpleNamespace(),
            markdown="甲方：测试客户有限公司",
            selections=[PipelineSelection(name="identity", confidence=0.9)],
        )
    )

    assert len(result) == 1
    assert result[0].name == "identity"
    assert result[0].extraction["customer"]["full_name"] == "测试客户有限公司"
    assert result[0].extraction_metadata == {"source": "landingai"}
    assert calls == [('{"schema": "identity"}', "甲方：测试客户有限公司")]
```

- [ ] **Step 2: Run failing test**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_landingai_extractor_provider.py -q
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement LandingAI provider**

Replace `platform/yinhu_brain/services/ingest/extractors/providers/landingai.py`:

```python
from __future__ import annotations

import asyncio

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.landingai_schemas.registry import load_schema_json
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult, PipelineSelection
from yinhu_brain.services.landingai_ade_client import LandingAIUnavailable, extract_with_schema


class LandingAIExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        return list(
            await asyncio.gather(
                *[self._extract_one(selection, input.markdown) for selection in input.selections]
            )
        )

    async def _extract_one(
        self,
        selection: PipelineSelection,
        markdown: str,
    ) -> PipelineExtractResult:
        try:
            response = await extract_with_schema(
                schema_json=load_schema_json(selection.name),
                markdown=markdown,
            )
            return PipelineExtractResult(
                name=selection.name,
                extraction=response.extraction,
                extraction_metadata=response.extraction_metadata,
                warnings=[],
            )
        except LandingAIUnavailable as exc:
            return PipelineExtractResult(
                name=selection.name,
                extraction={},
                extraction_metadata={},
                warnings=[f"LandingAI extract failed for {selection.name}: {exc!s}"],
            )
```

- [ ] **Step 4: Run LandingAI tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_landingai_extractor_provider.py tests/test_landingai_extract_runner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ingest/extractors/providers/landingai.py platform/tests/test_landingai_extractor_provider.py
git commit -m "refactor: wrap LandingAI extraction as provider"
```

## Task 6: Legacy Extractor Provider

**Files:**
- Modify: `platform/yinhu_brain/services/ingest/extractors/providers/legacy.py`
- Test: `platform/tests/test_legacy_extractor_provider.py`

- [ ] **Step 1: Write failing legacy provider tests**

Create `platform/tests/test_legacy_extractor_provider.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.extractors.providers.legacy import LegacyExtractorProvider
from yinhu_brain.services.ingest.unified_schemas import PipelineSelection


@pytest.mark.asyncio
async def test_legacy_provider_maps_supported_schemas_to_pipeline_results(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import legacy as module

    async def fake_identity(**kwargs):
        from yinhu_brain.services.ingest.unified_schemas import IdentityDraft

        return IdentityDraft.model_validate(
            {"customer": {"full_name": "测试客户有限公司"}, "confidence_overall": 0.9}
        )

    async def fake_commercial(**kwargs):
        from yinhu_brain.services.ingest.unified_schemas import CommercialDraft

        return CommercialDraft.model_validate(
            {"order": {"amount_total": 120000, "amount_currency": "CNY"}, "confidence_overall": 0.8}
        )

    monkeypatch.setitem(module.EXTRACTOR_FUNCTIONS, "identity", fake_identity)
    monkeypatch.setitem(module.EXTRACTOR_FUNCTIONS, "commercial", fake_commercial)

    result = await LegacyExtractorProvider().extract_selected(
        ExtractionInput(
            document_id=uuid4(),
            session=SimpleNamespace(bind=None, commit=lambda: None),
            markdown="甲方：测试客户有限公司",
            selections=[
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="contract_order", confidence=0.8),
            ],
        )
    )

    assert [r.name for r in result] == ["identity", "contract_order"]
    assert result[0].extraction["customer"]["full_name"] == "测试客户有限公司"
    assert result[1].extraction["order"]["amount_total"] == 120000


@pytest.mark.asyncio
async def test_legacy_provider_surfaces_unsupported_schema_warning():
    result = await LegacyExtractorProvider().extract_selected(
        ExtractionInput(
            document_id=uuid4(),
            session=SimpleNamespace(bind=None, commit=lambda: None),
            markdown="发票号码 123",
            selections=[PipelineSelection(name="finance", confidence=0.9)],
        )
    )

    assert len(result) == 1
    assert result[0].name == "finance"
    assert result[0].extraction == {}
    assert "no legacy extractor available" in result[0].warnings[0]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_legacy_extractor_provider.py -q
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement legacy provider sequentially**

Replace `platform/yinhu_brain/services/ingest/extractors/providers/legacy.py`:

```python
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from yinhu_brain.services.ingest.extractors.commercial import extract_commercial
from yinhu_brain.services.ingest.extractors.identity import extract_identity
from yinhu_brain.services.ingest.extractors.ops import extract_ops
from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.unified_schemas import (
    CommercialDraft,
    ExtractorName,
    IdentityDraft,
    OpsDraft,
    PipelineExtractResult,
)

logger = logging.getLogger(__name__)


SCHEMA_TO_LEGACY: dict[str, ExtractorName] = {
    "identity": "identity",
    "contract_order": "commercial",
    "commitment_task_risk": "ops",
}

EXTRACTOR_FUNCTIONS: dict[
    ExtractorName,
    Callable[..., Awaitable[IdentityDraft | CommercialDraft | OpsDraft]],
] = {
    "identity": extract_identity,
    "commercial": extract_commercial,
    "ops": extract_ops,
}


class LegacyExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        results: list[PipelineExtractResult] = []
        seen_extractors: set[ExtractorName] = set()
        for selection in input.selections:
            legacy_name = SCHEMA_TO_LEGACY.get(selection.name)
            if legacy_name is None:
                results.append(
                    PipelineExtractResult(
                        name=selection.name,
                        extraction={},
                        extraction_metadata={},
                        warnings=[
                            f"schema {selection.name!r} selected by router but no legacy extractor available"
                        ],
                    )
                )
                continue
            if legacy_name in seen_extractors:
                continue
            seen_extractors.add(legacy_name)
            try:
                draft = await EXTRACTOR_FUNCTIONS[legacy_name](
                    session=input.session,
                    document_id=input.document_id,
                    ocr_text=input.markdown,
                    progress=progress,
                )
                results.append(self._draft_to_pipeline_result(selection.name, draft))
            except Exception as exc:
                logger.warning("legacy extractor %s failed: %s", legacy_name, exc)
                results.append(
                    PipelineExtractResult(
                        name=selection.name,
                        extraction={},
                        extraction_metadata={"legacy_extractor": legacy_name},
                        warnings=[f"extractor {legacy_name!r} failed: {exc!s}"],
                    )
                )
        return results

    def _draft_to_pipeline_result(
        self,
        schema_name: str,
        draft: IdentityDraft | CommercialDraft | OpsDraft,
    ) -> PipelineExtractResult:
        return PipelineExtractResult(
            name=schema_name,
            extraction=draft.model_dump(mode="json", exclude_none=True),
            extraction_metadata={"legacy_extractor": schema_name},
            warnings=list(getattr(draft, "parse_warnings", []) or []),
        )
```

This implementation deliberately runs legacy extractors sequentially in V1.
That keeps the provider simple and avoids the old per-extractor session
fan-out complexity while preserving behavior and audit logging.

- [ ] **Step 4: Run tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_legacy_extractor_provider.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ingest/extractors/providers/legacy.py platform/tests/test_legacy_extractor_provider.py
git commit -m "refactor: wrap legacy extractors as provider"
```

## Task 7: DeepSeek Schema Extractor Provider

**Files:**
- Create: `platform/prompts/schema_extraction.md`
- Modify: `platform/yinhu_brain/services/ingest/extractors/providers/deepseek_schema.py`
- Test: `platform/tests/test_deepseek_schema_extractor_provider.py`

- [ ] **Step 1: Write DeepSeek provider tests**

Create `platform/tests/test_deepseek_schema_extractor_provider.py`:

```python
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.extractors.providers.deepseek_schema import (
    SCHEMA_EXTRACT_TOOL_NAME,
    DeepSeekSchemaExtractorProvider,
)
from yinhu_brain.services.ingest.unified_schemas import PipelineSelection


def _fake_response(tool_input: dict):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", name=SCHEMA_EXTRACT_TOOL_NAME, input=tool_input)
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        model_dump=lambda: {"content": [{"type": "tool_use", "input": tool_input}]},
    )


@pytest.mark.asyncio
async def test_deepseek_schema_provider_runs_one_call_per_selected_schema(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import deepseek_schema as module

    calls = []

    async def fake_call_claude(messages, *, purpose, session, model, tools, tool_choice, max_tokens, temperature, document_id):
        calls.append({"purpose": purpose, "messages": messages, "tools": tools, "document_id": document_id})
        return _fake_response({"customer": {"full_name": "测试客户有限公司"}})

    monkeypatch.setattr(module, "call_claude", fake_call_claude)
    monkeypatch.setattr(module, "load_schema_json", lambda name: '{"type":"object","properties":{"customer":{"type":"object"}}}')

    document_id = uuid4()
    results = await DeepSeekSchemaExtractorProvider().extract_selected(
        ExtractionInput(
            document_id=document_id,
            session=SimpleNamespace(),
            markdown="甲方：测试客户有限公司",
            selections=[PipelineSelection(name="identity", confidence=0.9)],
        )
    )

    assert len(results) == 1
    assert results[0].name == "identity"
    assert results[0].extraction["customer"]["full_name"] == "测试客户有限公司"
    assert results[0].extraction_metadata["provider"] == "deepseek"
    assert calls[0]["purpose"] == "schema_extract_identity"
    assert calls[0]["document_id"] == document_id


@pytest.mark.asyncio
async def test_deepseek_schema_provider_returns_warning_on_schema_failure(monkeypatch):
    from yinhu_brain.services.ingest.extractors.providers import deepseek_schema as module
    from yinhu_brain.services.llm import LLMCallFailed

    async def boom(*args, **kwargs):
        raise LLMCallFailed("upstream down")

    monkeypatch.setattr(module, "call_claude", boom)
    monkeypatch.setattr(module, "load_schema_json", lambda name: '{"type":"object","properties":{}}')

    results = await DeepSeekSchemaExtractorProvider().extract_selected(
        ExtractionInput(
            document_id=uuid4(),
            session=SimpleNamespace(),
            markdown="发票号码 123",
            selections=[PipelineSelection(name="finance", confidence=0.9)],
        )
    )

    assert len(results) == 1
    assert results[0].name == "finance"
    assert results[0].extraction == {}
    assert "DeepSeek extract failed" in results[0].warnings[0]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_deepseek_schema_extractor_provider.py -q
```

Expected: FAIL with `ImportError` or `NotImplementedError`.

- [ ] **Step 3: Add schema extraction prompt**

Create `platform/prompts/schema_extraction.md`:

```markdown
你是业务文档结构化抽取助手。给定 OCR Markdown 和一个业务 JSON schema，请只抽取该 schema 描述的字段。

## 规则

- 只从 OCR 文本中抽取，不要编造。
- 缺失或不确定的字段省略或返回 null。
- 数字金额去掉货币符号和千分位。
- 日期尽量输出 YYYY-MM-DD；无法确定则保留原文或返回 null。
- 人和公司字段只抽取客户、买方、甲方一侧；不要把供方、乙方、卖方写成客户。
- 输出必须是 JSON 对象，不要 Markdown，不要解释文字。

## Schema 名称

{schema_name}

## JSON Schema

```json
{schema_json}
```

## OCR Markdown

```text
{ocr_text}
```
```

- [ ] **Step 4: Implement DeepSeek schema provider**

Replace `platform/yinhu_brain/services/ingest/extractors/providers/deepseek_schema.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.landingai_schemas.registry import load_schema_json
from yinhu_brain.services.ingest.progress import ProgressCallback
from yinhu_brain.services.ingest.schemas import _strip_titles
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult, PipelineSelection
from yinhu_brain.services.llm import LLMCallFailed, call_claude, extract_tool_use_input


SCHEMA_EXTRACT_TOOL_NAME = "submit_schema_extraction"
_PROMPT_PATH = Path(__file__).resolve().parents[5] / "prompts" / "schema_extraction.md"
_LLM_CONTEXT_CHARS = 30000


class DeepSeekSchemaExtractorProvider:
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        results: list[PipelineExtractResult] = []
        for selection in input.selections:
            results.append(await self._extract_one(input=input, selection=selection))
        return results

    async def _extract_one(
        self,
        *,
        input: ExtractionInput,
        selection: PipelineSelection,
    ) -> PipelineExtractResult:
        schema_json = load_schema_json(selection.name)
        prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prompt.replace("{schema_name}", selection.name)
        prompt = prompt.replace("{schema_json}", schema_json)
        prompt = prompt.replace("{ocr_text}", (input.markdown or "")[:_LLM_CONTEXT_CHARS])
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

        try:
            response = await call_claude(
                messages=messages,
                purpose=f"schema_extract_{selection.name}",
                session=input.session,
                model=settings.model_parse,
                tools=[self._schema_tool(schema_json)],
                tool_choice={"type": "tool", "name": SCHEMA_EXTRACT_TOOL_NAME},
                max_tokens=4096,
                temperature=0,
                document_id=input.document_id,
            )
            extraction = extract_tool_use_input(response, SCHEMA_EXTRACT_TOOL_NAME)
            if not isinstance(extraction, dict):
                raise LLMCallFailed("schema extraction output was not a JSON object")
            return PipelineExtractResult(
                name=selection.name,
                extraction=extraction,
                extraction_metadata={"provider": "deepseek", "model": settings.model_parse},
                warnings=[],
            )
        except Exception as exc:
            return PipelineExtractResult(
                name=selection.name,
                extraction={},
                extraction_metadata={"provider": "deepseek", "model": settings.model_parse},
                warnings=[f"DeepSeek extract failed for {selection.name}: {exc!s}"],
            )

    def _schema_tool(self, schema_json: str) -> dict[str, Any]:
        import json

        schema = json.loads(schema_json)
        return {
            "name": SCHEMA_EXTRACT_TOOL_NAME,
            "description": "Submit one business-schema extraction as a JSON object.",
            "input_schema": _strip_titles(schema),
        }
```

- [ ] **Step 5: Run DeepSeek provider tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_deepseek_schema_extractor_provider.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add platform/prompts/schema_extraction.md platform/yinhu_brain/services/ingest/extractors/providers/deepseek_schema.py platform/tests/test_deepseek_schema_extractor_provider.py
git commit -m "feat: add DeepSeek schema extractor provider"
```

## Task 8: Rewire Auto Ingest To Extractor Providers

**Files:**
- Modify: `platform/yinhu_brain/services/ingest/auto.py`
- Modify: `platform/tests/test_ingest_auto_flow.py`

- [ ] **Step 1: Write failing orchestrator provider test**

Add to `platform/tests/test_ingest_auto_flow.py`:

```python
@pytest.mark.asyncio
async def test_auto_ingest_uses_configured_extractor_provider(monkeypatch) -> None:
    engine = await _make_engine()
    _patch_storage(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "extractor_provider", "deepseek")

    async def fake_collect_evidence(**kwargs):
        from yinhu_brain.models import (
            Document,
            DocumentProcessingStatus,
            DocumentReviewStatus,
            DocumentType,
        )
        from yinhu_brain.services.ingest.evidence import Evidence

        doc = Document(
            type=DocumentType.contract,
            file_url="/tmp/fake.pdf",
            original_filename="contract.pdf",
            content_type="application/pdf",
            file_sha256="1" * 64,
            file_size_bytes=10,
            ocr_text="甲方：测试客户有限公司\n合同编号：HT-001",
            processing_status=DocumentProcessingStatus.parsed,
            review_status=DocumentReviewStatus.pending_review,
        )
        kwargs["session"].add(doc)
        await kwargs["session"].flush()
        return Evidence(document_id=doc.id, document=doc, ocr_text=doc.ocr_text, modality="pdf")

    async def fake_route_schemas(**kwargs):
        return PipelineRoutePlan(
            primary_pipeline="identity",
            selected_pipelines=[PipelineSelection(name="identity", confidence=0.9)],
            document_summary="identity",
        )

    class FakeExtractorProvider:
        async def extract_selected(self, input, progress=None):
            assert input.markdown == "甲方：测试客户有限公司\n合同编号：HT-001"
            return [
                PipelineExtractResult(
                    name="identity",
                    extraction={"customer": {"full_name": "测试客户有限公司"}},
                )
            ]

    monkeypatch.setattr(auto_module, "collect_evidence", fake_collect_evidence)
    monkeypatch.setattr(auto_module, "route_schemas", fake_route_schemas)
    monkeypatch.setattr(auto_module, "get_extractor_provider", lambda: FakeExtractorProvider())

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF",
                original_filename="contract.pdf",
                content_type="application/pdf",
                source_hint="file",
            )
            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            assert len(result.draft.pipeline_results) == 1
    finally:
        await engine.dispose()
```

Also import `PipelineExtractResult` in the existing unified schema import block.

- [ ] **Step 2: Run failing orchestrator test**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_auto_flow.py::test_auto_ingest_uses_configured_extractor_provider -q
```

Expected: FAIL because `auto_module.get_extractor_provider` is not imported or not used.

- [ ] **Step 3: Simplify `auto.py` extraction path**

In `platform/yinhu_brain/services/ingest/auto.py`:

Remove imports for direct extractor functions, `extract_selected_pipelines`, and old mapping constants when no longer used.

Add imports:

```python
from yinhu_brain.services.ingest.extractors.providers import (
    ExtractionInput,
    get_extractor_provider,
)
```

Replace provider-specific extraction branches after `route_plan` with:

```python
    extractor = get_extractor_provider()
    await emit_progress(progress, "extract", "正在执行 schema 提取")
    pipeline_results = await extractor.extract_selected(
        ExtractionInput(
            document_id=evidence.document_id,
            session=session,
            markdown=evidence.ocr_text,
            selections=route_plan.selected_pipelines,
        ),
        progress=progress,
    )

    await emit_progress(progress, "merge", "正在合并 schema 提取结果")
    draft = normalize_pipeline_results(pipeline_results)
    if route_plan.needs_human_review:
        draft.warnings = list(draft.warnings) + ["router requested human review"]
    if evidence.warnings:
        draft.warnings = list(evidence.warnings) + list(draft.warnings)
    draft.summary = draft.summary or route_plan.document_summary

    evidence.document.raw_llm_response = {
        "provider": settings.extractor_provider or settings.document_ai_provider,
        "route_plan": route_plan.model_dump(mode="json"),
        "draft": draft.model_dump(mode="json"),
    }
    await session.flush()
    await emit_progress(progress, "auto_done", "统一抽取完成，等待用户确认")

    synthesized_plan = IngestPlan(
        targets={
            "identity": next((s.confidence for s in route_plan.selected_pipelines if s.name == "identity"), 0.0),
            "commercial": next((s.confidence for s in route_plan.selected_pipelines if s.name == "contract_order"), 0.0),
            "ops": next((s.confidence for s in route_plan.selected_pipelines if s.name == "commitment_task_risk"), 0.0),
        },
        extractors=[],
        reason=route_plan.document_summary,
        review_required=route_plan.needs_human_review,
    )
    candidates = await build_merge_candidates(
        session=session,
        customer=draft.customer,
        contacts=draft.contacts,
    )
    return AutoIngestResult(
        document_id=evidence.document_id,
        plan=synthesized_plan,
        draft=draft,
        candidates=candidates,
        route_plan=route_plan,
    )
```

Remove `_run_extractor_with_own_session`, `_EXTRACTOR_FUNCTIONS`, `_SCHEMA_TO_LEGACY`, `_UNSUPPORTED_SCHEMAS_FOR_MISTRAL`, and the old branch below.

- [ ] **Step 4: Run auto flow tests**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_auto_flow.py -q
```

Expected: Some existing tests may fail because they patch old `extract_selected_pipelines`; update those tests to patch `get_extractor_provider` with a fake provider returning the same `PipelineExtractResult[]`.

- [ ] **Step 5: Update existing LandingAI auto test patches**

In `test_auto_ingest_uses_landingai_schema_flow_when_enabled`, replace:

```python
monkeypatch.setattr(auto_module, "extract_selected_pipelines", fake_extract_selected_pipelines)
```

with:

```python
class FakeExtractorProvider:
    async def extract_selected(self, input, progress=None):
        return await fake_extract_selected_pipelines(
            selections=input.selections,
            markdown=input.markdown,
        )


monkeypatch.setattr(auto_module, "get_extractor_provider", lambda: FakeExtractorProvider())
```

- [ ] **Step 6: Run auto flow tests again**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_auto_flow.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add platform/yinhu_brain/services/ingest/auto.py platform/tests/test_ingest_auto_flow.py
git commit -m "refactor: route auto ingest through extractor providers"
```

## Task 9: End-To-End Provider Combination Tests

**Files:**
- Modify: `platform/tests/test_ingest_auto_flow.py`

- [ ] **Step 1: Add MinerU plus DeepSeek composition test**

Add to `platform/tests/test_ingest_auto_flow.py`:

```python
@pytest.mark.asyncio
async def test_auto_ingest_mineru_deepseek_provider_combination(monkeypatch) -> None:
    engine = await _make_engine()
    _patch_storage(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "ocr_provider", "mineru")
    monkeypatch.setattr(auto_module.settings, "extractor_provider", "deepseek")

    from yinhu_brain.services.ocr.base import OcrResult

    class FakeOcrProvider:
        async def parse(self, input):
            assert input.modality == "pdf"
            return OcrResult(markdown="甲方：测试客户有限公司\n合同编号：HT-001", provider="mineru")

    class FakeExtractorProvider:
        async def extract_selected(self, input, progress=None):
            assert input.markdown == "甲方：测试客户有限公司\n合同编号：HT-001"
            return [
                PipelineExtractResult(
                    name="identity",
                    extraction={"customer": {"full_name": "测试客户有限公司"}},
                )
            ]

    monkeypatch.setattr(evidence_module, "get_ocr_provider", lambda: FakeOcrProvider())
    monkeypatch.setattr(auto_module, "get_extractor_provider", lambda: FakeExtractorProvider())
    _patch_route_schemas(
        monkeypatch,
        [
            PipelineSelection(name="identity", confidence=0.9),
        ],
    )

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF",
                original_filename="contract.pdf",
                content_type="application/pdf",
                source_hint="file",
            )

            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            assert result.route_plan is not None
            assert result.draft.pipeline_results[0].name == "identity"
    finally:
        await engine.dispose()
```

Ensure `evidence_module` and `PipelineExtractResult` are imported in this test file.

- [ ] **Step 2: Run the new composition test**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_auto_flow.py::test_auto_ingest_mineru_deepseek_provider_combination -q
```

Expected: PASS.

- [ ] **Step 3: Run focused provider suite**

Run:

```bash
cd platform && ./.venv/bin/pytest \
  tests/test_ocr_provider_factory.py \
  tests/test_mistral_ocr_provider.py \
  tests/test_mineru_ocr_provider.py \
  tests/test_extractor_provider_factory.py \
  tests/test_landingai_extractor_provider.py \
  tests/test_legacy_extractor_provider.py \
  tests/test_deepseek_schema_extractor_provider.py \
  tests/test_evidence.py \
  tests/test_ingest_auto_flow.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add platform/tests/test_ingest_auto_flow.py
git commit -m "test: cover modular ingest provider composition"
```

## Task 10: Final Verification And Docs Check

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run full backend tests**

Run:

```bash
cd platform && ./.venv/bin/pytest -q
```

Expected: PASS. If project-level integration tests require services unavailable locally, record the failing tests and rerun the focused provider suite from Task 9.

- [ ] **Step 2: Inspect diff for accidental UI/DB changes**

Run:

```bash
git diff --stat HEAD
git diff -- platform/app-win platform/migrations
```

Expected: no app-win or migration diffs from this plan.

- [ ] **Step 3: Commit any final test-only adjustment**

If Step 1 required a test-only fix, commit it:

```bash
git add platform/tests
git commit -m "test: stabilize modular provider coverage"
```

If no changes remain, skip this commit.

## Self-Review

Spec coverage:

- OCR provider boundary: Tasks 1-3.
- Mistral adapter preserving existing behavior: Task 2.
- MinerU precise API signed upload, polling, zip `full.md`: Task 3.
- Extractor provider boundary: Task 4.
- LandingAI adapter: Task 5.
- Legacy rollback provider: Task 6.
- DeepSeek schema-routed extractor: Task 7.
- Orchestrator rewiring and response compatibility: Task 8.
- MinerU + DeepSeek composition: Task 9.
- Verification: Task 10.

Red-flag scan: no task relies on unspecified behavior; every new module has concrete code or test snippets.

Type consistency:

- `OcrInput`, `OcrResult`, `OcrUnavailable`, `OcrProvider` names match across tasks.
- `ExtractionInput` includes `document_id`, `session`, `markdown`, and `selections`.
- Provider factories expose `get_ocr_provider`, `get_extractor_provider`, and `resolve_extractor_provider_name`.
