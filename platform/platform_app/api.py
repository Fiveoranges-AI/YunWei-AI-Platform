"""/api/* 路由(SSO.md §2)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from . import auth, db
from .settings import settings

router = APIRouter()


def _user_from_request(request: Request) -> dict:
    cookie = request.cookies.get("app_session")
    user = auth.current_user_from_request(cookie)
    if not user:
        raise HTTPException(401, {"error": "not_logged_in", "message": "请登录"})
    return user


@router.get("/api/me")
def me(request: Request):
    user = _user_from_request(request)
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"]}


@router.get("/api/agents")
def agents(request: Request):
    user = _user_from_request(request)
    rows = db.main().execute(
        "SELECT t.client_id, t.agent_id, t.display_name, t.icon_url, t.description, t.health "
        "FROM tenants t JOIN user_tenant ut ON t.client_id=ut.client_id AND t.agent_id=ut.agent_id "
        "WHERE ut.user_id=? AND t.active=1",
        (user["id"],),
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
