"""SSO.md §11.6 周期 healthz 探测."""
from __future__ import annotations
import asyncio
import time
import httpx
from . import db
from .settings import settings


async def probe_loop():
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
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
            await asyncio.sleep(settings.health_probe_interval_seconds)
