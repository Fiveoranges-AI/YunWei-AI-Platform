from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yinhu_brain.models  # noqa: F401 - register SQLAlchemy mappers
from yinhu_brain.api.customer_profile.metrics import _milestones_paid
from yinhu_brain.db import Base
from yinhu_brain.models import Contact, Contract, Customer, Document, DocumentType, Order
from yinhu_brain.models.customer_memory import DocumentReviewStatus
from yinhu_brain.services.ingest import business_card as business_card_service
from yinhu_brain.services.ingest.contract import commit_contract_extraction
from yinhu_brain.services.ingest.schemas import ContractConfirmRequest


@pytest.mark.asyncio
async def test_contract_confirm_writes_customer_order_contract() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        doc = Document(
            type=DocumentType.contract,
            file_url="/tmp/contract.pdf",
            original_filename="contract.pdf",
            file_sha256="0" * 64,
            file_size_bytes=123,
            ocr_text="测试客户 合同金额 1000",
            review_status=DocumentReviewStatus.pending_review,
        )
        session.add(doc)
        await session.flush()

        request = ContractConfirmRequest(
            customer={
                "mode": "new",
                "final": {"full_name": "测试客户有限公司", "short_name": "测试客户"},
            },
            contacts=[],
            order={
                "amount_total": 1000,
                "amount_currency": "CNY",
                "delivery_promised_date": None,
                "delivery_address": None,
                "description": "测试订单",
            },
            contract={
                "contract_no_external": "T-001",
                "payment_milestones": [
                    {"name": "预付款", "ratio": 0.3, "trigger_event": "contract_signed"},
                    {"name": "尾款", "ratio": 0.7, "trigger_event": "on_acceptance"},
                ],
                "delivery_terms": None,
                "penalty_terms": None,
                "signing_date": None,
                "effective_date": None,
                "expiry_date": None,
            },
            field_provenance=[],
            confidence_overall=0.91,
            field_confidence={},
            parse_warnings=[],
        )

        result = await commit_contract_extraction(
            session=session,
            document_id=doc.id,
            request=request,
        )
        await session.commit()

        customers = (await session.execute(select(Customer))).scalars().all()
        orders = (await session.execute(select(Order))).scalars().all()
        contracts = (await session.execute(select(Contract))).scalars().all()

        assert len(customers) == 1
        assert len(orders) == 1
        assert len(contracts) == 1
        assert result.customer_id == customers[0].id
        assert contracts[0].contract_no_external == "T-001"
        assert doc.review_status == DocumentReviewStatus.confirmed
        assert doc.assigned_customer_id == customers[0].id

    await engine.dispose()


@pytest.mark.asyncio
async def test_business_card_ingest_creates_customer_and_attaches_contact(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def fake_call_claude(*args, **kwargs):
        return object()

    def fake_extract_tool_use_input(response, tool_name):
        return {
            "name": "王强",
            "title": "销售经理",
            "company_full_name": "测试客户有限公司",
            "company_short_name": "测试客户",
            "mobile": "13800000000",
            "email": "wang@example.com",
            "address": "上海市测试路 1 号",
            "field_provenance": [
                {
                    "path": "company_full_name",
                    "source_page": None,
                    "source_excerpt": "测试客户有限公司",
                },
                {"path": "name", "source_page": None, "source_excerpt": "王强"},
            ],
            "confidence_overall": 0.93,
            "parse_warnings": [],
        }

    monkeypatch.setattr(business_card_service, "call_claude", fake_call_claude)
    monkeypatch.setattr(
        business_card_service,
        "extract_tool_use_input",
        fake_extract_tool_use_input,
    )
    monkeypatch.setattr(
        business_card_service,
        "store_upload",
        lambda image_bytes, original_filename, default_ext=".jpg": (
            "/tmp/card.jpg",
            "1" * 64,
            len(image_bytes),
        ),
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await business_card_service.ingest_business_card(
            session=session,
            image_bytes=b"fake image",
            original_filename="card.jpg",
            content_type="image/jpeg",
            uploader="tester",
        )
        await session.commit()

        customers = (await session.execute(select(Customer))).scalars().all()
        contacts = (await session.execute(select(Contact))).scalars().all()
        doc = (
            await session.execute(select(Document).where(Document.id == result.document_id))
        ).scalar_one()

        assert len(customers) == 1
        assert len(contacts) == 1
        assert customers[0].full_name == "测试客户有限公司"
        assert contacts[0].customer_id == customers[0].id
        assert result.customer_id == customers[0].id
        assert result.customer_name == "测试客户有限公司"
        assert result.contact_name == "王强"
        assert doc.assigned_customer_id == customers[0].id
        assert doc.review_status == DocumentReviewStatus.confirmed

    await engine.dispose()


def test_milestones_paid_supports_amount_or_ratio() -> None:
    paid = _milestones_paid(
        [
            {"status": "paid", "amount": "120.50", "ratio": 0.3},
            {"status": "paid", "ratio": 0.2},
            {"status": "pending", "amount": "999"},
        ],
        Decimal("1000"),
    )

    assert paid == Decimal("320.50")
