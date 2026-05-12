"""LandingAI extractor provider placeholder.

The real implementation will wrap the existing `extract_selected_pipelines`
behavior — loading the static schema JSON and calling LandingAI Extract with
`markdown=evidence.ocr_text`. Until then `extract_selected` raises
NotImplementedError so the factory can still wire up the provider and tests
can exercise selection.
"""

from __future__ import annotations

from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult

from .base import ExtractionInput, ExtractorProvider, ProgressCallback


class LandingAIExtractorProvider(ExtractorProvider):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        raise NotImplementedError(
            "LandingAIExtractorProvider.extract_selected is not implemented yet"
        )
