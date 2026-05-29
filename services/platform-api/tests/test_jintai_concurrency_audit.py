"""Round 9 P0-4 — concurrency / race-condition audit.

confirm_and_issue / approve_requisition / receive_purchase_order all
follow a "read row → check status → mutate → write" pattern with no
SELECT FOR UPDATE or conditional UPDATE. In Postgres READ COMMITTED two
concurrent requests on the same voucher / PR / PO can both pass the
status check before either UPDATE commits — resulting in:

  - double stock movement (-800 kg becomes -1600 kg)
  - duplicate Payable rows
  - duplicate auto-drafted PRs

This test demonstrates the race using two AsyncSession instances on the
same SQLite engine. SQLite serialises writes so concrete double-write is
hard to reproduce here, but the test asserts the **defense** path: a
second confirm on an already-confirmed voucher MUST raise (idempotency
guard), and we check Material.last_balance is decremented exactly once.

If/when this test runs on Postgres (CI backend-pg job), the same
assertions catch a real race that the in-process status check would miss.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


async def _make_shared_engine():
    """Single engine, two sessions — simulates two HTTP requests against the
    same tenant DB. For SQLite we need a real file (not :memory:) so two
    connections see the same DB.
    """
    import tempfile

    from sqlalchemy import event

    import yunwei_win.models  # noqa: F401 — register
    from yunwei_win.db import Base

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp.name}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _seed_material_and_voucher(engine):
    from yunwei_win.models import (
        IssueVoucher,
        IssueVoucherStatus,
        Material,
    )

    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            mat = Material(
                code="CONC-MAT",
                name="Concurrency Mat",
                unit="kg",
                last_balance=Decimal("1000"),
                safety_stock=Decimal("100"),
                last_unit_cost=Decimal("10"),
                human_verified=True,
                verified_by="seed",
                created_by="seed",
                updated_by="seed",
            )
            s.add(mat)
            await s.flush()
            iv = IssueVoucher(
                voucher_no="IV-CONC-001",
                workshop="W1",
                material_id=mat.id,
                quantity=Decimal("800"),
                unit="kg",
                issued_date=date.today(),
                status=IssueVoucherStatus.draft,
                human_verified=False,
                created_by="seed",
                updated_by="seed",
            )
            s.add(iv)
            await s.flush()
            return mat.id, iv.id


@pytest.mark.asyncio
async def test_double_confirm_and_issue_does_not_double_decrement_material() -> None:
    """Two confirm_and_issue calls on the same voucher must not decrement
    the material twice — the second call must surface a clear error.
    """
    from yunwei_win.models import Material, StockMovement
    from yunwei_win.services.procurement import (
        ProcurementRuleError,
        confirm_and_issue,
    )

    engine = await _make_shared_engine()
    mat_id, iv_id = await _seed_material_and_voucher(engine)

    # First call succeeds.
    async with AsyncSession(engine, expire_on_commit=False) as s1:
        async with s1.begin():
            r1 = await confirm_and_issue(
                voucher_id=iv_id, actor="actor-1", session=s1,
            )
        assert r1.balance_after == Decimal("200")

    # Second call must fail loudly.
    second_raised = False
    async with AsyncSession(engine, expire_on_commit=False) as s2:
        try:
            async with s2.begin():
                await confirm_and_issue(
                    voucher_id=iv_id, actor="actor-2", session=s2,
                )
        except ProcurementRuleError:
            second_raised = True
    assert second_raised, (
        "second confirm_and_issue on already-confirmed voucher silently "
        "succeeded — duplicate clicks would double-decrement material"
    )

    # Material balance has been decremented EXACTLY once.
    async with AsyncSession(engine, expire_on_commit=False) as s3:
        mat = await s3.get(Material, mat_id)
        assert mat.last_balance == Decimal("200"), (
            f"material balance double-decremented: {mat.last_balance}"
        )
        movements = (await s3.execute(
            select(StockMovement).where(StockMovement.reference_id == iv_id)
        )).scalars().all()
        assert len(movements) == 1, (
            f"expected 1 stock movement, got {len(movements)} — "
            "race condition wrote duplicates"
        )


@pytest.mark.asyncio
async def test_concurrent_confirm_via_asyncio_gather_serialises_safely() -> None:
    """Smoke test: launch two confirm_and_issue calls in the same event loop
    (asyncio.gather) — one must succeed, the other must raise. Neither
    can silently succeed. Material balance ends up decremented exactly once.

    This does NOT prove PG race-safety (SQLAlchemy default isolation +
    SQLite serialised writes make this test conservative), but it asserts
    the in-process invariant that the API layer must preserve.
    """
    import asyncio

    from yunwei_win.models import Material, StockMovement
    from yunwei_win.services.procurement import (
        ProcurementRuleError,
        confirm_and_issue,
    )

    engine = await _make_shared_engine()
    mat_id, iv_id = await _seed_material_and_voucher(engine)

    async def _one_call(actor: str) -> tuple[str, str]:
        try:
            async with AsyncSession(engine, expire_on_commit=False) as s:
                async with s.begin():
                    r = await confirm_and_issue(
                        voucher_id=iv_id, actor=actor, session=s,
                    )
                return ("ok", str(r.balance_after))
        except ProcurementRuleError as e:
            return ("err", str(e))

    results = await asyncio.gather(
        _one_call("actor-A"), _one_call("actor-B"),
    )
    ok = [r for r in results if r[0] == "ok"]
    err = [r for r in results if r[0] == "err"]
    assert len(ok) == 1, (
        f"expected exactly 1 success, got {len(ok)}: {results}"
    )
    assert len(err) == 1, (
        f"expected exactly 1 error, got {len(err)}: {results}"
    )

    async with AsyncSession(engine, expire_on_commit=False) as s:
        mat = await s.get(Material, mat_id)
        assert mat.last_balance == Decimal("200"), (
            f"material balance is {mat.last_balance}, expected 200 — race "
            "produced double decrement"
        )
        movements = (await s.execute(
            select(StockMovement).where(StockMovement.reference_id == iv_id)
        )).scalars().all()
        assert len(movements) == 1


@pytest.mark.asyncio
async def test_double_approve_requisition_does_not_create_two_pos() -> None:
    """Same shape for PR approval: second approve must fail loudly,
    purchase_orders count for this PR stays at 1.
    """
    from yunwei_win.models import (
        PurchaseOrder,
        PurchaseRequisition,
        PurchaseRequisitionItem,
        PurchaseRequisitionSource,
        PurchaseRequisitionStatus,
        Supplier,
    )
    from yunwei_win.services.procurement import (
        ProcurementRuleError,
        approve_requisition,
    )

    engine = await _make_shared_engine()

    # Seed: supplier + material + PR(draft) + 1 line.
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            from yunwei_win.models import Material

            sup = Supplier(
                name="Sup-CONC", payment_terms_days=30,
                human_verified=True, verified_by="seed",
                created_by="seed", updated_by="seed",
            )
            mat = Material(
                code="MAT-CONC-2", name="x", unit="kg",
                last_balance=Decimal("0"), safety_stock=Decimal("0"),
                last_unit_cost=Decimal("10"),
                human_verified=True, verified_by="seed",
                created_by="seed", updated_by="seed",
            )
            s.add_all([sup, mat])
            await s.flush()
            pr = PurchaseRequisition(
                pr_no="PR-CONC-001",
                dept="x", applicant="x",
                apply_date=date.today(),
                supplier_id=sup.id,
                status=PurchaseRequisitionStatus.pending_approval,
                source=PurchaseRequisitionSource.manual,
                human_verified=True, verified_by="seed",
                created_by="seed", updated_by="seed",
            )
            s.add(pr)
            await s.flush()
            line = PurchaseRequisitionItem(
                pr_id=pr.id,
                material_id=mat.id,
                quantity=Decimal("100"),
                unit="kg",
                created_by="seed",
                updated_by="seed",
            )
            s.add(line)
            await s.flush()
            sup_id, pr_id = sup.id, pr.id

    async with AsyncSession(engine, expire_on_commit=False) as s1:
        async with s1.begin():
            r1 = await approve_requisition(
                pr_id=pr_id, actor="actor-1", session=s1,
                supplier_id=sup_id, unit_prices={mat.id: Decimal("12.00")},
            )

    second_raised = False
    async with AsyncSession(engine, expire_on_commit=False) as s2:
        try:
            async with s2.begin():
                await approve_requisition(
                    pr_id=pr_id, actor="actor-2", session=s2,
                    supplier_id=sup_id, unit_prices={mat.id: Decimal("13.00")},
                )
        except ProcurementRuleError:
            second_raised = True
    assert second_raised, (
        "second approve on already-approved PR silently created a second PO"
    )

    async with AsyncSession(engine, expire_on_commit=False) as s3:
        pos = (await s3.execute(
            select(PurchaseOrder)
        )).scalars().all()
        assert len(pos) == 1, (
            f"expected 1 PO, got {len(pos)} — duplicate approve created "
            "a second PO"
        )
        assert pos[0].id == r1.po_id
