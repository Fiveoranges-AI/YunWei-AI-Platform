from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override Postgres+Redis fixture
    yield


from yunwei_win.services.schema_ingest import llm_adapter  # noqa: E402
from yunwei_win.services.schema_ingest.llm_adapter import (  # noqa: E402
    DeepSeekCompleteJsonLLM,
)


@pytest.mark.asyncio
async def test_complete_json_calls_call_claude_with_tool_schema(monkeypatch):
    captured: dict = {}

    async def fake_call_claude(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return SimpleNamespace(name="fake-response")

    def fake_extract(response, tool_name):
        captured["tool_name_for_extract"] = tool_name
        return {"ok": True}

    monkeypatch.setattr(llm_adapter, "call_claude", fake_call_claude)
    monkeypatch.setattr(llm_adapter, "extract_tool_use_input", fake_extract)

    fake_session = SimpleNamespace()
    document_id = uuid4()
    adapter = DeepSeekCompleteJsonLLM(
        session=fake_session,  # type: ignore[arg-type]
        document_id=document_id,
    )

    response_schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    result = await adapter.complete_json(
        prompt="抽取", response_schema=response_schema
    )

    assert result == {"ok": True}
    assert captured["purpose"] == "schema_ingest:complete_json"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == 8192
    assert captured["session"] is fake_session
    assert captured["document_id"] == document_id
    tools = captured["tools"]
    assert len(tools) == 1
    assert tools[0]["input_schema"] == response_schema
    assert captured["tool_choice"]["name"] == tools[0]["name"]
    assert captured["tool_name_for_extract"] == tools[0]["name"]
    assert captured["messages"][0]["role"] == "user"
    assert captured["messages"][0]["content"][0]["text"] == "抽取"


@pytest.mark.asyncio
async def test_complete_json_rejects_non_dict_tool_input(monkeypatch):
    async def fake_call_claude(messages, **kwargs):
        return SimpleNamespace()

    def fake_extract(response, tool_name):
        return ["not", "a", "dict"]

    monkeypatch.setattr(llm_adapter, "call_claude", fake_call_claude)
    monkeypatch.setattr(llm_adapter, "extract_tool_use_input", fake_extract)

    adapter = DeepSeekCompleteJsonLLM(session=SimpleNamespace())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="complete_json expected dict"):
        await adapter.complete_json(prompt="x", response_schema={})
