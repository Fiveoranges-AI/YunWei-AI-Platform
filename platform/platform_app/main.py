"""FastAPI 入口 + 路由分发。"""
from __future__ import annotations
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import admin_api, api, context as _context, db, enterprise_api, firewall, proxy
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
    """For /win/api/* requests, resolve the caller's AuthContext from the
    app_session cookie and stamp it on request.state. yunwei_win.db reads
    ``request.state.enterprise_id`` to route the SQLAlchemy session to the
    right per-tenant database.

    The actual cookie → user → enterprise → plan resolution lives in
    :func:`platform_app.context.require_auth_context` so that the shared
    assistant and the runtime resolver can use the same hard boundary.
    """
    if request.url.path.startswith("/win/api/"):
        try:
            ctx = _context.require_auth_context(request)
        except HTTPException as exc:
            # Preserve the legacy JSONResponse shape so unauthenticated
            # callers see ``{"error": ..., "message": ...}`` rather than
            # FastAPI's default ``{"detail": ...}`` envelope.
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            return JSONResponse(detail, status_code=exc.status_code)
        request.state.auth_context = ctx
        request.state.enterprise_id = ctx.enterprise_id
        request.state.user_id = ctx.user_id
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
# yunwei-win-web/ is the /win/ SPA. Its dist/ ends up in two different
# layouts depending on environment:
#  - container:  /app/platform_app/main.py → parent.parent = /app
#                → /app/yunwei-win-web/dist  (Dockerfile copies it there)
#  - local dev:  <repo>/platform/platform_app/main.py → parent.parent.parent
#                = <repo> → <repo>/apps/yunwei-win-web/dist
# We probe both candidates and pick the first that exists; tests can
# monkeypatch _WIN_DIST to point at a fixture instead.
def _resolve_win_dist() -> Path:
    here = Path(__file__).resolve()
    # container layout: /app/yunwei-win-web/dist
    container_dist = here.parent.parent / "yunwei-win-web" / "dist"
    if container_dist.is_dir():
        return container_dist
    # local dev layout: <repo>/apps/yunwei-win-web/dist
    repo_dist = here.parent.parent.parent / "apps" / "yunwei-win-web" / "dist"
    if repo_dist.is_dir():
        return repo_dist
    # Neither exists yet (front-end not built); fall back to repo-root path
    # so the win_root handler can return a clear "win_not_built" 503 instead
    # of a misleading 500.
    return repo_dist


_WIN_DIST = _resolve_win_dist()
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
    #
    # Logged-in users go to /win/ (the 智通客户 SPA, the customer-facing
    # product). The legacy agents.html dashboard is no longer in the
    # customer path; it stays on disk for now and may be archived in a
    # follow-up task.
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return RedirectResponse("/win/", status_code=303, headers=_NO_STORE)


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
