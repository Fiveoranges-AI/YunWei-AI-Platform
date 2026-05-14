from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from fastapi import FastAPI, Request  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.api.customer_profile.ask import _build_customer_kb  # noqa: E402
from yunwei_win.db import Base, dispose_all, get_session  # noqa: E402
from yunwei_win.models.company_data import (  # noqa: E402
    ContractPaymentMilestone,
    CustomerJournalItem,
    Invoice,
    InvoiceItem,
    Payment,
    Product,
    ProductRequirement,
    Shipment,
    ShipmentItem,
)
from yunwei_win.models.contact import Contact, ContactRole  # noqa: E402
from yunwei_win.models.contract import Contract  # noqa: E402
from yunwei_win.models.customer import Customer  # noqa: E402
from yunwei_win.models.customer_memory import (  # noqa: E402
    CustomerTask,
    TaskPriority,
    TaskStatus,
)
from yunwei_win.models.document import Document, DocumentType  # noqa: E402
from yunwei_win.models.order import Order  # noqa: E402
from yunwei_win.routes import router as yinhu_router  # noqa: E402


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_enterprise(request: Request, call_next):
        request.state.enterprise_id = "tenant_test"
        return await call_next(request)

    async def session_dep():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = session_dep
    app.include_router(yinhu_router, prefix="/api/win")
    return app


async def _seed_full_customer(engine) -> dict:
    """Seed a customer + every first-version review-visible table."""

    async with AsyncSession(engine, expire_on_commit=False) as session:
        customer = Customer(
            full_name="测试有限公司",
            industry="制造业",
            notes="重点客户",
            short_name="测试",
            tax_id="91330000ABC",
        )
        session.add(customer)
        await session.flush()

        document = Document(
            type=DocumentType.contract,
            file_url="memory://contract.pdf",
            file_sha256="abcd" * 16,
            file_size_bytes=1234,
            original_filename="contract.pdf",
            content_type="application/pdf",
            assigned_customer_id=customer.id,
        )
        session.add(document)
        await session.flush()

        contact = Contact(
            customer_id=customer.id,
            name="张三",
            title="采购经理",
            phone="0571-12345678",
            mobile="13800000000",
            email="zs@example.com",
            address="杭州市西湖区",
            wechat_id="zs_wx",
            role=ContactRole.buyer,
        )
        session.add(contact)

        product = Product(
            sku="SKU-001",
            name="高精度法兰盘",
            specification="DN50",
            unit="件",
        )
        session.add(product)
        await session.flush()

        requirement = ProductRequirement(
            customer_id=customer.id,
            product_id=product.id,
            requirement_type="工艺",
            requirement_text="表面粗糙度 ≤ Ra1.6",
            tolerance="±0.05mm",
            source_document_id=document.id,
        )
        session.add(requirement)

        order = Order(
            customer_id=customer.id,
            amount_total=Decimal("30000.00"),
            amount_currency="CNY",
            delivery_promised_date=date(2026, 6, 1),
            description="首批合作订单",
        )
        session.add(order)
        await session.flush()

        contract = Contract(
            customer_id=customer.id,
            order_id=order.id,
            contract_no_external="HT-2026-001",
            amount_total=Decimal("30000.00"),
            amount_currency="CNY",
            delivery_terms="FOB 上海",
            penalty_terms="逾期每日 0.05% 违约金",
            signing_date=date(2026, 5, 1),
        )
        session.add(contract)
        await session.flush()

        milestone = ContractPaymentMilestone(
            contract_id=contract.id,
            name="预付款",
            ratio=Decimal("0.3"),
            amount=Decimal("9000.00"),
            trigger_event="合同签订",
        )
        session.add(milestone)

        invoice = Invoice(
            customer_id=customer.id,
            order_id=order.id,
            invoice_no="INV-001",
            issue_date=date(2026, 5, 5),
            amount_total=Decimal("9000.00"),
            amount_currency="CNY",
            tax_amount=Decimal("810.00"),
            status="open",
        )
        session.add(invoice)
        await session.flush()

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            description="法兰盘 30 件",
            quantity=Decimal("30"),
            unit_price=Decimal("300"),
            amount=Decimal("9000.00"),
        )
        session.add(invoice_item)

        payment = Payment(
            customer_id=customer.id,
            invoice_id=invoice.id,
            payment_date=date(2026, 5, 10),
            amount=Decimal("9000.00"),
            currency="CNY",
            method="transfer",
            reference_no="P-202605-01",
        )
        session.add(payment)

        shipment = Shipment(
            customer_id=customer.id,
            order_id=order.id,
            shipment_no="S-2026-01",
            carrier="顺丰",
            tracking_no="SF1234567890",
            ship_date=date(2026, 5, 20),
            status="in_transit",
        )
        session.add(shipment)
        await session.flush()

        shipment_item = ShipmentItem(
            shipment_id=shipment.id,
            product_id=product.id,
            description="法兰盘",
            quantity=Decimal("30"),
            unit="件",
        )
        session.add(shipment_item)

        journal = CustomerJournalItem(
            customer_id=customer.id,
            document_id=document.id,
            item_type="commitment",
            title="承诺 6 月底前完成首批交付",
            content="销售在沟通中承诺 6 月底前完成首批 30 件交付。",
            occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        )
        session.add(journal)

        task = CustomerTask(
            customer_id=customer.id,
            document_id=document.id,
            title="跟进首批交付进度",
            description="确认 6 月底前发货",
            assignee="销售助理 Lily",
            due_date=date(2026, 6, 25),
            priority=TaskPriority.high,
            status=TaskStatus.open,
        )
        session.add(task)

        await session.commit()
        return {
            "customer_id": customer.id,
            "document_id": document.id,
            "product_id": product.id,
            "contract_id": contract.id,
            "invoice_id": invoice.id,
            "shipment_id": shipment.id,
            "task_id": task.id,
        }


