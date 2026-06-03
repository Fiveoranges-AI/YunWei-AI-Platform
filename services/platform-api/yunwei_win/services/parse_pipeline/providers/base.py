"""ExtractionProvider protocol — swappable LLM/OCR backend.

The contract / screenshot adapters delegate the actual model call to an
ExtractionProvider so the pipeline is decoupled from any one upstream
(Anthropic / DeepSeek / a future local VLM). Tests use MockProvider to
avoid burning tokens; the wired-up runtime uses ClaudeProvider.

This is intentionally minimal — providers return raw entity dicts and
let the adapters apply ontology-aware shaping + confidence math. Same
Protocol shape as OcrProvider / FileParser elsewhere in the repo.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ExtractionPayload(BaseModel):
    """Inputs the adapter hands to the provider."""

    model_config = ConfigDict(extra="allow")

    source_type: str          # "contract" | "wechat_screenshot" | "excel"
    filename: str
    markdown: str = ""        # parser-emitted text, may be empty for vision-only
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    grounding: dict[str, Any] = Field(default_factory=dict)
    image_b64: str | None = None         # for vision providers
    image_media_type: str | None = None  # e.g. "image/png"


class ProviderField(BaseModel):
    """One field extracted by a provider — minimal, pre-confidence-math.

    ``source_excerpt`` is the verbatim text the model claimed it came
    from. ``source_ref_id`` is an opaque pointer back into the parse
    artifact (e.g. ``sheet:订单!R7C2`` for spreadsheets, ``chunk-12``
    for visual parsers). Either may be empty; the adapter penalises
    confidence when the model fails to supply provenance.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    value: Any | None = None
    confidence: float | None = None
    source_excerpt: str | None = None
    source_ref_id: str | None = None
    source_page: int | None = None
    source_bbox: list[float] | None = None


class ProviderEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_type: str  # must match one of the CandidateJSON EntityType values
    temp_id: str
    fields: list[ProviderField] = Field(default_factory=list)


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    entities: list[ProviderEntity] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider_name: str = ""


@runtime_checkable
class ExtractionProvider(Protocol):
    name: str

    async def extract(self, payload: ExtractionPayload) -> ProviderResult: ...
