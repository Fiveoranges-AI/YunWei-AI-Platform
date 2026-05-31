"""光天 demo 用的轻量 FastAPI dev launcher.

**仅供前端 backend-mode 演示**. 不是生产入口. 跳过 platform middleware (无 cookie
auth / 无 Redis / 无平台用户表), 直接把 yunwei_win router 挂到 `/api/win/*`,
中间件 stamp 一个固定 ``enterprise_id = guangtian_demo`` 让 per-tenant DB 自动
provision 出 ``tenant_guangtian_demo`` SQLite 文件. 启动时自动 seed 8 个 SKU +
开账库存 + 3 张客户订单 (复刻前端 data.ts).

启动:
    python dev_guangtian_backend.py
    # 默认监听 127.0.0.1:8000 + CORS 允许 127.0.0.1:5175

DB 文件落在 ``./guangtian_dev_admin.db`` (platform admin DB) +
``./yinhu_tenant_guangtian_demo.db`` (tenant DB). 删两个文件即可重置.

与锦泰 dev launcher (``dev_jintai_backend.py``) 共存: 不同 enterprise_id → 不同
tenant DB, 物理隔离. 同一时间只起一个 (都用 8000 端口) 或改端口.

This file MUST set required env vars before importing yunwei_win — settings
reads on import and otherwise pins on the prod Postgres URL.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB_FILE = Path(__file__).resolve().parent / "guangtian_dev_admin.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("COOKIE_SECRET", "demo-cookie-secret-32-bytes-padding=")
os.environ.setdefault("JWT_SECRET", "demo-jwt-secret-32-bytes-padding=========")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from yunwei_win.routes import router as win_router  # noqa: E402


DEMO_ENTERPRISE_ID = "guangtian_demo"
DEMO_ACTOR = "demo-user"

# Observability parity with the jintai stack (PR #129): a pollable /api/health
# + a request-id / commit-sha trail on every response. Self-contained here —
# the shared platform_app.observability helper isn't on this branch yet.
_COMMIT_ENV_VARS = ("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "SOURCE_COMMIT", "COMMIT_SHA")


def _commit_sha() -> str:
    for var in _COMMIT_ENV_VARS:
        v = os.environ.get(var, "").strip()
        if v:
            return v[:12]
    return "unknown"


def create_app() -> FastAPI:
    app = FastAPI(
        title="光天 demo dev backend",
        description=(
            "Standalone SQLite-backed runner for the win API surface (光天 AI 库存管家). "
            "Bypasses platform auth/Redis. **NOT for production.**"
        ),
        version="guangtian-dev",
    )

    app.add_middleware(
        CORSMiddleware,
        # Dev launcher: allow any localhost vite port (5173/5175/5180/... ) — this
        # is a no-auth SQLite demo runner, not production. Regex covers
        # 127.0.0.1 / localhost on any port.
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Demo-Actor"],
    )

    @app.middleware("http")
    async def _stamp_demo_tenant(request: Request, call_next):
        request.state.enterprise_id = DEMO_ENTERPRISE_ID
        request.state.actor = request.headers.get("x-demo-actor") or DEMO_ACTOR
        return await call_next(request)

    # Registered after the tenant stamp → wraps outermost. Stamps a request-id
    # (propagates an upstream X-Request-ID if present) and echoes it + the
    # deployed commit sha on every response, so a prod log line is traceable.
    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Commit-SHA"] = _commit_sha()
        return response

    @app.on_event("startup")
    async def _seed_on_startup() -> None:
        # provision tenant DB + tables, then seed demo data (idempotent).
        from yunwei_win.db import ensure_schema_ingest_tables_for, get_engine_for
        from yunwei_win.services.guangtian_seed import seed_guangtian_demo

        await ensure_schema_ingest_tables_for(DEMO_ENTERPRISE_ID)
        engine = await get_engine_for(DEMO_ENTERPRISE_ID)
        seeded = await seed_guangtian_demo(engine)
        print(f"[guangtian-dev] seed {'written' if seeded else 'skipped (exists)'}")

    @app.get("/health")
    async def health() -> dict[str, str]:
        db_url = os.environ.get("DATABASE_URL", "")
        db_label = "postgres (dev-stack)" if "postgres" in db_url else "sqlite (file)"
        return {
            "status": "ok",
            "enterprise_id": DEMO_ENTERPRISE_ID,
            "db": db_label,
            "mode": f"dev ({db_label}, no auth)",
        }

    @app.api_route("/api/health", methods=["GET", "HEAD"])
    async def api_health():
        """Canonical self-health (same shape as jintai #129's /api/health) so an
        uptime monitor hits one path across both demos. dev backend is always a
        live local DB file → status ok."""
        db_url = os.environ.get("DATABASE_URL", "")
        db_label = "postgres (dev-stack)" if "postgres" in db_url else "sqlite (file)"
        return {
            "status": "ok",
            "version": "guangtian-dev",
            "commit": _commit_sha(),
            "checks": {"db": db_label, "tenant": DEMO_ENTERPRISE_ID},
            "deployment": "dev-backend",
            "auth": "bypassed",
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    app.include_router(win_router, prefix="/api/win")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
