"""光天 — "AI 先填→人确认" 路径 (confirm_writer 扩展验证).

上传/抽取出的候选 JSON 经 confirm_candidate 写入: 一个 GuangtianSku + 一张草稿
入库单 (经关系挂到 SKU), 断言审计戳 (human_verified / ActionLog) + 关系 FK 解析,
然后过账草稿单到库存.
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


async def _engine():
    from yunwei_win.db import ensure_schema_ingest_tables_for, get_engine_for

    tag = f"gtcf_{uuid.uuid4().hex[:8]}"
    await ensure_schema_ingest_tables_for(tag)
    return await get_engine_for(tag)


@pytest.mark.asyncio
async def test_confirm_writes_guangtian_sku_with_audit(_sqlite_tenant_root):
    from yunwei_win.models import ActionLog, GuangtianSku
    from yunwei_win.services.confirm_writer import (
        ConfirmedEntity,
        ConfirmedField,
        ConfirmRequest,
        confirm_candidate,
    )

    engine = await _engine()
    req = ConfirmRequest(
        ingestion_id="ing-1", source_type="wechat_screenshot", source_ref="upload://abc",
        actor="王主管",
        entities=[
            ConfirmedEntity(
                entity_type="GuangtianSku", temp_id="t1",
                fields=[
                    ConfirmedField("code", "GT-NEW-001", confidence=0.97),
                    ConfirmedField("name", "新到高铝砖", confidence=0.95),
                    ConfirmedField("spec", "230×114×65", confidence=0.9),
                    ConfirmedField("category", "高铝砖", confidence=0.9),
                    ConfirmedField("unit", "块", confidence=0.99),
                    ConfirmedField("location", "A-07", confidence=0.88),
                    ConfirmedField("safety_stock", "500", confidence=1.0),
                ],
            )
        ],
    )
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            result = await confirm_candidate(req, s)
        assert len(result.written) == 1
        assert result.written[0].human_verified is True
        assert result.written[0].verified_by == "王主管"
        assert len(result.action_log_ids) == 1

        sku = (await s.execute(select(GuangtianSku).where(GuangtianSku.code == "GT-NEW-001"))).scalar_one()
        assert sku.name == "新到高铝砖"
        assert sku.location == "A-07"
        assert sku.human_verified is True
        logs = (await s.execute(select(ActionLog))).scalars().all()
        assert any("GuangtianSku" in (l.input_summary or "") for l in logs)


@pytest.mark.asyncio
async def test_confirm_inbound_voucher_relationship_then_apply(_sqlite_tenant_root):
    """确认一个 SKU + 一张草稿入库单 (关系挂到 SKU), 再过账 → 库存增加."""
    from yunwei_win.models import (
        GuangtianInboundVoucher,
        GuangtianSku,
        GuangtianVoucherStatus,
    )
    from yunwei_win.services.confirm_writer import (
        ConfirmedEntity,
        ConfirmedField,
        ConfirmedRelationship,
        ConfirmRequest,
        confirm_candidate,
    )
    from yunwei_win.services.guangtian import apply_inbound_voucher

    engine = await _engine()
    req = ConfirmRequest(
        ingestion_id="ing-2", source_type="excel", source_ref="upload://xls", actor="李师傅",
        entities=[
            ConfirmedEntity(
                entity_type="GuangtianSku", temp_id="sku1",
                fields=[
                    ConfirmedField("code", "GT-REL-001"),
                    ConfirmedField("name", "关系砖"),
                    ConfirmedField("unit", "块"),
                    ConfirmedField("safety_stock", "100"),
                ],
            ),
            ConfirmedEntity(
                entity_type="GuangtianInboundVoucher", temp_id="iv1",
                fields=[
                    ConfirmedField("voucher_no", "IN-REL-001"),
                    ConfirmedField("quantity", "800"),
                    ConfirmedField("unit", "块"),
                    ConfirmedField("batch", "P20260519-01"),
                ],
            ),
        ],
        relationships=[
            ConfirmedRelationship("sku1", "iv1", "GuangtianSku-has-GuangtianInboundVoucher"),
        ],
    )
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            result = await confirm_candidate(req, s)
        assert len(result.written) == 2
        v = (await s.execute(select(GuangtianInboundVoucher).where(GuangtianInboundVoucher.voucher_no == "IN-REL-001"))).scalar_one()
        sku = (await s.execute(select(GuangtianSku).where(GuangtianSku.code == "GT-REL-001"))).scalar_one()
        assert v.sku_id == sku.id  # relationship FK resolved
        assert v.status == GuangtianVoucherStatus.draft
        assert Decimal(sku.last_balance) == Decimal("0")  # not applied yet

    # now post the draft voucher → stock increases
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            res = await apply_inbound_voucher(session=s, voucher_id=v.id, actor="李师傅")
        assert Decimal(res.balance_after) == Decimal("800")
        sku2 = await s.get(GuangtianSku, sku.id)
        assert Decimal(sku2.last_balance) == Decimal("800")


@pytest.mark.asyncio
async def test_confirm_empty_entities_rejected(_sqlite_tenant_root):
    from yunwei_win.services.confirm_writer import ConfirmRequest, confirm_candidate

    engine = await _engine()
    req = ConfirmRequest(ingestion_id="x", source_type="excel", source_ref="r", actor="a")
    async with AsyncSession(engine, expire_on_commit=False) as s:
        with pytest.raises(Exception):
            async with s.begin():
                await confirm_candidate(req, s)
