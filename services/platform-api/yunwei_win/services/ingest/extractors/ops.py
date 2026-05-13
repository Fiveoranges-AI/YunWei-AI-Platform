"""Ops extractor — text → ``OpsDraft`` (events / commitments / tasks /
risk-signals / memory-items).

Pipeline step 3 (one of three parallel extractors): take ``ocr_text`` produced
by ``collect_evidence`` and ask the LLM (text-only, no image blocks) to pull
out the **ops** dimension — non-structural customer-operations information:
what happened, who promised what, what we still need to do, what could go
wrong, and any long-lived facts about the customer.

Design notes:

- *Single LLM call*. We do not chunk the document; the upstream
  ``collect_evidence`` already produced a unified text view.
- *Text-only*. DeepSeek's Anthropic-compat endpoint cannot reliably consume
  ``image`` content blocks, so we never attach the original file. The OCR
  stage is the canonical pipeline for visual content.
- *No DB writes*. The extractor returns an :class:`OpsDraft` for the
  orchestrator/merge stage to act on — entity binding (which customer this
  belongs to), dedupe, and the ``customer_events`` / ``customer_commitments``
  / ``customer_tasks`` / ``customer_risk_signals`` / ``customer_memory_items``
  row creation all live downstream (Agent G's job).
- *No customer binding*. Unlike the legacy ``extract_customer_memory`` which
  is hard-bound to a specific ``Customer`` row at extraction time, the new
  ops extractor is customer-agnostic — confirm-stage merge resolves the
  customer link.
- *Lightweight post-validation*. The LLM is asked to flag non-ops documents
  in ``parse_warnings`` itself, but we add a fallback warning if all five
  arrays come back empty without the explicit "非运营文档" phrase, so the
  reviewer always knows why the panel is empty.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.ingest.schemas import _strip_titles
from yunwei_win.services.ingest.unified_schemas import OpsDraft
from yunwei_win.services.llm import call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)


# ---------- public constants ---------------------------------------------

OPS_TOOL_NAME = "submit_ops_extraction"

# How much OCR text we hand to the LLM. Ops content is usually short (chat
# screenshots, memos, meeting notes) but appended contract addenda can run
# long, so we keep the same cap as identity / commercial — truncating beats
# tripping a token-limit retry.
_LLM_CONTEXT_CHARS = 30000

from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("ops_extraction.md")


# ---------- LLM tool spec -------------------------------------------------


def ops_tool() -> dict[str, Any]:
    """Anthropic-format tool descriptor for the ops extractor.

    On real Anthropic upstreams the LLM emits a ``tool_use`` block. On
    DeepSeek-compat upstreams ``call_claude`` automatically converts the tool
    into a "reply with JSON only" prompt and ``extract_tool_use_input``
    falls back to scanning the assistant's text for the JSON object.
    """
    schema = _strip_titles(OpsDraft.model_json_schema())
    return {
        "name": OPS_TOOL_NAME,
        "description": (
            "Submit the customer-ops information extracted from a "
            "document's OCR text — events, commitments, tasks, risk "
            "signals, and long-lived memory items. Leave any dimension "
            "empty if absent; do not fabricate. If the document is not "
            "ops-relevant (pure contract clauses, pure business-card "
            "fields), return all-empty arrays plus a parse_warning."
        ),
        "input_schema": schema,
    }


# ---------- post-validation ----------------------------------------------


def _validate_non_ops_warning(draft: OpsDraft) -> None:
    """If all five ops arrays are empty but the LLM didn't say "非运营文档",
    add a warning so reviewers know the extractor was consulted but found
    nothing operational to extract.

    Lightweight match — we look for the literal "非运营" substring rather
    than a full classifier, because the prompt asks the LLM to use exactly
    that phrase. False positives here are harmless (a duplicate-ish
    warning), false negatives leave the reviewer guessing why the panel is
    empty.
    """
    if (
        draft.events
        or draft.commitments
        or draft.tasks
        or draft.risk_signals
        or draft.memory_items
    ):
        return
    if any("非运营" in w for w in draft.parse_warnings):
        return
    draft.parse_warnings.append(
        "未抽出 events/commitments/tasks/risk_signals/memory_items，"
        "且 LLM 未声明为非运营文档"
    )


# ---------- main entrypoint ----------------------------------------------


async def extract_ops(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    ocr_text: str,
    progress: ProgressCallback | None = None,
) -> OpsDraft:
    """Extract the ops dimension (events / commitments / tasks /
    risk-signals / memory-items) from ``ocr_text``.

    A single text-only LLM call. Returns an :class:`OpsDraft` — the
    extractor itself never writes to the DB, never binds to a specific
    customer; entity binding, dedupe, and persistence are the orchestrator's
    job (the confirm stage resolves the customer link).

    Validation failures from Pydantic propagate up to the caller (consistent
    with the identity / commercial extractors); the orchestrator decides
    whether to mark the document failed or fall back to other dimensions.
    """
    await emit_progress(
        progress, "ops_extract", "正在抽取事件/承诺/任务/风险/记忆"
    )

    # NOTE: we substitute via ``str.replace`` rather than ``str.format`` because
    # the prompt body contains regex/JSON snippets with ``{...}`` braces (e.g.
    # ``{"path": "events[0].title"}``) that ``format`` would mis-interpret as
    # positional fields.
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace(
        "{ocr_text}", (ocr_text or "(no text extracted)")[:_LLM_CONTEXT_CHARS]
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    response = await call_claude(
        messages,
        purpose="ops_extraction",
        session=session,
        model=settings.model_parse,
        tools=[ops_tool()],
        tool_choice={"type": "tool", "name": OPS_TOOL_NAME},
        max_tokens=8192,
        temperature=0,
        document_id=document_id,
    )
    tool_input = extract_tool_use_input(response, OPS_TOOL_NAME)

    draft = OpsDraft.model_validate(tool_input)

    # Post-validation: if everything came back empty without the explicit
    # "非运营文档" declaration, surface a fallback warning so the reviewer
    # knows the extractor was consulted. We only append warnings — never
    # rewrite LLM output, so the reviewer always sees the raw extraction.
    _validate_non_ops_warning(draft)

    await emit_progress(progress, "ops_done", "事件/承诺/任务/风险/记忆抽取完成")
    return draft
