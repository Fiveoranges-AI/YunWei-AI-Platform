"""LLM-driven schema router for the ingest extraction pipeline.

Replaces the regex-based pipeline_router with a single Claude/DeepSeek call
that returns a multi-label PipelineRoutePlan. Fail-open semantics: any
upstream failure surfaces as all-6-schemas + needs_human_review=True so we
prefer over-extraction to silent under-routing.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.services.ingest.landingai_schemas.registry import PIPELINE_NAMES
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.ingest.schemas import _strip_titles
from yunwei_win.services.ingest.unified_schemas import (
    PipelineRoutePlan,
    PipelineSelection,
)
from yunwei_win.services.llm import (
    LLMCallFailed,
    call_claude,
    extract_tool_use_input,
)

logger = logging.getLogger(__name__)

SCHEMA_ROUTE_TOOL_NAME = "submit_schema_route_plan"

from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("schema_route.md")

_OCR_LIMIT = 8000  # leave room for the prompt prefix


def _schema_route_tool() -> dict[str, Any]:
    return {
        "name": SCHEMA_ROUTE_TOOL_NAME,
        "description": (
            "Submit a multi-label schema selection plan. Pick every schema "
            "potentially relevant to the document; do not limit to one."
        ),
        "input_schema": _strip_titles(PipelineRoutePlan.model_json_schema()),
    }


def _failopen_plan(reason: str) -> PipelineRoutePlan:
    """All six schemas + review required. Used when the LLM is unavailable
    or returns garbage — prefer over-extraction to silent loss."""
    return PipelineRoutePlan(
        primary_pipeline="contract_order",
        selected_pipelines=[
            PipelineSelection(name=name, confidence=0.5, reason="fail-open: LLM unavailable")
            for name in PIPELINE_NAMES
        ],
        rejected_pipelines=[],
        document_summary=reason[:300],
        needs_human_review=True,
    )


def _coerce_plan(raw: dict[str, Any]) -> PipelineRoutePlan:
    """Best-effort: tolerate fields the LLM may have omitted."""
    # Discard selections whose name isn't a known schema (DeepSeek may
    # hallucinate). Don't apply any hard cap.
    sel_raw = raw.get("selected_pipelines") or []
    selected: list[PipelineSelection] = []
    seen: set[str] = set()
    for s in sel_raw:
        if not isinstance(s, dict):
            continue
        name = s.get("name")
        if name not in PIPELINE_NAMES or name in seen:
            continue
        seen.add(name)
        try:
            selected.append(PipelineSelection.model_validate(s))
        except Exception:
            continue

    rej_raw = raw.get("rejected_pipelines") or []
    rejected: list[PipelineSelection] = []
    for s in rej_raw:
        if isinstance(s, dict) and s.get("name") in PIPELINE_NAMES:
            try:
                rejected.append(PipelineSelection.model_validate(s))
            except Exception:
                continue

    primary = raw.get("primary_pipeline")
    if primary not in PIPELINE_NAMES:
        primary = selected[0].name if selected else None

    return PipelineRoutePlan(
        primary_pipeline=primary,
        selected_pipelines=selected,
        rejected_pipelines=rejected,
        document_summary=str(raw.get("document_summary") or "")[:600],
        needs_human_review=bool(raw.get("needs_human_review")),
    )


async def route_schemas(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    markdown: str,
    modality: Literal["image", "pdf", "office", "text"],
    source_hint: Literal["file", "camera", "pasted_text"],
    progress: ProgressCallback | None = None,
) -> PipelineRoutePlan:
    """Multi-label LLM schema router.

    Returns a PipelineRoutePlan whose selected_pipelines contains every schema
    the LLM judges potentially-relevant. No hard cap. On any LLM/parsing
    failure, fail-open by selecting all 6 schemas and setting
    needs_human_review=True with a warning in document_summary.
    """
    await emit_progress(progress, "route", "正在让 LLM 判定需要哪些 schema")
    text = (markdown or "").strip()
    if not text:
        return _failopen_plan("empty markdown — fail-open all schemas")

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").replace(
        "{ocr_text}", text[:_OCR_LIMIT]
    )
    # Modality + source_hint go as a separate line so the model gets
    # structural hints alongside the body.
    prompt = (
        f"modality={modality} source_hint={source_hint}\n\n" + prompt
    )

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    try:
        response = await call_claude(
            messages=messages,
            purpose="schema_route_plan",
            session=session,
            model=settings.model_parse,
            tools=[_schema_route_tool()],
            tool_choice={"type": "tool", "name": SCHEMA_ROUTE_TOOL_NAME},
            max_tokens=2000,
            temperature=0,
            document_id=document_id,
        )
    except LLMCallFailed as exc:
        logger.warning("schema router LLM failed: %s", exc)
        return _failopen_plan(f"LLM router failed: {exc!s}")

    try:
        tool_input = extract_tool_use_input(response, SCHEMA_ROUTE_TOOL_NAME)
    except Exception as exc:
        logger.warning("schema router parse failed: %s", exc)
        return _failopen_plan(f"router output unparseable: {exc!s}")

    plan = _coerce_plan(tool_input)
    if not plan.selected_pipelines:
        # LLM returned but selected nothing — treat as fail-open
        return _failopen_plan("LLM returned empty selection — fail-open")

    await emit_progress(
        progress,
        "route_done",
        f"LLM 选择了 {len(plan.selected_pipelines)} 个 schema",
    )
    return plan
