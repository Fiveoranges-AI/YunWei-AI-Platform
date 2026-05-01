"""FastAPI 入口 + 路由分发。"""
from __future__ import annotations
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import api, db, firewall, proxy
from .settings import settings

PATH_RE = re.compile(r"^/(?P<client>[a-z0-9-]{1,32})/(?P<agent>[a-z0-9-]{1,32})(?P<sub>/.*)?$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    from . import health
    task = asyncio.create_task(health.probe_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.include_router(api.router)

_STATIC = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


_NO_STORE = {"Cache-Control": "no-store, must-revalidate"}


@app.api_route("/", methods=["GET", "HEAD"])
def index(request: Request):
    # no-store: index branches on the app_session cookie, so the response
    # for "/" must never be cached. Without this, a browser that loaded
    # login.html before login will keep serving the cached login.html
    # after login until the user manually refreshes (Cmd+Shift+R).
    page = "agents.html" if request.cookies.get("app_session") else "login.html"
    return FileResponse(_STATIC / page, headers=_NO_STORE)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
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

    return await proxy.reverse_proxy(
        request, client_id=client_id, agent_id=agent_id, user=user, subpath=subpath,
    )
