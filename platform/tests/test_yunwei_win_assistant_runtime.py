"""Routing-policy tests for POST /win/api/assistant/chat (Task 7).

These tests focus on the *decision*: does the request go to the shared
QA service (Free/Lite + Pro-without-binding), or does it forward to a
dedicated runtime (Pro with a healthy ``assistant`` binding)? The actual
HTTP forwarding inside ``ask_dedicated_runtime`` is monkeypatched away —
we never want to hit a real network from the test suite.

Plan upgrades (trial → pro) are done with a direct UPDATE against
``enterprises`` because the registration flow only mints trial accounts
and there is no plan-change API. ``list_user_enterprises`` reads the
``plan`` column directly, so an UPDATE is enough for
``entitlements_for`` to see ``can_use_dedicated_runtime=True``.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from platform_app import db, runtime_registry


# ─── helpers (cribbed from test_yunwei_win_assistant.py) ──────────────────


def _client() -> TestClient:
    from platform_app.main import app

    return TestClient(app)


def _mint_code() -> str:
    import time

    from platform_app.admin import _generate_invite_code

    code = _generate_invite_code()
    db.insert_invite(
        code,
        created_by="test",
        note="assistant-runtime-test",
        expires_at_epoch=int(time.time()) + 30 * 86400,
    )
    return code


def _register(c: TestClient, username: str) -> tuple[str, str]:
    code = _mint_code()
    r = c.post(
        "/api/register",
        json={
            "code": code,
            "username": username,
            "password": "passwd1234",
            "display_name": username.capitalize(),
        },
    )
    assert r.status_code == 200, r.text
    sid = r.cookies.get("app_session")
    assert sid
    return sid, f"e_{username}"


def _set_plan(enterprise_id: str, plan: str) -> None:
    """Upgrade a freshly-registered trial enterprise to ``plan``.

    ``require_auth_context`` reads ``plan`` from ``enterprises`` via
    ``list_user_enterprises``; the column is the only source of truth
    for ``Entitlements.can_use_dedicated_runtime``.
    """
    db.main().execute(
        "UPDATE enterprises SET plan=%s WHERE id=%s",
        (plan, enterprise_id),
    )


def _bind_assistant_runtime(
    enterprise_id: str,
    *,
    runtime_id: str = "rt_pro_assistant",
    endpoint_url: str = "http://pro-runtime.internal",
    health: str | None = None,
) -> None:
    runtime_registry.upsert_runtime(
        runtime_id=runtime_id,
        mode="dedicated",
        provider="railway",
        endpoint_url=endpoint_url,
        version="v1.0.0",
    )
    runtime_registry.bind_runtime(
        enterprise_id=enterprise_id,
        capability="assistant",
        runtime_id=runtime_id,
    )
    if health is not None:
        db.main().execute(
            "UPDATE runtimes SET health=%s WHERE id=%s",
            (health, runtime_id),
        )


def _cleanup_tenant_db(enterprise_id: str) -> None:
    from yunwei_win.db import _tenant_db_name, dispose_all

    asyncio.new_event_loop().run_until_complete(dispose_all())
    name = _tenant_db_name(enterprise_id)
    db.main().execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid != pg_backend_pid()",
        (name,),
    )
    db.main().execute(f'DROP DATABASE IF EXISTS "{name}"', ())


def _shared_stub(answer: str = "shared-answer"):
    """Build an ``answer_shared_assistant`` monkeypatch + call recorder."""
    calls: list[dict] = []

    async def fake(session, question, customer_id=None):
        calls.append({"question": question, "customer_id": customer_id})
        return {
            "answer": answer,
            "citations": [],
            "confidence": 0.5,
            "no_relevant_info": False,
        }

    return fake, calls


def _dedicated_stub(answer: str = "dedicated-answer"):
    """Build an ``ask_dedicated_runtime`` monkeypatch + call recorder."""
    calls: list[dict] = []

    async def fake(endpoint_url, *, question, customer_id, user_id):
        calls.append(
            {
                "endpoint_url": endpoint_url,
                "question": question,
                "customer_id": customer_id,
                "user_id": user_id,
            }
        )
        return {
            "answer": answer,
            "citations": [],
            "confidence": 0.9,
            "no_relevant_info": False,
        }

    return fake, calls


# ─── 1. Pro with binding → dedicated wins ─────────────────────────────────


def test_pro_with_binding_forwards_to_dedicated_runtime(monkeypatch):
    c = _client()
    sid, ent_id = _register(c, "rt_pro_a")
    try:
        _set_plan(ent_id, "pro")
        _bind_assistant_runtime(
            ent_id, endpoint_url="http://pro-a-runtime.internal"
        )

        shared_fake, shared_calls = _shared_stub("shared-WRONG")
        dedicated_fake, dedicated_calls = _dedicated_stub("dedicated-OK")
        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", shared_fake
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.router.ask_dedicated_runtime", dedicated_fake
        )

        r = c.post(
            "/win/api/assistant/chat",
            json={"question": "pro question", "customer_id": "all"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "dedicated-OK"
        assert shared_calls == []
        assert len(dedicated_calls) == 1
        assert dedicated_calls[0]["endpoint_url"] == "http://pro-a-runtime.internal"
        assert dedicated_calls[0]["question"] == "pro question"
        # customer_id "all" is forwarded verbatim — the dedicated runtime
        # is responsible for interpreting it (we do not parse here).
        assert dedicated_calls[0]["customer_id"] == "all"
    finally:
        _cleanup_tenant_db(ent_id)


# ─── 2. Pro without binding → shared fallback ─────────────────────────────


def test_pro_without_binding_uses_shared_assistant(monkeypatch):
    c = _client()
    sid, ent_id = _register(c, "rt_pro_b")
    try:
        _set_plan(ent_id, "pro")
        # No bind_runtime call → get_runtime_for returns None.

        shared_fake, shared_calls = _shared_stub("shared-OK")
        dedicated_fake, dedicated_calls = _dedicated_stub("dedicated-WRONG")
        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", shared_fake
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.router.ask_dedicated_runtime", dedicated_fake
        )

        r = c.post(
            "/win/api/assistant/chat",
            json={"question": "pro no binding"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "shared-OK"
        assert dedicated_calls == []
        assert shared_calls == [{"question": "pro no binding", "customer_id": None}]
    finally:
        _cleanup_tenant_db(ent_id)


# ─── 3. Pro with binding but runtime raises → shared fallback ─────────────


def test_dedicated_runtime_error_falls_back_to_shared(monkeypatch):
    from yunwei_win.assistant.dedicated import DedicatedRuntimeError

    c = _client()
    sid, ent_id = _register(c, "rt_pro_c")
    try:
        _set_plan(ent_id, "pro")
        _bind_assistant_runtime(ent_id)

        shared_fake, shared_calls = _shared_stub("shared-fallback")

        async def boom(endpoint_url, *, question, customer_id, user_id):
            raise DedicatedRuntimeError("connection refused")

        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", shared_fake
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.router.ask_dedicated_runtime", boom
        )

        r = c.post(
            "/win/api/assistant/chat",
            json={"question": "with broken runtime"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answer"] == "shared-fallback"
        # Make sure no infra detail leaked into the user-facing response.
        assert "connection refused" not in body["answer"]
        assert "endpoint" not in body["answer"].lower()
        assert shared_calls == [
            {"question": "with broken runtime", "customer_id": None}
        ]
    finally:
        _cleanup_tenant_db(ent_id)


# ─── 4. Lite with binding → entitlements gate stops dedicated ─────────────


def test_lite_with_binding_still_uses_shared(monkeypatch):
    """Even if ops mis-binds a lite enterprise to a dedicated runtime,
    ``can_use_dedicated_runtime=False`` short-circuits before the
    registry lookup. This is the defence-in-depth check: plan policy
    wins over a stray binding row."""
    c = _client()
    sid, ent_id = _register(c, "rt_lite_a")
    try:
        _set_plan(ent_id, "lite")
        _bind_assistant_runtime(ent_id)

        shared_fake, shared_calls = _shared_stub("shared-lite")
        dedicated_fake, dedicated_calls = _dedicated_stub("dedicated-WRONG")
        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", shared_fake
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.router.ask_dedicated_runtime", dedicated_fake
        )

        r = c.post(
            "/win/api/assistant/chat",
            json={"question": "lite question"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "shared-lite"
        assert dedicated_calls == []
        assert shared_calls == [{"question": "lite question", "customer_id": None}]
    finally:
        _cleanup_tenant_db(ent_id)


# ─── 5. Pro with binding flagged unhealthy → shared fallback ─────────────


def test_unhealthy_runtime_skips_dedicated_and_uses_shared(monkeypatch):
    """A runtime row with ``health='unhealthy'`` means an out-of-band
    probe has marked the container as down. We skip the dedicated path
    immediately instead of issuing a doomed HTTP call."""
    c = _client()
    sid, ent_id = _register(c, "rt_pro_d")
    try:
        _set_plan(ent_id, "pro")
        _bind_assistant_runtime(ent_id, health="unhealthy")

        shared_fake, shared_calls = _shared_stub("shared-after-unhealthy")
        dedicated_fake, dedicated_calls = _dedicated_stub("dedicated-WRONG")
        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", shared_fake
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.router.ask_dedicated_runtime", dedicated_fake
        )

        r = c.post(
            "/win/api/assistant/chat",
            json={"question": "unhealthy runtime"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "shared-after-unhealthy"
        assert dedicated_calls == []
        assert shared_calls == [
            {"question": "unhealthy runtime", "customer_id": None}
        ]
    finally:
        _cleanup_tenant_db(ent_id)
