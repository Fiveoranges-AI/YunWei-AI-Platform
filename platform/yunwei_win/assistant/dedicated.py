"""Forwarder for dedicated assistant runtimes.

Pro/Max enterprises with an ``assistant`` runtime binding (Task 6) have
their chat requests served by a per-tenant container instead of the
shared QA path. This module is the thin HTTP client that talks to that
container; the routing decision (whether to call us at all) lives in
:mod:`yunwei_win.assistant.router`.

The dedicated runtime is expected to expose ``POST /assistant/chat``
returning the same ``{answer, citations, confidence, no_relevant_info}``
shape the shared assistant produces, so the Win SPA does not need to
care which path served the answer. We normalise the response defensively
in case a runtime omits a field.
"""
from __future__ import annotations

import httpx


class DedicatedRuntimeError(Exception):
    """Raised when the dedicated runtime is unreachable or 5xx.

    The router catches this and falls back to the shared assistant; we
    deliberately do not surface the raw endpoint URL in the message so
    callers can log it without leaking internal infra to the user.
    """


async def ask_dedicated_runtime(
    endpoint_url: str,
    *,
    question: str,
    customer_id: str | None,
    user_id: str,
) -> dict:
    """Forward a chat request to a dedicated runtime.

    - 5xx / connection / timeout → :class:`DedicatedRuntimeError` so the
      router can fall back to the shared path.
    - 4xx → return a friendly degraded payload (no exception). A 4xx is
      typically a client-shape problem on the runtime side; surfacing it
      as a hard error would mask the issue behind a shared-path retry.
    - 2xx → normalise to the shared assistant's response shape.
    """
    url = endpoint_url.rstrip("/") + "/assistant/chat"
    payload = {
        "question": question,
        "customer_id": customer_id,
        "user_id": user_id,
    }
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise DedicatedRuntimeError(str(exc)) from exc

    if resp.status_code >= 500:
        raise DedicatedRuntimeError(f"runtime HTTP {resp.status_code}")
    if resp.status_code >= 400:
        return {
            "answer": "专属运行时暂时无法回答，请稍后重试。",
            "citations": [],
            "confidence": 0.0,
            "no_relevant_info": True,
        }

    body = resp.json()
    return {
        "answer": body.get("answer", ""),
        "citations": body.get("citations") or [],
        "confidence": float(body.get("confidence", 0.5)),
        "no_relevant_info": bool(body.get("no_relevant_info", False)),
    }
