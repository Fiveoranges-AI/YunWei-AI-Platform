"""Runtime registry tests (migration 010).

Covers:
- migration creates `runtimes` and `runtime_bindings` tables
- `get_runtime_for` returns None when no binding exists
- `upsert_runtime` + `bind_runtime` make `get_runtime_for` return the row
- re-binding the same (enterprise, capability) UPDATEs runtime_id
  instead of inserting a second row (ON CONFLICT path)
"""
from __future__ import annotations
import time

import pytest

from platform_app import db, runtime_registry


def _now() -> int:
    return int(time.time())


@pytest.fixture
def enterprise():
    """Seed a minimal enterprise so runtime_bindings FK is satisfied."""
    db.init()
    now = _now()
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "银湖", "银湖", now),
    )
    return "yinhu"


# ─── schema ─────────────────────────────────────────────────────

def test_010_creates_runtime_tables():
    db.init()
    rows = db.main().execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"runtimes", "runtime_bindings"} <= names


# ─── lookup semantics ───────────────────────────────────────────

def test_get_runtime_for_returns_none_without_binding(enterprise):
    assert runtime_registry.get_runtime_for(enterprise, "assistant") is None


def test_upsert_and_bind_makes_runtime_resolvable(enterprise):
    runtime_registry.upsert_runtime(
        runtime_id="rt_pooled_free",
        mode="pooled",
        provider="railway",
        endpoint_url="http://pooled.internal",
        version="v1.0.0",
    )
    runtime_registry.bind_runtime(
        enterprise_id=enterprise,
        capability="assistant",
        runtime_id="rt_pooled_free",
    )

    rt = runtime_registry.get_runtime_for(enterprise, "assistant")
    assert rt is not None
    assert rt.id == "rt_pooled_free"
    assert rt.mode == "pooled"
    assert rt.provider == "railway"
    assert rt.endpoint_url == "http://pooled.internal"
    assert rt.version == "v1.0.0"
    # health defaults to 'unknown' until an out-of-band health probe sets it.
    assert rt.health == "unknown"


def test_rebinding_updates_runtime_id(enterprise):
    """Second bind_runtime() for the same (enterprise, capability) must
    UPDATE (ON CONFLICT) rather than fail or insert a duplicate."""
    runtime_registry.upsert_runtime(
        runtime_id="rt_pooled_free",
        mode="pooled",
        provider="railway",
        endpoint_url="http://pooled.internal",
    )
    runtime_registry.upsert_runtime(
        runtime_id="rt_dedicated_pro",
        mode="dedicated",
        provider="railway",
        endpoint_url="http://yinhu-pro.internal",
    )

    runtime_registry.bind_runtime(
        enterprise_id=enterprise,
        capability="assistant",
        runtime_id="rt_pooled_free",
    )
    runtime_registry.bind_runtime(
        enterprise_id=enterprise,
        capability="assistant",
        runtime_id="rt_dedicated_pro",
    )

    # Still exactly one binding row.
    count = db.main().execute(
        "SELECT count(*) AS c FROM runtime_bindings "
        "WHERE enterprise_id=%s AND capability=%s",
        (enterprise, "assistant"),
    ).fetchone()["c"]
    assert count == 1

    rt = runtime_registry.get_runtime_for(enterprise, "assistant")
    assert rt is not None
    assert rt.id == "rt_dedicated_pro"
    assert rt.mode == "dedicated"


def test_upsert_runtime_updates_existing_row():
    """Re-calling upsert_runtime with the same id should UPDATE the row
    in place (endpoint_url / version drift after redeploy)."""
    db.init()
    runtime_registry.upsert_runtime(
        runtime_id="rt_pooled_free",
        mode="pooled",
        provider="railway",
        endpoint_url="http://old.internal",
        version="v1.0.0",
    )
    runtime_registry.upsert_runtime(
        runtime_id="rt_pooled_free",
        mode="pooled",
        provider="railway",
        endpoint_url="http://new.internal",
        version="v1.1.0",
    )
    row = db.main().execute(
        "SELECT endpoint_url, version FROM runtimes WHERE id=%s",
        ("rt_pooled_free",),
    ).fetchone()
    assert row["endpoint_url"] == "http://new.internal"
    assert row["version"] == "v1.1.0"


def test_disabled_binding_returns_none(enterprise):
    """If the binding is flipped to enabled=0, lookup returns None."""
    runtime_registry.upsert_runtime(
        runtime_id="rt_pooled_free",
        mode="pooled",
        provider="railway",
        endpoint_url="http://pooled.internal",
    )
    runtime_registry.bind_runtime(
        enterprise_id=enterprise,
        capability="assistant",
        runtime_id="rt_pooled_free",
    )
    db.main().execute(
        "UPDATE runtime_bindings SET enabled=0 "
        "WHERE enterprise_id=%s AND capability=%s",
        (enterprise, "assistant"),
    )
    assert runtime_registry.get_runtime_for(enterprise, "assistant") is None
