"""HTTP-level identity boundary tests for ``ask_dedicated_runtime``.

These tests are deliberately separate from ``test_yunwei_win_assistant_runtime.py``
(which monkeypatches the forwarder entirely to test routing decisions).
Here we exercise the forwarder itself with ``respx`` to assert what
goes on the wire to the dedicated runtime:

- ``X-User-Id`` header is set from the ``user_id`` argument.
- ``X-Platform-Service`` header identifies the caller as ``yunwei-win``.
- The POST body does NOT contain ``enterprise_id`` — enterprise scope
  must stay server-side; we don't trust a runtime to honour it as a
  header / field.
- 4xx still returns the degraded payload (no exception).
- 5xx still raises ``DedicatedRuntimeError``.
- Transport errors (``httpx.HTTPError`` subclasses) still raise
  ``DedicatedRuntimeError``.

These behaviours protect the auth boundary between the platform and a
per-tenant runtime, especially before the HMAC scheme in
``runtimes/README.md`` lands.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx


# Override the project-level autouse fixture so we don't need Postgres /
# Redis — none of these tests touch DB state.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yunwei_win.assistant.dedicated import (  # noqa: E402
    DedicatedRuntimeError,
    ask_dedicated_runtime,
)


ENDPOINT = "http://pro-runtime.internal"
CHAT_URL = ENDPOINT + "/assistant/chat"


def _ok_body() -> dict:
    return {
        "answer": "from runtime",
        "citations": [],
        "confidence": 0.9,
        "no_relevant_info": False,
    }


@pytest.mark.asyncio
async def test_request_carries_user_id_and_service_headers():
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(CHAT_URL).mock(
            return_value=httpx.Response(200, json=_ok_body())
        )

        result = await ask_dedicated_runtime(
            ENDPOINT,
            question="who?",
            customer_id="all",
            user_id="u_abc123",
        )

    assert result["answer"] == "from runtime"
    assert route.called
    req = route.calls[0].request

    # Identity headers: runtime must be able to attribute the call.
    assert req.headers["X-User-Id"] == "u_abc123"
    assert req.headers["X-Platform-Service"] == "yunwei-win"


@pytest.mark.asyncio
async def test_request_body_does_not_include_enterprise_id():
    """Enterprise scope is enforced server-side before we even resolve
    the runtime binding; sending it to the runtime would invite the
    runtime to trust a header it shouldn't. Defensive check that the
    function signature stays narrow."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(CHAT_URL).mock(
            return_value=httpx.Response(200, json=_ok_body())
        )

        await ask_dedicated_runtime(
            ENDPOINT,
            question="q",
            customer_id=None,
            user_id="u_42",
        )

    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert "enterprise_id" not in body
    # Sanity: the documented body fields ARE present.
    assert set(body.keys()) == {"question", "customer_id", "user_id"}
    assert body["user_id"] == "u_42"


@pytest.mark.asyncio
async def test_5xx_raises_dedicated_runtime_error():
    with respx.mock() as mock:
        mock.post(CHAT_URL).mock(return_value=httpx.Response(503))

        with pytest.raises(DedicatedRuntimeError) as exc_info:
            await ask_dedicated_runtime(
                ENDPOINT,
                question="q",
                customer_id=None,
                user_id="u_1",
            )

    # Status code preserved in the message so operators can grep logs.
    assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_4xx_returns_degraded_payload_without_raising():
    with respx.mock() as mock:
        mock.post(CHAT_URL).mock(
            return_value=httpx.Response(400, json={"error": "bad shape"})
        )

        result = await ask_dedicated_runtime(
            ENDPOINT,
            question="q",
            customer_id=None,
            user_id="u_1",
        )

    assert result["no_relevant_info"] is True
    assert result["citations"] == []
    assert result["confidence"] == 0.0
    # Don't leak the runtime's raw error message to the SPA.
    assert "bad shape" not in result["answer"]


@pytest.mark.asyncio
async def test_transport_error_raises_dedicated_runtime_error():
    with respx.mock() as mock:
        mock.post(CHAT_URL).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(DedicatedRuntimeError):
            await ask_dedicated_runtime(
                ENDPOINT,
                question="q",
                customer_id=None,
                user_id="u_1",
            )


@pytest.mark.asyncio
async def test_timeout_raises_dedicated_runtime_error():
    """``httpx.TimeoutException`` is an ``httpx.HTTPError`` subclass —
    the existing ``except httpx.HTTPError`` clause must still catch it
    so the router can fall back instead of crashing the request."""
    with respx.mock() as mock:
        mock.post(CHAT_URL).mock(side_effect=httpx.ReadTimeout("slow"))

        with pytest.raises(DedicatedRuntimeError):
            await ask_dedicated_runtime(
                ENDPOINT,
                question="q",
                customer_id=None,
                user_id="u_1",
            )
