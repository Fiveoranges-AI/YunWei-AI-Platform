"""锦泰 demo 用的轻量 FastAPI dev launcher.

**仅供前端 backend-mode 演示**. 不是生产入口. 跳过 platform middleware (无 cookie
auth / 无 Redis / 无平台用户表), 直接把 yunwei_win router 挂到 `/api/win/*`,
中间件 stamp 一个固定 ``enterprise_id = jintai_demo`` 让 per-tenant DB 自动
provision 出 ``tenant_jintai_demo`` SQLite 文件.

启动 (生产 platform 不变):
    bash scripts/jintai/dev-backend.sh
    # 默认监听 127.0.0.1:8000 + CORS 允许 127.0.0.1:5175

DB 文件落在 ``./jintai_dev_admin.db`` (platform "admin" DB) + ``./yinhu_tenant_jintai_demo.db``
(tenant DB, 跑业务规则用). 删两个 db 文件即可重置.

This file MUST set required env vars before importing yunwei_win — settings
reads on import and otherwise pins on the prod Postgres URL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 必须在 import yunwei_win 之前设置环境变量,因为 settings 在 import 时读取.
_DB_FILE = Path(__file__).resolve().parent / "jintai_dev_admin.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_DB_FILE}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("COOKIE_SECRET", "demo-cookie-secret-32-bytes-padding=")
os.environ.setdefault("JWT_SECRET", "demo-jwt-secret-32-bytes-padding=========")

# Make sure the local package path is importable when running `python dev_jintai_backend.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from yunwei_win.routes import router as win_router  # noqa: E402


DEMO_ENTERPRISE_ID = "jintai_demo"
DEMO_ACTOR = "demo-user"


def create_app() -> FastAPI:
    app = FastAPI(
        title="锦泰 demo dev backend",
        description=(
            "Standalone SQLite-backed runner for the win API surface. "
            "Bypasses platform auth/Redis. **NOT for production.**"
        ),
        version="round4-dev",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5175", "http://localhost:5175",
            "http://127.0.0.1:5173", "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Demo-Actor"],
    )

    @app.middleware("http")
    async def _stamp_demo_tenant(request: Request, call_next):
        request.state.enterprise_id = DEMO_ENTERPRISE_ID
        # Allow per-request actor override via header, default to DEMO_ACTOR.
        request.state.actor = request.headers.get("x-demo-actor") or DEMO_ACTOR
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        db_url = os.environ.get("DATABASE_URL", "")
        if "postgres" in db_url:
            db_label = "postgres (dev-stack)"
        else:
            db_label = "sqlite (file)"
        return {
            "status": "ok",
            "enterprise_id": DEMO_ENTERPRISE_ID,
            "db": db_label,
            "mode": f"dev ({db_label}, no auth)",
        }

    app.include_router(win_router, prefix="/api/win")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
