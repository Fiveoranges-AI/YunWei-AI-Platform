"""/api/* 路由(SSO.md §2)."""
from __future__ import annotations
import re
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from . import auth, db
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
    user = _user_from_request(request)
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_platform_admin": db.is_platform_admin(user["id"]),
        "enterprises": db.list_user_enterprises(user["id"]),
    }


@router.get("/api/agents")
def agents(request: Request):
    user = _user_from_request(request)
    # Visible agents = enterprise membership ∪ per-agent grants.
    rows = db.main().execute(
        "SELECT t.client_id, t.agent_id, t.display_name, t.icon_url, "
        "       t.description, t.health "
        "FROM tenants t "
        "WHERE t.active=1 AND ("
        "  t.client_id IN (SELECT enterprise_id FROM enterprise_members WHERE user_id=%s) "
        "  OR (t.client_id, t.agent_id) IN ("
        "       SELECT client_id, agent_id FROM agent_grants WHERE user_id=%s)"
        ") "
        "ORDER BY t.display_name",
        (user["id"], user["id"]),
    ).fetchall()
    return {"agents": [
        {"client": r["client_id"], "agent": r["agent_id"],
         "display_name": r["display_name"], "icon": r["icon_url"],
         "description": r["description"], "health": r["health"],
         "url": f"/{r['client_id']}/{r['agent_id']}/"}
        for r in rows
    ]}


@router.post("/auth/login")
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
    return {"ok": True}


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


@router.post("/api/register")
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
    return {"ok": True, "redirect": "/win/", "user_id": user_id}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get("app_session")
    if sid:
        auth.revoke_session(sid)
    response.delete_cookie("app_session", path="/")
    response.delete_cookie("app_csrf", path="/")
    return {"ok": True}


@router.post("/csp-report")
async def csp_report(request: Request):
    body = await request.body()
    print(f"[csp-report] {body[:500]!r}", flush=True)
    return Response(status_code=204)
