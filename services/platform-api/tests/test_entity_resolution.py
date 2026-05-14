from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register mappers
from yunwei_win.db import Base
from yunwei_win.models.company_data import Invoice
from yunwei_win.models.contact import Contact
from yunwei_win.models.customer import Customer
from yunwei_win.services.schema_ingest.entity_resolution import (
    EntityCandidate,
    propose_entity_resolution,
)
from yunwei_win.services.schema_ingest.extraction_normalize import (
    NormalizedExtraction,
    NormalizedFieldValue,
    NormalizedRow,
)
from yunwei_win.services.schema_ingest.schemas import (
    ReviewEntityCandidate,
    ReviewRowDecision,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


def _field(value, *, confidence: float | None = 0.95):
    return NormalizedFieldValue(value=value, confidence=confidence, source_refs=[])


def _extraction(table_name: str, fields: dict[str, NormalizedFieldValue]) -> NormalizedExtraction:
    return NormalizedExtraction(
        provider="deepseek",
        tables={
            table_name: [
                NormalizedRow(client_row_id=f"{table_name}:0", fields=fields)
            ]
        },
        metadata={},
    )


@pytest.mark.asyncio
async def test_customer_tax_id_strong_match_defaults_to_update():
    engine, session = await _session()
    try:
        existing = Customer(full_name="测试有限公司", tax_id="91330000X")
        session.add(existing)
        await session.flush()

        extraction = _extraction(
            "customers",
            {
                "full_name": _field("测试有限公司"),
                "tax_id": _field("91330000X"),
            },
        )
        proposal = await propose_entity_resolution(session=session, extraction=extraction)
        row = proposal.rows[0]
        assert row.table_name == "customers"
        assert row.proposed_operation == "update"
        assert row.selected_entity_id == existing.id
        assert row.match_level == "strong"
        assert row.match_keys == ["tax_id"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_customer_full_name_strong_match_when_tax_id_missing():
    engine, session = await _session()
    try:
        existing = Customer(full_name="测试有限公司")
        session.add(existing)
        await session.flush()

        # spaces and case differences must still match because we normalize.
        extraction = _extraction(
            "customers",
            {"full_name": _field(" 测试 有限公司 ")},
        )
        proposal = await propose_entity_resolution(session=session, extraction=extraction)
        row = proposal.rows[0]
        assert row.proposed_operation == "update"
        assert row.selected_entity_id == existing.id
        assert row.match_level == "strong"
        assert row.match_keys == ["full_name"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_contact_mobile_strong_match_within_selected_customer():
    engine, session = await _session()
    try:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.flush()
        contact = Contact(customer_id=customer.id, name="张三", mobile="13800000000")
        session.add(contact)
        await session.flush()

        extraction = _extraction(
            "contacts",
            {"name": _field("Anyone"), "mobile": _field("13800000000")},
        )
        proposal = await propose_entity_resolution(
            session=session,
            extraction=extraction,
            selected_customer_id=customer.id,
        )
        row = proposal.rows[0]
        assert row.proposed_operation == "update"
        assert row.selected_entity_id == contact.id
        assert row.match_level == "strong"
        assert row.match_keys == ["mobile"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_contact_name_only_candidate_defaults_to_create():
    engine, session = await _session()
    try:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.flush()
        contact = Contact(customer_id=customer.id, name="张三")
        session.add(contact)
        await session.flush()

        extraction = _extraction("contacts", {"name": _field("张三")})
        proposal = await propose_entity_resolution(
            session=session,
            extraction=extraction,
            selected_customer_id=customer.id,
        )
        row = proposal.rows[0]
        assert row.proposed_operation == "create"
        assert row.match_level == "weak"
        assert row.selected_entity_id is None
        assert row.candidates
        assert row.candidates[0].entity_id == contact.id
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_invoice_no_strong_match_with_selected_customer():
    engine, session = await _session()
    try:
        customer = Customer(full_name="测试有限公司")
        session.add(customer)
        await session.flush()
        invoice = Invoice(customer_id=customer.id, invoice_no="INV-001")
        session.add(invoice)
        await session.flush()

        extraction = _extraction("invoices", {"invoice_no": _field("INV-001")})
        proposal = await propose_entity_resolution(
            session=session,
            extraction=extraction,
            selected_customer_id=customer.id,
        )
        row = proposal.rows[0]
        assert row.proposed_operation == "update"
        assert row.selected_entity_id == invoice.id
        assert row.match_level == "strong"
        assert row.match_keys == ["invoice_no", "customer_id"]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_match_defaults_to_create():
    engine, session = await _session()
    try:
        # No existing customer / contact at all.
        extraction = NormalizedExtraction(
            provider="deepseek",
            tables={
                "customers": [
                    NormalizedRow(
                        client_row_id="customers:0",
                        fields={"full_name": _field("新客户")},
                    )
                ],
                "contacts": [
                    NormalizedRow(
                        client_row_id="contacts:0",
                        fields={"name": _field("李四")},
                    )
                ],
            },
            metadata={},
        )
        proposal = await propose_entity_resolution(session=session, extraction=extraction)
        by_table = {r.table_name: r for r in proposal.rows}
        for tbl in ("customers", "contacts"):
            row = by_table[tbl]
            assert row.proposed_operation == "create"
            assert row.selected_entity_id is None
            assert row.match_level == "none"
            assert row.candidates == []
    finally:
        await session.close()
        await engine.dispose()


def test_review_row_decision_schema_round_trips_uuid():
    candidate_id = uuid4()
    decision = ReviewRowDecision(
        operation="update",
        selected_entity_id=candidate_id,
        candidate_entities=[
            ReviewEntityCandidate(
                entity_id=candidate_id,
                label="测试有限公司",
                match_level="strong",
                match_keys=["tax_id"],
                confidence=0.95,
                reason=None,
            )
        ],
        match_level="strong",
        match_keys=["tax_id"],
        reason=None,
    )

    dumped = decision.model_dump(mode="json")
    assert dumped["operation"] == "update"
    assert dumped["selected_entity_id"] == str(candidate_id)
    assert dumped["candidate_entities"][0]["entity_id"] == str(candidate_id)
    assert dumped["match_level"] == "strong"
    assert dumped["match_keys"] == ["tax_id"]
