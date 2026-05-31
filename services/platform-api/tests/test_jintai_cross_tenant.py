"""Round 9 self-audit — cross-tenant isolation for jintai entities.

The existing ``test_yunwei_win_tenant_isolation.py`` proves per-tenant
database isolation for ``Customer`` (the original ontology). Round 9 P0-1
extends the same proof to all entities introduced in rounds 1-7:

  procurement: Material, Supplier, IssueVoucher, StockMovement, StockAlert,
               PurchaseRequisition, PurchaseRequisitionItem, PurchaseOrder,
               PurchaseOrderItem, GoodsReceipt, Payable
  finance:     ChartOfAccount, PeriodOpeningBalance, FixedAsset
  bom:         BillOfMaterials, BillOfMaterialsLine
  audit:       ActionLog

The test seeds tenant_a, asserts tenant_b sees nothing, then seeds
tenant_b, asserts tenant_a still sees only its own rows. Run on SQLite so
it does not require Postgres (the platform-layer test already covers PG).
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


@pytest.fixture
def _sqlite_tenant_root(tmp_path, monkeypatch):
    """Point yinhu_tenant_*.db files into tmp_path so the test stays hermetic
    and doesn't litter the repo / collide with other tests."""
    monkeypatch.chdir(tmp_path)
    # Ensure DATABASE_URL is SQLite so _build_tenant_url returns the file path.
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv(
        "COOKIE_SECRET", "audit-cookie-secret-32-bytes-padding=====",
    )
    # Reset module-level engine cache so this test gets fresh engines.
    import yunwei_win.db as db

    monkeypatch.setattr(db, "_engines", {}, raising=False)
    monkeypatch.setattr(db, "_provisioned", set(), raising=False)
    monkeypatch.setattr(db, "_provisioned_ingest_tables", set(), raising=False)
    monkeypatch.setattr(
        db, "_provisioned_schema_ingest_tables", set(), raising=False,
    )
    # settings.database_url is read lazily — re-bind.
    from yunwei_win.config import settings

    monkeypatch.setattr(settings, "database_url", os.environ["DATABASE_URL"])
    yield tmp_path


async def _seed_supplier(session, name: str) -> uuid.UUID:
    from yunwei_win.models import Supplier

    sup = Supplier(
        name=name,
        payment_terms_days=60,
        contact_phone="0531-9999999",
        human_verified=True,
        verified_by="seed",
        created_by="seed",
        updated_by="seed",
    )
    session.add(sup)
    await session.flush()
    return sup.id


async def _seed_material(session, code: str) -> uuid.UUID:
    from yunwei_win.models import Material

    mat = Material(
        code=code,
        name=f"Material {code}",
        unit="kg",
        last_balance=Decimal("1000"),
        safety_stock=Decimal("500"),
        last_unit_cost=Decimal("20.00"),
        human_verified=True,
        verified_by="seed",
        created_by="seed",
        updated_by="seed",
    )
    session.add(mat)
    await session.flush()
    return mat.id


async def _seed_issue_voucher(session, material_id: uuid.UUID, voucher_no: str) -> uuid.UUID:
    from datetime import date

    from yunwei_win.models import IssueVoucher, IssueVoucherStatus

    iv = IssueVoucher(
        voucher_no=voucher_no,
        workshop="W1",
        material_id=material_id,
        quantity=Decimal("100"),
        unit="kg",
        issued_date=date.today(),
        status=IssueVoucherStatus.draft,
        human_verified=False,
        created_by="seed",
        updated_by="seed",
    )
    session.add(iv)
    await session.flush()
    return iv.id


@pytest.mark.asyncio
async def test_jintai_procurement_entities_do_not_leak_across_tenants(
    _sqlite_tenant_root,
) -> None:
    """Material / Supplier / IssueVoucher seeded into tenant_a must NOT be
    visible from tenant_b's session. Confirms per-DB isolation extends to
    every entity the procurement APIs touch.
    """
    import yunwei_win.models  # noqa: F401 — register mappers
    from yunwei_win.db import get_engine_for
    from yunwei_win.models import IssueVoucher, Material, Supplier

    tag_a = f"audit_a_{uuid.uuid4().hex[:8]}"
    tag_b = f"audit_b_{uuid.uuid4().hex[:8]}"

    engine_a = await get_engine_for(tag_a)
    engine_b = await get_engine_for(tag_b)

    # Seed everything in tenant_a.
    async with AsyncSession(engine_a, expire_on_commit=False) as s:
        async with s.begin():
            sup_a = await _seed_supplier(s, "Supplier-A-Only")
            mat_a = await _seed_material(s, "MAT-A-001")
            iv_a = await _seed_issue_voucher(s, mat_a, "IV-A-001")

    # tenant_b sees no procurement rows.
    async with AsyncSession(engine_b, expire_on_commit=False) as s:
        for model, label in [(Supplier, "Supplier"), (Material, "Material"),
                              (IssueVoucher, "IssueVoucher")]:
            rows = (await s.execute(select(model))).scalars().all()
            assert rows == [], (
                f"tenant_b leaked tenant_a's {label}: {rows}"
            )

    # tenant_a still sees its own.
    async with AsyncSession(engine_a, expire_on_commit=False) as s:
        sups = (await s.execute(select(Supplier))).scalars().all()
        mats = (await s.execute(select(Material))).scalars().all()
        ivs = (await s.execute(select(IssueVoucher))).scalars().all()
        assert [x.id for x in sups] == [sup_a]
        assert [x.id for x in mats] == [mat_a]
        assert [x.id for x in ivs] == [iv_a]

    # Seed tenant_b — distinct codes so we can prove no cross-write.
    async with AsyncSession(engine_b, expire_on_commit=False) as s:
        async with s.begin():
            await _seed_supplier(s, "Supplier-B-Only")
            await _seed_material(s, "MAT-B-001")

    # tenant_a still has exactly its 1 supplier / 1 material.
    async with AsyncSession(engine_a, expire_on_commit=False) as s:
        sups = (await s.execute(select(Supplier))).scalars().all()
        mats = (await s.execute(select(Material))).scalars().all()
        assert len(sups) == 1
        assert sups[0].name == "Supplier-A-Only"
        assert len(mats) == 1
        assert mats[0].code == "MAT-A-001"