# ---------------------------------------------------------------------------
# 1. GET /customers/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_customer_returns_all_vnext_confirmed_tables():
    engine = await _make_engine()
    seed = await _seed_full_customer(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(f"/api/win/customers/{seed['customer_id']}")
            assert res.status_code == 200, res.text
            body = res.json()

            assert body["industry"] == "制造业"
            assert body["notes"] == "重点客户"

            assert body["contacts"][0]["title"] == "采购经理"
            assert body["contacts"][0]["address"] == "杭州市西湖区"
            assert body["contacts"][0]["wechat_id"] == "zs_wx"

            assert body["orders"]
            assert body["contracts"][0]["delivery_terms"] == "FOB 上海"
            assert body["contracts"][0]["penalty_terms"].startswith("逾期")

            assert body["contract_payment_milestones"]
            assert body["contract_payment_milestones"][0]["name"] == "预付款"

            assert body["invoices"][0]["invoice_no"] == "INV-001"
            assert body["invoice_items"][0]["description"].startswith("法兰盘")
            assert body["payments"][0]["amount"] == 9000.0
            assert body["payments"][0]["reference_no"] == "P-202605-01"

            assert body["shipments"][0]["tracking_no"] == "SF1234567890"
            assert body["shipment_items"][0]["quantity"] == 30.0

            assert body["products"][0]["name"] == "高精度法兰盘"
            assert body["product_requirements"][0]["requirement_text"].startswith(
                "表面粗糙度"
            )

            assert body["journal_items"][0]["item_type"] == "commitment"
            assert body["tasks"][0]["assignee"] == "销售助理 Lily"

            doc_ids = {d["id"] for d in body["source_documents"]}
            assert str(seed["document_id"]) in doc_ids
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 2. PATCH industry / notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customer_patch_updates_industry_and_notes():
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        cid: UUID = customer.id

    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.patch(
                f"/api/win/customers/{cid}",
                json={"industry": "电子", "notes": "本月新增"},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["industry"] == "电子"
            assert body["notes"] == "本月新增"

        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (
                await session.execute(select(Customer).where(Customer.id == cid))
            ).scalar_one()
            assert row.industry == "电子"
            assert row.notes == "本月新增"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 3. Timeline includes vNext journal items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customer_timeline_includes_journal_items():
    engine = await _make_engine()
    seed = await _seed_full_customer(engine)
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get(
                f"/api/win/customers/{seed['customer_id']}/timeline"
            )
            assert res.status_code == 200, res.text
            entries = res.json()
            kinds = {e["kind"] for e in entries}
            assert "journal" in kinds
            journal_entry = next(e for e in entries if e["kind"] == "journal")
            assert journal_entry["payload"]["item_type"] == "commitment"
    finally:
        await engine.dispose()
        await dispose_all()


# ---------------------------------------------------------------------------
# 4. KB builder includes vNext finance / logistics / journal / task signals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_customer_ask_kb_includes_vnext_journal_tasks_and_finance():
    engine = await _make_engine()
    seed = await _seed_full_customer(engine)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customer = (
                await session.execute(
                    select(Customer).where(Customer.id == seed["customer_id"])
                )
            ).scalar_one()
            kb = await _build_customer_kb(session, customer)

        assert "INV-001" in kb
        assert "P-202605-01" in kb  # payment reference
        assert "SF1234567890" in kb  # shipment tracking
        assert "FOB 上海" in kb  # contract delivery terms
        assert "journal_item:" in kb
        assert "销售助理 Lily" in kb
        assert "高精度法兰盘" in kb or "法兰盘" in kb
        assert "制造业" in kb  # customer industry
    finally:
        await engine.dispose()
        await dispose_all()
