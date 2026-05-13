"""URL contract — assert the SaaS-style URL surface.

This is the single place that pins the canonical URL layout introduced
by the ``feat/api-url-canonicalize`` work: ``/api/win/*`` for the 智通
客户 API, ``/api/admin/*`` / ``/api/enterprise/*`` for platform ops,
``/api/auth/*`` for login / logout / register, and ``/api/me`` for the
chrome.

Legacy URLs that used to exist (``/win/api/*``, the ``/<client>/<agent>``
HMAC reverse-proxy entrypoint, ``/data``, ``/enterprise/<id>`` page route,
``/api/agents``, ``/auth/login``, ``/auth/logout``, ``/api/register``)
MUST 404 outright — no aliases, no redirects, no compatibility rewrites.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from platform_app import auth, db


@pytest.fixture
def client() -> TestClient:
    from platform_app.main import app

    return TestClient(app)


@pytest.fixture
def logged_in_no_enterprise() -> str:
    """Logged-in user with no enterprise — used to confirm ``/api/me``
    still returns 200 for users mid-onboarding."""
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_noent", "noent", auth.hash_password("p"), "NoEnt", int(time.time())),
    )
    sid, _ = auth.create_session("u_noent", "127.0.0.1", "test")
    return sid


@pytest.fixture
def logged_in_with_enterprise() -> str:
    """Logged-in user belonging to an enterprise — used to confirm the
    ``/api/me`` payload exposes ``enterprise_id`` + ``entitlements`` and
    the win/admin/enterprise auth middleware accepts the session."""
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_url", "urluser", auth.hash_password("p"), "URL User", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
        ("e_url", "URL Inc", "URL", "trial", "signed_up", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, "
        "granted_at, granted_by) VALUES (%s,%s,%s,%s,%s)",
        ("u_url", "e_url", "owner", now, "test"),
    )
    sid, _ = auth.create_session("u_url", "127.0.0.1", "test")
    return sid


# ─── new URL surface: /api/win/* must be wired up ────────────────────


def test_assistant_chat_unauth_returns_401_not_404(client: TestClient) -> None:
    """A POST to ``/api/win/assistant/chat`` without a session must be 401
    (route exists but requires auth) — proves the new mount is live."""
    r = client.post("/api/win/assistant/chat", json={"question": "x"})
    assert r.status_code == 401
    body = r.json()
    # Legacy envelope shape preserved by ``_attach_enterprise``.
    assert body["error"] == "not_logged_in"


def test_assistant_chat_authed_with_stub_returns_200(
    client: TestClient,
    logged_in_with_enterprise: str,
    monkeypatch,
) -> None:
    """A POST to ``/api/win/assistant/chat`` from a logged-in user with an
    enterprise + a stubbed service must return 200 — proves the route
    forwards the auth context all the way to the handler."""
    captured: dict = {}

    async def fake(session, question, customer_id=None):
        captured["question"] = question
        captured["customer_id"] = customer_id
        return {
            "answer": "stubbed",
            "citations": [],
            "confidence": 0.7,
            "no_relevant_info": False,
        }

    monkeypatch.setattr(
        "yunwei_win.assistant.router.answer_shared_assistant", fake
    )

    try:
        r = client.post(
            "/api/win/assistant/chat",
            json={"question": "hi"},
            cookies={"app_session": logged_in_with_enterprise},
        )
        assert r.status_code == 200, r.text
        assert r.json()["answer"] == "stubbed"
        assert captured == {"question": "hi", "customer_id": None}
    finally:
        # Drop the per-tenant DB the assistant call lazy-provisioned so
        # the autouse TRUNCATE fixture doesn't trip on dangling state.
        import asyncio

        from yunwei_win.db import _tenant_db_name, dispose_all

        asyncio.new_event_loop().run_until_complete(dispose_all())
        name = _tenant_db_name("e_url")
        db.main().execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid != pg_backend_pid()",
            (name,),
        )
        db.main().execute(f'DROP DATABASE IF EXISTS "{name}"', ())


# ─── legacy URLs must be gone ───────────────────────────────────────


def test_legacy_win_api_assistant_chat_is_404(client: TestClient) -> None:
    """The pre-canonicalize URL ``/win/api/assistant/chat`` MUST 404.

    No legacy aliases. No redirects. No rewrites. This is the contract
    the SPA migration relies on so dual surfaces don't drift."""
    r = client.get("/win/api/assistant/chat")
    assert r.status_code == 404
    r2 = client.post("/win/api/assistant/chat", json={"question": "x"})
    assert r2.status_code == 404


