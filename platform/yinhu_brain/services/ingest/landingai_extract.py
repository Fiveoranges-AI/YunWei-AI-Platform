"""Run each LandingAI schema pipeline that the router selected.

This module turns a `list[PipelineSelection]` from
`pipeline_router.route_document` into a `list[PipelineExtractResult]` —
one entry per selected pipeline, each holding the raw LandingAI
`extraction` payload plus its metadata.

Pipelines run in parallel via `asyncio.gather`. If a pipeline fails (e.g.
LandingAI returns an error or VISION_AGENT_API_KEY is unset) it still
produces a `PipelineExtractResult` — with an empty extraction and a
warning string — so the orchestrator can surface partial results rather
than aborting the whole ingest.
"""

from __future__ import annotations

import asyncio

from yinhu_brain.services.ingest.landingai_schemas.registry import load_schema_json
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult, PipelineSelection
from yinhu_brain.services.landingai_ade_client import LandingAIUnavailable, extract_with_schema


async def _extract_one(selection: PipelineSelection, markdown: str) -> PipelineExtractResult:
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


async def extract_selected_pipelines(
    *,
    selections: list[PipelineSelection],
    markdown: str,
) -> list[PipelineExtractResult]:
    """Run every selected pipeline in parallel and return their results
    in the same order as `selections`."""

    return list(
        await asyncio.gather(
            *[_extract_one(selection, markdown) for selection in selections]
        )
    )
