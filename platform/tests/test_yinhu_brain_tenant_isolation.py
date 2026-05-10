"""End-to-end test: yinhu_brain per-enterprise database isolation.

Provisions two distinct tenant DBs (tenant_e2e_a, tenant_e2e_b), inserts a
customer into A, asserts B sees nothing, then inserts into B and re-asserts.
Cleans up both DBs after.

Skipped when no DATABASE_URL is set or the configured Postgres isn't
reachable. Locally::

    DATABASE_URL="postgresql+asyncpg://postgres@localhost:5433/postgres" \
    pytest platform/tests/test_yinhu_brain_tenant_isolation.py -v
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

asyncpg = pytest.importorskip("asyncpg")
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _has_pg_reachable() -> bool:
    if not DATABASE_URL.startswith(("postgres", "postgresql")):
        return False
    try:
        # Quick reachability check via asyncpg. asyncpg only accepts
        # 'postgresql://' (no driver suffix), so strip if present.
        async def _probe() -> None:
            url = DATABASE_URL.replace("+asyncpg", "")
            conn = await asyncpg.connect(url)
            await conn.close()

        asyncio.get_event_loop().run_until_complete(_probe()) if False else None
        # Use a fresh loop to avoid coupling with pytest-asyncio's loop.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_probe())
        finally:
            loop.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not DATABASE_URL.startswith(("postgresql", "postgres"))
    or not _has_pg_reachable(),
    reason="Set DATABASE_URL=postgresql://… (or +asyncpg) pointing at a reachable Postgres to run.",
)


@pytest.mark.asyncio
async def test_per_tenant_isolation_and_provisioning() -> None:
    # Ensure fresh state: drop any stale e2e tenant DBs from a previous run.
    a, b = f"e2e_a_{uuid.uuid4().hex[:8]}", f"e2e_b_{uuid.uuid4().hex[:8]}"

    from yinhu_brain.db import _tenant_db_name, dispose_all, get_engine_for
    from yinhu_brain.models import Customer

    try:
        engine_a = await get_engine_for(a)
        engine_b = await get_engine_for(b)

        # Insert into A
        async with AsyncSession(engine_a) as session:
            session.add(Customer(id=uuid.uuid4(), full_name="A-Only Customer"))
            await session.commit()

        # B sees nothing
        async with AsyncSession(engine_b) as session:
            rows = (await session.execute(select(Customer))).scalars().all()
            assert rows == [], "B leaked A's customer"

        # A sees its own
        async with AsyncSession(engine_a) as session:
            rows = (await session.execute(select(Customer))).scalars().all()
            assert len(rows) == 1
            assert rows[0].full_name == "A-Only Customer"

        # Insert into B
        async with AsyncSession(engine_b) as session:
            session.add(Customer(id=uuid.uuid4(), full_name="B-Only Customer"))
            await session.commit()

        # A still has only its one
        async with AsyncSession(engine_a) as session:
            rows = (await session.execute(select(Customer))).scalars().all()
            assert len(rows) == 1
            assert rows[0].full_name == "A-Only Customer"

        # B has only its one
        async with AsyncSession(engine_b) as session:
            rows = (await session.execute(select(Customer))).scalars().all()
            assert len(rows) == 1
            assert rows[0].full_name == "B-Only Customer"
    finally:
        await dispose_all()
        # Drop the per-tenant DBs we created.
        admin_url = DATABASE_URL.replace("+asyncpg", "")
        # Re-target the postgres admin DB if necessary.
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(admin_url)
        admin_url = urlunsplit(
            (parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment)
        )
        conn = await asyncpg.connect(admin_url)
        try:
            for tag in (a, b):
                db = _tenant_db_name(tag)
                await conn.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        finally:
            await conn.close()
