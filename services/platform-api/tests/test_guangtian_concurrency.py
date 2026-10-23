"""光天 — 并发幂等 (原子条件 UPDATE, 锦泰 round 9 P0-4 同款).

两次并发过账同一张草稿单 → 只有一个成功扣减/增加, 不重复写流水/不双扣库存.
两次采纳同一条补产建议 → 只有一个挂工单.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
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


async def _new_tenant():
    from yunwei_win.db import ensure_schema_ingest_tables_for, get_engine_for

    tag = f"gtc_{uuid.uuid4().hex[:8]}"
    await ensure_schema_ingest_tables_for(tag)
    return await get_engine_for(tag)


async def _make_sku_and_draft_outbound(engine, balance: Decimal, qty: Decimal):
    from yunwei_win.models import (
        GuangtianOutboundVoucher,
        GuangtianSku,
        GuangtianVoucherStatus,
    )

    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            sku = GuangtianSku(
                code=f"C-{uuid.uuid4().hex[:6]}", name="并发砖", unit="块",
                safety_stock=Decimal("100"), last_balance=balance,
                human_verified=True, created_by="seed", updated_by="seed",
            )
            s.add(sku)
            await s.flush()
            v = GuangtianOutboundVoucher(
                voucher_no=f"OUT-{uuid.uuid4().hex[:6]}", sku_id=sku.id, quantity=qty,
                status=GuangtianVoucherStatus.draft, human_verified=True,
                occurred_at=datetime.now(tz=timezone.utc),
                created_by="seed", updated_by="seed",
            )
            s.add(v)
            await s.flush()
            return sku.id, v.id


async def _apply_outbound_once(engine, voucher_id):
    from yunwei_win.services.guangtian import GuangtianRuleError, apply_outbound_voucher

    async with AsyncSession(engine, expire_on_commit=False) as s:
        try:
            async with s.begin():
                await apply_outbound_voucher(session=s, voucher_id=voucher_id, actor="t")
            return "ok"
        except GuangtianRuleError:
            return "rejected"


@pytest.mark.asyncio
async def test_concurrent_apply_outbound_decrements_once(_sqlite_tenant_root):
    from yunwei_win.models import GuangtianSku, GuangtianStockMovement

    engine = await _new_tenant()
    sku_id, voucher_id = await _make_sku_and_draft_outbound(engine, Decimal("500"), Decimal("120"))

    results = await asyncio.gather(
        _apply_outbound_once(engine, voucher_id),
        _apply_outbound_once(engine, voucher_id),
    )
    assert sorted(results) == ["ok", "rejected"], results

    async with AsyncSession(engine, expire_on_commit=False) as s:
        sku = await s.get(GuangtianSku, sku_id)
        assert Decimal(sku.last_balance) == Decimal("380")  # 500 - 120 exactly once
        n = (await s.execute(
            select(func.count()).select_from(GuangtianStockMovement)
            .where(GuangtianStockMovement.reference_id == voucher_id)
        )).scalar_one()
        assert n == 1, f"duplicate movements written: {n}"


@pytest.mark.asyncio
async def test_apply_outbound_idempotent_sequential(_sqlite_tenant_root):
    engine = await _new_tenant()
    _, voucher_id = await _make_sku_and_draft_outbound(engine, Decimal("500"), Decimal("100"))
    assert await _apply_outbound_once(engine, voucher_id) == "ok"
    assert await _apply_outbound_once(engine, voucher_id) == "rejected"


@pytest.mark.asyncio
async def test_concurrent_adopt_replenishment_one_winner(_sqlite_tenant_root):
    from yunwei_win.models import (
        GuangtianReplenishment,
        GuangtianReplenishStatus,
        GuangtianSku,
    )
    from yunwei_win.services.guangtian import GuangtianRuleError, adopt_replenishment

    engine = await _new_tenant()
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            sku = GuangtianSku(
                code=f"R-{uuid.uuid4().hex[:6]}", name="补产砖", unit="块",
                safety_stock=Decimal("100"), last_balance=Decimal("0"),
                human_verified=True, created_by="seed", updated_by="seed",
            )
            s.add(sku)
            await s.flush()
            rep = GuangtianReplenishment(
                sku_id=sku.id, current_stock=Decimal("0"), safety_stock=Decimal("100"),
                suggest_qty=Decimal("200"), status=GuangtianReplenishStatus.suggested,
                source="ai_autodraft", human_verified=False,
                created_by="ai", updated_by="ai",
            )
            s.add(rep)
            await s.flush()
            rep_id = rep.id

    async def adopt_once():
        async with AsyncSession(engine, expire_on_commit=False) as s:
            try:
                async with s.begin():
                    await adopt_replenishment(session=s, replenishment_id=rep_id, actor="t")
                return "ok"
            except GuangtianRuleError:
                return "rejected"

    results = await asyncio.gather(adopt_once(), adopt_once())
    assert sorted(results) == ["ok", "rejected"], results
