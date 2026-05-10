"""Tests for the ops extractor (``services/ingest/extractors/ops.py``).

Covers:
- LLM happy path: WeChat chat OCR → ``OpsDraft`` with events + commitments
- Pure contract clauses (non-ops document) → all five arrays empty + the
  LLM's "非运营文档" warning is preserved verbatim
- Silent all-empty fallback: if the LLM returned all empties but forgot the
  "非运营" declaration, we synthesise a warning so reviewers know why the
  panel is empty
- LLM-side errors propagate up
- ``call_claude`` is invoked text-only (no image content blocks)
- ``ops_extract`` (start) and ``ops_done`` (finish) progress callbacks fire

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_planner.py`` /
``test_evidence.py`` / ``test_identity_extractor.py`` /
``test_commercial_extractor.py``.
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

import yinhu_brain.models  # noqa: F401 — register SQLAlchemy mappers
from yinhu_brain.db import Base
from yinhu_brain.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
)
from yinhu_brain.services.ingest.extractors import ops as ops_module
from yinhu_brain.services.ingest.extractors.ops import (
    OPS_TOOL_NAME,
    _validate_non_ops_warning,
    extract_ops,
    ops_tool,
)
from yinhu_brain.services.ingest.unified_schemas import OpsDraft


# ---------- helpers -------------------------------------------------------


async def _make_session() -> tuple[AsyncSession, Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return session, engine


async def _make_doc(session: AsyncSession, ocr: str = "") -> Document:
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
        name=OPS_TOOL_NAME,
        input=tool_input,
    )
    return SimpleNamespace(content=[block])


# ---------- ops_tool schema ----------------------------------------------


def test_ops_tool_schema_shape() -> None:
    tool = ops_tool()
    assert tool["name"] == OPS_TOOL_NAME
    schema = tool["input_schema"]
    props = schema["properties"]
    # Must surface all OpsDraft top-level fields.
    for key in (
        "summary",
        "events",
        "commitments",
        "tasks",
        "risk_signals",
        "memory_items",
        "field_provenance",
        "confidence_overall",
    ):
        assert key in props, f"ops_tool schema missing {key}"
    # Must NOT surface identity / commercial dimensions (those belong to
    # other extractors — keeping them out is the whole point of splitting).
    assert "customer" not in props
    assert "contacts" not in props
    assert "order" not in props
    assert "contract" not in props
    # ``_strip_titles`` should have removed the ``title`` keys pydantic emits.
    assert "title" not in schema


# ---------- _validate_non_ops_warning ------------------------------------


def test_non_ops_warning_added_when_silent() -> None:
    """All five arrays empty but no "非运营" warning → we add one."""
    draft = OpsDraft.model_validate(
        {
            "summary": "",
            "events": [],
            "commitments": [],
            "tasks": [],
            "risk_signals": [],
            "memory_items": [],
            "field_provenance": [],
            "confidence_overall": 0.2,
            "parse_warnings": [],
        }
    )
    _validate_non_ops_warning(draft)
    assert any(
        "未抽出" in w or "非运营" in w for w in draft.parse_warnings
    )


def test_non_ops_warning_preserves_existing_declaration() -> None:
    """If the LLM already added a 非运营 warning, we don't pile on a duplicate."""
    draft = OpsDraft.model_validate(
        {
            "summary": "纯合同条款",
            "events": [],
            "commitments": [],
            "tasks": [],
            "risk_signals": [],
            "memory_items": [],
            "field_provenance": [],
            "confidence_overall": 0.1,
            "parse_warnings": ["非运营文档"],
        }
    )
    _validate_non_ops_warning(draft)
    assert draft.parse_warnings == ["非运营文档"]


def test_non_ops_warning_quiet_when_anything_extracted() -> None:
    """Any non-empty array → no synthetic warning."""
    draft = OpsDraft.model_validate(
        {
            "summary": "客户来电沟通",
            "events": [
                {
                    "title": "客户致电",
                    "event_type": "call",
                    "occurred_at": None,
                    "description": "讨论交期",
                    "raw_excerpt": "客户来电",
                    "confidence": 0.7,
                }
            ],
            "commitments": [],
            "tasks": [],
            "risk_signals": [],
            "memory_items": [],
            "field_provenance": [],
            "confidence_overall": 0.7,
            "parse_warnings": [],
        }
    )
    _validate_non_ops_warning(draft)
    assert draft.parse_warnings == []


# ---------- extract_ops happy paths --------------------------------------