def test_legacy_client_agent_proxy_is_404(client: TestClient) -> None:
    """The HMAC reverse-proxy catch-all at ``/<client>/<agent>/...`` has
    been removed entirely — no Auth, no ACL, just a flat 404."""
    r = client.get("/yinhu/super-xiaochen/foo")
    assert r.status_code == 404
    r2 = client.get("/some-client/some-agent/")
    assert r2.status_code == 404


def test_legacy_data_page_is_404(client: TestClient) -> None:
    """``/data`` (the old data-console HTML page) is gone."""
    r = client.get("/data")
    assert r.status_code == 404


def test_legacy_enterprise_page_is_404(client: TestClient) -> None:
    """``/enterprise/<id>`` page route is gone (the API still lives at
    ``/api/enterprise/<id>``)."""
    r = client.get("/enterprise/yinhu")
    assert r.status_code == 404


def test_legacy_api_agents_is_404(client: TestClient) -> None:
    """``/api/agents`` is the old agent-dashboard endpoint; admin no
    longer uses this surface, so it must be gone."""
    r = client.get("/api/agents")
    assert r.status_code == 404


# ─── /api/auth/* contract (login / logout / register moved here) ────


def test_legacy_auth_login_is_404(client: TestClient) -> None:
    """``POST /auth/login`` moved to ``/api/auth/login`` — no alias."""
    r = client.post("/auth/login", data={"username": "x", "password": "y"})
    assert r.status_code == 404


def test_legacy_auth_logout_is_404(client: TestClient) -> None:
    """``POST /auth/logout`` moved to ``/api/auth/logout`` — no alias."""
    r = client.post("/auth/logout")
    assert r.status_code == 404


def test_legacy_api_register_is_404(client: TestClient) -> None:
    """``POST /api/register`` moved to ``/api/auth/register`` — no alias."""
    r = client.post("/api/register", json={"code": "WIN-AAAA-AAAA"})
    assert r.status_code == 404


def test_api_auth_login_is_wired(client: TestClient) -> None:
    """``POST /api/auth/login`` must be wired (not 404). Bad credentials
    yield 401; this still proves the route exists."""
    r = client.post(
        "/api/auth/login", data={"username": "nobody", "password": "wrong"}
    )
    assert r.status_code != 404
    assert r.status_code == 401


def test_api_auth_logout_is_wired(client: TestClient) -> None:
    """``POST /api/auth/logout`` must be wired (not 404). Without a session
    cookie it's still a 200 — logout is idempotent and only clears cookies."""
    r = client.post("/api/auth/logout")
    assert r.status_code != 404
    assert r.status_code == 200


def test_api_auth_register_is_wired(client: TestClient) -> None:
    """``POST /api/auth/register`` must be wired (not 404). A malformed
    invite code yields a 400 business error — proves the route exists."""
    r = client.post(
        "/api/auth/register",
        json={"code": "not-a-code", "username": "x", "password": "p"},
    )
    assert r.status_code != 404
    assert r.status_code == 400


# ─── /api/me contract ───────────────────────────────────────────────


def test_api_me_unauth_returns_401(client: TestClient) -> None:
    r = client.get("/api/me")
    assert r.status_code == 401
    assert r.json()["error"] == "not_logged_in"


def test_api_me_authed_returns_enterprise_id_and_entitlements(
    client: TestClient,
    logged_in_with_enterprise: str,
) -> None:
    r = client.get(
        "/api/me", cookies={"app_session": logged_in_with_enterprise}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enterprise_id"] == "e_url"
    assert body["enterprise_plan"] == "trial"
    assert body["enterprise_role"] == "owner"
    ent = body["entitlements"]
    assert ent is not None
    assert "runtime_mode" in ent
    assert "can_use_shared_assistant" in ent
    assert "can_use_dedicated_runtime" in ent
    assert isinstance(ent["allowed_tools"], list)


def test_api_me_authed_no_enterprise_still_returns_200(
    client: TestClient,
    logged_in_no_enterprise: str,
) -> None:
    """Mid-onboarding users (logged in, no enterprise yet) must still get
    a usable ``/api/me`` payload — the chrome reads this to decide what
    to render. ``enterprise_id`` / ``entitlements`` are ``None`` then."""
    r = client.get(
        "/api/me", cookies={"app_session": logged_in_no_enterprise}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["enterprises"] == []
    assert body["enterprise_id"] is None
    assert body["entitlements"] is None
