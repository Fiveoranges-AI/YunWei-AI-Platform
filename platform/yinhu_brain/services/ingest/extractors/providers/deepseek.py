"""DeepSeek schema extractor provider placeholder.

The real implementation will, for each selected pipeline, load the same
schema JSON used by LandingAI, build a schema + rules + markdown prompt, call
the configured DeepSeek parse model, validate the JSON dict response, and
return one `PipelineExtractResult` per schema. Until then `extract_selected`
raises NotImplementedError so the factory can still wire up the provider and
tests can exercise selection.
"""

from __future__ import annotations

from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult

from .base import ExtractionInput, ExtractorProvider, ProgressCallback


class DeepSeekSchemaExtractorProvider(ExtractorProvider):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        raise NotImplementedError(
            "DeepSeekSchemaExtractorProvider.extract_selected is not implemented yet"
        )
