"""Tests for the shared assistant endpoint POST /api/win/assistant/chat.

The endpoint is the new collapse point for Free/Lite/Pro Q&A: it reads
enterprise scope from the server-side ``AuthContext`` (cookie → user →
first enterprise), never from the request body, and dispatches to either
the cross-customer KB (``customer_id`` is ``None``/``"all"``) or the
per-customer KB.

These tests:
- prove a missing/invalid cookie produces 401 with the legacy envelope
  (preserved by ``platform_app.main._attach_enterprise``);
- spy on ``answer_shared_assistant`` to confirm the router forwards the
  customer_id verbatim and does NOT propagate any body-supplied
  enterprise_id;
- confirm the response shape passes through unchanged so the Win SPA
  can keep its existing ``askResponseToBlock`` mapper.

We stub the service so no per-tenant database / LLM call is needed.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from platform_app import db


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
        note="assistant-test",
        expires_at_epoch=int(time.time()) + 30 * 86400,
    )
    return code


def _register(c: TestClient, username: str) -> tuple[str, str]:
    """Register a fresh trial user, return (session_id, enterprise_id)."""
    code = _mint_code()
    r = c.post(
        "/api/auth/register",
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


def _cleanup_tenant_db(enterprise_id: str) -> None:
    """Drop the per-tenant DB the registration provisioned so the test is
    idempotent and conftest TRUNCATE doesn't leave dangling state."""
    from yunwei_win.db import _tenant_db_name, dispose_all

    asyncio.new_event_loop().run_until_complete(dispose_all())
    name = _tenant_db_name(enterprise_id)
    db.main().execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid != pg_backend_pid()",
        (name,),
    )
    db.main().execute(f'DROP DATABASE IF EXISTS "{name}"', ())


# ─── 401 / unauthenticated ──────────────────────────────────────────────


def test_chat_without_cookie_returns_401():
    c = _client()
    r = c.post(
        "/api/win/assistant/chat",
        json={"question": "测试"},
    )
    assert r.status_code == 401
    body = r.json()
    # Preserves the legacy /api/win error envelope (not FastAPI's default
    # ``{"detail": ...}``).
    assert body["error"] == "not_logged_in"


# ─── happy path + body-enterprise_id ignored ────────────────────────────


def test_chat_returns_stubbed_answer_for_trial_user(monkeypatch):
    c = _client()
    sid, ent_id = _register(c, "asst_a")
    try:
        captured: dict = {}

        async def fake(session, question, customer_id=None):
            captured["question"] = question
            captured["customer_id"] = customer_id
            return {
                "answer": "stubbed answer",
                "citations": [
                    {"target_type": "customer", "target_id": "x", "snippet": None}
                ],
                "confidence": 0.42,
                "no_relevant_info": False,
            }

        # Patch the symbol bound inside the router module — that's the one
        # the endpoint actually calls.
        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", fake
        )

        r = c.post(
            "/api/win/assistant/chat",
            json={"question": "他们交了多少钱"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["answer"] == "stubbed answer"
        assert body["confidence"] == 0.42
        assert body["citations"][0]["target_id"] == "x"
        assert captured["question"] == "他们交了多少钱"
        assert captured["customer_id"] is None
    finally:
        _cleanup_tenant_db(ent_id)


def test_chat_ignores_enterprise_id_supplied_in_body(monkeypatch):
    """A logged-in user cannot escape their tenant scope by passing a
    different ``enterprise_id`` in the JSON body. The router pulls scope
    only from ``request.state.auth_context``."""
    c = _client()
    sid, ent_id = _register(c, "asst_b")
    try:
        captured_enterprise_ids: list[str | None] = []

        async def fake(session, question, customer_id=None):
            # ``session`` is bound to whatever enterprise the middleware
            # resolved from the cookie — verify by reading the bind URL.
            bind_url = str(session.get_bind().url)
            captured_enterprise_ids.append(bind_url)
            return {
                "answer": "ok",
                "citations": [],
                "confidence": 1.0,
                "no_relevant_info": False,
            }

        monkeypatch.setattr(
            "yunwei_win.assistant.router.answer_shared_assistant", fake
        )

        r = c.post(
            "/api/win/assistant/chat",
            json={
                "question": "hi",
                # Attacker-supplied; must be ignored.
                "enterprise_id": "e_someone_else",
            },
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        # Session DB URL must end with the *cookie-derived* tenant DB,
        # not the body-supplied one.
        assert captured_enterprise_ids, "service was not called"
        bind_url = captured_enterprise_ids[0]
        assert "tenant_e_asst_b" in bind_url
        assert "tenant_e_someone_else" not in bind_url
    finally:
        _cleanup_tenant_db(ent_id)


# ─── customer_id routing ────────────────────────────────────────────────


def test_chat_all_customer_id_routes_to_shared_path(monkeypatch):
    """``customer_id="all"`` must dispatch to the cross-customer Q&A path."""
    c = _client()
    sid, ent_id = _register(c, "asst_c")
    try:
        shared_calls: list[str] = []
        single_calls: list[tuple[str, str]] = []

        async def fake_shared(session, question):
            shared_calls.append(question)
            return {
                "answer": "shared",
                "citations": [],
                "confidence": 0.9,
                "no_relevant_info": False,
            }

        async def fake_single(session, customer_id, question):
            single_calls.append((str(customer_id), question))
            return {"answer": "single", "citations": [], "confidence": 0.9}

        monkeypatch.setattr(
            "yunwei_win.assistant.service.answer_question", fake_shared
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.service.answer_customer_question", fake_single
        )

        r = c.post(
            "/api/win/assistant/chat",
            json={"question": "总览", "customer_id": "all"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "shared"
        assert shared_calls == ["总览"]
        assert single_calls == []
    finally:
        _cleanup_tenant_db(ent_id)


def test_chat_uuid_customer_id_routes_to_single_customer_path(monkeypatch):
    c = _client()
    sid, ent_id = _register(c, "asst_d")
    try:
        shared_calls: list[str] = []
        single_calls: list[tuple[str, str]] = []

        async def fake_shared(session, question):
            shared_calls.append(question)
            return {"answer": "shared", "citations": [], "confidence": 0.9}

        async def fake_single(session, customer_id, question):
            single_calls.append((str(customer_id), question))
            return {
                "answer": "single",
                "citations": [],
                "confidence": 0.5,
                "no_relevant_info": False,
            }

        monkeypatch.setattr(
            "yunwei_win.assistant.service.answer_question", fake_shared
        )
        monkeypatch.setattr(
            "yunwei_win.assistant.service.answer_customer_question", fake_single
        )

        cid = uuid.uuid4()
        r = c.post(
            "/api/win/assistant/chat",
            json={"question": "他们的订单状态", "customer_id": str(cid)},
            cookies={"app_session": sid},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "single"
        assert single_calls == [(str(cid), "他们的订单状态")]
        assert shared_calls == []
    finally:
        _cleanup_tenant_db(ent_id)


def test_chat_invalid_customer_id_returns_400(monkeypatch):
    c = _client()
    sid, ent_id = _register(c, "asst_e")
    try:
        # No need to patch the service — _parse_customer_id rejects before
        # we even reach it.
        r = c.post(
            "/api/win/assistant/chat",
            json={"question": "x", "customer_id": "not-a-uuid"},
            cookies={"app_session": sid},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "invalid_customer_id"
    finally:
        _cleanup_tenant_db(ent_id)
