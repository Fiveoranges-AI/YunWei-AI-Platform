"""Data-center assistant tests (docs/data-layer.md §3.3).

Covers the tool-dispatch loop and the /api/data/assistant/* endpoints
without hitting the live Anthropic API. We monkeypatch
``anthropic.Anthropic`` to return a scripted sequence of responses so
the loop's behavior is deterministic and reviewable.
"""
from __future__ import annotations
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.data_layer import assistant as assistant_mod, ingest, paths
from platform_app.main import app
from platform_app.settings import settings


# ─── fixtures ───────────────────────────────────────────────────

@pytest.fixture
def tmp_data_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def http_client():
    return TestClient(app)


@pytest.fixture
def user_session(tmp_data_root):
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_eason", "eason", auth.hash_password("p"), "Eason", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "Yinhu", "Yinhu", now),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,'http://x','s','k',%s,%s)",
        ("yinhu", "x", "Yinhu", "u_x", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u_eason','yinhu','member',%s)", (now,),
    )
    sid, _ = auth.create_session("u_eason", "127.0.0.1", "test")
    return sid


def _make_xlsx(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, sheet_name="Sheet1", index=False)
    return buf.getvalue()


# ─── Mock the Anthropic SDK ─────────────────────────────────────
#
# Each scripted response is a list of content blocks; the mock replays
# them in order across successive client.messages.create calls.

@dataclass
class _MockBlock:
    type: str
    text: str | None = None
    name: str | None = None
    input: dict | None = None
    id: str | None = None


@dataclass
class _MockUsage:
    input_tokens: int = 100
    output_tokens: int = 30
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _MockResponse:
    content: list[_MockBlock]
    stop_reason: str
    usage: _MockUsage


class _MockMessages:
    def __init__(self, scripted: list[_MockResponse]):
        self.scripted = list(scripted)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        # Deep-copy the messages list so later mutations in the loop
        # don't retroactively change what we recorded.
        import copy
        snapshot = {**kwargs, "messages": copy.deepcopy(kwargs["messages"])}
        self.calls.append(snapshot)
        if not self.scripted:
            raise AssertionError("No more scripted responses")
        return self.scripted.pop(0)


