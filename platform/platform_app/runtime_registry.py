"""Runtime registry — maps (enterprise, capability) to a runtime endpoint.

Free/Lite tiers share a pooled runtime row (`mode='pooled'`); Pro/Max get
a dedicated row (`mode='dedicated'`). The HMAC proxy will eventually
resolve container URLs through this registry; for now it is a standalone
table populated by ops tooling and consulted by Task 7+.
"""
from __future__ import annotations
import time
from dataclasses import dataclass

from . import db


@dataclass(frozen=True)
class Runtime:
    id: str
    mode: str
    provider: str
    endpoint_url: str
    health: str
    version: str


def get_runtime_for(enterprise_id: str, capability: str) -> Runtime | None:
    """Resolve the runtime bound to (enterprise_id, capability).

    Returns None when no binding exists or the binding is disabled.
    """
    row = db.main().execute(
        "SELECT r.id, r.mode, r.provider, r.endpoint_url, r.health, r.version "
        "FROM runtime_bindings b "
        "JOIN runtimes r ON r.id = b.runtime_id "
        "WHERE b.enterprise_id=%s AND b.capability=%s AND b.enabled=1",
        (enterprise_id, capability),
    ).fetchone()
    if not row:
        return None
    return Runtime(
        id=row["id"],
        mode=row["mode"],
        provider=row["provider"],
        endpoint_url=row["endpoint_url"],
        health=row["health"],
        version=row["version"],
    )


def upsert_runtime(
    *,
    runtime_id: str,
    mode: str,
    provider: str,
    endpoint_url: str,
    version: str = "unknown",
) -> None:
    """Insert or update a runtime row. Health is left at its current value
    (defaults to 'unknown' on first insert)."""
    db.main().execute(
        "INSERT INTO runtimes (id, mode, provider, endpoint_url, version, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET "
        "  mode=EXCLUDED.mode, "
        "  provider=EXCLUDED.provider, "
        "  endpoint_url=EXCLUDED.endpoint_url, "
        "  version=EXCLUDED.version",
        (runtime_id, mode, provider, endpoint_url, version, int(time.time())),
    )


def bind_runtime(
    *,
    enterprise_id: str,
    capability: str,
    runtime_id: str,
) -> None:
    """Bind an enterprise capability to a runtime. Re-binding the same
    (enterprise_id, capability) updates the target runtime_id and
    re-enables the binding."""
    db.main().execute(
        "INSERT INTO runtime_bindings (enterprise_id, capability, runtime_id, created_at) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (enterprise_id, capability) DO UPDATE SET "
        "  runtime_id=EXCLUDED.runtime_id, "
        "  enabled=1",
        (enterprise_id, capability, runtime_id, int(time.time())),
    )
