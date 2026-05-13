"""End-to-end tests for the invite-code self-registration flow.

Covers:
  - GET /api/invite/{code} validity probing (each failure mode)
  - POST /api/register happy path → user + enterprise + member + session
  - Double-redeem fails atomically
  - Revoked / expired codes rejected
  - Username/format/password validation
  - /api/register also wires up the user so /win/api/* gets 200 instead
    of 401 (proves the middleware sees the new enterprise)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from platform_app import db


def _client():
    from platform_app.main import app

    return TestClient(app)


def _mint_code(note: str = "test", days: int = 30) -> str:
    from platform_app.admin import _generate_invite_code

    code = _generate_invite_code()
    db.insert_invite(code, created_by="test", note=note, expires_at_epoch=None if days == 0 else (
        __import__("time").time().__int__() + days * 86400
    ))
    return code


def test_invite_lookup_unknown_code():
    c = _client()
    r = c.get("/api/invite/WIN-AAAA-AAAA")
    assert r.status_code == 200
    assert r.json() == {"valid": False, "reason": "invalid_code"}


def test_invite_lookup_bad_format():
    c = _client()
    r = c.get("/api/invite/not-a-code")
    assert r.status_code == 200
    assert r.json()["valid"] is False
    assert r.json()["reason"] == "invalid_format"


def test_invite_lookup_active():
    code = _mint_code()
    c = _client()
    r = c.get(f"/api/invite/{code}")
    assert r.status_code == 200
    assert r.json() == {"valid": True}


def test_register_happy_path_creates_everything():
    code = _mint_code()
    c = _client()

    body = {
        "code": code,
        "username": "alice",
        "password": "supersecret123",
        "display_name": "Alice 测试",
        "email": "alice@example.com",
    }
    r = c.post("/api/register", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["redirect"] == "/win/"
    assert data["user_id"] == "u_alice"
    # Server set the auth cookie
    assert "app_session" in r.cookies

    # User row was created
    user_row = db.main().execute(
        "SELECT id, username, display_name, email FROM users WHERE id=%s",
        ("u_alice",),
    ).fetchone()
    assert user_row["username"] == "alice"
    assert user_row["display_name"] == "Alice 测试"
    assert user_row["email"] == "alice@example.com"

    # Per-user enterprise was created with plan='trial'
    ent = db.main().execute(
        "SELECT id, plan, onboarding_stage FROM enterprises WHERE id=%s",
        ("e_alice",),
    ).fetchone()
    assert ent["plan"] == "trial"
    assert ent["onboarding_stage"] == "signed_up"

    # Membership row links them as owner
    mem = db.main().execute(
        "SELECT role FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        ("u_alice", "e_alice"),
    ).fetchone()
    assert mem["role"] == "owner"

    # Code is now redeemed
    invite = db.get_invite(code)
    assert invite["redeemed_at"] is not None
    assert invite["redeemed_by_user_id"] == "u_alice"
    assert invite["redeemed_enterprise_id"] == "e_alice"

    # Subsequent /api/invite/<same code> says redeemed
    r2 = c.get(f"/api/invite/{code}")
    assert r2.json() == {"valid": False, "reason": "code_redeemed"}


def test_register_double_use_same_code():
    code = _mint_code()
    c = _client()
    body = {
        "code": code, "username": "first", "password": "passwd1234",
        "display_name": "First", "email": None,
    }
    assert c.post("/api/register", json=body).status_code == 200

    body["username"] = "second"
    body["display_name"] = "Second"
    r = c.post("/api/register", json=body)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "code_redeemed"


def test_register_revoked_code():
    code = _mint_code()
    db.revoke_invite(code)
    c = _client()
    r = c.post("/api/register", json={
        "code": code, "username": "bob", "password": "passwd1234",
        "display_name": "Bob",
    })
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "code_revoked"


def test_register_username_collision():
    # Mint two codes; first user registers as "carol", second tries same name
    c1 = _mint_code()
    c2 = _mint_code()
    c = _client()
    r1 = c.post("/api/register", json={
        "code": c1, "username": "carol", "password": "passwd1234",
        "display_name": "Carol",
    })
    assert r1.status_code == 200

    r2 = c.post("/api/register", json={
        "code": c2, "username": "carol", "password": "passwd1234",
        "display_name": "Carol-2",
    })
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "username_taken"

    # Critically: second code must NOT be marked redeemed (transaction rolled back)
    inv2 = db.get_invite(c2)
    assert inv2["redeemed_at"] is None, "code 2 was burned despite the failed insert"


@pytest.mark.parametrize("body, expected", [
    ({"code": "not-a-code", "username": "x", "password": "p"}, "invalid_code"),
    ({"code": "WIN-AAAA-AAAA", "username": "ab", "password": "passwd1234",
      "display_name": "X"}, "invalid_username"),
    ({"code": "WIN-AAAA-AAAA", "username": "valid", "password": "short",
      "display_name": "X"}, "password_too_short"),
])
def test_register_validation_errors(body, expected):
    c = _client()
    r = c.post("/api/register", json=body)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == expected


def test_register_followed_by_win_request():
    """Full flow: register, then call /win/api/customers using the same
    cookie. The middleware should resolve the new enterprise and provision
    its tenant DB lazily; the response should be a 200 with an empty list."""
    code = _mint_code()
    c = _client()
    r = c.post("/api/register", json={
        "code": code, "username": "dawn", "password": "passwd1234",
        "display_name": "Dawn",
    })
    assert r.status_code == 200
    # TestClient does not auto-persist cookies across requests; resend
    # the session cookie explicitly.
    sid = r.cookies.get("app_session")
    assert sid
    r2 = c.get("/win/api/customers", cookies={"app_session": sid})
    assert r2.status_code == 200, r2.text
    assert isinstance(r2.json(), list)
    # Cleanup the per-tenant DB we just provisioned to keep test idempotent.
    import asyncio
    from yunwei_win.db import dispose_all
    asyncio.get_event_loop().run_until_complete(dispose_all()) if False else asyncio.new_event_loop().run_until_complete(dispose_all())
    db.main().execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'tenant_e_dawn' AND pid != pg_backend_pid()",
        (),
    )
    db.main().execute('DROP DATABASE IF EXISTS "tenant_e_dawn"', ())
