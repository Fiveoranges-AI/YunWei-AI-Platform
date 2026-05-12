"""Auto orchestrator — end-to-end glue for ``/api/ingest/auto``.

Single pipeline:

    file/text → Evidence (OCR) → LLM schema router → provider-specific
                  extractors (LandingAI schemas OR legacy identity/commercial/ops)
                  → Merge → UnifiedDraft

This module is the only place where all the steps are linked. Each step is
independently testable in its own module; the orchestrator's job is sequencing,
parallelism, error tolerance, and progress emission.

Routing is now unified across providers: ``route_schemas`` (LLM-driven,
multi-label) selects which of the six canonical schemas the document touches —
``identity`` / ``contract_order`` / ``finance`` / ``logistics`` /
``manufacturing_requirement`` / ``commitment_task_risk``. The LandingAI
provider runs the corresponding extract schemas directly; the Mistral provider
maps a subset back onto its three legacy extractors (identity / commercial /
ops) and surfaces warnings for the schemas it cannot capture.

Key implementation notes:

- *One AsyncSession per concurrent extractor*. ``call_claude`` writes a
  bookkeeping row to ``llm_calls`` for every call; the SQLAlchemy session is
  not safe for concurrent writes, so each extractor gets its own
  ``AsyncSession`` bound to the same engine. The main session keeps
  responsibility for the ``Document`` row + final draft persistence.
- *Soft failure on a single extractor*. If extractor X raises while extractors
  Y and Z succeed, we surface a warning on the merged draft and keep going —
  the user's review form still gets the partial result. Letting one bad
  extractor kill the whole ingest defeats the point of router-driven
  fan-out.
- *Always emits ``auto`` / ``auto_done`` progress events* so the UI can mark
  the orchestrator's outer step. Each sub-stage (evidence, route, identity,
  commercial, ops, merge) emits its own progress event from the underlying
  module.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.evidence import Evidence, collect_evidence
from yinhu_brain.services.ingest.extractors.commercial import extract_commercial
from yinhu_brain.services.ingest.extractors.identity import extract_identity
from yinhu_brain.services.ingest.extractors.ops import extract_ops
from yinhu_brain.services.ingest.landingai_extract import extract_selected_pipelines
from yinhu_brain.services.ingest.landingai_normalize import normalize_pipeline_results
from yinhu_brain.services.ingest.merge import (
    MergeCandidates,
    build_merge_candidates,
    merge_drafts,
)
from yinhu_brain.services.ingest.llm_schema_router import route_schemas
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ingest.unified_schemas import (
    CommercialDraft,
    ExtractorName,
    ExtractorSelection,
    IdentityDraft,
    IngestPlan,
    OpsDraft,
    PipelineRoutePlan,
    UnifiedDraft,
)

logger = logging.getLogger(__name__)


# Map legacy extractor names to the function that runs them. Kept module-level
# so tests can monkeypatch a single entry instead of patching imports inside
# the orchestrator.
_EXTRACTOR_FUNCTIONS: dict[
    ExtractorName,
    Callable[..., Awaitable[IdentityDraft | CommercialDraft | OpsDraft]],
] = {
    "identity": extract_identity,
    "commercial": extract_commercial,
    "ops": extract_ops,
}


# Schema → legacy extractor mapping for the Mistral provider. Three of the
# six canonical schemas have a legacy DeepSeek/Claude extractor; the others
# (finance / logistics / manufacturing_requirement) only land via LandingAI
# Extract. Schemas without a legacy mapping surface as a warning instead of
# being silently dropped.
_SCHEMA_TO_LEGACY: dict[str, ExtractorName] = {
    "identity": "identity",
    "contract_order": "commercial",
    "commitment_task_risk": "ops",
}
_UNSUPPORTED_SCHEMAS_FOR_MISTRAL: set[str] = {
    "finance",
    "logistics",
    "manufacturing_requirement",
}


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


# ---------- per-extractor isolation --------------------------------------


async def _run_extractor_with_own_session(
    *,
    name: ExtractorName,
    document_id: uuid.UUID,
    ocr_text: str,
    engine,
    progress: ProgressCallback | None,
) -> IdentityDraft | CommercialDraft | OpsDraft:
    """Run one extractor in its own ``AsyncSession``.

    The orchestrator's main session is reserved for the ``Document`` row and
    any final audit columns — it cannot be shared with the extractors because
    ``call_claude`` writes ``llm_calls`` rows synchronously and concurrent
    writers on a single session corrupt SQLAlchemy's identity map.

    On success the sub-session is committed (so the ``llm_calls`` audit row
    persists even if a sibling extractor fails later) and closed. On failure
    we rollback then re-raise so the caller can convert the exception into a
    soft warning on the merged draft.
    """
    fn = _EXTRACTOR_FUNCTIONS[name]
    async with AsyncSession(engine, expire_on_commit=False) as sub_session:
        try:
            result = await fn(
                session=sub_session,
                document_id=document_id,
                ocr_text=ocr_text,
                progress=progress,
            )
            await sub_session.commit()
            return result
        except BaseException:
            await sub_session.rollback()
            raise


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
) -> AutoIngestResult:
    """End-to-end pipeline: bytes/text in → ``AutoIngestResult`` out.

    Step-by-step:

    1. ``collect_evidence`` — persist the original file/text, OCR if needed,
       insert the ``Document`` row, return ``ocr_text``.
    2. ``route_schemas`` — single LLM call returns a multi-label
       ``PipelineRoutePlan`` selecting which of the six canonical schemas the
       document touches. Drives both the LandingAI and Mistral branches.
    3a. (LandingAI branch) ``extract_selected_pipelines`` runs the selected
        schemas in parallel via LandingAI Extract, then
        ``normalize_pipeline_results`` folds the outputs onto ``UnifiedDraft``.
    3b. (Mistral branch) selected schemas map back to the legacy identity /
        commercial / ops extractors. Schemas without a legacy mapping
        (finance / logistics / manufacturing_requirement) surface as warnings
        on the merged draft so they don't silently vanish.
    4. ``merge_drafts`` — fuse the per-extractor outputs into ``UnifiedDraft``
       + ``MergeCandidates`` (Mistral branch only; LandingAI's normalizer
       already produces a UnifiedDraft).
    5. Persist the merged draft on ``Document.raw_llm_response`` so the
       confirm step can recover it from the row alone if the client repeats
       the request.

    The main session handles steps 1, 2, 5; each extractor in step 3b owns a
    sub-session bound to the same engine (see ``_run_extractor_with_own_session``).
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
    )

    # ----- 2. LLM schema router (unified across providers) -----------
    # Multi-label LLM call; replaces the regex pipeline_router (LandingAI) and
    # the legacy plan_extraction (Mistral). The same route plan drives both
    # branches below.
    route_plan = await route_schemas(
        session=session,
        document_id=evidence.document_id,
        markdown=evidence.ocr_text,
        modality=evidence.modality,
        source_hint=source_hint,
        progress=progress,
    )

    # ----- 3a. LandingAI schema-routed flow (alternate provider) -----
    # When the operator picks ``landingai`` as the document AI provider, we
    # feed the router's selected_pipelines into LandingAI Extract directly.
    # ``normalize_pipeline_results`` folds the responses onto the same
    # ``UnifiedDraft`` shape the legacy path produces. The synthesized
    # ``IngestPlan`` keeps the on-wire response identical so the frontend
    # and existing /auto consumers don't need to know which provider ran.
    if settings.document_ai_provider == "landingai":
        await emit_progress(progress, "extract", "正在并行执行 LandingAI schema 提取")
        pipeline_results = await extract_selected_pipelines(
            selections=route_plan.selected_pipelines,
            markdown=evidence.ocr_text,
        )
        await emit_progress(progress, "merge", "正在合并 LandingAI 提取结果")
        draft = normalize_pipeline_results(pipeline_results)
        draft.needs_review_fields = list(draft.needs_review_fields)
        if route_plan.needs_human_review:
            draft.warnings = list(draft.warnings) + ["router requested human review"]
        draft.summary = draft.summary or route_plan.document_summary

        evidence.document.raw_llm_response = {
            "provider": "landingai",
            "route_plan": route_plan.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
        }
        await session.flush()
        await emit_progress(
            progress, "auto_done", "LandingAI 提取完成，等待用户确认"
        )

        # Synthesize a legacy IngestPlan so AutoIngestResult shape stays
        # constant for the existing endpoint serializer and the frontend client.
        legacy_plan = IngestPlan(
            targets={
                "identity": next(
                    (s.confidence for s in route_plan.selected_pipelines if s.name == "identity"),
                    0.0,
                ),
                "commercial": next(
                    (s.confidence for s in route_plan.selected_pipelines if s.name == "contract_order"),
                    0.0,
                ),
                "ops": next(
                    (s.confidence for s in route_plan.selected_pipelines if s.name == "commitment_task_risk"),
                    0.0,
                ),
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
            plan=legacy_plan,
            draft=draft,
            candidates=candidates,
            route_plan=route_plan,
        )

    # ----- 3b. Mistral branch: schema → legacy extractor mapping -----
    # Translate the router's selected schemas into the three legacy extractor
    # names. Schemas without a legacy mapping (finance / logistics /
    # manufacturing_requirement) become warnings on the merged draft so the
    # operator knows they were detected but couldn't be captured under this
    # provider — switching to DOCUMENT_AI_PROVIDER=landingai recovers them.
    selected_extractor_names: list[ExtractorName] = []
    seen_extractors: set[ExtractorName] = set()
    unsupported_warnings: list[str] = []
    for selection in route_plan.selected_pipelines:
        if selection.name in _SCHEMA_TO_LEGACY:
            mapped = _SCHEMA_TO_LEGACY[selection.name]
            if mapped not in seen_extractors:
                seen_extractors.add(mapped)
                selected_extractor_names.append(mapped)
        elif selection.name in _UNSUPPORTED_SCHEMAS_FOR_MISTRAL:
            logger.warning(
                "auto_ingest: schema %r selected by router but no Mistral "
                "extractor available (document %s)",
                selection.name,
                evidence.document_id,
            )
            unsupported_warnings.append(
                f"schema {selection.name!r} selected by router but no Mistral "
                "extractor available — enable DOCUMENT_AI_PROVIDER=landingai "
                "to capture it"
            )

    # ----- 4. Selective parallel extractors ---------------------------
    # Each extractor runs against its own AsyncSession. We resolve the engine
    # via the main session's bind — that way the orchestrator's signature
    # stays the same as the legacy /contract path (caller hands us a session).
    # NOTE: ``session.bind`` returns the ``AsyncEngine``; ``session.get_bind()``
    # would unwrap to the underlying sync ``Engine`` and break ``AsyncSession``
    # construction below.
    #
    # **Commit before fan-out**: the Document row inserted by collect_evidence
    # and the router's llm_calls audit row live in the main session's open
    # transaction. The per-extractor sub-sessions are independent connections
    # with their own transactions — Postgres' default READ COMMITTED isolation
    # means they cannot see uncommitted rows from the main session, so when
    # call_claude inserts ``llm_calls(document_id=...)`` the FK to documents
    # fails with IntegrityError. Committing here makes the Document visible
    # to the fan-out. Step 5 (raw_llm_response persistence) runs in a new
    # implicit transaction on the main session afterwards.
    await session.commit()
    engine = session.bind

    extractor_results: dict[ExtractorName, IdentityDraft | CommercialDraft | OpsDraft] = {}
    extractor_warnings: list[str] = []

    if selected_extractor_names:
        tasks = [
            _run_extractor_with_own_session(
                name=name,
                document_id=evidence.document_id,
                ocr_text=evidence.ocr_text,
                engine=engine,
                progress=progress,
            )
            for name in selected_extractor_names
        ]
        # ``return_exceptions=True`` keeps a single failing extractor from
        # cascading into the others. We translate the exception into a
        # ``parse_warnings`` entry on the final draft instead.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(selected_extractor_names, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "auto_ingest extractor %r failed for document %s: %s",
                    name,
                    evidence.document_id,
                    result,
                )
                extractor_warnings.append(
                    f"extractor {name!r} failed: {result!s}"
                )
                continue
            extractor_results[name] = result

    identity_draft = extractor_results.get("identity")  # type: ignore[assignment]
    commercial_draft = extractor_results.get("commercial")  # type: ignore[assignment]
    ops_draft = extractor_results.get("ops")  # type: ignore[assignment]

    # ----- 5. Merge ---------------------------------------------------
    await emit_progress(progress, "merge", "正在合并抽取结果")
    draft, candidates = await merge_drafts(
        session=session,
        identity=identity_draft,  # type: ignore[arg-type]
        commercial=commercial_draft,  # type: ignore[arg-type]
        ops=ops_draft,  # type: ignore[arg-type]
    )

    # Feed extractor-level failures and router-side metadata into the merged
    # warnings list so the UI surfaces them next to the LLM-emitted ones.
    # Evidence-level warnings (OCR unreachable, short text) are already on
    # ``Document.parse_warnings``; we copy them through too so the review form
    # sees one canonical list.
    if extractor_warnings:
        draft.warnings = list(draft.warnings) + extractor_warnings
    if unsupported_warnings:
        draft.warnings = list(draft.warnings) + unsupported_warnings
    if route_plan.needs_human_review:
        draft.warnings = list(draft.warnings) + ["router requested human review"]
    if evidence.warnings:
        draft.warnings = list(evidence.warnings) + list(draft.warnings)

    # Synthesize a legacy IngestPlan from the router output so the API
    # response shape stays constant (frontend reads plan.targets /
    # plan.extractors / plan.reason / plan.review_required).
    synthesized_plan = IngestPlan(
        targets={
            "identity": next(
                (s.confidence for s in route_plan.selected_pipelines if s.name == "identity"),
                0.0,
            ),
            "commercial": next(
                (s.confidence for s in route_plan.selected_pipelines if s.name == "contract_order"),
                0.0,
            ),
            "ops": next(
                (s.confidence for s in route_plan.selected_pipelines if s.name == "commitment_task_risk"),
                0.0,
            ),
        },
        extractors=[
            ExtractorSelection(name=name, confidence=0.8)
            for name in selected_extractor_names
        ],
        reason=route_plan.document_summary,
        review_required=route_plan.needs_human_review,
    )

    # ----- 6. Persist merged draft on the Document row ---------------
    # ``Document.raw_llm_response`` was historically used by the contract
    # extractor to stash the raw tool_use input so a follow-up confirm could
    # rebuild the result without re-calling the LLM. We reuse it here so the
    # /auto confirm endpoint can rehydrate the ``UnifiedDraft`` from the
    # database row alone — same recovery story. We also persist the
    # route_plan so the audit trail captures why each extractor ran.
    evidence.document.raw_llm_response = {
        "provider": settings.document_ai_provider,
        "route_plan": route_plan.model_dump(mode="json"),
        "draft": draft.model_dump(mode="json"),
    }
    await session.flush()

    await emit_progress(progress, "auto_done", "统一抽取完成，等待用户确认")

    return AutoIngestResult(
        document_id=evidence.document_id,
        plan=synthesized_plan,
        draft=draft,
        candidates=candidates,
        route_plan=route_plan,
    )
