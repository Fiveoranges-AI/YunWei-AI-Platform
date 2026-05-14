from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override Postgres+Redis fixture
    yield


import yunwei_win.models  # noqa: E402, F401 — register mappers
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from yunwei_win.api.customer_profile import ask as ask_module  # noqa: E402
from yunwei_win.api.customer_profile.ask import (  # noqa: E402
    _ask_tool,
    answer_customer_question,
)
from yunwei_win.db import Base, dispose_all  # noqa: E402
from yunwei_win.models.customer import Customer  # noqa: E402
from yunwei_win.schemas.customer import CustomerAskCitation  # noqa: E402


_VNEXT_TARGET_TYPES = [
    "invoice",
    "invoice_item",
    "payment",
    "shipment",
    "shipment_item",
    "product",
    "product_requirement",
    "contract_payment_milestone",
    "journal_item",
]


def test_customer_ask_citation_accepts_vnext_target_types():
    for target_type in _VNEXT_TARGET_TYPES:
        citation = CustomerAskCitation(
            target_type=target_type,
            target_id=str(uuid4()),
            snippet=f"sample for {target_type}",
        )
        assert citation.target_type == target_type


def test_ask_tool_declares_vnext_target_type_enum():
    tool = _ask_tool()
    citation_schema = tool["input_schema"]["properties"]["citations"]
    target_type_schema = citation_schema["items"]["properties"]["target_type"]
    assert target_type_schema["type"] == "string"
    enum_values = target_type_schema["enum"]
    # vNext types present
    for target_type in _VNEXT_TARGET_TYPES:
        assert target_type in enum_values
    # Legacy types preserved so older drafts still cite-through cleanly.
    for legacy in (
        "customer",
        "contact",
        "contract",
        "order",
        "document",
        "event",
        "commitment",
        "task",
        "risk",
        "memory",
    ):
        assert legacy in enum_values


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


@pytest.mark.asyncio
async def test_answer_customer_question_preserves_vnext_citations(monkeypatch):
    engine = await _make_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        customer_id = customer.id

    invoice_id = str(uuid4())
    journal_id = str(uuid4())

    async def fake_call_claude(messages, **kwargs):
        return SimpleNamespace(content=[])

    def fake_extract(response, tool_name):
        return {
            "answer": "有一张发票和一条时间线记录",
            "confidence": 0.9,
            "citations": [
                {
                    "target_type": "invoice",
                    "target_id": invoice_id,
                    "snippet": "INV-001",
                },
                {
                    "target_type": "journal_item",
                    "target_id": journal_id,
                    "snippet": "客户承诺 6 月底前交付",
                },
            ],
            "no_relevant_info": False,
        }

    monkeypatch.setattr(ask_module, "call_claude", fake_call_claude)
    monkeypatch.setattr(ask_module, "extract_tool_use_input", fake_extract)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await answer_customer_question(
                session, customer_id, "最近的发票和承诺是什么？"
            )
        assert result["answer"].startswith("有一张发票")
        assert result["confidence"] == 0.9
        assert len(result["citations"]) == 2
        target_types = [c["target_type"] for c in result["citations"]]
        assert "invoice" in target_types
        assert "journal_item" in target_types
        # IDs round-trip untouched so the frontend can deep-link.
        ids = {c["target_id"] for c in result["citations"]}
        assert invoice_id in ids
        assert journal_id in ids
    finally:
        await engine.dispose()
        await dispose_all()
