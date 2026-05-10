"""Auto orchestrator — end-to-end glue for ``/api/ingest/auto``.

Single pipeline:

    file/text → Evidence (OCR) → Planner → selective parallel extractors
                  (identity / commercial / ops) → Merge → UnifiedDraft

This module is the only place where all five steps are linked. Each step is
independently testable in its own module; the orchestrator's job is sequencing,
parallelism, error tolerance, and progress emission.

Key implementation notes:

- *One AsyncSession per concurrent extractor*. ``call_claude`` writes a
  bookkeeping row to ``llm_calls`` for every call; the SQLAlchemy session is
  not safe for concurrent writes, so each extractor gets its own
  ``AsyncSession`` bound to the same engine. The main session keeps
  responsibility for the ``Document`` row + final draft persistence.
- *Soft failure on a single extractor*. If extractor X raises while extractors
  Y and Z succeed, we surface a warning on the merged draft and keep going —
  the user's review form still gets the partial result. Letting one bad
  extractor kill the whole ingest defeats the point of the planner-driven
  fan-out.
- *Always emits ``auto`` / ``auto_done`` progress events* so the UI can mark
  the orchestrator's outer step. Each sub-stage (evidence, plan, identity,
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

from yinhu_brain.services.ingest.evidence import Evidence, collect_evidence
from yinhu_brain.services.ingest.extractors.commercial import extract_commercial
from yinhu_brain.services.ingest.extractors.identity import extract_identity
from yinhu_brain.services.ingest.extractors.ops import extract_ops
from yinhu_brain.services.ingest.merge import MergeCandidates, merge_drafts
from yinhu_brain.services.ingest.planner import plan_extraction
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ingest.unified_schemas import (
    CommercialDraft,
    ExtractorName,
    IdentityDraft,
    IngestPlan,
    OpsDraft,
    UnifiedDraft,
)

logger = logging.getLogger(__name__)


# Map planner extractor names to the function that runs them. Kept module-level
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
    2. ``plan_extraction`` — pick which extractors to run. Always returns a
       plan even on LLM failure (heuristic fallback).
    3. Run each activated extractor in its own ``AsyncSession`` concurrently.
       A failing extractor produces a warning on the merged draft instead of
       killing the whole pipeline.
    4. ``merge_drafts`` — fuse the per-extractor outputs into ``UnifiedDraft``
       + ``MergeCandidates``.
    5. Persist the merged draft on ``Document.raw_llm_response`` so the
       confirm step can recover it from the row alone if the client repeats
       the request.

    The main session handles steps 1, 2, 5; each extractor in step 3 owns a
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

    # ----- 2. Planner -------------------------------------------------
    plan: IngestPlan = await plan_extraction(
        session=session,
        document_id=evidence.document_id,
        ocr_text=evidence.ocr_text,
        modality=evidence.modality,
        source_hint=source_hint,
        progress=progress,
    )

    # ----- 3. Selective parallel extractors ---------------------------
    # Each extractor runs against its own AsyncSession. We resolve the engine
    # via the main session's bind — that way the orchestrator's signature
    # stays the same as the legacy /contract path (caller hands us a session).
    # NOTE: ``session.bind`` returns the ``AsyncEngine``; ``session.get_bind()``
    # would unwrap to the underlying sync ``Engine`` and break ``AsyncSession``
    # construction below.
    #
    # **Commit before fan-out**: the Document row inserted by collect_evidence
    # and the planner's llm_calls audit row live in the main session's open
    # transaction. The per-extractor sub-sessions are independent connections
    # with their own transactions — Postgres' default READ COMMITTED isolation
    # means they cannot see uncommitted rows from the main session, so when
    # call_claude inserts ``llm_calls(document_id=...)`` the FK to documents
    # fails with IntegrityError. Committing here makes the Document visible
    # to the fan-out. Step 5 (raw_llm_response persistence) runs in a new
    # implicit transaction on the main session afterwards.
    await session.commit()
    engine = session.bind
    selected_names: list[ExtractorName] = [s.name for s in plan.extractors]

    extractor_results: dict[ExtractorName, IdentityDraft | CommercialDraft | OpsDraft] = {}
    extractor_warnings: list[str] = []

    if selected_names:
        tasks = [
            _run_extractor_with_own_session(
                name=name,
                document_id=evidence.document_id,
                ocr_text=evidence.ocr_text,
                engine=engine,
                progress=progress,
            )
            for name in selected_names
        ]
        # ``return_exceptions=True`` keeps a single failing extractor from
        # cascading into the others. We translate the exception into a
        # ``parse_warnings`` entry on the final draft instead.
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(selected_names, results, strict=True):
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

    # ----- 4. Merge ---------------------------------------------------
    await emit_progress(progress, "merge", "正在合并抽取结果")
    draft, candidates = await merge_drafts(
        session=session,
        identity=identity_draft,  # type: ignore[arg-type]
        commercial=commercial_draft,  # type: ignore[arg-type]
        ops=ops_draft,  # type: ignore[arg-type]
    )

    # Feed extractor-level failures into the merged warnings list so the UI
    # surfaces them next to the LLM-emitted ones. Evidence-level warnings
    # (OCR unreachable, short text) are already on ``Document.parse_warnings``;
    # we copy them through too so the review form sees one canonical list.
    if extractor_warnings:
        draft.warnings = list(draft.warnings) + extractor_warnings
    if evidence.warnings:
        draft.warnings = list(evidence.warnings) + list(draft.warnings)

    # ----- 5. Persist merged draft on the Document row ---------------
    # ``Document.raw_llm_response`` was historically used by the contract
    # extractor to stash the raw tool_use input so a follow-up confirm could
    # rebuild the result without re-calling the LLM. We reuse it here so the
    # /auto confirm endpoint can rehydrate the ``UnifiedDraft`` from the
    # database row alone — same recovery story.
    evidence.document.raw_llm_response = draft.model_dump(mode="json")
    await session.flush()

    await emit_progress(progress, "auto_done", "统一抽取完成，等待用户确认")

    return AutoIngestResult(
        document_id=evidence.document_id,
        plan=plan,
        draft=draft,
        candidates=candidates,
    )
