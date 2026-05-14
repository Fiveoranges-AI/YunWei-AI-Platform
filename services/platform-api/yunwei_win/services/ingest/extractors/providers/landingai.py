"""LandingAI extractor provider.

Each ``PipelineSelection`` is converted into a tenant-catalog JSON Schema so
LandingAI emits canonical company table/field names. The provider has no
static schema fallback; the tenant company schema is the contract.

Per-schema failures are soft. Any exception raised by either the schema
loader or the LandingAI call is caught, logged, and surfaced as a result
with an empty extraction and a warning of the form
``"LandingAI extract failed for {name}: {error}"`` — so one bad schema
never aborts the batch.

"""

from __future__ import annotations

import asyncio
import logging

from yunwei_win.services.ingest.extractors.canonical_schema import (
    build_pipeline_schema_json,
)
from yunwei_win.services.ingest.pipeline_schemas import (
    PipelineExtractResult,
    PipelineSelection,
)
from yunwei_win.services.landingai_ade_client import extract_with_schema

from .base import ExtractionInput, ExtractorProvider, ProgressCallback

logger = logging.getLogger(__name__)


class LandingAIExtractorProvider(ExtractorProvider):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        return list(
            await asyncio.gather(
                *[
                    _extract_one(
                        selection,
                        input.markdown,
                        input.company_schema,
                        progress,
                    )
                    for selection in input.selections
                ]
            )
        )


async def _extract_one(
    selection: PipelineSelection,
    markdown: str,
    company_schema: dict,
    progress: ProgressCallback | None,
) -> PipelineExtractResult:
    if progress is not None:
        await progress("pipeline_started", {"name": selection.name})

    try:
        schema = build_pipeline_schema_json(selection.name, company_schema)
        response = await extract_with_schema(
            schema_json=schema,
            markdown=markdown,
        )
        result = PipelineExtractResult(
            name=selection.name,
            extraction=response.extraction,
            extraction_metadata=response.extraction_metadata,
            warnings=[],
        )
        ok = True
    except Exception as exc:  # noqa: BLE001 — soft per-schema failure
        logger.warning(
            "LandingAI extract failed for %s: %s", selection.name, exc
        )
        result = PipelineExtractResult(
            name=selection.name,
            extraction={},
            extraction_metadata={},
            warnings=[f"LandingAI extract failed for {selection.name}: {exc!s}"],
        )
        ok = False

    if progress is not None:
        await progress("pipeline_done", {"name": selection.name, "ok": ok})

    return result