class _MockAnthropic:
    def __init__(self, scripted: list[_MockResponse]):
        self.messages = _MockMessages(scripted)


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Stub anthropic.Anthropic — call ``.script(responses)`` per test
    to control what the model returns."""
    holder = {"client": None}

    def factory(responses):
        client = _MockAnthropic(responses)
        holder["client"] = client

        def make(_self=None, **_kw):
            return client

        # Patch the constructor used inside assistant.chat()
        monkeypatch.setattr(
            "platform_app.data_layer.assistant.anthropic.Anthropic",
            lambda **kw: client,
        )
        return client

    factory.holder = holder
    return factory


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setattr(settings, "assistant_api_key", "sk-test-fake")
    yield


# ─── Tool dispatch (no LLM) ─────────────────────────────────────

def test_dispatch_data_health_uninitialized(tmp_data_root):
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    out = assistant_mod._dispatch_tool(
        "data_health", {}, client_id="yinhu", user_id="u",
    )
    assert out == {"initialized": False, "tables": {}}


def test_dispatch_data_health_initialized(tmp_data_root):
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    from platform_app.data_layer import silver_db
    silver_db.ensure_silver_tables("yinhu")
    out = assistant_mod._dispatch_tool(
        "data_health", {}, client_id="yinhu", user_id="u",
    )
    assert out["initialized"] is True
    assert set(out["tables"]) == {"customers", "orders", "order_items",
                                  "order_source_records", "boss_query_logs"}


def test_dispatch_list_bronze_files(tmp_data_root):
    db.init()
    blob = _make_xlsx([{"name": "甲"}, {"name": "乙"}])
    ingest.ingest_excel(client_id="yinhu", original_filename="x.xlsx",
                        file_bytes=blob, uploaded_by="u")
    out = assistant_mod._dispatch_tool(
        "list_bronze_files", {}, client_id="yinhu", user_id="u",
    )
    assert len(out["files"]) == 1
    assert out["files"][0]["row_count"] == 2


def test_dispatch_create_mapping_writes_silver(tmp_data_root):
    db.init()
    blob = _make_xlsx([{"客户名": "甲公司"}, {"客户名": "乙公司"}])
    res = ingest.ingest_excel(client_id="yinhu", original_filename="x.xlsx",
                              file_bytes=blob, uploaded_by="u")
    bid = res.sheets[0].bronze_file_id

    out = assistant_mod._dispatch_tool(
        "create_mapping_and_transform",
        {
            "bronze_file_id": bid,
            "silver_table": "customers",
            "column_map": {"客户名": "display_name"},
        },
        client_id="yinhu", user_id="u_eason",
    )
    assert out["rows_written"] == 2
    assert out["silver_table"] == "customers"


def test_dispatch_unknown_tool_returns_error(tmp_data_root):
    db.init()
    out = assistant_mod._dispatch_tool(
        "no_such_tool", {}, client_id="yinhu", user_id="u",
    )
    assert "error" in out


# ─── chat() tool loop ───────────────────────────────────────────

def test_chat_simple_text_response(tmp_data_root, with_api_key, mock_anthropic):
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="text", text="您好,有什么需要帮忙的?")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    result = assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="你好",
    )
    assert "您好" in result.final_text
    assert result.tool_invocations == []
    assert result.usage["input_tokens"] == 100


def test_chat_runs_tool_and_responds(tmp_data_root, with_api_key, mock_anthropic):
    """Model calls list_bronze_files, sees the result, then replies."""
    db.init()
    blob = _make_xlsx([{"name": "甲"}])
    ingest.ingest_excel(client_id="yinhu", original_filename="x.xlsx",
                        file_bytes=blob, uploaded_by="u_eason")

    mock_anthropic([
        _MockResponse(
            content=[
                _MockBlock(type="tool_use", id="toolu_1",
                           name="list_bronze_files", input={}),
            ],
            stop_reason="tool_use",
            usage=_MockUsage(),
        ),
        _MockResponse(
            content=[_MockBlock(type="text", text="您上传了 1 个 bronze 文件")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    result = assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="我上传了什么?",
    )
    assert "1 个" in result.final_text
    assert len(result.tool_invocations) == 1
    assert result.tool_invocations[0]["name"] == "list_bronze_files"
    assert result.tool_invocations[0]["is_error"] is False


def test_chat_tool_error_surfaces_to_model(tmp_data_root, with_api_key,
                                            mock_anthropic):
    """A tool that throws is reported back via tool_result with is_error=True
    so the model can recover."""
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    mock_anthropic([
        _MockResponse(
            content=[_MockBlock(
                type="tool_use", id="toolu_1",
                name="get_bronze_preview",
                input={"bronze_file_id": "deadbeefdeadbeefdeadbeefdeadbeef"},
            )],
            stop_reason="tool_use",
            usage=_MockUsage(),
        ),
        _MockResponse(
            content=[_MockBlock(type="text", text="找不到该文件,请确认 id")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    result = assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="预览那个文件",
    )
    assert result.tool_invocations[0]["is_error"] is True
    assert "找不到" in result.final_text


def test_chat_iteration_cap_short_circuits(tmp_data_root, with_api_key,
                                            mock_anthropic, monkeypatch):
    """If the model never returns end_turn, the loop bails after the
    configured iteration cap rather than running forever."""
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    monkeypatch.setattr(settings, "assistant_max_tool_iterations", 2)
    # Script 2 tool_use responses; the third call would error since the
    # mock is empty — the cap should prevent that.
    mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="tool_use", id=f"toolu_{i}",
                                name="data_health", input={})],
            stop_reason="tool_use",
            usage=_MockUsage(),
        )
        for i in range(2)
    ])
    result = assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="...",
    )
    assert len(result.tool_invocations) == 2


def test_chat_first_turn_injects_tenant_context(tmp_data_root, with_api_key,
                                                 mock_anthropic):
    """First user turn carries a [当前租户状态] preamble so the model has
    live state without needing a tool call for trivial 'do I have data' Qs."""
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    client = mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="text", text="ok")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="hello",
    )
    sent_messages = client.messages.calls[0]["messages"]
    assert len(sent_messages) == 1
    assert "当前租户状态" in sent_messages[0]["content"]
    assert "[用户消息]" in sent_messages[0]["content"]


def test_chat_subsequent_turn_does_not_reinject_context(
    tmp_data_root, with_api_key, mock_anthropic,
):
    """When history is non-empty, the new turn is appended verbatim — the
    tenant snapshot is not duplicated."""
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    client = mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="text", text="ok")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    history = [
        {"role": "user", "content": "之前的话"},
        {"role": "assistant", "content": [{"type": "text", "text": "好"}]},
    ]
    assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=history,
        user_text="继续",
    )
    sent_messages = client.messages.calls[0]["messages"]
    assert sent_messages[-1] == {"role": "user", "content": "继续"}
    assert "当前租户状态" not in sent_messages[-1]["content"]


def test_chat_uses_caching_and_adaptive_thinking(
    tmp_data_root, with_api_key, mock_anthropic,
):
    """Verify the request payload sets cache_control on system + adaptive
    thinking — these are the perf knobs from the claude-api skill."""
    db.init()
    paths.ensure_tenant_dirs("yinhu")
    client = mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="text", text="ok")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    assistant_mod.chat(
        client_id="yinhu", user_id="u_eason", history=[],
        user_text="hi",
    )
    call = client.messages.calls[0]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["model"] == settings.assistant_model


# ─── HTTP layer ─────────────────────────────────────────────────

def test_chat_endpoint_requires_acl(http_client, user_session):
    sid = user_session
    r = http_client.post(
        "/api/data/assistant/chat",
        json={"client": "somebody_else", "message": "hi"},
        cookies={"app_session": sid},
    )
    assert r.status_code == 403


def test_chat_endpoint_503_when_no_api_key(http_client, user_session, monkeypatch):
    monkeypatch.setattr(settings, "assistant_api_key", "")
    r = http_client.post(
        "/api/data/assistant/chat",
        json={"client": "yinhu", "message": "hi"},
        cookies={"app_session": user_session},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "assistant_disabled"


def test_chat_endpoint_succeeds_end_to_end(
    http_client, user_session, with_api_key, mock_anthropic, tmp_data_root,
):
    paths.ensure_tenant_dirs("yinhu")
    mock_anthropic([
        _MockResponse(
            content=[_MockBlock(type="text", text="您好")],
            stop_reason="end_turn",
            usage=_MockUsage(),
        ),
    ])
    r = http_client.post(
        "/api/data/assistant/chat",
        json={"client": "yinhu", "message": "你好"},
        cookies={"app_session": user_session},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["final_text"] == "您好"
    assert "messages" in body


def test_assistant_status_reflects_config(http_client, user_session, monkeypatch):
    monkeypatch.setattr(settings, "assistant_api_key", "")
    r1 = http_client.get("/api/data/assistant/status",
                         cookies={"app_session": user_session})
    assert r1.json()["enabled"] is False

    monkeypatch.setattr(settings, "assistant_api_key", "sk-fake")
    r2 = http_client.get("/api/data/assistant/status",
                         cookies={"app_session": user_session})
    assert r2.json()["enabled"] is True
    assert r2.json()["model"] == settings.assistant_model
