# Modular OCR And Extractor Provider Design

## Goal

Refactor the win ingest pipeline so OCR and schema extraction are independent
provider adapters. Business schemas, review payloads, and DB writeback remain
stable while operators can choose:

```text
OCR_PROVIDER=mistral|mineru
EXTRACTOR_PROVIDER=landingai|deepseek|legacy
```

The first implementation should preserve the current `/win/api/ingest/auto`
response shape and Review UI behavior.

## Current Context

`/api/ingest/auto` currently does all external document parsing through
`collect_evidence`, then routes the resulting text with `route_schemas`.
When `DOCUMENT_AI_PROVIDER=landingai`, only the extraction step changes:
LandingAI receives `evidence.ocr_text` plus a selected schema and returns raw
pipeline results. When the provider is not LandingAI, selected schemas are
mapped to the legacy DeepSeek/Claude extractors.

This coupling makes two things harder than they need to be:

- Replacing Mistral OCR with another parser such as MinerU.
- Replacing LandingAI Extract with DeepSeek JSON/schema extraction while
  preserving the same six business schemas.

`legacy` is a migration-only extractor provider that wraps the existing
identity/commercial/ops DeepSeek/Claude extractors. The target extractor
providers are `landingai` and schema-routed `deepseek`.

## Design Principles

- Business schemas are product contracts, not model contracts.
- OCR providers produce markdown/text and metadata. They do not decide which
  business schema applies.
- Extractor providers receive selected business schemas and markdown/text.
  They do not write DB rows directly.
- Provider adapters normalize external API quirks into internal dataclasses.
- The orchestrator should read like a pipeline, not like a provider-specific
  decision tree.
- V1 keeps synchronous request/stream behavior. Long-running background job
  support can reuse the same adapters later.

## Target Pipeline

```text
upload/text
  -> collect_evidence
       -> OCRProvider.parse(...) for non-text input
       -> Document.ocr_text
  -> route_schemas(markdown=ocr_text)
  -> ExtractorProvider.extract_selected(...)
       -> PipelineExtractResult[]
  -> normalize_pipeline_results(...)
  -> UnifiedDraft + MergeCandidates
  -> confirm/writeback
```

`route_schemas`, `normalize_pipeline_results`, Review UI, and confirm/writeback
stay as the stable business layer.

## OCR Provider Boundary

Create a focused OCR adapter module under:

```text
platform/yinhu_brain/services/ocr/
```

Core contracts:

```python
@dataclass
class OcrInput:
    file_bytes: bytes
    stored_path: str
    filename: str
    content_type: str | None
    modality: Literal["image", "pdf", "office"]
    source_hint: Literal["file", "camera"]


@dataclass
class OcrResult:
    markdown: str
    provider: str
    metadata: dict[str, Any]
    warnings: list[str]


class OcrProvider(Protocol):
    async def parse(self, input: OcrInput) -> OcrResult:
        ...
```

Text input bypasses OCR and becomes `OcrResult(markdown=text.strip(),
provider="text")` inside `collect_evidence`.

### Mistral OCR Provider

`MistralOcrProvider` preserves current behavior:

- image -> `parse_image_to_markdown`
- pdf -> native text via `pdf_utils` first, Mistral OCR fallback for scanned
  PDFs
- office/unknown file -> `parse_document_to_markdown`

It should move existing Mistral-specific branches out of `evidence.py`, not
change behavior.

### MinerU Precise OCR Provider

`MineruPreciseOcrProvider` uses MinerU 精准解析 API.

For local uploaded files, use the signed-upload batch flow:

1. `POST /api/v4/file-urls/batch` with one file.
2. `PUT` file bytes to returned `file_urls[0]`.
3. Poll `GET /api/v4/extract-results/batch/{batch_id}`.
4. When the first `extract_result.state == "done"`, download
   `full_zip_url`.
5. Extract `full.md` from the zip and return it as `OcrResult.markdown`.

Supported first-version settings:

```python
ocr_provider: Literal["mistral", "mineru"] = "mistral"
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

Failure behavior:

- Missing token raises `OcrUnavailable`.
- MinerU `code != 0` raises `OcrUnavailable` with `msg` and `trace_id`.
- `state == "failed"` raises `OcrUnavailable` with `err_msg`.
- Timeout raises `OcrUnavailable`.
- Zip without `full.md` raises `OcrUnavailable`.

No callback support in V1. Callback support belongs in the async ingest job
path after the provider boundary is stable.

## Extractor Provider Boundary

Create provider adapters under:

```text
platform/yinhu_brain/services/ingest/extractors/providers/
```

Core contract:

```python
@dataclass
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
        ...
