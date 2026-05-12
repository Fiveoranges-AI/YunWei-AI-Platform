"""Commercial extractor — text → ``CommercialDraft`` (order + contract).

Pipeline step 3 (one of three parallel extractors): take ``ocr_text`` produced
by ``collect_evidence`` and ask the LLM (text-only, no image blocks) to pull
out the **commercial** dimension — order amount/delivery + contract
metadata (number, signing/effective/expiry dates, payment milestones,
delivery terms, penalty terms).

Design notes:

- *Single LLM call*. We do not chunk the document; the upstream
  ``collect_evidence`` already produced a unified text view.
- *Text-only*. DeepSeek's Anthropic-compat endpoint cannot reliably consume
  ``image`` content blocks, so we never attach the original file. The OCR
  stage is the canonical pipeline for visual content.
- *No DB writes*. The extractor returns a :class:`CommercialDraft` for the
  orchestrator/merge stage to act on — Order / Contract row creation and any
  customer linkage all live downstream.
- *Lightweight post-validation*. The LLM is asked to filter ratio sums and
  flag non-commercial documents into ``parse_warnings`` itself, but we add
  an extra pass in case it forgets — without rewriting any value (raw OCR
  data stays visible for the reviewer).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ingest.schemas import _strip_titles
from yinhu_brain.services.ingest.unified_schemas import CommercialDraft
from yinhu_brain.services.llm import call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)


# ---------- public constants ---------------------------------------------

COMMERCIAL_TOOL_NAME = "submit_commercial_extraction"

# How much OCR text we hand to the LLM. Contract text bodies can be long
# (T&Cs, penalty clauses), but we'd rather truncate than trip a token-limit
# retry — the structural fields (amount, dates, milestones) cluster near
# the front of the document anyway.
_LLM_CONTEXT_CHARS = 30000

from yinhu_brain.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("commercial_extraction.md")

# Ratio-sum tolerance: matches the value used inside ContractExtractionResult
# so warnings emitted from this extractor are consistent with the legacy
# contract-only path.
_RATIO_SUM_LOW = 0.99
_RATIO_SUM_HIGH = 1.01


# ---------- LLM tool spec -------------------------------------------------


def commercial_tool() -> dict[str, Any]:
    """Anthropic-format tool descriptor for the commercial extractor.

    On real Anthropic upstreams the LLM emits a ``tool_use`` block. On
    DeepSeek-compat upstreams ``call_claude`` automatically converts the tool
    into a "reply with JSON only" prompt and ``extract_tool_use_input``
    falls back to scanning the assistant's text for the JSON object.
    """
    schema = _strip_titles(CommercialDraft.model_json_schema())
    return {
        "name": COMMERCIAL_TOOL_NAME,
        "description": (
            "Submit the order + contract commercial fields extracted from a "
            "document's OCR text. Fill missing fields with null; do not "
            "fabricate. If the document is not a commercial document, set "
            "order and contract to null and add a parse_warning."
        ),
        "input_schema": schema,
    }


# ---------- post-validation ----------------------------------------------


def _validate_milestones(draft: CommercialDraft) -> None:
    """Append a ``parse_warning`` if payment-milestone ratios don't sum to 1.0
    (within ±0.01). We deliberately do not normalise — the reviewer needs to
    see the raw mismatch so they can correct the source rather than trust
    a silent LLM rewrite.
    """
    contract = draft.contract
    if contract is None or not contract.payment_milestones:
        return

    total = sum(m.ratio for m in contract.payment_milestones)
    if not (_RATIO_SUM_LOW <= total <= _RATIO_SUM_HIGH):
        draft.parse_warnings.append(
            f"payment_milestones ratio sum = {total:.4f}, expected 1.00 (±0.01)"
        )


def _validate_non_commercial_warning(draft: CommercialDraft) -> None:
    """If both ``order`` and ``contract`` are null but the LLM didn't say
    "非商务文档", add a warning so reviewers know the extractor was
    consulted but found nothing structural to extract.

    Lightweight match — we look for the literal "非商务" substring rather
    than a full classifier, because the prompt asks the LLM to use exactly
    that phrase. False positives here are harmless (a duplicate-ish
    warning), false negatives leave the reviewer guessing why the panel is
    empty.
    """
    if draft.order is not None or draft.contract is not None:
        return
    if any("非商务" in w for w in draft.parse_warnings):
        return
    draft.parse_warnings.append(
        "未抽出 order/contract，且 LLM 未声明为非商务文档"
    )


# ---------- main entrypoint ----------------------------------------------


async def extract_commercial(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    ocr_text: str,
    progress: ProgressCallback | None = None,
) -> CommercialDraft:
    """Extract the commercial dimension (order + contract) from ``ocr_text``.

    A single text-only LLM call. Returns a :class:`CommercialDraft` — the
    extractor itself never writes to the DB; entity creation, dedupe, and
    persistence are the orchestrator's job.

    Validation failures from Pydantic propagate up to the caller (consistent
    with the identity extractor); the orchestrator decides whether to mark
    the document failed or fall back to other dimensions.
    """
    await emit_progress(progress, "commercial_extract", "正在抽取订单/合同字段")

    # NOTE: we substitute via ``str.replace`` rather than ``str.format`` because
    # the prompt body contains regex/JSON snippets with ``{...}`` braces (e.g.
    # ``\d{9}``) that ``format`` would mis-interpret as positional fields.
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace(
        "{ocr_text}", (ocr_text or "(no text extracted)")[:_LLM_CONTEXT_CHARS]
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    response = await call_claude(
        messages,
        purpose="commercial_extraction",
        session=session,
        model=settings.model_parse,
        tools=[commercial_tool()],
        tool_choice={"type": "tool", "name": COMMERCIAL_TOOL_NAME},
        max_tokens=8192,
        temperature=0,
        document_id=document_id,
    )
    tool_input = extract_tool_use_input(response, COMMERCIAL_TOOL_NAME)

    draft = CommercialDraft.model_validate(tool_input)

    # Post-validation: surface payment-milestone ratio drift and missing
    # non-commercial declaration. We only append warnings — never rewrite
    # LLM output, so the reviewer always sees the raw extraction.
    _validate_milestones(draft)
    _validate_non_commercial_warning(draft)

    await emit_progress(progress, "commercial_done", "订单/合同抽取完成")
    return draft
