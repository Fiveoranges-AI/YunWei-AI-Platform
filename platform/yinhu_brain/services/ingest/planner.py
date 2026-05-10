"""Ingest planner — picks which extractors to run for a piece of evidence.

Pipeline step 2: take the OCR text produced by ``collect_evidence`` and decide
which of the three extractor dimensions (identity / commercial / ops) is
worth running. The decision is encoded as an :class:`IngestPlan`:

- ``targets`` — relevance score in [0, 1] per dimension. Kept around even for
  dimensions that aren't activated, so downstream UI can hint at "we noticed
  some commercial signal but not enough to extract it".
- ``extractors`` — the actual activation list; only these run.
- ``review_required`` — soft signal asking the orchestrator to keep a human
  in the loop even when confidences look high (e.g. mixed-document red flag).

Strategy: deterministic keyword/regex prefilter → LLM rerank with the prefilter
score plus the OCR text as input, falling back to the prefilter alone when the
LLM is unavailable. The LLM goes through ``services.llm.call_claude`` which
auto-handles the DeepSeek-compat tool/JSON-mode quirk.

This module never touches the Document row or runs an OCR; collect_evidence
already did that. It also never invokes any extractor — that's the orchestrator's
job, after this returns.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ingest.schemas import _strip_titles
from yinhu_brain.services.ingest.unified_schemas import (
    ExtractorName,
    ExtractorSelection,
    IngestPlan,
)
from yinhu_brain.services.llm import LLMCallFailed, call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)


# ---------- public constants ---------------------------------------------

PLANNER_TOOL_NAME = "submit_ingest_plan"

# Activation thresholds. Must stay >= the smallest LLM-rounding error we'd
# tolerate. Tweaked from product spec: identity is the easiest to recover
# from later (a stray name in OCR), commercial is the most expensive to
# false-positive on, ops is in between.
_THRESHOLD_IDENTITY = 0.55
_THRESHOLD_COMMERCIAL = 0.65
_THRESHOLD_OPS = 0.60

# When all three dimensions are clearly absent (each below this floor) we
# still activate ops so the orchestrator can stash an "unstructured customer
# memory draft" rather than dropping the input on the floor.
_DEFAULT_FLOOR = 0.4

# How much OCR text we hand to the LLM. The planner doesn't need page-level
# accuracy — first 3 KB of characters is enough to distinguish "this is a
# contract" from "this is a business card" from "this is a chat".
_LLM_CONTEXT_CHARS = 3000


# ---------- heuristic prefilter -------------------------------------------


# Each tuple is (regex, weight). Multiple hits within the same dimension
# are de-duplicated (each pattern adds at most one weight) and the
# dimension's score is capped at 1.0. We pre-compile so a single planner
# call is essentially free.

_IDENTITY_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (
        re.compile(
            r"(有限公司|股份|集团|科技|工业|实业|公司|商行|商贸|"
            r"\benterprise\b|\binc\b|\bltd\b|\bco\.|\bcorp\b)",
            re.IGNORECASE,
        ),
        0.3,
    ),
    # Chinese mobile numbers (11 digits starting 1[3-9]).
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), 0.3),
    # Plain email addresses.
    (re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+"), 0.3),
    # Common title words on cards / contact sheets.
    (
        re.compile(
            r"(经理|总监|主管|工程师|总经理|董事|"
            r"\bCEO\b|\bCTO\b|\bCFO\b|\bCOO\b)",
            re.IGNORECASE,
        ),
        0.3,
    ),
    # Explicit field labels.
    (
        re.compile(
            r"(联系人|姓名|名字|电话|邮箱|地址|签约方|甲方|乙方)"
        ),
        0.3,
    ),
]

_COMMERCIAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    # Currency-prefixed amounts, "万元 / 万", or amounts with .xx cents.
    (
        re.compile(
            r"((¥|￥|RMB|CNY|USD|\$)\s*\d|\b\d[\d,]*\s*(元|万元|万)\b|\d{4,}\.\d{2})",
            re.IGNORECASE,
        ),
        0.4,
    ),
    # Contract / order / PO identifiers.
    (
        re.compile(
            r"(合同(号|编号)|订单号|采购单|\bPO\b\s*#?\s*\d)",
            re.IGNORECASE,
        ),
        0.4,
    ),
    # Payment-related vocabulary.
    (
        re.compile(r"(预付|首付|尾款|质保金|发票|月结|账期)"),
        0.4,
    ),
    # Contract-date vocabulary.
    (
        re.compile(r"(签订|签约|生效|到期|交付|交期|履行)"),
        0.4,
    ),
]

_OPS_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    # Time commitments — relative or weekday-anchored.
    (
        re.compile(
            r"(周(一|二|三|四|五|六|日)|今天|明天|后天|月底|"
            r"下个月|本月|下周|这周|前发货)"
        ),
        0.2,
    ),
    # Action verbs typical of follow-ups.
    (
        re.compile(
            r"(承诺|答应|确认|跟进|催|回复|开会|拜访|寄|送|安排|发货|交货)"
        ),
        0.2,
    ),
    # Complaints / risks / disputes.
    (
        re.compile(
            r"(投诉|延迟|不满|退货|赔偿|争议|质量问题|延期)"
        ),
        0.2,
    ),
    # Preference / relationship signal.
    (
        re.compile(
            r"(喜欢|偏好|总监姓|决策人|关系好|对接人|建议)"
        ),
        0.2,
    ),
    # Chat-screenshot fingerprints (timestamps, reporting verbs).
    (
        re.compile(r"(:\d\d|说道|发了|聊天|消息)"),
        0.2,
    ),
]


def _score_dimension(text: str, patterns: list[tuple[re.Pattern[str], float]]) -> float:
    """Sum weights for distinct matching patterns. Clipped to [0, 1].

    Each pattern contributes its weight at most once, even if it matches in
    several places — that keeps a single email address from running the
    identity score up to 1.0 by itself.
    """
    if not text:
        return 0.0
    score = 0.0
    for pat, weight in patterns:
        if pat.search(text):
            score += weight
    return min(1.0, round(score, 3))


def _heuristic_targets(ocr_text: str) -> dict[ExtractorName, float]:
    """Run the deterministic prefilter for all three dimensions."""
    return {
        "identity": _score_dimension(ocr_text, _IDENTITY_PATTERNS),
        "commercial": _score_dimension(ocr_text, _COMMERCIAL_PATTERNS),
        "ops": _score_dimension(ocr_text, _OPS_PATTERNS),
    }


# ---------- LLM tool spec -------------------------------------------------


def _planner_tool() -> dict[str, Any]:
    """Anthropic-format tool descriptor for the planner.

    On real Anthropic upstreams the LLM emits a tool_use block. On
    DeepSeek-compat upstreams ``call_claude`` automatically converts the
    tool into a "reply with JSON only" prompt (see
    ``llm._is_deepseek_compat_endpoint`` / ``llm._switch_tools_to_json_mode``)
    and ``extract_tool_use_input`` falls back to scanning the assistant's
    text for the JSON object — same shape, both paths.
    """
    schema = _strip_titles(IngestPlan.model_json_schema())
    return {
        "name": PLANNER_TOOL_NAME,
        "description": (
            "Submit a triage plan: per-dimension relevance score, the "
            "selected extractors, a one-sentence reason, and whether the "
            "merged draft should force human review."
        ),
        "input_schema": schema,
    }


# ---------- LLM prompt ----------------------------------------------------


_PLANNER_INSTRUCTIONS = (
    "你是一个 ingest pipeline 的 triage planner。根据 OCR 文本，判断三个数据维度的"
    "相关性，并选择需要运行的抽取器。\n\n"
    "三个维度：\n"
    "- identity（身份）：客户公司、联系人、电话、邮箱、地址、职位\n"
    "- commercial（商务）：合同号、金额、付款节点、签订日期、交期\n"
    "- ops（运营/记忆）：口头承诺、跟进事项、抱怨/投诉、关键日期、决策人偏好、"
    "微信聊天里出现的事件\n\n"
    "对每个维度给出 0.0 - 1.0 的 confidence。激活规则（你只在结果里反映、不要解释）：\n"
    "- identity ≥ 0.55 激活\n"
    "- commercial ≥ 0.65 激活\n"
    "- ops ≥ 0.60 激活\n"
    "- 如果三个维度全部低于 0.4，默认激活 ops 兜底（生成未结构化记忆草稿）\n\n"
    "review_required：当文档看起来混合了多种合同 / 你检测到信号冲突 / 任一 confidence "
    "高于 0.85 时设 true。\n\n"
    "reason：一句中文，说明为什么这样选。"
)


def _build_planner_prompt(
    *,
    ocr_text: str,
    modality: str,
    source_hint: str,
    heuristic: dict[ExtractorName, float],
) -> str:
    """Render the user-message body. Keeps the heuristic baseline visible to
    the LLM so it can override it when the text obviously says otherwise."""
    truncated = ocr_text[:_LLM_CONTEXT_CHARS]
    return (
        f"{_PLANNER_INSTRUCTIONS}\n\n"
        f"## 输入元数据\n"
        f"- modality: {modality}\n"
        f"- source_hint: {source_hint}\n\n"
        f"## 启发式打分（你可以在更可信的证据下覆盖）\n"
        f"- identity: {heuristic['identity']:.2f}\n"
        f"- commercial: {heuristic['commercial']:.2f}\n"
        f"- ops: {heuristic['ops']:.2f}\n\n"
        f"## OCR 文本（最多前 {_LLM_CONTEXT_CHARS} 字）\n"
        f"```\n{truncated}\n```"
    )


# ---------- activation rules ---------------------------------------------


def _build_activation_list(
    targets: dict[ExtractorName, float],
) -> list[ExtractorSelection]:
    """Apply the threshold rules. Returns a list ordered identity → commercial → ops
    so consumers see a stable order independent of dict iteration."""
    selected: list[ExtractorSelection] = []

    if targets.get("identity", 0.0) >= _THRESHOLD_IDENTITY:
        selected.append(ExtractorSelection(name="identity", confidence=targets["identity"]))
    if targets.get("commercial", 0.0) >= _THRESHOLD_COMMERCIAL:
        selected.append(
            ExtractorSelection(name="commercial", confidence=targets["commercial"])
        )
    if targets.get("ops", 0.0) >= _THRESHOLD_OPS:
        selected.append(ExtractorSelection(name="ops", confidence=targets["ops"]))

    if not selected:
        # All three look noisy — default to ops so we still capture an
        # unstructured customer-memory draft instead of dropping the doc.
        if all(targets.get(dim, 0.0) < _DEFAULT_FLOOR for dim in ("identity", "commercial", "ops")):
            selected.append(
                ExtractorSelection(name="ops", confidence=targets.get("ops", 0.0))
            )

    return selected


_REVIEW_KEYWORDS = ("冲突", "不一致", "可能错误")


def _needs_review(reason: str, targets: dict[ExtractorName, float]) -> bool:
    """``review_required`` policy.

    True when:
    - Any dimension's confidence is above 0.85 (very high — second pair of
      eyes is cheap insurance against an over-confident bad parse), OR
    - The planner's reason mentions a known red-flag keyword.
    """
    if any(score > 0.85 for score in targets.values()):
        return True
    if reason and any(kw in reason for kw in _REVIEW_KEYWORDS):
        return True
    return False


def _normalize_targets(raw: Any) -> dict[ExtractorName, float]:
    """Coerce LLM-provided ``targets`` into a clean ``{dim: float}`` dict.

    The LLM might emit extra keys or omit some — we ignore unknown keys and
    fill missing dims with 0.0. Values are clamped to [0, 1].
    """
    out: dict[ExtractorName, float] = {"identity": 0.0, "commercial": 0.0, "ops": 0.0}
    if not isinstance(raw, dict):
        return out
    for key in ("identity", "commercial", "ops"):
        v = raw.get(key)
        if isinstance(v, (int, float)):
            out[key] = max(0.0, min(1.0, float(v)))
    return out


# ---------- main entrypoint ----------------------------------------------


async def plan_extraction(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    ocr_text: str,
    modality: Literal["image", "pdf", "office", "text"],
    source_hint: Literal["file", "camera", "pasted_text"],
    progress: ProgressCallback | None = None,
) -> IngestPlan:
    """Decide which extractors to run for this document.

    Returns an :class:`IngestPlan`. The plan is *always* returned — even on
    LLM failure the heuristic prefilter is enough to drive the orchestrator,
    just with ``review_required=True`` so a human re-checks the result.
    """
    await emit_progress(progress, "plan", "正在判断该文档的相关数据维度")

    heuristic = _heuristic_targets(ocr_text)

    # ----- LLM rerank ------------------------------------------------
    try:
        prompt = _build_planner_prompt(
            ocr_text=ocr_text,
            modality=modality,
            source_hint=source_hint,
            heuristic=heuristic,
        )
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        response = await call_claude(
            messages,
            purpose="ingest_plan",
            session=session,
            model=settings.model_parse,
            tools=[_planner_tool()],
            tool_choice={"type": "tool", "name": PLANNER_TOOL_NAME},
            max_tokens=1024,
            document_id=document_id,
        )
        tool_input = extract_tool_use_input(response, PLANNER_TOOL_NAME)
        targets = _normalize_targets(tool_input.get("targets"))
        reason = str(tool_input.get("reason", "") or "")
    except (LLMCallFailed, Exception) as exc:  # noqa: BLE001 — fallback path
        logger.warning(
            "ingest_plan LLM call failed (%s); falling back to heuristic prefilter",
            exc,
        )
        targets = dict(heuristic)
        reason = "fallback: 启发式打分 (LLM 不可用)"
        extractors = _build_activation_list(targets)
        plan = IngestPlan(
            targets=targets,
            extractors=extractors,
            reason=reason,
            review_required=True,
        )
        await emit_progress(progress, "plan_done", _summarize_plan(plan))
        return plan

    # ----- Re-validate activation list using server-side rules -------
    # The LLM may pick a different list; we re-derive ours from its scores
    # so the threshold contract stays a single source of truth.
    extractors = _build_activation_list(targets)
    review_required = bool(tool_input.get("review_required")) or _needs_review(
        reason, targets
    )

    plan = IngestPlan(
        targets=targets,
        extractors=extractors,
        reason=reason or "LLM rerank 完成",
        review_required=review_required,
    )

    await emit_progress(progress, "plan_done", _summarize_plan(plan))
    return plan


def _summarize_plan(plan: IngestPlan) -> str:
    """One-liner used as the ``plan_done`` progress message."""
    if plan.extractors:
        names = ", ".join(s.name for s in plan.extractors)
        return f"已选择抽取器: {names}"
    return "未触发任何抽取器"
