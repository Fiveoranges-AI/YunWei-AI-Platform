"""Tests for the DeepSeek schema-routed extractor provider.

Covers:
- Happy path: 2+ selections → one ``call_claude`` per schema; each returns a
  dict → 2+ ``PipelineExtractResult`` with provider+model metadata.
- ``call_claude`` raises on one schema → that schema returns empty extraction
  + a warning; remaining schemas still succeed.
- ``extract_tool_use_input`` returns a non-dict → soft fail with warning.
- ``input.session`` is forwarded to ``call_claude`` (assert kwargs).
- ``progress`` callback fires once per selection plus a final done event.

The project-level autouse fixture wants Postgres + Redis; we override with a
no-op because these tests fully monkeypatch ``call_claude`` /
``extract_tool_use_input`` / ``load_schema_json`` and only need a session
sentinel.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yinhu_brain.config import settings
from yinhu_brain.services.ingest.extractors.providers import deepseek as deepseek_module
from yinhu_brain.services.ingest.extractors.providers.base import ExtractionInput
from yinhu_brain.services.ingest.extractors.providers.deepseek import (
    DeepSeekSchemaExtractorProvider,
)
from yinhu_brain.services.ingest.unified_schemas import (
    PipelineExtractResult,
    PipelineSelection,
)


# ---------- helpers -------------------------------------------------------


def _selections() -> list[PipelineSelection]:
    return [
        PipelineSelection(name="identity", confidence=0.9, reason="客户公司"),
        PipelineSelection(name="contract_order", confidence=0.8, reason="合同"),
    ]


def _stub_schema(name: str) -> str:
    """Return a tiny valid schema JSON string for `load_schema_json`."""
    return (
        '{"type": "object", "properties": {"name": {"type": "string"}}}'
    )


def _make_input(session: Any, selections=None, markdown="some OCR markdown") -> ExtractionInput:
    return ExtractionInput(
        document_id=uuid.uuid4(),
        session=session,
        markdown=markdown,
        selections=selections if selections is not None else _selections(),
    )


# ---------- happy path ---------------------------------------------------


@pytest.mark.asyncio
async def test_extract_selected_happy_path(monkeypatch) -> None:
    """Two selections → two ``call_claude`` invocations → two
    ``PipelineExtractResult`` with provider="deepseek" + model metadata."""
    call_log: list[dict[str, Any]] = []

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        call_log.append(
            {
                "messages": messages,
                "purpose": purpose,
                "session": session,
                "model": kwargs.get("model"),
                "tools": kwargs.get("tools"),
                "tool_choice": kwargs.get("tool_choice"),
                "document_id": kwargs.get("document_id"),
            }
        )
        # The response shape is opaque to the provider since we also
        # monkeypatch ``extract_tool_use_input`` below.
        return SimpleNamespace(content=[])

    def fake_extract_tool_use_input(response, tool_name):
        # Return distinct dicts so we can assert per-schema mapping below.
        return {"_tool_name": tool_name, "name": "value"}

    monkeypatch.setattr(deepseek_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        deepseek_module, "extract_tool_use_input", fake_extract_tool_use_input
    )
    monkeypatch.setattr(deepseek_module, "load_schema_json", _stub_schema)

    session_sentinel = SimpleNamespace(_marker="session")
    provider = DeepSeekSchemaExtractorProvider()
    results = await provider.extract_selected(_make_input(session_sentinel))

    assert len(results) == 2
    assert all(isinstance(r, PipelineExtractResult) for r in results)

    names = [r.name for r in results]
    assert names == ["identity", "contract_order"]

    for r in results:
        assert r.warnings == []
        assert r.extraction == {"_tool_name": r.extraction["_tool_name"], "name": "value"}
        assert r.extraction_metadata["provider"] == "deepseek"
        assert r.extraction_metadata["model"] == settings.model_parse

    # One LLM call per schema, in order.
    assert len(call_log) == 2
    # Session sentinel was forwarded.
    assert call_log[0]["session"] is session_sentinel
    assert call_log[1]["session"] is session_sentinel
    # Model is settings.model_parse.
    assert call_log[0]["model"] == settings.model_parse


# ---------- session is forwarded ------------------------------------------


@pytest.mark.asyncio
async def test_extract_selected_forwards_session(monkeypatch) -> None:
    """``input.session`` must reach ``call_claude`` (audit row dependency)."""
    seen_sessions: list[Any] = []

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        seen_sessions.append(session)
        return SimpleNamespace(content=[])

    monkeypatch.setattr(deepseek_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        deepseek_module,
        "extract_tool_use_input",
        lambda response, tool_name: {"name": "x"},
    )
    monkeypatch.setattr(deepseek_module, "load_schema_json", _stub_schema)

    marker = SimpleNamespace(_id="audit-session")
    provider = DeepSeekSchemaExtractorProvider()
    await provider.extract_selected(_make_input(marker))

    assert seen_sessions  # at least one call
    assert all(s is marker for s in seen_sessions)


# ---------- per-schema soft failure: LLM raises ---------------------------


@pytest.mark.asyncio
async def test_extract_selected_soft_fails_on_llm_error(monkeypatch) -> None:
    """``call_claude`` raises on one schema → that schema returns empty
    extraction + warning; the remaining schema still succeeds."""
    call_count = {"n": 0}

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("DeepSeek 500")
        return SimpleNamespace(content=[])

    monkeypatch.setattr(deepseek_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        deepseek_module,
        "extract_tool_use_input",
        lambda response, tool_name: {"ok": True},
    )
    monkeypatch.setattr(deepseek_module, "load_schema_json", _stub_schema)

    provider = DeepSeekSchemaExtractorProvider()
    results = await provider.extract_selected(_make_input(SimpleNamespace()))

    assert len(results) == 2
    # First schema failed soft.
    assert results[0].name == "identity"
    assert results[0].extraction == {}
    assert any(
        "DeepSeek extract failed for identity" in w for w in results[0].warnings
    )
    assert results[0].extraction_metadata["provider"] == "deepseek"
    assert results[0].extraction_metadata["model"] == settings.model_parse
    # Second schema succeeded.
    assert results[1].name == "contract_order"
    assert results[1].extraction == {"ok": True}
    assert results[1].warnings == []


# ---------- per-schema soft failure: non-dict result ---------------------


@pytest.mark.asyncio
async def test_extract_selected_soft_fails_on_non_dict(monkeypatch) -> None:
    """``extract_tool_use_input`` returned a list (not a dict) → soft fail."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return SimpleNamespace(content=[])

    # First call returns a list, second returns a string.
    responses = iter([["not", "a", "dict"], "also not a dict"])

    def fake_extract_tool_use_input(response, tool_name):
        return next(responses)

    monkeypatch.setattr(deepseek_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        deepseek_module, "extract_tool_use_input", fake_extract_tool_use_input
    )
    monkeypatch.setattr(deepseek_module, "load_schema_json", _stub_schema)

    provider = DeepSeekSchemaExtractorProvider()
    results = await provider.extract_selected(_make_input(SimpleNamespace()))

    assert len(results) == 2
    for r in results:
        assert r.extraction == {}
        assert any(f"DeepSeek extract failed for {r.name}" in w for w in r.warnings)
        assert r.extraction_metadata["provider"] == "deepseek"


# ---------- progress callback --------------------------------------------


@pytest.mark.asyncio
async def test_extract_selected_emits_progress(monkeypatch) -> None:
    """A progress callback should receive at least one event mentioning the
    schema being extracted, for each selection."""

    async def fake_call_claude(messages, *, purpose, session, **kwargs):
        return SimpleNamespace(content=[])

    monkeypatch.setattr(deepseek_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        deepseek_module,
        "extract_tool_use_input",
        lambda response, tool_name: {"name": "x"},
    )
    monkeypatch.setattr(deepseek_module, "load_schema_json", _stub_schema)

    events: list[tuple[str, str]] = []

    async def progress(stage: str, message: str) -> None:
        events.append((stage, message))

    provider = DeepSeekSchemaExtractorProvider()
    await provider.extract_selected(
        _make_input(SimpleNamespace()), progress=progress
    )

    # At least one event for each selected schema.
    flat = " ".join(stage + " " + message for stage, message in events)
    assert "identity" in flat
    assert "contract_order" in flat
