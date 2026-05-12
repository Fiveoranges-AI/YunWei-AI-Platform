"""Identity extractor — text → ``IdentityDraft`` (customer + contacts).

Pipeline step 3 (one of three parallel extractors): take ``ocr_text`` produced
by ``collect_evidence`` and ask the LLM (text-only, no image blocks) to pull
out the **identity** dimension — the client company plus any people it can
recognise on the page.

Design notes:

- *Single LLM call*. We do not chunk the document; the upstream
  ``collect_evidence`` already produced a unified text view.
- *Text-only*. DeepSeek's Anthropic-compat endpoint cannot reliably consume
  ``image`` content blocks, so we never attach the original file. The OCR
  stage is the canonical pipeline for visual content.
- *No DB writes*. The extractor returns an :class:`IdentityDraft` for the
  orchestrator/merge stage to act on — entity matching, dedupe, and the
  ``Customer`` / ``Contact`` row creation all live downstream.
- *Lightweight post-validation*. The LLM is asked to filter bad mobiles /
  emails into ``parse_warnings`` itself (per the prompt's hard rules) but
  we add an extra pass against the same regexes so a forgetful model still
  surfaces obvious format failures to the reviewer.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ingest.schemas import _strip_titles
from yinhu_brain.services.ingest.unified_schemas import IdentityDraft
from yinhu_brain.services.llm import call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)


# ---------- public constants ---------------------------------------------

IDENTITY_TOOL_NAME = "submit_identity_extraction"

# How much OCR text we hand to the LLM. A single pass is enough; identity
# fields cluster at the top of cards / signatures / chat headers, and we'd
# rather truncate than trip a token-limit retry.
_LLM_CONTEXT_CHARS = 30000

from yinhu_brain.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("identity_extraction.md")


# ---------- post-validation regexes ---------------------------------------

# Chinese mobile (11 digits, 1[3-9] prefix). Same regex the planner / business-
# card extractor use, kept as a module constant so tests can re-use it.
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")

# Loose email regex. ``[^@\s]+@[^@\s]+\.[^@\s]+`` is intentionally permissive —
# we want to flag obviously broken values (no ``@``, no ``.``) without
# rejecting legitimate plus-tags or international domains.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- LLM tool spec -------------------------------------------------


def identity_tool() -> dict[str, Any]:
    """Anthropic-format tool descriptor for the identity extractor.

    On real Anthropic upstreams the LLM emits a ``tool_use`` block. On
    DeepSeek-compat upstreams ``call_claude`` automatically converts the tool
    into a "reply with JSON only" prompt and ``extract_tool_use_input``
    falls back to scanning the assistant's text for the JSON object.
    """
    schema = _strip_titles(IdentityDraft.model_json_schema())
    return {
        "name": IDENTITY_TOOL_NAME,
        "description": (
            "Submit the customer + contacts identity extracted from a "
            "document's OCR text. Fill missing fields with null; do not "
            "fabricate."
        ),
        "input_schema": schema,
    }


# ---------- post-validation ----------------------------------------------


def _validate_contacts(draft: IdentityDraft) -> None:
    """Append ``parse_warnings`` for contact fields whose format looks wrong.

    We deliberately do NOT mutate the LLM-supplied values — even a malformed
    mobile is useful evidence for the reviewer ("OCR cut off the last
    digit"). We only flag the warning so the UI can highlight the field.
    """
    for idx, contact in enumerate(draft.contacts):
        mobile = (contact.mobile or "").strip()
        if mobile and not _MOBILE_RE.match(mobile):
            draft.parse_warnings.append(
                f"contacts[{idx}].mobile {mobile!r} 不符合中国大陆手机号格式 "
                "(1[3-9]xxxxxxxxx)"
            )

        email = (contact.email or "").strip()
        if email and not _EMAIL_RE.match(email):
            draft.parse_warnings.append(
                f"contacts[{idx}].email {email!r} 不符合邮箱格式 (需含 @ 与域名)"
            )


# ---------- main entrypoint ----------------------------------------------


async def extract_identity(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    ocr_text: str,
    progress: ProgressCallback | None = None,
) -> IdentityDraft:
    """Extract the identity dimension (customer + contacts) from ``ocr_text``.

    A single text-only LLM call. Returns an :class:`IdentityDraft` — the
    extractor itself never writes to the DB; entity matching, dedupe, and
    persistence are the orchestrator's job.

    Validation failures from Pydantic propagate up to the caller (consistent
    with the contract extractor); the orchestrator decides whether to mark
    the document failed or fall back to ops-only.
    """
    await emit_progress(progress, "identity_extract", "正在抽取客户/联系人")

    # NOTE: we substitute via ``str.replace`` rather than ``str.format`` because
    # the prompt body contains regex/JSON snippets with ``{...}`` braces (e.g.
    # ``1[3-9]\d{9}``) that ``format`` would mis-interpret as positional fields.
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")
    prompt = prompt_template.replace(
        "{ocr_text}", (ocr_text or "(no text extracted)")[:_LLM_CONTEXT_CHARS]
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    response = await call_claude(
        messages,
        purpose="identity_extraction",
        session=session,
        model=settings.model_parse,
        tools=[identity_tool()],
        tool_choice={"type": "tool", "name": IDENTITY_TOOL_NAME},
        max_tokens=4096,
        temperature=0,
        document_id=document_id,
    )
    tool_input = extract_tool_use_input(response, IDENTITY_TOOL_NAME)

    draft = IdentityDraft.model_validate(tool_input)

    # Post-validation: flag malformed mobiles/emails the LLM may have left
    # through. We append warnings rather than rewriting values so the
    # original OCR-derived string stays visible to the reviewer.
    _validate_contacts(draft)

    await emit_progress(progress, "identity_done", "客户/联系人抽取完成")
    return draft
