"""Tests for the unified ingest planner.

Covers:
- Heuristic prefilter scores (commercial / identity / chat / noise)
- Activation thresholds (boundary cases at 0.55 / 0.65 / 0.60)
- All-low fallback → default ops activation
- ``review_required`` triggers (high confidence, conflict keywords)
- LLM rerank success path (tool_use input is honoured)
- LLM rerank failure path (heuristic fallback + review flag)

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_evidence.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base
from yunwei_win.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
)
from yunwei_win.services.ingest import planner as planner_module
from yunwei_win.services.ingest.planner import (
    PLANNER_TOOL_NAME,
    _build_activation_list,
    _heuristic_targets,
    _needs_review,
    _normalize_targets,
    _score_dimension,
    plan_extraction,
)
from yunwei_win.services.ingest.planner import (
    _IDENTITY_PATTERNS,
    _COMMERCIAL_PATTERNS,
    _OPS_PATTERNS,
)
from yunwei_win.services.ingest.unified_schemas import IngestPlan
from yunwei_win.services.llm import LLMCallFailed


# ---------- helpers -------------------------------------------------------


async def _make_session() -> tuple[AsyncSession, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return session, engine


async def _make_doc(session: AsyncSession, ocr: str = "") -> Document:
    """Persist a Document row so plan_extraction has a valid document_id."""
    doc = Document(
        type=DocumentType.text_note,
        file_url="/tmp/note.txt",
        original_filename="note.txt",
        content_type="text/plain",
        file_sha256="0" * 64,
        file_size_bytes=len(ocr.encode("utf-8")) or 1,
        ocr_text=ocr,
        processing_status=DocumentProcessingStatus.parsed,
        review_status=DocumentReviewStatus.pending_review,
    )
    session.add(doc)
    await session.flush()
    return doc


def _make_response(tool_input: dict[str, Any]) -> Any:
    """Build a fake Anthropic SDK response with a single ``tool_use`` block.

    ``extract_tool_use_input`` reads ``response.content[i].type``,
    ``.name``, and ``.input`` — a SimpleNamespace is plenty.
    """
    block = SimpleNamespace(
        type="tool_use",
        name=PLANNER_TOOL_NAME,
        input=tool_input,
    )
    return SimpleNamespace(content=[block])


# ---------- heuristic prefilter ------------------------------------------


def test_heuristic_scores_contract_text_high_on_commercial() -> None:
    text = (
        "本合同由甲方测试有限公司与乙方某某公司于 2025年10月15日 签订。\n"
        "合同总金额：人民币 ¥123,456.00 元。\n"
        "付款节点：预付款 30%，尾款 70%，签订后 30 日内交付。\n"
        "联系人：王经理，13800000000。"
    )
    scores = _heuristic_targets(text)
    # Commercial should dominate (amount + contract vocab + payment + dates)
    assert scores["commercial"] >= 0.65
    # Identity also lights up because of company suffix + mobile + 联系人
    assert scores["identity"] >= 0.55
    # No real ops signal in this text
    assert scores["ops"] < 0.4


def test_heuristic_scores_business_card_high_on_identity() -> None:
    text = (
        "测试有限公司\n王强 销售经理\n"
        "电话: 13900000000\n邮箱: wang@test.com\n地址: 上海市浦东新区"
    )
    scores = _heuristic_targets(text)
    assert scores["identity"] >= 0.55
    # No commercial/ops signal
    assert scores["commercial"] < 0.4
    assert scores["ops"] < 0.4


def test_heuristic_scores_wechat_chat_high_on_ops() -> None:
    text = (
        "10:23 王总说道: 这周五前发货可以吗\n"
        "10:25 我承诺周三安排发货\n"
        "10:30 王总: 好的，记得跟进物流"
    )
    scores = _heuristic_targets(text)
    # Multiple ops patterns hit (timestamp ":\d\d", 说道, 承诺, 跟进, 周三, 发货)
    assert scores["ops"] >= 0.6
    # No real commercial/identity signal beyond the timestamps
    assert scores["commercial"] < 0.4


def test_heuristic_scores_noise_text_all_low() -> None:
    text = "这是一段没有任何业务含义的随便记录的文字测试一下"
    scores = _heuristic_targets(text)
    assert scores["identity"] < 0.4
    assert scores["commercial"] < 0.4
    assert scores["ops"] < 0.4


def test_heuristic_score_clipped_to_one() -> None:
    """Each dimension caps at 1.0 even when many patterns hit."""
    # All five identity patterns hit
    text = (
        "联系人：王经理 总监 13800000000 wang@a.com 上海市 测试有限公司"
    )
    score = _score_dimension(text, _IDENTITY_PATTERNS)
    assert score == 1.0


def test_heuristic_score_pattern_dedup() -> None:
    """A single pattern matching multiple times only contributes its weight once."""
    # Three emails — but the email pattern still adds 0.3 once.
    text = "a@a.com b@b.com c@c.com"
    score = _score_dimension(text, _IDENTITY_PATTERNS)
    assert score == 0.3


def test_heuristic_empty_text_zero() -> None:
    assert _score_dimension("", _IDENTITY_PATTERNS) == 0.0
    assert _score_dimension("", _COMMERCIAL_PATTERNS) == 0.0
    assert _score_dimension("", _OPS_PATTERNS) == 0.0


# ---------- activation rules ---------------------------------------------


def test_activation_thresholds_boundary_identity() -> None:
    # Identity threshold is 0.55 — exactly on the boundary should activate.
    plan = _build_activation_list({"identity": 0.55, "commercial": 0.0, "ops": 0.0})
    assert [s.name for s in plan] == ["identity"]
    # Below threshold but identity (0.54) is still ≥ 0.4 default-floor →
    # the all-low fallback does NOT fire; we just return an empty list and
    # let the orchestrator decide.
    plan = _build_activation_list({"identity": 0.54, "commercial": 0.0, "ops": 0.0})
    assert plan == []
    # Identity below 0.4 + others 0 → all-low fallback kicks in → ops default.
    plan = _build_activation_list({"identity": 0.39, "commercial": 0.0, "ops": 0.0})
    assert [s.name for s in plan] == ["ops"]


def test_activation_thresholds_boundary_commercial() -> None:
    plan = _build_activation_list({"identity": 0.0, "commercial": 0.65, "ops": 0.0})
    assert [s.name for s in plan] == ["commercial"]
    # Just below the threshold but commercial sits above the all-low floor (0.4)
    # so we DON'T trigger the ops default — we just produce nothing.
    plan = _build_activation_list({"identity": 0.0, "commercial": 0.5, "ops": 0.0})
    assert plan == []


def test_activation_thresholds_boundary_ops() -> None:
    plan = _build_activation_list({"identity": 0.0, "commercial": 0.0, "ops": 0.60})
    assert [s.name for s in plan] == ["ops"]
    # ops (0.59) is ≥ 0.4 floor but below threshold → no extractors and no
    # fallback (all-low rule requires every dim < 0.4).
    plan = _build_activation_list({"identity": 0.0, "commercial": 0.0, "ops": 0.59})
    assert plan == []
    # Drop ops below the floor → all three below 0.4 → ops fallback fires.
    plan = _build_activation_list({"identity": 0.0, "commercial": 0.0, "ops": 0.39})
    assert [s.name for s in plan] == ["ops"]


def test_activation_all_low_defaults_to_ops() -> None:
    """All three dimensions clearly absent → still emit ops as a memory draft."""
    plan = _build_activation_list({"identity": 0.1, "commercial": 0.1, "ops": 0.1})
    assert [s.name for s in plan] == ["ops"]
    # The selection's confidence reflects the actual ops heuristic, not 1.0.
    assert plan[0].confidence == pytest.approx(0.1)


def test_activation_multi_dimension() -> None:
    """All three above threshold → all three activate, in stable identity→commercial→ops order."""
    plan = _build_activation_list({"identity": 0.9, "commercial": 0.9, "ops": 0.9})
    assert [s.name for s in plan] == ["identity", "commercial", "ops"]


# ---------- review_required ----------------------------------------------


def test_review_required_high_confidence() -> None:
    """Any dim > 0.85 → review_required."""
    assert _needs_review("looks fine", {"identity": 0.9, "commercial": 0.0, "ops": 0.0})


def test_review_required_conflict_keyword() -> None:
    assert _needs_review("信号有冲突", {"identity": 0.5, "commercial": 0.5, "ops": 0.5})
    assert _needs_review("结果不一致", {"identity": 0.5, "commercial": 0.5, "ops": 0.5})


def test_review_required_quiet_case_false() -> None:
    assert not _needs_review("正常合同", {"identity": 0.6, "commercial": 0.7, "ops": 0.0})


# ---------- _normalize_targets -------------------------------------------


def test_normalize_targets_clamps_and_fills_missing() -> None:
    out = _normalize_targets({"identity": 1.5, "commercial": -0.2, "extra": 0.9})
    assert out == {"identity": 1.0, "commercial": 0.0, "ops": 0.0}


def test_normalize_targets_handles_non_dict() -> None:
    assert _normalize_targets(None) == {"identity": 0.0, "commercial": 0.0, "ops": 0.0}
    assert _normalize_targets("string") == {"identity": 0.0, "commercial": 0.0, "ops": 0.0}


# ---------- LLM happy path ------------------------------------------------


@pytest.mark.asyncio
async def test_plan_extraction_uses_llm_output(monkeypatch) -> None:
    """LLM returns a clean tool_use input → planner trusts the scores
    (after re-applying activation thresholds server-side)."""
    captured: dict[str, Any] = {}

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        captured["purpose"] = purpose
        captured["model"] = kwargs.get("model")
        captured["tools"] = kwargs.get("tools")
        captured["document_id"] = kwargs.get("document_id")
        captured["prompt"] = messages[0]["content"][0]["text"]
        return _make_response(
            {
                "targets": {"identity": 0.92, "commercial": 0.18, "ops": 0.73},
                "extractors": [
                    {"name": "identity", "confidence": 0.92},
                    {"name": "ops", "confidence": 0.73},
                ],
                "reason": "包含公司名、联系人电话以及客户承诺付款时间",
                "review_required": False,
            }
        )

    monkeypatch.setattr(planner_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session, ocr="测试有限公司 王经理 13800000000 周五前发货"
        )
        plan = await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
            modality="image",
            source_hint="camera",
        )
        await session.commit()

        assert isinstance(plan, IngestPlan)
        # LLM scores propagate to targets
        assert plan.targets["identity"] == pytest.approx(0.92)
        assert plan.targets["commercial"] == pytest.approx(0.18)
        assert plan.targets["ops"] == pytest.approx(0.73)
        # Activation list is server-derived: identity (0.92) and ops (0.73)
        # qualify, commercial (0.18) does not.
        names = sorted(s.name for s in plan.extractors)
        assert names == ["identity", "ops"]
        # >0.85 on identity → review_required even though LLM said False
        assert plan.review_required is True
        # The reason is preserved verbatim
        assert "公司" in plan.reason

        # Confirm the LLM was called for the right purpose with our tool
        assert captured["purpose"] == "ingest_plan"
        assert captured["document_id"] == doc.id
        assert captured["tools"][0]["name"] == PLANNER_TOOL_NAME
        # The prompt must include heuristic scores AND OCR text snippet
        assert "启发式打分" in captured["prompt"]
        assert "测试有限公司" in captured["prompt"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_plan_extraction_llm_low_scores_trigger_default_ops(monkeypatch) -> None:
    """LLM agrees nothing is here → planner still emits an ops fallback."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "targets": {"identity": 0.05, "commercial": 0.02, "ops": 0.03},
                "extractors": [],
                "reason": "看起来是无业务相关的纯文本",
                "review_required": False,
            }
        )

    monkeypatch.setattr(planner_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="今天天气不错")
        plan = await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text="今天天气不错",
            modality="text",
            source_hint="pasted_text",
        )
        await session.commit()

        # All three < 0.4 → ops default kicks in
        assert [s.name for s in plan.extractors] == ["ops"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_plan_extraction_llm_explicit_review_flag_respected(monkeypatch) -> None:
    """LLM says review_required=True even with mid-range confidences → preserved."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "targets": {"identity": 0.6, "commercial": 0.7, "ops": 0.3},
                "extractors": [],
                "reason": "正常合同",
                "review_required": True,
            }
        )

    monkeypatch.setattr(planner_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="some contract text")
        plan = await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text="some contract text",
            modality="pdf",
            source_hint="file",
        )
        await session.commit()

        assert plan.review_required is True
        # identity(0.6) ≥ 0.55, commercial(0.7) ≥ 0.65 → both activate
        assert sorted(s.name for s in plan.extractors) == ["commercial", "identity"]
    finally:
        await session.close()
        await engine.dispose()


# ---------- LLM fallback --------------------------------------------------


@pytest.mark.asyncio
async def test_plan_extraction_falls_back_when_llm_raises(monkeypatch) -> None:
    """LLMCallFailed → fall back to heuristic, force review_required."""

    async def boom(messages, *, purpose, session, **kwargs):
        raise LLMCallFailed("upstream timeout")

    monkeypatch.setattr(planner_module, "call_claude", boom)

    session, engine = await _make_session()
    try:
        text = (
            "测试有限公司\n王经理 销售总监 13800000000 wang@test.com\n"
            "上海市浦东新区联系人地址"
        )
        doc = await _make_doc(session, ocr=text)
        plan = await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text=text,
            modality="image",
            source_hint="file",
        )
        await session.commit()

        # Heuristic-driven targets — identity should clear its threshold
        assert plan.targets["identity"] >= 0.55
        # Activation honors the same rules even on the fallback path
        names = [s.name for s in plan.extractors]
        assert "identity" in names
        # Fallback always asks for human review
        assert plan.review_required is True
        assert "fallback" in plan.reason
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_plan_extraction_falls_back_when_extraction_parse_fails(monkeypatch) -> None:
    """Even if call_claude returns 200 but the response has no usable
    tool_use block, ``extract_tool_use_input`` raises and the planner
    falls back to heuristic + review."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        # Response with no tool_use block AND no fallback JSON in text
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="oops")])

    monkeypatch.setattr(planner_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="一些无业务相关的文字")
        plan = await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text="一些无业务相关的文字",
            modality="text",
            source_hint="pasted_text",
        )
        await session.commit()

        # Fallback branch
        assert "fallback" in plan.reason
        assert plan.review_required is True
        # Default-ops still fires because heuristic is all-low
        assert [s.name for s in plan.extractors] == ["ops"]
    finally:
        await session.close()
        await engine.dispose()


# ---------- progress emit -------------------------------------------------


@pytest.mark.asyncio
async def test_plan_extraction_emits_progress(monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    async def fake_progress(stage: str, message: str) -> None:
        events.append((stage, message))

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "targets": {"identity": 0.9, "commercial": 0.0, "ops": 0.0},
                "extractors": [{"name": "identity", "confidence": 0.9}],
                "reason": "looks like a card",
                "review_required": True,
            }
        )

    monkeypatch.setattr(planner_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="测试有限公司")
        await plan_extraction(
            session=session,
            document_id=doc.id,
            ocr_text="测试有限公司",
            modality="image",
            source_hint="camera",
            progress=fake_progress,
        )
        await session.commit()

        stages = [s for s, _ in events]
        assert stages == ["plan", "plan_done"]
    finally:
        await session.close()
        await engine.dispose()
