"""/api/* 路由(SSO.md §2)."""
from __future__ import annotations
import re
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from . import auth, db
from .context import AuthContext
from .entitlements import entitlements_for
from .settings import settings

router = APIRouter()

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
_INVITE_RE = re.compile(r"^WIN-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _user_from_request(request: Request) -> dict:
    cookie = request.cookies.get("app_session")
    user = auth.current_user_from_request(cookie)
    if not user:
        raise HTTPException(401, {"error": "not_logged_in", "message": "请登录"})
    return user


@router.get("/api/me")
def me(request: Request):
    """Return the caller's identity + enterprise context + entitlements.

    Auth surface for the SaaS chrome:
      - ``id`` / ``username`` / ``display_name``: from the session cookie.
      - ``is_platform_admin`` / ``enterprises``: classic platform-admin flag
        and the list of enterprises the user is a member of (used by the
        login-landing chrome to render an enterprise picker).
      - ``enterprise_id`` / ``enterprise_plan`` / ``enterprise_role``: the
        active tenant (first enterprise, matching ``require_auth_context``).
        ``None`` if the user has no enterprise membership yet.
      - ``entitlements``: capability flags derived from the active plan;
        ``None`` when the user has no enterprise.

    Unlike the ``/api/win/*`` middleware, this handler is tolerant of the
    no-enterprise case so the chrome can still render something useful
    for users mid-onboarding. Unauthenticated callers get the legacy
    ``{"error": ..., "message": ...}`` envelope (not FastAPI's default
    ``{"detail": ...}``).
    """
    cookie = request.cookies.get("app_session")
    user = auth.current_user_from_request(cookie)
    if not user:
        return JSONResponse(
            {"error": "not_logged_in", "message": "请登录"},
            status_code=401,
        )
    enterprises = db.list_user_enterprises(user["id"])
    active = enterprises[0] if enterprises else None
    enterprise_id = active["id"] if active else None
    enterprise_plan = (active.get("plan") if active else None) or None
    enterprise_role = (active.get("role") if active else None) or None

    entitlements_payload: dict | None = None
    if active is not None:
        ctx = AuthContext(
            user_id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            session_id=user["session_id"],
            enterprise_id=active["id"],
            enterprise_plan=enterprise_plan or "trial",
            enterprise_role=enterprise_role or "member",
        )
        ent = entitlements_for(ctx)
        entitlements_payload = {
            "runtime_mode": ent.runtime_mode,
            "can_use_shared_assistant": ent.can_use_shared_assistant,
            "can_use_dedicated_runtime": ent.can_use_dedicated_runtime,
            "allowed_tools": list(ent.allowed_tools),
        }

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_platform_admin": db.is_platform_admin(user["id"]),
        "enterprises": enterprises,
        "enterprise_id": enterprise_id,
        "enterprise_plan": enterprise_plan,
        "enterprise_role": enterprise_role,
        "entitlements": entitlements_payload,
    }


@router.patch("/api/me")
def update_me(request: Request, body: dict = Body(...)):
    """Update the caller's own profile. Currently only ``display_name``.

    Session-cookie authenticated like the rest of ``/api/*`` (no CSRF
    header — same-origin SOP covers it, see ``firewall.check_request``).
    The user row is read fresh on every ``/api/me`` call, so no cache
    invalidation is needed for the new name to show up.
    """
    user = _user_from_request(request)
    if "display_name" not in body:
        raise HTTPException(400, {"error": "nothing_to_update", "message": "没有可更新的字段"})
    display_name = (body.get("display_name") or "").strip()
    if len(display_name) < 1 or len(display_name) > 64:
        raise HTTPException(400, {"error": "invalid_display_name", "message": "显示名 1-64 字"})
    db.main().execute(
        "UPDATE users SET display_name=%s WHERE id=%s", (display_name, user["id"]),
    )
    return {"ok": True, "display_name": display_name}


@router.get("/api/agents")
def agents(request: Request):
    user = _user_from_request(request)
    rows = db.main().execute(
        "SELECT t.client_id, t.agent_id, t.display_name, t.icon_url, "
        "       t.description, t.health "
        "FROM tenants t "
        "WHERE t.active=1 AND ("
        "  t.client_id IN ("
        "    SELECT enterprise_id FROM enterprise_members WHERE user_id=%s"
        "  ) "
        "  OR (t.client_id, t.agent_id) IN ("
        "    SELECT client_id, agent_id FROM agent_grants WHERE user_id=%s"
        "  )"
        ") "
        "ORDER BY t.display_name",
        (user["id"], user["id"]),
    ).fetchall()
    return {
        "agents": [
            {
                "client": r["client_id"],
                "agent": r["agent_id"],
                "display_name": r["display_name"],
                "icon": r["icon_url"],
                "description": r["description"],
                "health": r["health"],
                "url": f"/{r['client_id']}/{r['agent_id']}/",
            }
            for r in rows
        ]
    }