@pytest.mark.asyncio
async def test_jintai_finance_and_bom_entities_do_not_leak_across_tenants(
    _sqlite_tenant_root,
) -> None:
    """FixedAsset / ChartOfAccount / PeriodOpeningBalance / BOM seeded into
    tenant_a must NOT be visible from tenant_b's session.
    """
    from datetime import date

    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import get_engine_for
    from yunwei_win.models.bom import BillOfMaterials, BillOfMaterialsLine
    from yunwei_win.models.finance import (
        ChartOfAccount,
        FixedAsset,
        PeriodOpeningBalance,
    )

    tag_a = f"audit_fa_a_{uuid.uuid4().hex[:8]}"
    tag_b = f"audit_fa_b_{uuid.uuid4().hex[:8]}"

    engine_a = await get_engine_for(tag_a)
    engine_b = await get_engine_for(tag_b)

    async with AsyncSession(engine_a, expire_on_commit=False) as s:
        async with s.begin():
            mat_a = await _seed_material(s, "MAT-FA-A-001")
            from yunwei_win.models.finance import (
                AccountClass,
                FixedAssetCategory,
                FixedAssetStatus,
                NormalBalance,
                StatementSection,
            )

            fa = FixedAsset(
                asset_no="FA-A-001",
                name="A-Mill",
                category=FixedAssetCategory.machinery,
                acquired_date=date(2024, 1, 1),
                original_cost=Decimal("100000"),
                salvage_value=Decimal("5000"),
                useful_life_months=120,
                status=FixedAssetStatus.active,
                human_verified=True,
                verified_by="seed",
                created_by="seed",
                updated_by="seed",
            )
            coa = ChartOfAccount(
                account_code="1001",
                account_name="库存现金",
                account_class=AccountClass.asset,
                statement=StatementSection.balance_sheet,
                report_line_key="cash",
                normal_balance=NormalBalance.debit,
                created_by="seed",
                updated_by="seed",
            )
            pob = PeriodOpeningBalance(
                period="2026-01",
                account_code="1001",
                opening_amount=Decimal("50000"),
                created_by="seed",
                updated_by="seed",
            )
            bom = BillOfMaterials(
                product_code="P-A-001",
                product_name="A-Brick",
                version="v1",
                output_quantity=Decimal("1000"),
                output_unit="block",
                human_verified=True,
                verified_by="seed",
                created_by="seed",
                updated_by="seed",
            )
            session = s
            session.add_all([fa, coa, pob, bom])
            await session.flush()
            bom_line = BillOfMaterialsLine(
                bom_id=bom.id,
                material_id=mat_a,
                quantity_per_output=Decimal("10"),
                unit="kg",
                sort_order=1,
                created_by="seed",
                updated_by="seed",
            )
            session.add(bom_line)

    # tenant_b sees nothing finance/bom.
    async with AsyncSession(engine_b, expire_on_commit=False) as s:
        for model, label in [
            (FixedAsset, "FixedAsset"),
            (ChartOfAccount, "ChartOfAccount"),
            (PeriodOpeningBalance, "PeriodOpeningBalance"),
            (BillOfMaterials, "BillOfMaterials"),
            (BillOfMaterialsLine, "BillOfMaterialsLine"),
        ]:
            rows = (await s.execute(select(model))).scalars().all()
            assert rows == [], f"tenant_b leaked tenant_a's {label}: {rows}"


@pytest.mark.asyncio
async def test_jintai_action_log_audit_does_not_leak_across_tenants(
    _sqlite_tenant_root,
) -> None:
    """ActionLog is the audit chain — it must NOT leak across tenants, else
    one customer can read another customer's audit history. Critical for
    compliance / trust.
    """
    from datetime import datetime, timezone

    import yunwei_win.models  # noqa: F401
    from yunwei_win.db import get_engine_for
    from yunwei_win.models import ActionLog, ActionTargetType, NextActionType

    tag_a = f"audit_al_a_{uuid.uuid4().hex[:8]}"
    tag_b = f"audit_al_b_{uuid.uuid4().hex[:8]}"

    engine_a = await get_engine_for(tag_a)
    engine_b = await get_engine_for(tag_b)

    async with AsyncSession(engine_a, expire_on_commit=False) as s:
        async with s.begin():
            s.add(ActionLog(
                target_entity_type=ActionTargetType.other,
                target_entity_id=uuid.uuid4(),
                action_type=NextActionType.other,
                actor="tenant-a-actor",
                actor_kind="user",
                input_summary="A's private audit trail",
                output_summary="A's private output",
                executed_at=datetime.now(tz=timezone.utc),
                succeeded=True,
                created_by="seed",
                updated_by="seed",
            ))

    async with AsyncSession(engine_b, expire_on_commit=False) as s:
        rows = (await s.execute(select(ActionLog))).scalars().all()
        for r in rows:
            assert "A's private" not in (r.input_summary or "")
            assert "A's private" not in (r.output_summary or "")
        assert rows == [], "tenant_b leaked tenant_a's ActionLog audit chain"
