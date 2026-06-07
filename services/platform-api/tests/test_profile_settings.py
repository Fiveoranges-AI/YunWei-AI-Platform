"""Profile self-service settings: PATCH /api/me + change-password.

Covers the two endpoints backing the win-web 设置 page:
- editing one's own display name
- changing one's own password (with current-password check + other-session
  revocation, current session preserved).
"""
from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _mk_user(uid: str, username: str, password: str = "p") -> str:
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        (uid, username, auth.hash_password(password), username, int(time.time())),
    )
    sid, _ = auth.create_session(uid, "127.0.0.1", "test")
    return sid


@pytest.fixture
def session():
    db.init()
    return _mk_user("u_a", "alice", "currentpw1")


# ─── PATCH /api/me ──────────────────────────────────────────────

def test_update_display_name(client, session):
    r = client.patch("/api/me", json={"display_name": "许总"},
                     cookies={"app_session": session})
    assert r.status_code == 200
    assert r.json()["display_name"] == "许总"
    # GET /api/me reflects the new name.
    me = client.get("/api/me", cookies={"app_session": session}).json()
    assert me["display_name"] == "许总"


def test_update_display_name_trims(client, session):
    r = client.patch("/api/me", json={"display_name": "  Bob  "},
                     cookies={"app_session": session})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Bob"


def test_update_display_name_rejects_empty(client, session):
    r = client.patch("/api/me", json={"display_name": "   "},
                     cookies={"app_session": session})
    assert r.status_code == 400


def test_update_display_name_rejects_too_long(client, session):
    r = client.patch("/api/me", json={"display_name": "x" * 65},
                     cookies={"app_session": session})
    assert r.status_code == 400


def test_update_me_requires_login(client, session):
    r = client.patch("/api/me", json={"display_name": "X"})
    assert r.status_code == 401


# ─── POST /api/auth/change-password ─────────────────────────────

def test_change_password_success(client, session):
    r = client.post("/api/auth/change-password",
                    json={"current_password": "currentpw1", "new_password": "brandnew99"},
                    cookies={"app_session": session})
    assert r.status_code == 200
    # Old password no longer authenticates; new one does.
    assert auth.authenticate("alice", "currentpw1") is None
    assert auth.authenticate("alice", "brandnew99") == "u_a"


def test_change_password_wrong_current(client, session):
    r = client.post("/api/auth/change-password",
                    json={"current_password": "WRONG", "new_password": "brandnew99"},
                    cookies={"app_session": session})
    assert r.status_code == 403
    assert auth.authenticate("alice", "currentpw1") == "u_a"  # unchanged


def test_change_password_too_short(client, session):
    r = client.post("/api/auth/change-password",
                    json={"current_password": "currentpw1", "new_password": "short"},
                    cookies={"app_session": session})
    assert r.status_code == 400


def test_change_password_unchanged_rejected(client, session):
    r = client.post("/api/auth/change-password",
                    json={"current_password": "currentpw1", "new_password": "currentpw1"},
                    cookies={"app_session": session})
    assert r.status_code == 400


def test_change_password_requires_login(client, session):
    r = client.post("/api/auth/change-password",
                    json={"current_password": "currentpw1", "new_password": "brandnew99"})
    assert r.status_code == 401


def test_change_password_revokes_other_sessions_keeps_current(client, session):
    # A second device for the same user.
    other_sid, _ = auth.create_session("u_a", "10.0.0.1", "other-device")
    assert auth.current_user_from_request(other_sid) is not None

    r = client.post("/api/auth/change-password",
                    json={"current_password": "currentpw1", "new_password": "brandnew99"},
                    cookies={"app_session": session})
    assert r.status_code == 200
    # Other device logged out; current session still valid.
    assert auth.current_user_from_request(other_sid) is None
    assert auth.current_user_from_request(session) is not None