@router.post("/api/auth/login")
async def login(request: Request, response: Response):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    user_id = auth.authenticate(username, password)
    if not user_id:
        raise HTTPException(401, {"error": "invalid_credentials", "message": "用户名或密码错误"})
    # 旧 cookie 撤销(防 fixation)
    old = request.cookies.get("app_session")
    if old:
        auth.revoke_session(old)
    sid, csrf = auth.create_session(
        user_id, request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    response.set_cookie("app_session", sid, httponly=True, secure=True, samesite="lax",
                       max_age=settings.session_lifetime_seconds, path="/")
    response.set_cookie("app_csrf", csrf, httponly=False, secure=True, samesite="strict",
                       max_age=settings.csrf_lifetime_seconds, path="/")
    return {"ok": True, "redirect": "/dashboard"}


@router.get("/api/invite/{code}")
def check_invite(code: str):
    """Public: returns whether an invite code is currently redeemable.

    The register page calls this on input to give immediate feedback
    before the user fills out the full form.
    """
    code = code.strip().upper()
    if not _INVITE_RE.match(code):
        return {"valid": False, "reason": "invalid_format"}
    info = db.get_invite(code)
    if not info:
        return {"valid": False, "reason": "invalid_code"}
    if info["redeemed_at"]:
        return {"valid": False, "reason": "code_redeemed"}
    if info["revoked_at"]:
        return {"valid": False, "reason": "code_revoked"}
    if info["expires_at"]:
        # tz-aware compare via DB
        row = db.main().execute(
            "SELECT expires_at < now() AS expired FROM invite_codes WHERE code=%s",
            (code,),
        ).fetchone()
        if row and row["expired"]:
            return {"valid": False, "reason": "code_expired"}
    return {"valid": True}


@router.post("/api/auth/register")
def register(request: Request, response: Response, body: dict = Body(...)):
    """Trial registration: invite code → new user + per-user enterprise."""
    code = (body.get("code") or "").strip().upper()
    username = (body.get("username") or "").strip().lower()
    password = body.get("password") or ""
    display_name = (body.get("display_name") or username).strip()
    email = (body.get("email") or "").strip() or None

    if not _INVITE_RE.match(code):
        raise HTTPException(400, {"error": "invalid_code", "message": "邀请码格式不对"})
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, {"error": "invalid_username",
                                  "message": "用户名 3-32 字符,只能用小写字母 / 数字 / _ / -,且不能数字开头"})
    if len(password) < 8:
        raise HTTPException(400, {"error": "password_too_short",
                                  "message": "密码至少 8 位"})
    if len(display_name) < 1 or len(display_name) > 64:
        raise HTTPException(400, {"error": "invalid_display_name",
                                  "message": "显示名 1-64 字"})

    user_id = f"u_{username}"
    enterprise_id = f"e_{username}"
    pwd_hash = auth.hash_password(password)

    try:
        db.redeem_invite_and_register(
            invite_code=code,
            user_id=user_id,
            username=username,
            password_hash=pwd_hash,
            display_name=display_name,
            email=email,
            enterprise_id=enterprise_id,
        )
    except db.InviteError as e:
        raise HTTPException(409, {"error": e.code, "message": e.message})

    sid, csrf = auth.create_session(
        user_id,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    response.set_cookie("app_session", sid, httponly=True, secure=True,
                       samesite="lax", max_age=settings.session_lifetime_seconds, path="/")
    response.set_cookie("app_csrf", csrf, httponly=False, secure=True,
                       samesite="strict", max_age=settings.csrf_lifetime_seconds, path="/")
    return {"ok": True, "redirect": "/dashboard", "user_id": user_id}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get("app_session")
    if sid:
        auth.revoke_session(sid)
    response.delete_cookie("app_session", path="/")
    response.delete_cookie("app_csrf", path="/")
    return {"ok": True}


@router.post("/api/auth/change-password")
def change_password(request: Request, body: dict = Body(...)):
    """Change the caller's own password.

    Verifies the current password (constant-time bcrypt), enforces the
    same ≥8-char rule as registration, then revokes every *other* session
    so a leaked cookie elsewhere is logged out. The current session stays
    valid so the caller isn't bounced to the login page.
    """
    user = _user_from_request(request)
    current = body.get("current_password") or ""
    new = body.get("new_password") or ""
    if len(new) < 8:
        raise HTTPException(400, {"error": "password_too_short", "message": "新密码至少 8 位"})
    row = db.main().execute(
        "SELECT password_hash FROM users WHERE id=%s", (user["id"],),
    ).fetchone()
    if not row or not auth.verify_password(current, row["password_hash"]):
        raise HTTPException(403, {"error": "wrong_password", "message": "当前密码不正确"})
    if auth.verify_password(new, row["password_hash"]):
        raise HTTPException(400, {"error": "password_unchanged", "message": "新密码不能与当前密码相同"})
    db.main().execute(
        "UPDATE users SET password_hash=%s WHERE id=%s",
        (auth.hash_password(new), user["id"]),
    )
    # Log out other devices; keep this session alive.
    others = db.main().execute(
        "SELECT id FROM platform_sessions WHERE user_id=%s AND id != %s",
        (user["id"], user["session_id"]),
    ).fetchall()
    for r in others:
        auth.revoke_session(r["id"])
    return {"ok": True}


@router.post("/csp-report")
async def csp_report(request: Request):
    body = await request.body()
    print(f"[csp-report] {body[:500]!r}", flush=True)
    return Response(status_code=204)
