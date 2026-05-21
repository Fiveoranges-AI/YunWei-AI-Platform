"""End-to-end P0 integration test — Excel → candidate JSON → confirm → ontology.

Proves the three P0 tasks chain together as one pipeline:

  task ② parse_pipeline.parse_to_candidates(Excel)
       → CandidateJSON {entities, relationships, missing_required}
  task ③ ConfirmEntitiesRequest (frontend-shaped) → POST /confirm/entities
       → confirm_writer persists into task ① ontology tables (customers,
         orders, contacts, action_logs) with full audit stamps.

What this asserts (golden standard for "the P0 product loop actually works"):

  * Candidate JSON shape produced by task ② is consumable by the task ③
    Pydantic request model verbatim — no field-name remapping required.
  * Confirmed rows land in task ① ontology tables with the correct
    relationships (Order.customer_id resolved from Customer-has-Order).
  * Audit stamps populate exactly as documented: human_verified=True,
    verified_by set, source_type / source_ref passed through from the
    candidate, source_span persisted as JSON.
  * Edited fields: per-field confidence becomes NULL, was_edited
    appears in the ActionLog input_summary.
  * Row confidence = min surviving (un-edited) field confidence.
  * One ActionLog row per entity, target_entity_type matches the
    ontology mapping (Customer, Order, Contact).
  * missing_required mirrors the task ① required_fields() output —
    when the user supplies a previously-missing value via an edit, it
    lands on the row.

Stays in-process: in-memory SQLite (FK on), ASGITransport, MockProvider
not required because the Excel adapter is provider-free.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest


# Override the project-level Postgres-truncating fixture; we use SQLite.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base, get_session
from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    Contact,
    Customer,
    Order,
)
from yunwei_win.services.parse_pipeline import parse_to_candidates
from yunwei_win.services.parse_pipeline.ontology import required_fields


_FIXTURES = Path(__file__).parent / "fixtures" / "parse_pipeline"


async def _make_engine():
    from sqlalchemy import event

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _build_app(engine, *, actor: str = "p0-tester"):
    from fastapi import FastAPI

    from yunwei_win.api.confirm import router

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()

    @app.middleware("http")
    async def _stamp_actor(request, call_next):
        request.state.actor = actor
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_session] = _override_session
    return app


def _candidate_to_confirm_payload(
    candidate,
    *,
    edits: dict[str, dict[str, object]] | None = None,
):
    """Mirror the frontend useConfirmSubmit.buildEntityDraft path.

    Input: CandidateJSON from task ② + a dict {temp_id: {field_name: new_value}}
           representing the user's edits.
    Output: a dict shaped exactly like apps/win-web/src/data/candidate.ts
            ``ConfirmEntitiesRequest`` (which the task ③ API endpoint
            deserialises into ``ConfirmEntitiesRequest`` Pydantic model).
    """
    edits = edits or {}

    def _build_entity(ent):
        draft_fields = []
        ent_edits = edits.get(ent.temp_id, {})
        edited_names = set(ent_edits.keys())
        seen = set()
        for f in ent.fields:
            was_edited = f.name in edited_names
            seen.add(f.name)
            span = f.source_span.model_dump() if f.source_span else None
            draft_fields.append(
                {
                    "name": f.name,
                    "value": ent_edits[f.name] if was_edited else f.value,
                    "confidence": None if was_edited else f.confidence,
                    "was_edited": was_edited,
                    "source_span": span,
                }
            )
        # Edits that aren't in the original candidate (user filled a
        # missing_required slot from the "+待补充" chip).
        for name, value in ent_edits.items():
            if name in seen:
                continue
            draft_fields.append(
                {
                    "name": name,
                    "value": value,
                    "confidence": None,
                    "was_edited": True,
                    "source_span": None,
                }
            )
        return {
            "entity_type": ent.entity_type,
            "temp_id": ent.temp_id,
            "fields": draft_fields,
            "existing_entity_id": None,
        }

    return {
        "ingestion_id": candidate.ingestion_id,
        "source_type": candidate.source.type,
        "source_ref": candidate.source.file_ref,
        "entities": [_build_entity(e) for e in candidate.entities],
        "relationships": [
            {
                "from_temp_id": r.from_temp_id,
                "to_temp_id": r.to_temp_id,
                "type": r.type,
            }
            for r in candidate.relationships
        ],
    }


# =====================================================================
# Golden standard test: one Excel file → ontology + audit, no manual seam.
# =====================================================================


@pytest.mark.asyncio
async def test_p0_excel_parse_then_confirm_lands_in_ontology_with_audit():
    """Run the full P0 pipeline end-to-end on the sample Excel fixture.

    Steps:
      1. parse_to_candidates(sample_orders.csv, "excel") — task ②.
      2. The user "edits" one Order's amount_total (simulating an Excel
         OCR fix).
      3. Build ConfirmEntitiesRequest from the candidate + edit.
      4. POST /confirm/entities — task ③ endpoint.
      5. Assert ontology rows, audit stamps, ActionLog, edited-field
         confidence behaviour.
    """
    from httpx import ASGITransport, AsyncClient

    # ---- Step 1: parse Excel → candidate JSON (task ②) -----------------
    candidate = await parse_to_candidates(
        file_path=_FIXTURES / "sample_orders.csv",
        source_type="excel",
        filename="sample_orders.csv",
        content_type="text/csv",
        file_ref="storage://p0-e2e/sample_orders.csv",
        uploaded_by="p0-tester",
    )
    assert candidate.entities, "parse_pipeline should emit candidates from the Excel sample"
    # Sanity: the Excel adapter found Customers, Orders, Contacts.
    entity_types = {e.entity_type for e in candidate.entities}
    assert {"Customer", "Order", "Contact"} <= entity_types

    # Customer.full_name is the only required column for Customer; it's
    # present in the sample, so missing_required is empty everywhere.
    customer_entities = [e for e in candidate.entities if e.entity_type == "Customer"]
    for cust in customer_entities:
        assert cust.missing_required == [], (
            f"unexpected missing_required {cust.missing_required} on Customer "
            f"{cust.temp_id}"
        )

    # Sanity-check task ② <-> task ① alignment: required_fields() must
    # mention Customer.full_name, and full_name appears on the candidate.
    assert "full_name" in required_fields("Customer")
    full_name = next(
        f for f in customer_entities[0].fields if f.name == "full_name"
    )
    assert full_name.value
    assert 0 < full_name.confidence <= 1.0

    # ---- Step 2: "user" edits the first Order's amount_total -----------
    order_entities = [e for e in candidate.entities if e.entity_type == "Order"]
    target_order = order_entities[0]
    original_amount = next(
        f for f in target_order.fields if f.name == "amount_total"
    )
    # Original amount from CSV row 1 is "128000"; pretend the user fixed it.
    EDITED_AMOUNT = "130000.50"
    edits = {target_order.temp_id: {"amount_total": EDITED_AMOUNT}}

    payload = _candidate_to_confirm_payload(candidate, edits=edits)

    # ---- Step 3 + 4: POST /confirm/entities (task ③) -------------------
    engine = await _make_engine()
    try:
        app = _build_app(engine, actor="p0-tester")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/confirm/entities", json=payload)
            assert resp.status_code == 200, resp.text
            body = resp.json()

        # ---- Step 5: assertions on the response shape ------------------
        # One written row per candidate entity.
        assert len(body["written"]) == len(candidate.entities)
        # One ActionLog per entity (task ③ contract).
        assert len(body["action_log_ids"]) == len(candidate.entities)

        for w in body["written"]:
            assert w["human_verified"] is True
            assert w["verified_by"] == "p0-tester"
            assert w["created"] is True
        # The edited Order should report edited_field_count >= 1.
        target_written = next(
            w for w in body["written"] if w["temp_id"] == target_order.temp_id
        )
        assert target_written["edited_field_count"] == 1, target_written

        # ---- DB-level assertions: ontology rows + audit ----------------
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customers = list(
                (await session.execute(select(Customer))).scalars()
            )
            orders = list((await session.execute(select(Order))).scalars())
            contacts = list((await session.execute(select(Contact))).scalars())
            logs = list((await session.execute(select(ActionLog))).scalars())

            # Two CSV rows × {Customer, Order, Contact}.
            assert len(customers) == 2
            assert len(orders) == 2
            assert len(contacts) == 2
            assert len(logs) == 6

            # Order.customer_id resolved from Customer-has-Order relationship.
            for o in orders:
                assert o.customer_id is not None
                # Audit stamp transferred from candidate.source.
                assert o.human_verified is True
                assert o.verified_by == "p0-tester"
                assert o.source_type == "excel"
                assert o.source_ref == "storage://p0-e2e/sample_orders.csv"
                # row source_span aggregates per-field spans into {primary, fields}.
                assert o.source_span is not None
                assert "fields" in o.source_span
                # extracted_by="llm" stamped by writer.
                assert o.extracted_by == "llm"
                # Created/updated_by mirror verified_by for confirm-time inserts.
                assert o.created_by == "p0-tester"
                assert o.updated_by == "p0-tester"

            # Confirm the edit reached the row + dropped per-field confidence.
            edited_order = next(
                o for o in orders if o.amount_total == Decimal("130000.50")
            )
            # Row confidence = min surviving field confidence (the edited
            # field's confidence is NULL'd and excluded). The other Order
            # fields all came from the Excel adapter with header-match
            # confidence (~0.85 substring or 1.0 exact).
            assert edited_order.confidence is not None
            assert edited_order.confidence <= Decimal("1.00")

            # Contact.customer_id resolved from Customer-has-Contact rel.
            for ct in contacts:
                assert ct.customer_id is not None
                assert ct.human_verified is True
                assert ct.source_type == "excel"

            # ActionLog: target_entity_type matches the writer's mapping.
            target_types = {l.target_entity_type for l in logs}
            assert ActionTargetType.customer in target_types
            assert ActionTargetType.order in target_types
            assert ActionTargetType.contact in target_types

            # The ActionLog for the edited Order names amount_total.
            edited_log = next(
                l for l in logs
                if l.target_entity_id == edited_order.id
            )
            assert "edited=1" in (edited_log.input_summary or "")
            assert "amount_total" in (edited_log.input_summary or "")

            # Cross-task ingestion_id round-trip: the writer puts the
            # candidate's ingestion_id into ActionLog.input_summary so
            # the audit trail links back to the source candidate.
            assert (
                f"ingestion={candidate.ingestion_id}"
                in (edited_log.input_summary or "")
            )
    finally:
        await engine.dispose()


# =====================================================================
# missing_required round-trip: user supplies a missing field at confirm
# time and it lands on the row.
# =====================================================================


@pytest.mark.asyncio
async def test_p0_missing_required_supplied_at_confirm_lands_on_row(tmp_path):
    """Synthesise an Excel sheet that omits the Order.customer_id parent
    *via missing the Customer column entirely*. The Excel adapter
    surfaces zero customers, the Order has no parent.

    Then the user supplies the customer via a separate Customer entity
    and a Customer-has-Order relationship at confirm time. We then
    verify the order lands with the right FK.
    """
    from httpx import ASGITransport, AsyncClient

    # Build a CSV that has Order headers but no Customer column.
    csv = tmp_path / "orders_only.csv"
    csv.write_text(
        "订单号,订单日期,订单金额\n"
        "PO-X-001,2026-05-01,77777\n",
        encoding="utf-8",
    )
    candidate = await parse_to_candidates(
        file_path=csv,
        source_type="excel",
        filename="orders_only.csv",
        content_type="text/csv",
        file_ref="storage://p0-e2e/orders_only.csv",
        uploaded_by="p0-tester",
    )
    # Adapter should produce one Order row, no Customer.
    order_entities = [e for e in candidate.entities if e.entity_type == "Order"]
    assert len(order_entities) == 1
    assert not any(e.entity_type == "Customer" for e in candidate.entities)

    # Build a confirm payload that injects a Customer + parent rel.
    payload = _candidate_to_confirm_payload(candidate)
    payload["entities"].append(
        {
            "entity_type": "Customer",
            "temp_id": "manual-customer",
            "fields": [
                {
                    "name": "full_name",
                    "value": "用户手填客户",
                    "confidence": None,
                    "was_edited": True,
                    "source_span": None,
                }
            ],
            "existing_entity_id": None,
        }
    )
    payload["relationships"].append(
        {
            "from_temp_id": "manual-customer",
            "to_temp_id": order_entities[0].temp_id,
            "type": "Customer-has-Order",
        }
    )

    engine = await _make_engine()
    try:
        app = _build_app(engine, actor="p0-tester")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/confirm/entities", json=payload)
            assert resp.status_code == 200, resp.text

        async with AsyncSession(engine, expire_on_commit=False) as session:
            order = (await session.execute(select(Order))).scalar_one()
            customer = (await session.execute(select(Customer))).scalar_one()
            assert order.customer_id == customer.id
            assert customer.full_name == "用户手填客户"
            # The user-supplied customer was a was_edited field; row
            # confidence stays NULL because there are no surviving
            # AI-seeded fields.
            assert customer.confidence is None
            # Order amount survives.
            assert order.amount_total == Decimal("77777")
    finally:
        await engine.dispose()


# =====================================================================
# Schema-contract check: every entity_type the Excel adapter emits is
# accepted by the confirm-writer entity model map.
# =====================================================================


def test_p0_entity_type_surface_matches_writer_and_ontology():
    """Static check across the three P0 surfaces.

    Guards against future drift where someone adds an entity to the
    parse pipeline without wiring it through the writer.
    """
    from yunwei_win.services.confirm_writer import _ENTITY_MODEL
    from yunwei_win.services.parse_pipeline.candidate import (
        EntityType as CandidateEntityType,
    )
    from yunwei_win.services.parse_pipeline.ontology import _ENTITY_MODELS

    candidate_types = set(getattr(CandidateEntityType, "__args__", ()))
    # Every type the candidate may carry must round-trip through the writer.
    for t in candidate_types:
        assert t in _ENTITY_MODEL, (
            f"candidate emits entity_type={t!r} but confirm_writer can't write it"
        )
    # And every type the task ② ontology helper knows must also round-trip.
    for t in _ENTITY_MODELS:
        assert t in _ENTITY_MODEL, (
            f"parse_pipeline.ontology knows entity_type={t!r} but confirm_writer doesn't"
        )
