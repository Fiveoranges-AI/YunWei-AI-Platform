"""Per-enterprise async SQLAlchemy engine pool.

Each enterprise gets its own Postgres database (e.g. tenant_yinhu, tenant_acme).
The pool keeps one async engine per enterprise; engines are created lazily on
first access and the database is provisioned (CREATE DATABASE + create_all) if
it does not yet exist.

Routes use this via the standard FastAPI dependency::

    @router.get("/customers")
    async def list_customers(session: AsyncSession = Depends(get_session)):
        ...

The dependency reads the enterprise_id that platform middleware stamped onto
``request.state.enterprise_id`` before the route handler runs. See
``platform_app/main.py`` for the middleware that does the cookie → user →
enterprise lookup.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from yinhu_brain.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by every per-tenant database."""


def _tenant_db_name(enterprise_id: str) -> str:
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in enterprise_id.lower())
    return f"tenant_{safe}"


def _build_tenant_url(enterprise_id: str) -> str:
    """Derive the per-tenant database URL from settings.database_url.

    The base URL points at the platform postgres (typically the ``postgres``
    or ``platform`` database). We swap the database name to the tenant DB.
    """
    base = settings.database_url
    if base.startswith("sqlite"):
        return f"sqlite+aiosqlite:///./yinhu_{_tenant_db_name(enterprise_id)}.db"
    parts = urlsplit(base)
    new_path = "/" + _tenant_db_name(enterprise_id)
    return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))


def _admin_url() -> str:
    """A URL pointing at the postgres admin DB so we can CREATE DATABASE."""
    base = settings.database_url
    if base.startswith("sqlite"):
        return base
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment))


_engines: dict[str, AsyncEngine] = {}
_provisioned: set[str] = set()
_engine_lock = asyncio.Lock()


async def _ensure_database(enterprise_id: str) -> None:
    """Create the per-tenant database if it does not exist, then create_all."""
    if enterprise_id in _provisioned:
        return
    db_name = _tenant_db_name(enterprise_id)
    if not settings.database_url.startswith("sqlite"):
        admin_engine = create_async_engine(_admin_url(), isolation_level="AUTOCOMMIT")
        try:
            async with admin_engine.connect() as conn:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :n").bindparams(n=db_name)
                )
                if not exists:
                    await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        finally:
            await admin_engine.dispose()
    # Now run create_all on the tenant DB. Importing models registers them
    # against Base.metadata so create_all sees every table.
    import yinhu_brain.models  # noqa: F401  — register mappers

    engine = await _get_engine(enterprise_id)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _provisioned.add(enterprise_id)


async def _get_engine(enterprise_id: str) -> AsyncEngine:
    if enterprise_id in _engines:
        return _engines[enterprise_id]
    async with _engine_lock:
        if enterprise_id in _engines:
            return _engines[enterprise_id]
        engine = create_async_engine(
            _build_tenant_url(enterprise_id),
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        _engines[enterprise_id] = engine
        return engine


async def get_engine_for(enterprise_id: str) -> AsyncEngine:
    """Public: return the engine bound to ``enterprise_id``, provisioning the
    database on first access. Used by the metrics endpoint and any code that
    needs a raw engine instead of a session."""
    await _ensure_database(enterprise_id)
    return await _get_engine(enterprise_id)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session bound to the caller's enterprise.

    The enterprise_id is set on ``request.state`` by platform middleware after
    looking up the user from the ``app_session`` cookie. Routes that hit this
    without authentication get a 401.
    """
    enterprise_id = getattr(request.state, "enterprise_id", None)
    if not enterprise_id:
        raise HTTPException(status_code=401, detail="not_authenticated")
    engine = await get_engine_for(enterprise_id)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise


async def dispose_all() -> None:
    """Tear down every cached engine. Called on app shutdown."""
    for engine in list(_engines.values()):
        await engine.dispose()
    _engines.clear()
    _provisioned.clear()
