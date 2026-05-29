"""光天 ↔ 锦泰 跨租户隔离 (SQLite).

红线: 光天 (tenant guangtian_demo) 和锦泰 (tenant jintai_demo) 不能互看.
per-DB 隔离 — 不同 enterprise_id → 不同物理 DB. 这里证明:
  1. 光天 SKU 写入 gt 租户, jt 租户看不到.
  2. 锦泰 Material 写入 jt 租户, gt 租户看不到.
  3. 同一租户里光天表 + 锦泰表可共存 (无 schema 冲突).
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


@pytest.fixture
def _sqlite_tenant_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("COOKIE_SECRET", "gt-cookie-secret-32-bytes-padding=====")
    import yunwei_win.db as db

    monkeypatch.setattr(db, "_engines", {}, raising=False)
    monkeypatch.setattr(db, "_provisioned", set(), raising=False)
    monkeypatch.setattr(db, "_provisioned_ingest_tables", set(), raising=False)
    monkeypatch.setattr(db, "_provisioned_schema_ingest_tables", set(), raising=False)
    from yunwei_win.config import settings

    monkeypatch.setattr(settings, "database_url", os.environ["DATABASE_URL"])
    yield tmp_path


async def _add_gt_sku(session, code: str) -> uuid.UUID:
    from yunwei_win.models import GuangtianSku

    s = GuangtianSku(
        code=code, name=f"SKU {code}", unit="块", safety_stock=Decimal("100"),
        last_balance=Decimal("500"), human_verified=True, verified_by="seed",
        created_by="seed", updated_by="seed",
    )
    session.add(s)
    await session.flush()
    return s.id


async def _add_jt_material(session, code: str) -> uuid.UUID:
    from yunwei_win.models import Material

    m = Material(
        code=code, name=f"Mat {code}", unit="kg", last_balance=Decimal("1000"),
        safety_stock=Decimal("500"), last_unit_cost=Decimal("20"),
        human_verified=True, verified_by="seed", created_by="seed", updated_by="seed",
    )
    session.add(m)
    await session.flush()
    return m.id


@pytest.mark.asyncio
async def test_guangtian_sku_does_not_leak_to_jintai_tenant(_sqlite_tenant_root):
    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import get_engine_for
    from yunwei_win.models import GuangtianSku

    gt = f"guangtian_{uuid.uuid4().hex[:8]}"
    jt = f"jintai_{uuid.uuid4().hex[:8]}"
    eng_gt = await get_engine_for(gt)
    eng_jt = await get_engine_for(jt)

    async with AsyncSession(eng_gt, expire_on_commit=False) as s:
        async with s.begin():
            sku_id = await _add_gt_sku(s, "GT-ONLY-001")

    # jintai tenant sees no guangtian SKU
    async with AsyncSession(eng_jt, expire_on_commit=False) as s:
        rows = (await s.execute(select(GuangtianSku))).scalars().all()
        assert rows == [], f"jintai tenant leaked guangtian SKU: {rows}"

    # guangtian tenant still has it
    async with AsyncSession(eng_gt, expire_on_commit=False) as s:
        rows = (await s.execute(select(GuangtianSku))).scalars().all()
        assert [r.id for r in rows] == [sku_id]


@pytest.mark.asyncio
async def test_jintai_material_does_not_leak_to_guangtian_tenant(_sqlite_tenant_root):
    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import get_engine_for
    from yunwei_win.models import Material

    gt = f"guangtian_{uuid.uuid4().hex[:8]}"
    jt = f"jintai_{uuid.uuid4().hex[:8]}"
    eng_gt = await get_engine_for(gt)
    eng_jt = await get_engine_for(jt)

    async with AsyncSession(eng_jt, expire_on_commit=False) as s:
        async with s.begin():
            await _add_jt_material(s, "JT-MAT-ONLY-001")

    async with AsyncSession(eng_gt, expire_on_commit=False) as s:
        rows = (await s.execute(select(Material))).scalars().all()
        assert rows == [], f"guangtian tenant leaked jintai Material: {rows}"


@pytest.mark.asyncio
async def test_guangtian_and_jintai_tables_coexist_in_one_tenant(_sqlite_tenant_root):
    """同一 DB 里光天 + 锦泰表能共存 — 证明无表名/schema 冲突."""
    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import get_engine_for
    from yunwei_win.models import GuangtianSku, Material

    one = f"both_{uuid.uuid4().hex[:8]}"
    eng = await get_engine_for(one)
    async with AsyncSession(eng, expire_on_commit=False) as s:
        async with s.begin():
            await _add_gt_sku(s, "COEXIST-GT")
            await _add_jt_material(s, "COEXIST-JT")
    async with AsyncSession(eng, expire_on_commit=False) as s:
        assert len((await s.execute(select(GuangtianSku))).scalars().all()) == 1
        assert len((await s.execute(select(Material))).scalars().all()) == 1
