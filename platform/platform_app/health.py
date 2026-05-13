"""SSO.md §11.6 周期 healthz 探测.

Probes two distinct populations:

1. Legacy ``tenants(client_id, agent_id, container_url)`` rows — the
   pre-v3 customer-agent gateway. ``health`` is flipped to ``healthy``
   on HTTP 200 from ``/healthz`` and ``unhealthy`` otherwise.
2. ``runtimes`` rows from migration 010 (the dedicated/pooled runtime
   registry). ``yunwei_win.assistant.router`` reads ``runtimes.health``
   to skip a doomed dedicated-runtime forward when the container has
   already been marked down out-of-band.

Both populations are probed by the same loop so a single uvicorn worker
covers both. Each individual probe is wrapped in try/except so one bad
endpoint never breaks the loop.
"""
from __future__ import annotations
import asyncio
import time
import httpx
from . import db
from .runtime_registry import Runtime
from .settings import settings


# ─── runtime probes ─────────────────────────────────────────────
#
# Status mapping (see runtimes/README.md):
#   HTTP non-2xx / exception   → "unhealthy"
#   200 + {"status": "ok"}     → "healthy"
#   200 + {"status":"degraded"}→ "degraded"
#   200 + {"status": "down"}   → "unhealthy"
#   200 + anything else / JSON parse failure → "unknown"
#
# We default to "unknown" rather than "unhealthy" on shape mismatch so
# we don't accidentally take traffic away from a runtime whose /healthz
# is merely returning a body we don't understand.

async def probe_runtime(runtime: Runtime, client: httpx.AsyncClient) -> str:
    """Probe a single runtime's /healthz and return the new status string.

    Does NOT write to the DB — callers do that. Returns one of
    ``"healthy" | "degraded" | "unhealthy" | "unknown"``.
    """
    url = runtime.endpoint_url.rstrip("/") + "/healthz"
    try:
        resp = await client.get(url)
    except Exception:
        return "unhealthy"
    if resp.status_code < 200 or resp.status_code >= 300:
        return "unhealthy"
    try:
        body = resp.json()
    except Exception:
        return "unknown"
    status = body.get("status") if isinstance(body, dict) else None
    if status == "ok":
        return "healthy"
    if status == "degraded":
        return "degraded"
    if status == "down":
        return "unhealthy"
    return "unknown"


async def probe_all_runtimes_once(
    client: httpx.AsyncClient | None = None,
) -> dict[str, str]:
    """Probe every row in ``runtimes`` once and write the result back.

    Returns ``{runtime_id: status}`` for callers that want to observe
    the round (tests, future ops endpoints). A failure to probe one
    runtime never stops the loop — the offending entry just gets
    ``"unhealthy"`` (transport failures already map there in
    :func:`probe_runtime`) and we keep going.
    """
    rows = db.main().execute(
        "SELECT id, mode, provider, endpoint_url, health, version FROM runtimes"
    ).fetchall()
    if not rows:
        return {}

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=5.0)
    try:
        results: dict[str, str] = {}
        for r in rows:
            rt = Runtime(
                id=r["id"],
                mode=r["mode"],
                provider=r["provider"],
                endpoint_url=r["endpoint_url"],
                health=r["health"],
                version=r["version"],
            )
            try:
                status = await probe_runtime(rt, client)
            except Exception:
                # Belt-and-braces: probe_runtime catches its own errors,
                # but if anything slips through we still don't want one
                # bad row to abort the rest of the round.
                status = "unhealthy"
            try:
                db.main().execute(
                    "UPDATE runtimes SET health=%s WHERE id=%s",
                    (status, rt.id),
                )
            except Exception:
                # DB hiccup on one row — log via results, continue.
                pass
            results[rt.id] = status
        return results
    finally:
        if owns_client:
            await client.aclose()


# ─── loop driver (legacy tenants + runtimes) ────────────────────

async def probe_loop():
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            # Legacy tenants probe — unchanged behaviour.
            try:
                rows = db.main().execute(
                    "SELECT client_id, agent_id, container_url FROM tenants WHERE active=1",
                ).fetchall()
                for r in rows:
                    health = "unhealthy"
                    try:
                        resp = await client.get(r["container_url"].rstrip("/") + "/healthz")
                        if resp.status_code == 200:
                            health = "healthy"
                    except Exception:
                        pass
                    db.main().execute(
                        "UPDATE tenants SET health=%s, health_checked_at=%s WHERE client_id=%s AND agent_id=%s",
                        (health, int(time.time()), r["client_id"], r["agent_id"]),
                    )
                    db.invalidate_tenant(r["client_id"], r["agent_id"])
            except Exception:
                pass

            # Runtime registry probe — keep router-side health gating accurate.
            try:
                await probe_all_runtimes_once(client)
            except Exception:
                pass

            await asyncio.sleep(settings.health_probe_interval_seconds)
