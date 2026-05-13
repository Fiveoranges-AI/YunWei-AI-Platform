"""yunwei_win — 客户档案智能整理后端,作为 Python 模块集成进 platform。

Originally `/Users/eason/yunwei-tools/yinhu-brain/backend/app/`. Vendored here
so platform_app can include its routes directly (no separate FastAPI app, no
HMAC, no reverse proxy).

Per-enterprise database isolation: see ``yunwei_win.db`` — each enterprise
gets its own Postgres database, lazily provisioned on first access.

Keep this package import-light. Worker entrypoints import submodules such as
``yunwei_win.workers.ingest_rq_worker`` and must not eagerly import the web
router or platform app settings.
"""

__all__ = ["create_router", "router"]


def create_router():
    from yunwei_win.routes import create_router as _create_router

    return _create_router()


def __getattr__(name: str):
    if name == "router":
        from yunwei_win.routes import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
