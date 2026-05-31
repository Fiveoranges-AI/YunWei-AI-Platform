"""P1-b backend safety patches.

1. reject_requisition gains an atomic conditional UPDATE (mirrors the Round 9
   approve/confirm/receive guards) so a concurrent reject — or a reject racing
   an approve — can't both win.
2. Customer maintenance edits/deletes now leave an ActionLog audit trail
   (the "AI 先填、人确认" red line extended to manual edits).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    Customer,
    PurchaseRequisition,
    PurchaseRequisitionStatus,
    PurchaseRequisitionSource,
)
from yunwei_win.services.procurement import (
    ProcurementRuleError,
    approve_requisition,
    reject_requisition,
)


# Override the project-level autouse Postgres-truncating fixture.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


async def _make_engine(*, file_backed: bool = False):
    if file_backed:
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        url = f"sqlite+aiosqlite:///{tmp.name}"
    else:
        url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(url)

    @event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _seed_pr(engine) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        async with s.begin():
            pr = PurchaseRequisition(
                pr_no="PR-REJ-RACE-1",
                status=PurchaseRequisitionStatus.pending_approval,
                source=PurchaseRequisitionSource.ai_autodraft,
                human_verified=False,
                created_by="seed",
                updated_by="seed",
            )
            s.add(pr)
            await s.flush()
            return pr.id


# ---------- reject atomic guard ------------------------------------------


@pytest.mark.asyncio
async def test_reject_writes_status_and_actionlog():
    engine = await _make_engine()
    try:
        pr_id = await _seed_pr(engine)
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                await reject_requisition(
                    pr_id=pr_id, actor="张主管", reason="预算超标", session=s
                )
        async with AsyncSession(engine, expire_on_commit=False) as s:
            pr = await s.get(PurchaseRequisition, pr_id)
            assert pr.status == PurchaseRequisitionStatus.rejected
            assert pr.rejected_reason == "预算超标"
            assert pr.approver == "张主管"
            logs = (
                await s.execute(
                    select(ActionLog).where(ActionLog.target_entity_id == pr_id)
                )
            ).scalars().all()
            assert len(logs) == 1
            assert "reject_requisition" in logs[0].input_summary
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_double_reject_is_rejected_by_guard():
    engine = await _make_engine()
    try:
        pr_id = await _seed_pr(engine)
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                await reject_requisition(
                    pr_id=pr_id, actor="A", reason="first", session=s
                )
        # Second reject must fail the conditional UPDATE (status no longer pending).
        async with AsyncSession(engine, expire_on_commit=False) as s:
            with pytest.raises(ProcurementRuleError):
                async with s.begin():
                    await reject_requisition(
                        pr_id=pr_id, actor="B", reason="second", session=s
                    )
        # The first decision/reason is intact — not overwritten.
        async with AsyncSession(engine, expire_on_commit=False) as s:
            pr = await s.get(PurchaseRequisition, pr_id)
            assert pr.rejected_reason == "first"
            assert pr.approver == "A"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_approve_after_reject_is_blocked():
    engine = await _make_engine()
    try:
        pr_id = await _seed_pr(engine)
        async with AsyncSession(engine, expire_on_commit=False) as s:
            async with s.begin():
                await reject_requisition(pr_id=pr_id, actor="A", reason="x", session=s)
        async with AsyncSession(engine, expire_on_commit=False) as s:
            with pytest.raises(ProcurementRuleError):
                async with s.begin():
                    await approve_requisition(pr_id=pr_id, actor="B", session=s)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_reject_only_one_wins():
    # File-backed so two sessions share one DB.
    engine = await _make_engine(file_backed=True)
    try:
        pr_id = await _seed_pr(engine)

        async def _attempt(reason: str):
            async with AsyncSession(engine, expire_on_commit=False) as s:
                try:
                    async with s.begin():
                        await reject_requisition(
                            pr_id=pr_id, actor=reason, reason=reason, session=s
                        )
                    return True
                except ProcurementRuleError:
                    return False

        results = await asyncio.gather(_attempt("one"), _attempt("two"))
        assert sum(1 for r in results if r) == 1, results
        async with AsyncSession(engine, expire_on_commit=False) as s:
            logs = (
                await s.execute(
                    select(ActionLog).where(ActionLog.target_entity_id == pr_id)
                )
            ).scalars().all()
            assert len(logs) == 1  # exactly one decision audited
    finally:
        await engine.dispose()


# ---------- customer maintenance audit -----------------------------------


def _build_app(engine, *, actor: str = "test-actor"):
    from fastapi import FastAPI, Request

    from yunwei_win.api.customer_management import router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp_actor(request: Request, call_next):
        request.state.actor = actor
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_session] = _override_session
    return app


async def _seed_customer(engine) -> uuid.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        c = Customer(full_name="审计客户有限公司", short_name="审计")
        s.add(c)
        await s.commit()
        return c.id


async def _logs_for(engine, customer_id):
    async with AsyncSession(engine, expire_on_commit=False) as s:
        return (
            await s.execute(
                select(ActionLog).where(ActionLog.target_entity_id == customer_id)
            )
        ).scalars().all()


@pytest.mark.asyncio
async def test_patch_customer_writes_actionlog():
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        cid = await _seed_customer(engine)
        app = _build_app(engine)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.patch(f"/customers/{cid}", json={"notes": "VIP 客户"})
            assert r.status_code == 200, r.text
        logs = await _logs_for(engine, cid)
        assert len(logs) == 1
        log = logs[0]
        assert log.target_entity_type == ActionTargetType.customer
        assert log.actor == "test-actor"
        assert log.actor_kind == "user"
        assert "patch_customer" in log.input_summary
        assert "notes" in log.input_summary
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_patch_customer_no_change_no_log():
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        cid = await _seed_customer(engine)
        app = _build_app(engine)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.patch(f"/customers/{cid}", json={})
            assert r.status_code == 200, r.text
        assert await _logs_for(engine, cid) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_put_contacts_writes_actionlog():
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        cid = await _seed_customer(engine)
        app = _build_app(engine)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.put(
                f"/customers/{cid}/contacts",
                json={"contacts": [{"name": "王经理", "mobile": "13800000000"}]},
            )
            assert r.status_code == 200, r.text
        logs = await _logs_for(engine, cid)
        assert len(logs) == 1
        assert "put_contacts" in logs[0].input_summary
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_customer_actionlog_survives_cascade():
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        cid = await _seed_customer(engine)
        app = _build_app(engine)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.delete(f"/customers/{cid}")
            assert r.status_code == 200, r.text
        # Customer gone, but the audit row remains (append-only, no FK).
        async with AsyncSession(engine, expire_on_commit=False) as s:
            assert await s.get(Customer, cid) is None
        logs = await _logs_for(engine, cid)
        assert len(logs) == 1
        assert "delete_customer" in logs[0].input_summary
        assert "审计客户有限公司" in logs[0].input_summary
    finally:
        await engine.dispose()
