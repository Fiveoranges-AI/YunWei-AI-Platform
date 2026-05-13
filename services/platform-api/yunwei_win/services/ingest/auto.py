"""Auto orchestrator — end-to-end glue for ``/api/ingest/auto``.

Single pipeline:

    file/text → Evidence (OCR) → LLM schema router → ExtractorProvider
                  (LandingAI Extract OR DeepSeek JSON tool-use) → Normalize
                  → Merge → UnifiedDraft

This module is the only place where all the steps are linked. Each step is
independently testable in its own module; the orchestrator's job is sequencing,
error tolerance, and progress emission.

Routing is unified: ``route_schemas`` (LLM-driven, multi-label) selects which
of the six canonical schemas the document touches —
``identity`` / ``contract_order`` / ``finance`` / ``logistics`` /
``manufacturing_requirement`` / ``commitment_task_risk``. The configured
``ExtractorProvider`` (LandingAI or DeepSeek) runs the selected schemas and
returns one ``PipelineExtractResult`` per schema. ``normalize_pipeline_results``
folds those onto a single ``UnifiedDraft``.

Provider selection is driven by ``settings.extractor_provider``;
``document_ai_provider`` is no longer consulted here.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.services.ingest.evidence import Evidence, PreStoredFile, collect_evidence
from yunwei_win.services.ingest.extractors.providers.base import (
    ExtractionInput,
    ProgressCallback as ExtractorProgressCallback,
)
from yunwei_win.services.ingest.extractors.providers.factory import get_extractor_provider
from yunwei_win.services.ingest.landingai_normalize import normalize_pipeline_results
from yunwei_win.services.ingest.llm_schema_router import route_schemas
from yunwei_win.services.ingest.merge import (
    MergeCandidates,
    build_merge_candidates,
)
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.ingest.unified_schemas import (
    IngestPlan,
    PipelineRoutePlan,
    UnifiedDraft,
)

logger = logging.getLogger(__name__)


@dataclass
class AutoIngestResult:
    """Bundle returned by ``auto_ingest``.

    ``document_id`` lets the caller hand it back via ``/auto/{id}/confirm``;
    ``plan`` is preserved for telemetry and UI hints; ``draft`` is the merged
    payload the review form binds to; ``candidates`` carries the customer +
    per-contact match candidates so the UI can offer "merge into existing".
    """

    document_id: uuid.UUID
    plan: IngestPlan
    draft: UnifiedDraft
    candidates: MergeCandidates
    route_plan: PipelineRoutePlan | None = None


# ---------- progress adapter ---------------------------------------------


def _build_provider_progress_adapter(
    progress: ProgressCallback | None,
) -> ExtractorProgressCallback | None:
    """Bridge the provider-level event vocabulary onto the SSE ``(stage, msg)``
    shape the winapp consumes.

    Providers emit ``Callable[[str, Any], Awaitable[None]]`` where the payload
    is either a ``dict`` (LandingAI: ``{"name": ..., "ok": ...}``) or a ``str``
    (DeepSeek). The orchestrator's existing ``ProgressCallback`` is
    ``Callable[[str, str], Awaitable[None]]``. We flatten the dict cases into a
    short Chinese message and pass strings through unchanged so the NDJSON
    payload schema does not change.
    """

    if progress is None:
        return None

    async def adapter(event: str, payload: Any) -> None:
        if event == "pipeline_started" and isinstance(payload, dict):
            await progress("extract", f"开始抽取 {payload.get('name', '?')}")
        elif event == "pipeline_done" and isinstance(payload, dict):
            ok = payload.get("ok", True)
            name = payload.get("name", "?")
            status = "完成" if ok else "失败"
            await progress("extract", f"{name} 抽取{status}")
        elif event in {"schema_extract", "schema_extract_done"} and isinstance(payload, str):
            await progress("extract", payload)
        else:
            # Fallback — coerce payload to string so unknown events still surface.
            await progress(event, str(payload))

    return adapter


# ---------- main entrypoint ----------------------------------------------


async def auto_ingest(
    *,
    session: AsyncSession,
    file_bytes: bytes | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    text_content: str | None = None,
    source_hint: Literal["file", "camera", "pasted_text"],
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
    pre_stored: PreStoredFile | None = None,
) -> AutoIngestResult:
    """End-to-end pipeline: bytes/text in → ``AutoIngestResult`` out.

    Step-by-step:

    1. ``collect_evidence`` — persist the original file/text, OCR if needed,
       insert the ``Document`` row, return ``ocr_text``.
    2. ``route_schemas`` — single LLM call returns a multi-label
       ``PipelineRoutePlan`` selecting which of the six canonical schemas the
       document touches.
    3. ``get_extractor_provider().extract_selected(...)`` — the configured
       provider (LandingAI or DeepSeek) runs each selected schema and returns
       a ``list[PipelineExtractResult]``.
    4. ``normalize_pipeline_results`` — fold the per-schema extracts onto a
       single ``UnifiedDraft`` shape.
    5. ``build_merge_candidates`` — look up customer + per-contact match
       candidates for the review form's "merge into existing" affordance.
    6. Persist the merged draft + route plan on ``Document.raw_llm_response``
       so the confirm step can recover it from the row alone.
    """
    await emit_progress(progress, "auto", "开始统一抽取流水线")

    # ----- 1. Evidence ------------------------------------------------
    evidence: Evidence = await collect_evidence(
        session=session,
        file_bytes=file_bytes,
        original_filename=original_filename,
        content_type=content_type,
        text_content=text_content,
        source_hint=source_hint,
        uploader=uploader,
        progress=progress,
        pre_stored=pre_stored,
    )

    # ----- 2. LLM schema router (unified across providers) -----------
    route_plan = await route_schemas(
        session=session,
        document_id=evidence.document_id,
        markdown=evidence.ocr_text,
        modality=evidence.modality,
        source_hint=source_hint,
        progress=progress,
    )

    # ----- 3. Run the configured extractor provider over the selected
    #         pipelines. Provider abstracts the LandingAI / DeepSeek split.
    extractor = get_extractor_provider()
    extraction_input = ExtractionInput(
        document_id=evidence.document_id,
        session=session,
        markdown=evidence.ocr_text,
        selections=route_plan.selected_pipelines,
    )
    await emit_progress(progress, "extract", "正在执行 schema 抽取")
    pipeline_results = await extractor.extract_selected(
        extraction_input,
        progress=_build_provider_progress_adapter(progress),
    )

    # ----- 4. Normalize per-pipeline extracts onto a single UnifiedDraft.
    await emit_progress(progress, "merge", "正在合并抽取结果")
    draft = normalize_pipeline_results(pipeline_results)
    draft.needs_review_fields = list(draft.needs_review_fields)
    if route_plan.needs_human_review:
        draft.warnings = list(draft.warnings) + ["router requested human review"]
    if evidence.warnings:
        draft.warnings = list(evidence.warnings) + list(draft.warnings)
    draft.summary = draft.summary or route_plan.document_summary

    # ----- 5. Match candidates for the review form -------------------
    candidates = await build_merge_candidates(
        session=session,
        customer=draft.customer,
        contacts=draft.contacts,
    )

    # ----- 6. Persist on the Document row so /auto/{id}/confirm can
    #         rehydrate without recalling the LLM.
    evidence.document.raw_llm_response = {
        "provider": settings.extractor_provider,
        "route_plan": route_plan.model_dump(mode="json"),
        "draft": draft.model_dump(mode="json"),
    }
    await session.flush()

    # Synthesize a legacy IngestPlan so the on-wire response shape stays
    # constant for existing /auto consumers (frontend reads plan.targets /
    # plan.extractors / plan.reason / plan.review_required).
    synthesized_plan = IngestPlan(
        targets={
            "identity": next(
                (s.confidence for s in route_plan.selected_pipelines if s.name == "identity"),
                0.0,
            ),
            "commercial": next(
                (
                    s.confidence
                    for s in route_plan.selected_pipelines
                    if s.name == "contract_order"
                ),
                0.0,
            ),
            "ops": next(
                (
                    s.confidence
                    for s in route_plan.selected_pipelines
                    if s.name == "commitment_task_risk"
                ),
                0.0,
            ),
        },
        extractors=[],
        reason=route_plan.document_summary,
        review_required=route_plan.needs_human_review,
    )

    await emit_progress(progress, "auto_done", "统一抽取完成，等待用户确认")

    return AutoIngestResult(
        document_id=evidence.document_id,
        plan=synthesized_plan,
        draft=draft,
        candidates=candidates,
        route_plan=route_plan,
    )
