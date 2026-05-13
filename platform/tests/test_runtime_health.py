"""Runtime health-probe tests.

These cover :func:`platform_app.health.probe_all_runtimes_once` — the
single-round helper that polls ``GET {endpoint_url}/healthz`` for every
row in ``runtimes`` and writes the resulting status back. The router
(``yunwei_win.assistant.router``) skips dedicated forwarding when
``runtimes.health == 'unhealthy'``; if this probe never runs, every
runtime stays at ``'unknown'`` forever and the router can only learn
about an outage by trying a forward and catching the failure.

We do NOT test the infinite ``probe_loop()`` driver here — that just
wraps this helper in ``while True: ... sleep()``. One pytest-managed
event loop should never sit on an infinite probe.

HTTP is mocked with ``respx`` (same pattern used by
``test_mineru_ocr_provider.py``); no live network needed.
"""
from __future__ import annotations

import time

import httpx
import pytest
import respx

from platform_app import db, health, runtime_registry


def _now() -> int:
    return int(time.time())


@pytest.fixture
def enterprise():
    """Seed a minimal enterprise so runtime_bindings FK is satisfied if
    we choose to bind. ``_clean_state`` (autouse, conftest) has already
    run ``db.init()`` + truncated; we just insert."""
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'pro','active',%s)",
        ("yinhu", "银湖", "银湖", _now()),
    )
    return "yinhu"


def _current_health(runtime_id: str) -> str:
    row = db.main().execute(
        "SELECT health FROM runtimes WHERE id=%s", (runtime_id,)
    ).fetchone()
    assert row is not None, f"runtime {runtime_id} missing"
    return row["health"]


# ─── empty registry ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_all_runtimes_once_empty_returns_empty_dict():
    """Zero rows in ``runtimes`` → helper returns ``{}`` and doesn't blow up."""
    result = await health.probe_all_runtimes_once()
    assert result == {}


# ─── single healthy runtime ─────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_marks_healthy_when_runtime_returns_ok(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_ok",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-ok.internal",
        version="v1",
    )
    # Pre-condition: defaults to 'unknown'.
    assert _current_health("rt_ok") == "unknown"

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-ok.internal/healthz").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_ok": "healthy"}
    assert _current_health("rt_ok") == "healthy"


@pytest.mark.asyncio
async def test_probe_marks_degraded_when_runtime_reports_degraded(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_degraded",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-degraded.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-degraded.internal/healthz").mock(
            return_value=httpx.Response(200, json={"status": "degraded"})
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_degraded": "degraded"}
    assert _current_health("rt_degraded") == "degraded"


@pytest.mark.asyncio
async def test_probe_marks_unhealthy_when_runtime_reports_down(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_down",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-down.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-down.internal/healthz").mock(
            return_value=httpx.Response(200, json={"status": "down"})
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_down": "unhealthy"}
    assert _current_health("rt_down") == "unhealthy"


# ─── single unhealthy runtime ───────────────────────────────────


@pytest.mark.asyncio
async def test_probe_marks_unhealthy_on_5xx(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_5xx",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-5xx.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-5xx.internal/healthz").mock(
            return_value=httpx.Response(503, text="bad gateway")
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_5xx": "unhealthy"}
    assert _current_health("rt_5xx") == "unhealthy"


@pytest.mark.asyncio
async def test_probe_marks_unhealthy_on_connection_error(enterprise):
    """A connect-refused / DNS failure must map to ``unhealthy`` and must
    NOT abort the round — there is exactly one runtime here, so we just
    check the helper returns rather than raises."""
    runtime_registry.upsert_runtime(
        runtime_id="rt_refused",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-refused.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-refused.internal/healthz").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_refused": "unhealthy"}
    assert _current_health("rt_refused") == "unhealthy"


# ─── unknown / unparseable shapes ───────────────────────────────


@pytest.mark.asyncio
async def test_probe_marks_unknown_on_unrecognised_status(enterprise):
    """200 + a body we don't recognise → ``unknown`` (conservative, no
    auto-flip to unhealthy that would steal traffic from a runtime whose
    /healthz simply has a custom shape)."""
    runtime_registry.upsert_runtime(
        runtime_id="rt_weird",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-weird.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-weird.internal/healthz").mock(
            return_value=httpx.Response(200, json={"status": "marinating"})
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_weird": "unknown"}
    assert _current_health("rt_weird") == "unknown"


@pytest.mark.asyncio
async def test_probe_marks_unknown_on_non_json_body(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_text",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-text.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-text.internal/healthz").mock(
            return_value=httpx.Response(200, text="ok")
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_text": "unknown"}
    assert _current_health("rt_text") == "unknown"


# ─── mixed fleet: one failure does not abort the round ──────────


@pytest.mark.asyncio
async def test_probe_continues_when_one_runtime_fails(enterprise):
    """Two runtimes, one healthy + one connection-refused. Both must end
    up with their correct status; the failure must not abort the loop."""
    runtime_registry.upsert_runtime(
        runtime_id="rt_a_ok",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-a.internal",
    )
    runtime_registry.upsert_runtime(
        runtime_id="rt_b_dead",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://rt-b.internal",
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://rt-a.internal/healthz").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        mock.get("http://rt-b.internal/healthz").mock(
            side_effect=httpx.ConnectError("nope")
        )
        result = await health.probe_all_runtimes_once()

    assert result == {"rt_a_ok": "healthy", "rt_b_dead": "unhealthy"}
    assert _current_health("rt_a_ok") == "healthy"
    assert _current_health("rt_b_dead") == "unhealthy"
