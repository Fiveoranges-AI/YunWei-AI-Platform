"""FastAPI 入口 + 路由分发。"""
from __future__ import annotations
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import admin_api, api, db, enterprise_api, firewall, proxy
from .data_layer import api as data_api
from .daily_report import api as daily_report_api
from .settings import settings
# yunwei_win (智通客户) — vendored from yunwei-tools, mounted at /win/api/.
# Per-enterprise Postgres database; lazy-provisioned on first access.
from yunwei_win import router as _win_router
from yunwei_win.db import dispose_all as _win_dispose

PATH_RE = re.compile(r"^/(?P<client>[a-z0-9-]{1,32})/(?P<agent>[a-z0-9-]{1,32})(?P<sub>/.*)?$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    from . import health
    from .daily_report import scheduler as dr_scheduler
    health_task = asyncio.create_task(health.probe_loop())
    scheduler_task = asyncio.create_task(dr_scheduler.run_forever())
    yield
    health_task.cancel()
    scheduler_task.cancel()
    await _win_dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(api.router)
app.include_router(data_api.router)
app.include_router(admin_api.router)
app.include_router(enterprise_api.router)
app.include_router(daily_report_api.router)
# /win/api/* — 智通客户 routes. The middleware below stamps
# request.state.enterprise_id from the app_session cookie, which
# yunwei_win.db.get_session reads to pick the right per-tenant DB.
# NB: yunwei_win's inner routers already mount under /api/* (legacy from
# yunwei-tools), so prefix is just /win/.
app.include_router(_win_router, prefix="/win")


@app.middleware("http")
async def _attach_enterprise(request: Request, call_next):
    """For /win/api/* requests, resolve the caller's enterprise from the
    app_session cookie and stamp it on request.state. yunwei_win.db reads
    this to route the SQLAlchemy session to the right per-tenant database."""
    if request.url.path.startswith("/win/api/"):
        cookie = request.cookies.get("app_session")
        if not cookie:
            return JSONResponse(
                {"error": "not_logged_in", "message": "请登录"}, status_code=401
            )
        from . import auth as _auth
        user = _auth.current_user_from_request(cookie)
        if not user:
            return JSONResponse(
                {"error": "not_logged_in", "message": "请登录"}, status_code=401
            )
        enterprises = db.list_user_enterprises(user["id"])
        if not enterprises:
            return JSONResponse(
                {"error": "no_enterprise", "message": "当前账号未绑定企业"},
                status_code=403,
            )
        # Spec: one user = one enterprise. If the data accidentally has more
        # than one row, take the first deterministically (sorted by name).
        request.state.enterprise_id = enterprises[0]["id"]
        request.state.user_id = user["id"]
    return await call_next(request)

_STATIC = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# app/dist/ holds the Phase 1+ chat UI build artifacts. Stage 1 of
# platform/Dockerfile populates it; if index.html is missing (e.g. an old
# image without the new stage), catch_all transparently falls through to
# reverse_proxy, preserving pre-Phase-1 behavior. This is the deploy-safety
# guarantee documented in 2026-05-07-platform-chat-ui-design.md.
#
# We compute index existence inside catch_all (not as a module-level
# constant) so tests can monkeypatch _APP_DIST and have the change picked up
# on the next request without touching a derived constant.
_APP_DIST = Path(__file__).parent.parent.parent / "app" / "dist"
# app-win/ lives INSIDE platform/ (one level up from platform_app), so:
#  - container:  /app/platform_app/main.py → /app → /app/app-win/dist
#  - local dev:  <repo>/platform/platform_app/main.py → <repo>/platform/ →
#                <repo>/platform/app-win/dist
_WIN_DIST = Path(__file__).resolve().parent.parent / "app-win" / "dist"
# Subpaths under /<client>/<agent>/ that the platform serves from app/dist
# instead of forwarding to the agent. Anything else proxies through.
_APP_STATIC_PREFIXES: tuple[str, ...] = ("/assets/", "/base-href.js", "/favicon.ico")


_NO_STORE = {"Cache-Control": "no-store, must-revalidate"}


@app.api_route("/", methods=["GET", "HEAD"])
def index(request: Request):
    # no-store: index branches on the app_session cookie, so the response
    # for "/" must never be cached. Without this, a browser that loaded
    # login.html before login will keep serving the cached login.html
    # after login until the user manually refreshes (Cmd+Shift+R).
    page = "agents.html" if request.cookies.get("app_session") else "login.html"
    return FileResponse(_STATIC / page, headers=_NO_STORE)


@app.api_route("/register", methods=["GET", "HEAD"])
def register_page():
    """Public: invite-code self-registration. No auth required."""
    return FileResponse(_STATIC / "register.html", headers=_NO_STORE)


@app.api_route("/data", methods=["GET", "HEAD"])
def data_console(request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "data.html", headers=_NO_STORE)


@app.api_route("/admin", methods=["GET", "HEAD"])
def admin_dashboard(request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "admin.html", headers=_NO_STORE)


# Must be declared *before* the customer-agent catch-all below — otherwise
# /enterprise/<id> would match the {client}/{agent} pattern and get
# reverse-proxied as if it were a tenant request.
@app.api_route("/enterprise/{enterprise_id}", methods=["GET", "HEAD"])
def enterprise_page(enterprise_id: str, request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "enterprise.html", headers=_NO_STORE)


# /win/ — 智通客户 SPA. Cross-enterprise visible: any logged-in user can hit
# this. The bundled JS calls /win/api/* which the middleware above scopes to
# the user's enterprise database.
@app.api_route("/win", methods=["GET", "HEAD"])
@app.api_route("/win/", methods=["GET", "HEAD"])
def win_root(request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    win_index = _WIN_DIST / "index.html"
    if not win_index.is_file():
        raise HTTPException(503, {"error": "win_not_built", "message": "前端未构建"})
    return HTMLResponse(win_index.read_text(encoding="utf-8"), headers=_NO_STORE)


@app.api_route("/win/{subpath:path}", methods=["GET", "HEAD"])
def win_static(subpath: str, request: Request):
    # /win/api/* is handled by the included router above; this route only
    # fires for non-api subpaths.
    if subpath.startswith("api/"):
        raise HTTPException(404)
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    asset = _WIN_DIST / subpath
    if asset.is_file():
        return FileResponse(asset)
    # SPA fallback: unknown route → serve index.html so client-side routing
    # works (vite/wouter etc).
    win_index = _WIN_DIST / "index.html"
    if win_index.is_file():
        return HTMLResponse(win_index.read_text(encoding="utf-8"), headers=_NO_STORE)
    raise HTTPException(404)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all(full_path: str, request: Request):
    m = PATH_RE.match("/" + full_path)
    if not m:
        raise HTTPException(404)

    client_id = m.group("client")
    agent_id = m.group("agent")
    subpath = m.group("sub") or "/"

    # auth
    user = api._user_from_request(request)

    # ACL
    if not db.has_acl(user["id"], client_id, agent_id):
        raise HTTPException(403, {"error": "not_authorized_for_tenant", "message": "无权访问"})

    # §7.2 firewall
    try:
        firewall.check_request(
            sec_fetch_mode=request.headers.get("sec-fetch-mode"),
            sec_fetch_site=request.headers.get("sec-fetch-site"),
            referer=request.headers.get("referer"),
            host=request.headers.get("host", ""),
            dest_path_prefix=f"/{client_id}/{agent_id}/",
            csrf_header=request.headers.get("x-csrf-token"),
            csrf_cookie=request.cookies.get("app_csrf"),
            method=request.method,
        )
    except firewall.FirewallReject as e:
        raise HTTPException(403, {"error": "cross_agent_blocked", "message": str(e)})

    # Phase 1: serve the new chat UI from app/dist when populated. The
    # exists() check is the deploy-safe fallback — if the platform image
    # hasn't been rebuilt with the node stage yet, every request falls
    # through to the existing reverse_proxy path below.
    app_index = _APP_DIST / "index.html"
    if request.method in ("GET", "HEAD") and app_index.exists():
        if subpath in ("/", "/index.html"):
            html = app_index.read_text(encoding="utf-8")
            nonce = request.headers.get("x-csp-nonce", "")
            if nonce:
                html = html.replace("<script>", f'<script nonce="{nonce}">')
                html = html.replace("<style>", f'<style nonce="{nonce}">')
            return HTMLResponse(html, headers=_NO_STORE)
        for prefix in _APP_STATIC_PREFIXES:
            if subpath.startswith(prefix) or subpath == prefix.rstrip("/"):
                asset = _APP_DIST / subpath.lstrip("/")
                if not asset.is_file():
                    raise HTTPException(404)
                return FileResponse(asset)

    return await proxy.reverse_proxy(
        request, client_id=client_id, agent_id=agent_id, user=user, subpath=subpath,
    )