```

Every extractor provider returns the same internal type:

```python
PipelineExtractResult(
    name=<schema name>,
    extraction=<schema-shaped dict>,
    extraction_metadata=<provider metadata>,
    warnings=<provider/schema warnings>,
)
```

`session` is explicit because DeepSeek and the legacy extractors call
`call_claude`, which persists `llm_calls` audit rows. LandingAI currently does
not need DB access, but accepting the same input keeps the orchestrator simple
without hiding DB writes in globals.

### LandingAI Extractor Provider

`LandingAIExtractorProvider` wraps the current `extract_selected_pipelines`
behavior. It loads the existing static schema JSON and calls LandingAI Extract
with `markdown=evidence.ocr_text`.

### DeepSeek Schema Extractor Provider

`DeepSeekSchemaExtractorProvider` is a schema-routed extractor, not the legacy
identity/commercial/ops extractor set.

For each selected pipeline:

1. Load the same schema JSON used by LandingAI.
2. Build a prompt that includes:
   - schema name
   - schema JSON
   - extraction rules shared across providers
   - OCR markdown
3. Call the configured DeepSeek parse model.
4. Parse JSON.
5. Validate the result as a dict.
6. Return one `PipelineExtractResult` per selected schema.

V1 can use the existing Anthropic-compatible `call_claude` JSON fallback, so
we do not need to add a second LLM client before the refactor lands. A later
increment can add native DeepSeek OpenAI-compatible `response_format:
{"type":"json_object"}` behind the same provider class.

DeepSeek extraction failures should be soft per schema: return an empty
`extraction` and a warning for that schema, matching LandingAI's current
partial-result behavior.

## Orchestrator Changes

Replace `settings.document_ai_provider` branching with two explicit provider
choices:

```python
ocr = get_ocr_provider(settings.ocr_provider)
extractor = get_extractor_provider(settings.extractor_provider)
```

`collect_evidence` owns:

- input validation
- modality detection
- storing original upload
- text bypass
- calling the configured OCR provider for non-text input
- creating the `Document` row

`auto_ingest` owns:

- route schemas
- call configured extractor provider
- normalize pipeline results
- build merge candidates
- persist `raw_llm_response`

The legacy extractor mapping remains available only as a rollback provider
if needed. It should not be the default abstraction for DeepSeek schema
extraction because it only covers three of six schemas.

## API And UI Compatibility

The backend response stays compatible:

```json
{
  "document_id": "...",
  "plan": "...",
  "route_plan": "...",
  "draft": "...",
  "pipeline_results": "...",
  "candidates": "...",
  "needs_review_fields": "..."
}
```

The winapp Review page should not need structural changes. It already prefers
`route_plan` for schema labels and reads `pipeline_results` for per-schema
summary details.

## Tests

Add focused tests before implementation:

- OCR provider factory selects Mistral or MinerU from settings.
- Mistral provider preserves image/pdf/office behavior using monkeypatched
  client functions.
- MinerU provider:
  - applies for signed upload URL
  - uploads bytes with PUT
  - polls until `done`
  - downloads a zip and extracts `full.md`
  - raises `OcrUnavailable` on failed state, non-zero code, timeout, and
    missing `full.md`
- Extractor provider factory selects LandingAI, DeepSeek, or legacy.
- LandingAI provider preserves existing `PipelineExtractResult` shape.
- DeepSeek schema extractor:
  - runs one call per selected schema
  - validates JSON dict output
  - returns empty result plus warning on per-schema failure
- `auto_ingest` with `OCR_PROVIDER=mineru` and
  `EXTRACTOR_PROVIDER=deepseek` returns `route_plan`, `pipeline_results`, and
  a normalized `UnifiedDraft`.

No live MinerU, Mistral, LandingAI, or DeepSeek network calls in unit tests.
All provider HTTP/model calls are monkeypatched.

## Rollout

1. Add provider contracts and settings.
2. Move current Mistral OCR behavior behind `MistralOcrProvider`.
3. Move current LandingAI Extract behavior behind `LandingAIExtractorProvider`.
4. Rewire `collect_evidence` and `auto_ingest` with provider factories.
5. Add `MineruPreciseOcrProvider`.
6. Add `DeepSeekSchemaExtractorProvider`.
7. Keep defaults equivalent to current production behavior:

```text
OCR_PROVIDER=mistral
EXTRACTOR_PROVIDER=landingai when old DOCUMENT_AI_PROVIDER=landingai
EXTRACTOR_PROVIDER=legacy when old DOCUMENT_AI_PROVIDER=mistral
```

After the refactor is stable, remove or deprecate `DOCUMENT_AI_PROVIDER` in a
separate cleanup.

## Open Decisions Resolved

- MinerU uses 精准解析 API, not the Agent lightweight API.
- First MinerU implementation uses signed upload and polling, not callback.
- Schema definitions stay aligned to business/database concepts and are
  shared across LandingAI and DeepSeek.
- The first implementation does not alter DB tables, confirm writeback, or
  winapp Review UI structure.