@pytest.mark.asyncio
async def test_extract_ops_returns_full_draft(monkeypatch) -> None:
    """Standard WeChat-chat flow: LLM returns clean tool_use input → parsed
    OpsDraft with events + commitments populated."""
    captured: dict[str, Any] = {}

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        captured["purpose"] = purpose
        captured["model"] = kwargs.get("model")
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        captured["document_id"] = kwargs.get("document_id")
        captured["max_tokens"] = kwargs.get("max_tokens")
        captured["temperature"] = kwargs.get("temperature")
        captured["messages"] = messages
        return _make_response(
            {
                "summary": "客户许总在微信里确认周三前付清尾款 5 万，并抱怨上批包装质量差。",
                "events": [
                    {
                        "title": "客户抱怨包装质量",
                        "event_type": "complaint",
                        "occurred_at": None,
                        "description": "上批货外包装破损，客户在微信沟通时提出。",
                        "raw_excerpt": "上批货外包装破损了好几个",
                        "confidence": 0.85,
                    }
                ],
                "commitments": [
                    {
                        "summary": "客户承诺周三前付清尾款 5 万",
                        "description": "许总确认本周三前完成尾款支付。",
                        "direction": "customer_to_us",
                        "due_date": "2025-11-12",
                        "raw_excerpt": "周三前我把剩下 5 万付了",
                        "confidence": 0.9,
                    }
                ],
                "tasks": [
                    {
                        "title": "下批发货时改用木箱包装",
                        "description": "回应客户对包装的投诉。",
                        "assignee": "陈工",
                        "due_date": None,
                        "priority": "high",
                        "raw_excerpt": "下次能不能换木箱",
                    }
                ],
                "risk_signals": [
                    {
                        "summary": "客户连续两批反映包装问题",
                        "description": "若不改进可能影响后续订单。",
                        "severity": "medium",
                        "kind": "quality",
                        "raw_excerpt": "上次也是这样",
                        "confidence": 0.7,
                    }
                ],
                "memory_items": [
                    {
                        "content": "客户决策人是采购总监许总",
                        "kind": "decision_maker",
                        "raw_excerpt": "我是许总",
                        "confidence": 0.8,
                    }
                ],
                "field_provenance": [
                    {
                        "path": "events[0].title",
                        "source_page": None,
                        "source_excerpt": "上批货外包装破损了好几个",
                    },
                    {
                        "path": "commitments[0].summary",
                        "source_page": None,
                        "source_excerpt": "周三前我把剩下 5 万付了",
                    },
                ],
                "confidence_overall": 0.82,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(ops_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session,
            ocr=(
                "许总：周三前我把剩下 5 万付了。\n"
                "我：好的。\n"
                "许总：上批货外包装破损了好几个，下次能不能换木箱"
            ),
        )
        draft = await extract_ops(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert isinstance(draft, OpsDraft)
        # All five dimensions populated.
        assert len(draft.events) == 1
        assert draft.events[0].event_type.value == "complaint"
        assert len(draft.commitments) == 1
        assert draft.commitments[0].direction.value == "customer_to_us"
        assert str(draft.commitments[0].due_date) == "2025-11-12"
        assert len(draft.tasks) == 1
        assert draft.tasks[0].assignee == "陈工"
        assert draft.tasks[0].priority.value == "high"
        assert len(draft.risk_signals) == 1
        assert draft.risk_signals[0].kind.value == "quality"
        assert len(draft.memory_items) == 1
        assert draft.memory_items[0].kind.value == "decision_maker"
        # summary + confidence threaded through unchanged.
        assert "尾款" in draft.summary
        assert draft.confidence_overall == pytest.approx(0.82)
        # No empty-extraction → no synthetic warning.
        assert draft.parse_warnings == []
        # Provenance threaded through unchanged.
        paths = {entry.path for entry in draft.field_provenance}
        assert "events[0].title" in paths
        assert "commitments[0].summary" in paths

        # The LLM was called with the expected purpose + model + tool spec.
        assert captured["purpose"] == "ops_extraction"
        assert captured["document_id"] == doc.id
        assert captured["temperature"] == 0
        assert captured["max_tokens"] == 8192
        tools = captured["tools"]
        assert tools[0]["name"] == OPS_TOOL_NAME
        assert captured["tool_choice"] == {
            "type": "tool",
            "name": OPS_TOOL_NAME,
        }

        # Critically: messages must be text-only (no image content block).
        assert len(captured["messages"]) == 1
        content = captured["messages"][0]["content"]
        assert isinstance(content, list)
        assert all(block.get("type") == "text" for block in content)
        # OCR text must be substituted into the prompt.
        joined = "".join(b.get("text", "") for b in content)
        assert "周三前我把剩下 5 万付了" in joined
    finally:
        await session.close()
        await engine.dispose()


# ---------- non-ops + silent-empty paths ---------------------------------


@pytest.mark.asyncio
async def test_extract_ops_pure_contract_returns_empty(monkeypatch) -> None:
    """Pure contract-clause document → LLM returns all-empty arrays + a
    "非运营文档" warning. The post-validation pass must NOT pile a duplicate
    warning on top."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "summary": "纯合同条款，无客户运营信息。",
                "events": [],
                "commitments": [],
                "tasks": [],
                "risk_signals": [],
                "memory_items": [],
                "field_provenance": [],
                "confidence_overall": 0.1,
                "parse_warnings": ["非运营文档"],
            }
        )

    monkeypatch.setattr(ops_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(
            session,
            ocr=(
                "第一条 本合同自双方签字盖章之日起生效。\n"
                "第二条 任何一方违约，应按未付金额日 0.5% 支付违约金。"
            ),
        )
        draft = await extract_ops(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        # All five arrays empty.
        assert draft.events == []
        assert draft.commitments == []
        assert draft.tasks == []
        assert draft.risk_signals == []
        assert draft.memory_items == []
        # Original 非运营文档 declaration preserved verbatim.
        assert "非运营文档" in draft.parse_warnings
        # And NOT duplicated by the synthetic fallback.
        assert len(draft.parse_warnings) == 1
        # Summary still populated.
        assert draft.summary
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_extract_ops_silent_empty_adds_fallback_warning(
    monkeypatch,
) -> None:
    """LLM returned all empties but forgot to say 非运营文档 → we add a
    synthetic warning so the reviewer knows the extractor was consulted."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "summary": "",
                "events": [],
                "commitments": [],
                "tasks": [],
                "risk_signals": [],
                "memory_items": [],
                "field_provenance": [],
                "confidence_overall": 0.2,
                "parse_warnings": [],
            }
        )

    monkeypatch.setattr(ops_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="一些没什么内容的文本")
        draft = await extract_ops(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
        )
        await session.commit()

        assert draft.events == []
        assert draft.commitments == []
        assert draft.tasks == []
        assert draft.risk_signals == []
        assert draft.memory_items == []
        assert any("未抽出" in w for w in draft.parse_warnings)
    finally:
        await session.close()
        await engine.dispose()


# ---------- error propagation --------------------------------------------


@pytest.mark.asyncio
async def test_extract_ops_propagates_llm_error(monkeypatch) -> None:
    """When ``call_claude`` raises, the extractor lets the exception bubble
    up — the orchestrator decides how to handle a failed dimension."""

    class BoomError(RuntimeError):
        pass

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        raise BoomError("upstream LLM is down")

    monkeypatch.setattr(ops_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    try:
        doc = await _make_doc(session, ocr="anything")
        with pytest.raises(BoomError):
            await extract_ops(
                session=session,
                document_id=doc.id,
                ocr_text=doc.ocr_text or "",
            )
    finally:
        await session.close()
        await engine.dispose()


# ---------- progress callbacks -------------------------------------------


@pytest.mark.asyncio
async def test_extract_ops_emits_progress(monkeypatch) -> None:
    """Both ``ops_extract`` (start) and ``ops_done`` (finish) stages must
    reach the progress callback."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return _make_response(
            {
                "summary": "",
                "events": [],
                "commitments": [],
                "tasks": [],
                "risk_signals": [],
                "memory_items": [],
                "field_provenance": [],
                "confidence_overall": 0.1,
                "parse_warnings": ["非运营文档"],
            }
        )

    monkeypatch.setattr(ops_module, "call_claude", fake_call_claude)

    session, engine = await _make_session()
    progress_events: list[tuple[str, str]] = []

    async def progress(stage: str, message: str) -> None:
        progress_events.append((stage, message))

    try:
        doc = await _make_doc(session, ocr="just a memo")
        await extract_ops(
            session=session,
            document_id=doc.id,
            ocr_text=doc.ocr_text or "",
            progress=progress,
        )
        await session.commit()

        stages = [stage for stage, _ in progress_events]
        assert "ops_extract" in stages
        assert "ops_done" in stages
    finally:
        await session.close()
        await engine.dispose()
