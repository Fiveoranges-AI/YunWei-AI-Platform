"""yunwei_win — 客户档案智能整理后端,作为 Python 模块集成进 platform。

Originally `/Users/eason/yunwei-tools/yinhu-brain/backend/app/`. Vendored here
so platform_app can include its routes directly (no separate FastAPI app, no
HMAC, no reverse proxy).

Usage from platform_app::

    from yunwei_win import router as win_router
    app.include_router(win_router, prefix="/win/api")

Per-enterprise database isolation: see ``yunwei_win.db`` — each enterprise
gets its own Postgres database, lazily provisioned on first access.
"""
from fastapi import APIRouter

from yunwei_win.api.ask import router as _ask_router
from yunwei_win.api.customer_management import router as _customer_management_router
from yunwei_win.api.customer_profile import router as _customer_profile_router
from yunwei_win.api.ingest import router as _ingest_router
from yunwei_win.api.read import router as _read_router

router = APIRouter()
router.include_router(_ingest_router)
router.include_router(_read_router)
router.include_router(_ask_router)
router.include_router(_customer_profile_router)
router.include_router(_customer_management_router)
