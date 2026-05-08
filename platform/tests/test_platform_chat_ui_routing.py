"""Phase 1 platform chat UI routing tests.

Verifies the catch_all static-vs-proxy split:
- GET /<client>/<agent>/ serves app/dist/index.html (when present)
- GET /<client>/<agent>/index.html serves app/dist/index.html
- GET /<client>/<agent>/assets/<file> serves from app/dist/assets/
- GET /<client>/<agent>/base-href.js serves from app/dist/
- Non-static subpaths fall through to reverse_proxy
- If app/dist/index.html does NOT exist (deploy-safe fallback), every
  request falls through to reverse_proxy (Phase 1 ships independently
  of when app/dist/ is populated).
"""
from __future__ import annotations
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from platform_app import auth, db
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_session():
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_chat", "chatuser", auth.hash_password("p"), "Chat User", now),
    )
    # enterprises FK is required by enterprise_members
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "银湖", "银湖", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_chat", "yinhu", "member", now),
    )
    sid, _ = auth.create_session("u_chat", "127.0.0.1", "test")
    return sid


# --- helpers ---------------------------------------------------------------

NAV_HEADERS = {
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}
SUBRESOURCE_HEADERS = {
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "same-origin",
    "referer": "http://testserver/yinhu/super-xiaochen/",
}


@pytest.fixture
def fake_app_dist(tmp_path, monkeypatch):
    """Point platform_app.main._APP_DIST at a tmp dir with a fake build.

    Yields the dist Path so tests can write/delete index.html as needed.
    catch_all derives index/asset paths from _APP_DIST inside the function,
    so a single monkeypatch is sufficient (no derived constants to update).
    """
    from platform_app import main as main_mod

    dist = tmp_path / "app" / "dist"
    dist.mkdir(parents=True)
    # Include a bare <script> + <style> so the CSP nonce-injection branch is
    # actually exercised (rather than no-op'd by the absence of inline tags).
    (dist / "index.html").write_text(
        "<!doctype html><html><head>"
        "<title>运帷 AI · 平台 chat UI</title>"
        "<script src=\"./base-href.js\"></script>"
        "<script>window.__BOOT__ = 1;</script>"
        "<style>body{color:red}</style>"
        "</head><body><div id=root></div></body></html>",
        encoding="utf-8",
    )
    (dist / "base-href.js").write_text("(function(){})();", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "index-deadbeef.js").write_text("/* fake bundle */", encoding="utf-8")

    monkeypatch.setattr(main_mod, "_APP_DIST", dist)
    return dist


# --- positive cases (app/dist populated) -----------------------------------


def test_root_serves_spa_shell(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<title>运帷 AI · 平台 chat UI</title>" in r.text
    assert r.headers.get("cache-control", "").lower().startswith("no-store")


def test_index_html_serves_spa_shell(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/index.html",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<title>运帷 AI · 平台 chat UI</title>" in r.text


def test_assets_served_from_app_dist(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/assets/index-deadbeef.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 200
    assert "fake bundle" in r.text


def test_base_href_js_served_from_app_dist(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/base-href.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 200
    assert r.text == "(function(){})();"


def test_unknown_asset_under_assets_returns_404(client, authed_session, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/assets/does-not-exist.js",
        cookies={"app_session": authed_session},
        headers=SUBRESOURCE_HEADERS,
    )
    assert r.status_code == 404


def test_csp_nonce_injected_when_header_present(
    client, authed_session, fake_app_dist
):
    """fake_app_dist's index.html contains a bare `<script>` and a bare
    `<style>` — both must be rewritten to carry the nonce attribute."""
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers={**NAV_HEADERS, "x-csp-nonce": "abc123"},
    )
    assert r.status_code == 200
    assert '<script nonce="abc123">window.__BOOT__' in r.text
    assert '<style nonce="abc123">body{color:red}' in r.text


def test_csp_nonce_no_op_when_header_absent(
    client, authed_session, fake_app_dist
):
    """Without the X-CSP-Nonce header, HTML is served verbatim."""
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": authed_session},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 200
    assert "<script>window.__BOOT__" in r.text
    assert "<style>body{color:red}" in r.text
    assert "nonce=" not in r.text


# --- pass-through cases (non-static subpaths) ------------------------------


def test_chat_post_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    """POST /<client>/<agent>/chat must NOT be intercepted by static logic
    even when app/dist exists; it's an API call destined for the agent."""
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"proxied": True})
        r = client.post(
            "/yinhu/super-xiaochen/chat",
            cookies={"app_session": authed_session},
            headers={**SUBRESOURCE_HEADERS, "x-csrf-token": "x"},
            json={"message": "hi", "session_id": "s1"},
        )
    assert mock_proxy.called, "API POST must reach reverse_proxy"


def test_get_history_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"history": []})
        r = client.get(
            "/yinhu/super-xiaochen/history",
            cookies={"app_session": authed_session},
            headers=SUBRESOURCE_HEADERS,
        )
    assert mock_proxy.called, "API GET /history must reach reverse_proxy"


def test_agent_static_fonts_falls_through_to_proxy(
    client, authed_session, fake_app_dist
):
    """The agent serves its own /static/fonts/*.woff2 — those must reach
    the agent, not be looked up under app/dist/."""
    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import Response
        mock_proxy.return_value = Response(b"woff2 data", media_type="font/woff2")
        r = client.get(
            "/yinhu/super-xiaochen/static/fonts/foo.woff2",
            cookies={"app_session": authed_session},
            headers=SUBRESOURCE_HEADERS,
        )
    assert mock_proxy.called, "agent /static/* must reach reverse_proxy"


# --- deploy-safe fallback (app/dist absent) --------------------------------


def test_deploy_safe_fallback_when_index_missing(
    client, authed_session, tmp_path, monkeypatch
):
    """If app/dist/index.html does not exist, every request falls through
    to reverse_proxy. Phase 1 ships safely before stage 1 populates dist."""
    from platform_app import main as main_mod
    empty = tmp_path / "app" / "dist"
    empty.mkdir(parents=True)
    monkeypatch.setattr(main_mod, "_APP_DIST", empty)

    with patch("platform_app.main.proxy.reverse_proxy") as mock_proxy:
        from fastapi.responses import JSONResponse
        mock_proxy.return_value = JSONResponse({"legacy": True})
        r = client.get(
            "/yinhu/super-xiaochen/",
            cookies={"app_session": authed_session},
            headers=NAV_HEADERS,
        )
    assert mock_proxy.called, "missing dist must fall through to proxy"


# --- ACL / auth still enforced --------------------------------------------


def test_unauthed_static_request_rejected(client, fake_app_dist):
    r = client.get(
        "/yinhu/super-xiaochen/",
        headers=NAV_HEADERS,
    )
    # No cookie → auth fails before static branch is even consulted.
    assert r.status_code in (401, 403)


def test_acl_denied_static_request_rejected(client, fake_app_dist):
    """User exists but has no enterprise_members row for yinhu — must 403
    even though the SPA shell is harmless to leak (defense in depth)."""
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_no_acl", "noacl", auth.hash_password("p"), "No ACL", int(time.time())),
    )
    # Intentionally: no enterprise_members insert — user has no ACL
    sid, _ = auth.create_session("u_no_acl", "127.0.0.1", "test")
    r = client.get(
        "/yinhu/super-xiaochen/",
        cookies={"app_session": sid},
        headers=NAV_HEADERS,
    )
    assert r.status_code == 403
