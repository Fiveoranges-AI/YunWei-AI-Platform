"""Anthropic Claude wrapper.

Single entry point: `call_claude(messages, *, purpose, session, ...) -> Message`.

- Retries 3× on 429/5xx/timeout with exponential backoff. 4xx fails immediately.
- Always writes one row to llm_calls with request, response, tokens, latency,
  cost, retries, error. Sanitizes base64 payloads so the row stays compact.
- No stub fallback: missing/invalid key raises LLMCallFailed loudly. Tests
  monkeypatch this module's `call_claude` instead.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any
from uuid import UUID

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    RateLimitError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.models import LLMCall

logger = logging.getLogger(__name__)


# Defaults read from settings; callers may override per-call. Kept as
# module-level helpers so callers can do `model=parse_model()` while still
# letting tests monkeypatch settings.
def parse_model() -> str:
    return settings.model_parse


def qa_model() -> str:
    return settings.model_qa


def vision_model() -> str:
    return settings.model_vision


# Backwards-compatible module attributes (used by older test fixtures and a
# few callers that import these directly). Resolve at call time via __getattr__.
def __getattr__(name: str):
    if name == "PARSE_MODEL":
        return settings.model_parse
    if name == "QA_MODEL":
        return settings.model_qa
    if name == "VISION_MODEL":
        return settings.model_vision
    raise AttributeError(name)


class LLMCallFailed(Exception):
    pass


# Approximate USD per token (input, output). Update when prices change.
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    # Anthropic Claude (Dec 2025 list price)
    "claude-sonnet-4-6": (3.0e-6, 15.0e-6),
    "claude-opus-4-7": (15.0e-6, 75.0e-6),
    "claude-haiku-4-5-20251001": (0.8e-6, 4.0e-6),
    # DeepSeek v4 — rough public rates (RMB → USD); update when DeepSeek publishes new pricing
    "deepseek-v4-pro": (0.27e-6, 1.10e-6),
    "deepseek-v4-flash": (0.07e-6, 0.27e-6),
}


_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise LLMCallFailed("ANTHROPIC_API_KEY not set; cannot call upstream LLM")
        kwargs: dict = {"api_key": settings.anthropic_api_key}
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        _client = AsyncAnthropic(**kwargs)
    return _client


def _reset_client_for_tests() -> None:
    """Allow tests to swap key by clearing the cached client."""
    global _client
    _client = None


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or 500 <= exc.status_code < 600
    return False


def _approx_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    in_rate, out_rate = _PRICE_TABLE.get(model, (3.0e-6, 15.0e-6))
    return round(tokens_in * in_rate + tokens_out * out_rate, 6)


def _sanitize_request(req: dict) -> dict:
    """Replace large base64 blobs with size markers before persisting."""
    out = copy.deepcopy(req)
    for msg in out.get("messages", []):
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            src = block.get("source")
            if isinstance(src, dict) and "data" in src and len(str(src["data"])) > 256:
                src["data"] = f"<base64 omitted, {len(src['data'])} chars>"
    return out


def _is_deepseek_compat_endpoint() -> bool:
    """Truthy when ANTHROPIC_BASE_URL points at a non-Anthropic upstream
    (DeepSeek today; could be others later). Used to switch the tool-call
    strategy because DeepSeek's Anthropic-compat tool_use is unreliable —
    it routinely returns a tool_use block with empty input."""
    return bool(
        settings.anthropic_base_url
        and "api.anthropic.com" not in settings.anthropic_base_url
    )


def _switch_tools_to_json_mode(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Convert a tool_use call into a 'return JSON' prompt for upstreams
    where tool_use is unreliable. Mutates messages: appends the tool's
    JSON schema and a 'reply with JSON only' instruction to the last user
    text block. Returns the new messages list."""
    import copy
    import json as _json

    if not tools:
        return messages
    schema = tools[0].get("input_schema") or {}
    suffix = (
        "\n\n## 输出格式（重要）\n"
        "**直接返回一个 JSON 对象**，不要包裹在 ```json ``` 里，不要任何前后文字。\n"
        "JSON 必须严格符合下面这个 schema：\n\n"
        + _json.dumps(schema, ensure_ascii=False, indent=2)
    )
    new_messages = copy.deepcopy(messages)
    for msg in reversed(new_messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = content + suffix
            return new_messages
        if isinstance(content, list):
            for block in reversed(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    block["text"] = block.get("text", "") + suffix
                    return new_messages
            content.append({"type": "text", "text": suffix})
            return new_messages
    # No user message to attach to (shouldn't happen) — append a fresh one.
    new_messages.append({"role": "user", "content": suffix})
    return new_messages


async def call_claude(
    messages: list[dict[str, Any]],
    *,
    purpose: str,
    session: AsyncSession,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    max_tokens: int = 4096,
    temperature: float | None = None,
    document_id: UUID | None = None,
) -> Any:
    """Call Claude. Always writes to llm_calls. Raises LLMCallFailed on failure."""
    client = _get_client()
    if model is None:
        model = settings.model_parse

    # DeepSeek-compat endpoints: drop tools and ask for JSON in text instead.
    # extract_tool_use_input has a fallback that parses the assistant's text
    # for a JSON object, so downstream callers don't need to change.
    if _is_deepseek_compat_endpoint() and tools:
        messages = _switch_tools_to_json_mode(messages, tools)
        tools = None
        tool_choice = None

    request_payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools is not None:
        request_payload["tools"] = tools
    if tool_choice is not None:
        request_payload["tool_choice"] = tool_choice
    if temperature is not None:
        request_payload["temperature"] = temperature

    last_exc: Exception | None = None
    response: Any = None
    retries = 0
    t0 = time.monotonic()

    for attempt in range(3):
        retries = attempt
        try:
            response = await client.messages.create(**request_payload)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if not _should_retry(exc) or attempt == 2:
                break
            backoff = (2 ** attempt) + 0.1 * attempt
            logger.warning(
                "call_claude attempt %d failed (%s); retry in %.1fs",
                attempt + 1, type(exc).__name__, backoff,
            )
            await asyncio.sleep(backoff)

    latency_ms = int((time.monotonic() - t0) * 1000)
    sanitized_req = _sanitize_request(request_payload)

    if response is None:
        log = LLMCall(
            model=model,
            purpose=purpose,
            document_id=document_id,
            request_payload=sanitized_req,
            response_payload=None,
            tokens_in=None,
            tokens_out=None,
            latency_ms=latency_ms,
            cost_usd=None,
            error=f"{type(last_exc).__name__}: {last_exc!s}"[:1000],
            retries=retries,
        )
        session.add(log)
        await session.flush()
        raise LLMCallFailed(
            f"Claude call failed after {retries + 1} attempts: {last_exc!r}"
        ) from last_exc

    tokens_in = getattr(response.usage, "input_tokens", 0) or 0
    tokens_out = getattr(response.usage, "output_tokens", 0) or 0
    cost = _approx_cost_usd(model, tokens_in, tokens_out)

    log = LLMCall(
        model=model,
        purpose=purpose,
        document_id=document_id,
        request_payload=sanitized_req,
        response_payload=response.model_dump(),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        cost_usd=cost,
        error=None,
        retries=retries,
    )
    session.add(log)
    await session.flush()
    return response


def extract_tool_use_input(response: Any, tool_name: str) -> dict[str, Any]:
    """Pull the structured input from a tool_use response block.

    Compatibility quirks:
    - DeepSeek sometimes nests the tool arguments inside a single wrapper key
      derived from the tool name (``{"contract_extraction": {...}}``); we
      unwrap that.
    - DeepSeek occasionally returns a tool_use block with empty input ``{}``
      and dumps the actual structured payload as a JSON code block in a
      text block instead. We fall back to scanning text blocks for the first
      ```json fenced block (or a bare top-level object) and parse it.
    """
    tool_input: dict[str, Any] | None = None
    for block in response.content:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use" and getattr(block, "name", None) == tool_name:
            tool_input = dict(block.input)
            if len(tool_input) == 1:
                key, val = next(iter(tool_input.items()))
                expected_wrapper = tool_name.removeprefix("submit_")
                if (
                    isinstance(val, dict)
                    and (key == expected_wrapper or key == tool_name)
                ):
                    tool_input = val
            break

    if tool_input:
        return tool_input

    # Fallback: DeepSeek may have stuffed the JSON into a text block.
    fallback = _try_extract_json_from_text(extract_text(response))
    if fallback is not None:
        return fallback

    if tool_input is not None:
        # The model returned an empty tool_use block AND no usable JSON in text.
        return tool_input
    raise LLMCallFailed(
        f"response did not contain expected tool_use block for {tool_name!r}"
    )


def _try_extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of a JSON object from free text. Looks for a
    fenced ``` ```json ``` block first, then for the first balanced
    top-level ``{...}`` substring. Returns None on any failure."""
    if not text:
        return None
    import json
    import re

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Fall back to scanning for a balanced top-level object.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
                    break
        start = text.find("{", start + 1)
    return None


def extract_text(response: Any) -> str:
    """Pull plain text from a message; concat all text blocks."""
    parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)
