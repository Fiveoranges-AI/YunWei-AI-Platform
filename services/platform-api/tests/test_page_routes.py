"""Page route smoke tests for /admin and the /win SPA.

The HTML payloads are not fully exercised here — we just confirm the
routes serve the expected static file when the user is logged in and
fall through to the login page otherwise.

Routes that used to exist but no longer do (``/data``,
``/enterprise/<id>``, the ``/<client>/<agent>`` HMAC catch-all,
``/api/agents``) have their 404 contract pinned in
``test_url_contract.py``.
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


@pytest.fixture
def logged_in():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_a", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    sid, _ = auth.create_session("u_a", "127.0.0.1", "test")
    return sid


def test_admin_page_serves_login_when_unauthed(client):
    db.init()
    r = client.get("/admin")
    # login.html marker (登录 in UTF-8) — same fall-through as /.
    assert r.status_code == 200
    assert b"\xe7\x99\xbb\xe5\xbd\x95" in r.content or b"login" in r.content.lower()


def test_root_serves_login_when_unauthed(client):
    """GET / without a session cookie returns the login page (200)."""
    db.init()
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    # login.html marker (登录 in UTF-8)
    assert b"\xe7\x99\xbb\xe5\xbd\x95" in r.content or b"login" in r.content.lower()


def test_root_redirects_to_win_when_authed(client, logged_in):
    """GET / with a valid session cookie redirects (303) to /win/.

    The legacy agents.html dashboard is no longer the logged-in entry
    point — customers land on the 智通客户 SPA at /win/.
    """
    r = client.get("/", cookies={"app_session": logged_in}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/win/"
    # Cache-Control: no-store must still be set so a browser that cached
    # the login.html response from before sign-in doesn't keep serving it.
    assert "no-store" in r.headers.get("cache-control", "")


def test_admin_page_serves_dashboard_when_authed(client, logged_in):
    r = client.get("/admin", cookies={"app_session": logged_in})
    assert r.status_code == 200
    # Dashboard marker (平台管理后台)
    assert b"\xe5\xb9\xb3\xe5\x8f\xb0\xe7\xae\xa1\xe7\x90\x86\xe5\x90\x8e\xe5\x8f\xb0" in r.content


def test_me_includes_platform_admin_and_enterprises(client, logged_in):
    """/api/me payload exposes is_platform_admin + enterprises so the
    chrome can hide/show the platform admin link.

    A logged-in user with no enterprise membership must still get a 200
    (we don't want to lock out mid-onboarding users). ``enterprise_id``
    and ``entitlements`` are ``None`` in that case — see
    ``test_url_contract.py`` for the enterprise-bound contract."""
    r = client.get("/api/me", cookies={"app_session": logged_in})
    assert r.status_code == 200
    body = r.json()
    assert body["is_platform_admin"] is False
    assert body["enterprises"] == []
    assert body["enterprise_id"] is None
    assert body["entitlements"] is None


def test_win_root_serves_spa_when_authed(client, logged_in):
    """/win/ should return the Win SPA shell (title + root div) when the
    user is logged in and the front-end has been built. If the dist/ dir
    is missing (CI without a build), accept the 503 win_not_built marker —
    we just want to verify the route is wired up and not 500ing."""
    from platform_app import main as _main

    r = client.get("/win/", cookies={"app_session": logged_in})
    if (_main._WIN_DIST / "index.html").is_file():
        assert r.status_code == 200
        # Win SPA markers: <title>智通客户 ...</title> + <div id="root">
        assert b"\xe6\x99\xba\xe9\x80\x9a\xe5\xae\xa2\xe6\x88\xb7" in r.content
        assert b'<div id="root">' in r.content
    else:
        # Front-end not built in this environment. Route must still respond
        # cleanly (503), not crash.
        assert r.status_code == 503


def test_me_marks_platform_admin(client):
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, "
        "is_platform_admin, created_at) VALUES (%s,%s,%s,%s,1,%s)",
        ("u_root", "root", auth.hash_password("p"), "Root", int(time.time())),
    )
    sid, _ = auth.create_session("u_root", "127.0.0.1", "test")
    r = client.get("/api/me", cookies={"app_session": sid})
    assert r.json()["is_platform_admin"] is True
