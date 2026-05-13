"""FastAPI 入口 + 路由分发。"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import admin_api, api, context as _context, db, enterprise_api
from .data_layer import api as data_api
from .daily_report import api as daily_report_api
# yunwei_win (智通客户) — vendored from yunwei-tools, mounted at /api/win/.
# Per-enterprise Postgres database; lazy-provisioned on first access.
from yunwei_win import router as _win_router
from yunwei_win.db import dispose_all as _win_dispose


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
# /api/win/* — 智通客户 routes. The middleware below stamps
# request.state.enterprise_id from the app_session cookie, which
# yunwei_win.db.get_session reads to pick the right per-tenant DB.
app.include_router(_win_router, prefix="/api/win")


@app.middleware("http")
async def _attach_enterprise(request: Request, call_next):
    """For /api/win/* requests, resolve the caller's AuthContext from the
    app_session cookie and stamp it on request.state. yunwei_win.db reads
    ``request.state.enterprise_id`` to route the SQLAlchemy session to the
    right per-tenant database.

    The actual cookie → user → enterprise → plan resolution lives in
    :func:`platform_app.context.require_auth_context` so that the shared
    assistant and the runtime resolver can use the same hard boundary.

    Only ``/api/win/*`` needs a hard enterprise binding here — admin /
    enterprise / ``/api/me`` endpoints either run their own auth check
    (``_require_platform_admin`` / ``_require_member``) or are tolerant
    of the no-enterprise case (the chrome's ``/api/me`` call).
    """
    if request.url.path.startswith("/api/win/"):
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


_NO_STORE = {"Cache-Control": "no-store, must-revalidate"}


@app.api_route("/", methods=["GET", "HEAD"])
def index(request: Request):
    # no-store: index branches on the app_session cookie, so the response
    # for "/" must never be cached. Without this, a browser that loaded
    # login.html before login will keep serving the cached login.html
    # after login until the user manually refreshes (Cmd+Shift+R).
    #
    # Logged-in users go to /win/ (the 智通客户 SPA, the customer-facing
    # product). The legacy agents.html dashboard has been archived under
    # docs/migration/archive/ and is no longer in the customer path.
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return RedirectResponse("/win/", status_code=303, headers=_NO_STORE)


@app.api_route("/register", methods=["GET", "HEAD"])
def register_page():
    """Public: invite-code self-registration. No auth required."""
    return FileResponse(_STATIC / "register.html", headers=_NO_STORE)


@app.api_route("/admin", methods=["GET", "HEAD"])
def admin_dashboard(request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "admin.html", headers=_NO_STORE)


# /win/ — 智通客户 SPA. Cross-enterprise visible: any logged-in user can hit
# this. The bundled JS calls /api/win/* which the middleware above scopes to
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


@app.api_route(
    "/win/{subpath:path}",
    methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
)
def win_static(subpath: str, request: Request):
    # /win/api/* used to be the API mount but has moved to /api/win/*.
    # No legacy aliases / redirects — must 404 outright (for *any* method)
    # so the SPA can rely on a single canonical surface and stale clients
    # don't silently keep working against the old prefix.
    if subpath.startswith("api/") or subpath == "api":
        raise HTTPException(404)
    # Non-API sub-paths only serve GET/HEAD (static assets / SPA shell).
    if request.method not in ("GET", "HEAD"):
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
