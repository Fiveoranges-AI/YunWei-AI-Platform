"""Schema-first auto-ingest orchestrator.

Same OCR/route/extract front-half as the extractor pipeline; the back-half
materializes a schema-shaped ``ReviewDraft``:

1. ``collect_evidence`` — OCR + Document row.
2. ``route_schemas`` — pipeline route plan.
3. ``get_extractor_provider().extract_selected(...)`` — per-pipeline extract.
4. ``ensure_default_company_schema`` + ``get_company_schema`` — tenant catalog.
5. ``materialize_review_draft`` — schema-first cell/table draft.
6. Insert a ``DocumentExtraction`` row carrying the route plan, raw pipeline
   results, and the review draft.

Failures inside the extract step do NOT crash the auto-ingest: a degraded
draft is built with a warning so the worker can persist ``extracted`` state
and surface the failure in the UI instead of bouncing the job to ``failed``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.services.company_schema import (
    ensure_default_company_schema,
    get_company_schema,
)
from yunwei_win.services.ingest.evidence import (
    Evidence,
    PreStoredFile,
    collect_evidence,
)
from yunwei_win.services.ingest.extractors.providers.base import (
    ExtractionInput,
    ProgressCallback as ExtractorProgressCallback,
)
from yunwei_win.services.ingest.extractors.providers.factory import (
    get_extractor_provider,
)
from yunwei_win.services.ingest.llm_schema_router import route_schemas
from yunwei_win.services.ingest.pipeline_schemas import PipelineRoutePlan
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.schema_ingest.review_draft import materialize_review_draft
from yunwei_win.services.schema_ingest.schemas import ReviewDraft

logger = logging.getLogger(__name__)


@dataclass
class AutoIngestResult:
    """Bundle returned to the worker — the worker persists these onto the
    IngestJob row."""

    document_id: uuid.UUID
    extraction_id: uuid.UUID
    route_plan: PipelineRoutePlan | None
    review_draft: ReviewDraft


def _build_provider_progress_adapter(
    progress: ProgressCallback | None,
) -> ExtractorProgressCallback | None:
    """Bridge provider event callbacks onto the worker progress shape."""

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
        elif event in {"schema_extract", "schema_extract_done"} and isinstance(
            payload, str
        ):
            await progress("extract", payload)
        else:
            await progress(event, str(payload))

    return adapter


async def auto_ingest(
    *,
    session: AsyncSession,
    file_bytes: bytes | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    text_content: str | None = None,
    source_hint: Literal["file", "camera", "pasted_text"] = "file",
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
    pre_stored: PreStoredFile | None = None,
) -> AutoIngestResult:
    """Run the schema-first pipeline end-to-end.

    Evidence/route/extract builds a ``ReviewDraft`` from the tenant catalog.

    The session is owned by the caller (the worker); we ``flush`` so the
    Document + DocumentExtraction rows are visible inside this session but
    leave commit to the caller.
    """

    await emit_progress(progress, "auto", "开始 schema-first 抽取流水线")

    # --- 1. Evidence ----------------------------------------------------
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

    # --- 2. Route schemas ----------------------------------------------
    route_plan = await route_schemas(
        session=session,
        document_id=evidence.document_id,
        markdown=evidence.ocr_text,
        modality=evidence.modality,
        source_hint=source_hint,
        progress=progress,
    )

    # --- 3. Catalog -----------------------------------------------------
    # The extractor schema is generated from the tenant company catalog, so
    # providers are constrained to emit canonical table/field names.
    await ensure_default_company_schema(session)
    catalog = await get_company_schema(session)

    # --- 4. Run extractor providers over the selected pipelines --------
    pipeline_dump: list[dict] = []
    extract_warnings: list[str] = []
    await emit_progress(progress, "extract", "正在执行 schema 抽取")
    try:
        extractor = get_extractor_provider()
        extraction_input = ExtractionInput(
            document_id=evidence.document_id,
            session=session,
            markdown=evidence.ocr_text,
            selections=route_plan.selected_pipelines,
            company_schema=catalog,
        )
        pipeline_results = await extractor.extract_selected(
            extraction_input,
            progress=_build_provider_progress_adapter(progress),
        )
        pipeline_dump = [pr.model_dump(mode="json") for pr in pipeline_results]
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        logger.exception("schema ingest extract step failed for document %s", evidence.document_id)
        extract_warnings.append(f"extraction failed: {type(exc).__name__}: {exc!s}")
        pipeline_dump = []

    # --- 5. Materialize the ReviewDraft --------------------------------
    await emit_progress(progress, "merge", "拼装 schema-first 草稿")
    extraction_id = uuid.uuid4()
    route_plan_dump = route_plan.model_dump(mode="json")
    general_warnings = list(extract_warnings)
    if evidence.warnings:
        general_warnings = list(evidence.warnings) + general_warnings
    review_draft = materialize_review_draft(
        extraction_id=extraction_id,
        document_id=evidence.document_id,
        schema_version=1,
        document_filename=evidence.document.original_filename or "",
        route_plan=route_plan_dump,
        pipeline_results=pipeline_dump,
        catalog=catalog,
        document_summary=route_plan.document_summary or None,
        document_source_text=evidence.ocr_text or None,
        warnings=general_warnings or None,
    )

    # --- 6. Persist DocumentExtraction ---------------------------------
    extraction = DocumentExtraction(
        id=extraction_id,
        document_id=evidence.document_id,
        schema_version=1,
        provider=settings.extractor_provider,
        route_plan=route_plan_dump,
        raw_pipeline_results=pipeline_dump,
        review_draft=review_draft.model_dump(mode="json"),
        status=DocumentExtractionStatus.pending_review,
        warnings=general_warnings or None,
        created_by="ai",
    )
    session.add(extraction)

    # Stamp the document so we can rehydrate the workflow.
    evidence.document.raw_llm_response = {
        "workflow": "schema_first",
        "extraction_id": str(extraction_id),
        "provider": settings.extractor_provider,
        "route_plan": route_plan_dump,
    }
    await session.flush()

    await emit_progress(progress, "auto_done", "schema-first 抽取完成，待人工确认")

    return AutoIngestResult(
        document_id=evidence.document_id,
        extraction_id=extraction_id,
        route_plan=route_plan,
        review_draft=review_draft,
    )
