"""Tests for ``platform_app.context.require_auth_context``.

Covers:
  - No cookie → 401 ``not_logged_in``.
  - Valid cookie but user has no enterprise → 403 ``no_enterprise``.
  - Valid cookie + enterprise membership → AuthContext with user_id,
    enterprise_id, plan and role populated.
"""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException, Request

from platform_app import auth, db
from platform_app.context import AuthContext, require_auth_context


def _fake_request(*, cookie: str | None) -> Request:
    """Build a minimal ASGI scope so ``require_auth_context`` can call
    ``request.cookies.get(...)``. We never await anything here."""
    headers = []
    if cookie is not None:
        headers.append((b"cookie", f"app_session={cookie}".encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/win/customers",
        "headers": headers,
    }
    return Request(scope)


def test_require_auth_context_no_cookie_raises_401():
    req = _fake_request(cookie=None)
    with pytest.raises(HTTPException) as exc:
        require_auth_context(req)
    assert exc.value.status_code == 401
    assert exc.value.detail == {"error": "not_logged_in", "message": "请登录"}


def test_require_auth_context_invalid_cookie_raises_401():
    req = _fake_request(cookie="not-a-real-session-id")
    with pytest.raises(HTTPException) as exc:
        require_auth_context(req)
    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "not_logged_in"


def test_require_auth_context_user_without_enterprise_raises_403():
    # Create a bare user + session, but no enterprise_members row.
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        ("u_noent", "noent", auth.hash_password("pw"), "No Enterprise", now),
    )
    sid, _csrf = auth.create_session("u_noent", ip=None, ua=None)
    req = _fake_request(cookie=sid)

    with pytest.raises(HTTPException) as exc:
        require_auth_context(req)
    assert exc.value.status_code == 403
    assert exc.value.detail == {"error": "no_enterprise", "message": "当前账号未绑定企业"}


def test_require_auth_context_happy_path_returns_authcontext():
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        ("u_eve", "eve", auth.hash_password("pw"), "Eve 测试", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        ("e_eve", "Eve Inc", "Eve Display", "pro", "signed_up", now),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at, granted_by) "
        "VALUES (%s, %s, %s, %s, %s)",
        ("u_eve", "e_eve", "owner", now, "test"),
    )
    sid, _csrf = auth.create_session("u_eve", ip=None, ua=None)
    req = _fake_request(cookie=sid)

    ctx = require_auth_context(req)
    assert isinstance(ctx, AuthContext)
    assert ctx.user_id == "u_eve"
    assert ctx.username == "eve"
    assert ctx.display_name == "Eve 测试"
    assert ctx.session_id == sid
    assert ctx.enterprise_id == "e_eve"
    assert ctx.enterprise_plan == "pro"
    assert ctx.enterprise_role == "owner"
