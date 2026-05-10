"""Tests for the unified /api/ingest/auto pipeline (Agent G).

Coverage:
- ``merge_drafts`` fuses identity / commercial / ops drafts and computes match
  candidates against existing customers/contacts.
- ``auto_ingest`` orchestrator: end-to-end with mocked LLM + OCR ensures
  Document row + plan + draft + candidates are returned and that each
  concurrent extractor uses its own AsyncSession.
- ``commit_auto_extraction`` writes customer + contacts + order + contract +
  the five customer-memory tables, and stamps Document.review_status =
  confirmed.
- An extractor raising mid-flight does NOT kill the pipeline — its failure
  becomes a warning on the merged draft.
- /api/ingest/auto endpoint streams NDJSON with the expected shape.
- /api/ingest/auto/{id}/confirm + /cancel endpoints work end-to-end.

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_planner.py`` /
``test_evidence.py``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import yinhu_brain.models  # noqa: F401 — register SQLAlchemy mappers
from yinhu_brain.db import Base
from yinhu_brain.models import (
    Contact,
    Contract,
    Customer,
    CustomerCommitment,
    CustomerEvent,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    DocumentReviewStatus,
    Order,
)
from yinhu_brain.services.ingest import auto as auto_module
from yinhu_brain.services.ingest import evidence as evidence_module
from yinhu_brain.services.ingest import planner as planner_module
from yinhu_brain.services.ingest.auto import auto_ingest
from yinhu_brain.services.ingest.auto_confirm import commit_auto_extraction
from yinhu_brain.services.ingest.merge import merge_drafts
from yinhu_brain.services.ingest.unified_schemas import (
    AutoConfirmRequest,
    CommercialDraft,
    IdentityDraft,
    IngestPlan,
    OpsDraft,
    UnifiedDraft,
)


# ---------- helpers -------------------------------------------------------


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


def _patch_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace storage.store_upload with a deterministic in-memory stub."""
    from yinhu_brain.services.storage import StoredFile

    def fake_store(content, original_filename, *, default_ext=""):
        suffix = (
            original_filename.rsplit(".", 1)[1]
            if "." in original_filename
            else default_ext.lstrip(".")
        )
        return StoredFile(
            path=f"/tmp/fake.{suffix or 'bin'}",
            sha256="a" * 64,
            size=len(content),
        )

    monkeypatch.setattr(evidence_module, "store_upload", fake_store)


def _identity_payload() -> dict:
    return {
        "customer": {
            "full_name": "测试客户有限公司",
            "short_name": "测试客户",
            "address": "上海市浦东新区",
            "tax_id": None,
        },
        "contacts": [
            {
                "name": "王经理",
                "title": "销售总监",
                "phone": None,
                "mobile": "13800000000",
                "email": "wang@test.com",
                "role": "buyer",
                "address": None,
            },
        ],
        "field_provenance": [
            {
                "path": "customer.full_name",
                "source_page": None,
                "source_excerpt": "测试客户有限公司",
            }
        ],
        "confidence_overall": 0.9,
        "parse_warnings": [],
    }


def _commercial_payload() -> dict:
    return {
        "order": {
            "amount_total": 120000.0,
            "amount_currency": "CNY",
            "delivery_promised_date": "2026-06-30",
            "delivery_address": "上海市浦东新区",
            "description": "测试订单",
        },
        "contract": {
            "contract_no_external": "T-001",
            "payment_milestones": [
                {"name": "预付款", "ratio": 0.3, "trigger_event": "contract_signed"},
                {"name": "尾款", "ratio": 0.7, "trigger_event": "on_acceptance"},
            ],
            "delivery_terms": "FCA 上海",
            "penalty_terms": None,
            "signing_date": "2026-05-01",
            "effective_date": "2026-05-01",
            "expiry_date": None,
        },
        "field_provenance": [],
        "confidence_overall": 0.85,
        "parse_warnings": [],
    }


def _ops_payload() -> dict:
    return {
        "summary": "客户王经理来电，确认 6 月底交付，金额 12 万",
        "events": [
            {
                "title": "签订合同",
                "event_type": "contract_signed",
                "occurred_at": None,
                "description": "完成签约",
                "raw_excerpt": "签约成功",
                "confidence": 0.8,
            }
        ],
        "commitments": [
            {
                "summary": "客户承诺 6 月底前付 30% 预付",
                "description": None,
                "direction": "customer_to_us",
                "due_date": "2026-06-30",
                "raw_excerpt": "6 月底前付 30%",
                "confidence": 0.7,
            }
        ],
        "tasks": [
            {
                "title": "跟进合同发货安排",
                "description": None,
                "assignee": "我",
                "due_date": None,
                "priority": "normal",
                "raw_excerpt": "跟进发货",
            }
        ],
        "risk_signals": [
            {
                "summary": "客户提出延期付款",
                "description": "可能的逾期信号",
                "severity": "medium",
                "kind": "payment",
                "raw_excerpt": "暂时还没钱",
                "confidence": 0.6,
            }
        ],
        "memory_items": [
            {
                "content": "客户偏好周一沟通",
                "kind": "preference",
                "raw_excerpt": "周一最方便",
                "confidence": 0.9,
            }
        ],
        "field_provenance": [],
        "confidence_overall": 0.8,
        "parse_warnings": [],
    }


# ---------- merge_drafts -------------------------------------------------


@pytest.mark.asyncio
async def test_merge_drafts_combines_three_drafts() -> None:
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            identity = IdentityDraft.model_validate(_identity_payload())
            commercial = CommercialDraft.model_validate(_commercial_payload())
            ops = OpsDraft.model_validate(_ops_payload())

            draft, candidates = await merge_drafts(
                session=session,
                identity=identity,
                commercial=commercial,
                ops=ops,
            )

            assert isinstance(draft, UnifiedDraft)
            assert draft.customer is not None
            assert draft.customer.full_name == "测试客户有限公司"
            assert len(draft.contacts) == 1
            assert draft.order is not None
            assert draft.order.amount_total == pytest.approx(120000.0)
            assert draft.contract is not None
            assert draft.contract.contract_no_external == "T-001"
            assert len(draft.events) == 1
            assert len(draft.commitments) == 1
            assert len(draft.tasks) == 1
            assert len(draft.risk_signals) == 1
            assert len(draft.memory_items) == 1
            # min of 0.9, 0.85, 0.8 = 0.8
            assert draft.confidence_overall == pytest.approx(0.8)
            # No customer/contact rows in DB → no candidates.
            assert candidates.customer_candidates == []
            assert candidates.contact_candidates == [[]]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_merge_drafts_handles_missing_dimensions() -> None:
    """Identity-only draft should still produce a valid UnifiedDraft with
    None for commercial fields and empty ops lists."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            identity = IdentityDraft.model_validate(_identity_payload())

            draft, candidates = await merge_drafts(
                session=session,
                identity=identity,
                commercial=None,
                ops=None,
            )

            assert draft.customer is not None
            assert draft.order is None
            assert draft.contract is None
            assert draft.events == []
            assert draft.commitments == []
            assert draft.confidence_overall == pytest.approx(0.9)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_merge_drafts_flags_low_confidence_review_fields() -> None:
    """Customer name missing + low confidence_overall both surface in
    needs_review_fields."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            identity = IdentityDraft.model_validate(
                {
                    "customer": {"full_name": None, "short_name": None},
                    "contacts": [
                        {"name": None, "role": "other"},
                    ],
                    "field_provenance": [],
                    "confidence_overall": 0.4,
                    "parse_warnings": [],
                }
            )

            draft, _candidates = await merge_drafts(
                session=session,
                identity=identity,
                commercial=None,
                ops=None,
            )

            assert "customer.full_name" in draft.needs_review_fields
            assert "contacts[0].name" in draft.needs_review_fields
            assert "identity" in draft.needs_review_fields
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_merge_drafts_flags_unbalanced_milestones() -> None:
    """Payment milestones that don't sum to 1.0 surface as a review field."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            commercial = CommercialDraft.model_validate(
                {
                    "order": None,
                    "contract": {
                        "contract_no_external": "X-1",
                        "payment_milestones": [
                            {"name": "P1", "ratio": 0.5, "trigger_event": "contract_signed"},
                            {"name": "P2", "ratio": 0.3, "trigger_event": "on_acceptance"},
                        ],
                    },
                    "field_provenance": [],
                    "confidence_overall": 0.95,
                    "parse_warnings": [],
                }
            )
            draft, _ = await merge_drafts(
                session=session,
                identity=None,
                commercial=commercial,
                ops=None,
            )
            assert "contract.payment_milestones" in draft.needs_review_fields
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_merge_drafts_finds_existing_customer_candidate() -> None:
    """An existing Customer row with a similar name appears as a candidate."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(
                Customer(
                    full_name="测试客户有限公司",
                    short_name="测试",
                    address="上海",
                    tax_id=None,
                )
            )
            await session.commit()

            identity = IdentityDraft.model_validate(_identity_payload())
            _, candidates = await merge_drafts(
                session=session,
                identity=identity,
                commercial=None,
                ops=None,
            )
            assert len(candidates.customer_candidates) == 1
            assert candidates.customer_candidates[0].fields["full_name"] == "测试客户有限公司"
    finally:
        await engine.dispose()


# ---------- auto_ingest orchestrator -------------------------------------


def _stub_extractors(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session_counter: list[AsyncSession] | None = None,
    raise_on: str | None = None,
) -> None:
    """Replace the three extractor functions with stubs that return canned
    drafts. If ``session_counter`` is given, each call appends its received
    session to the list so we can assert per-extractor isolation. If
    ``raise_on`` matches an extractor name, that one raises mid-flight.
    """

    async def fake_identity(*, session, document_id, ocr_text, progress=None):
        if session_counter is not None:
            session_counter.append(session)
        if raise_on == "identity":
            raise RuntimeError("synthetic identity failure")
        return IdentityDraft.model_validate(_identity_payload())

    async def fake_commercial(*, session, document_id, ocr_text, progress=None):
        if session_counter is not None:
            session_counter.append(session)
        if raise_on == "commercial":
            raise RuntimeError("synthetic commercial failure")
        return CommercialDraft.model_validate(_commercial_payload())

    async def fake_ops(*, session, document_id, ocr_text, progress=None):
        if session_counter is not None:
            session_counter.append(session)
        if raise_on == "ops":
            raise RuntimeError("synthetic ops failure")
        return OpsDraft.model_validate(_ops_payload())

    monkeypatch.setitem(auto_module._EXTRACTOR_FUNCTIONS, "identity", fake_identity)
    monkeypatch.setitem(auto_module._EXTRACTOR_FUNCTIONS, "commercial", fake_commercial)
    monkeypatch.setitem(auto_module._EXTRACTOR_FUNCTIONS, "ops", fake_ops)


def _stub_planner_full_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make plan_extraction return a plan that activates all three dims."""

    async def fake_plan(*, session, document_id, ocr_text, modality, source_hint, progress=None):
        return IngestPlan(
            targets={"identity": 0.9, "commercial": 0.9, "ops": 0.9},
            extractors=[
                {"name": "identity", "confidence": 0.9},
                {"name": "commercial", "confidence": 0.9},
                {"name": "ops", "confidence": 0.9},
            ],
            reason="test fan-out",
            review_required=False,
        )

    monkeypatch.setattr(auto_module, "plan_extraction", fake_plan)


@pytest.mark.asyncio
async def test_auto_ingest_text_path_returns_draft_and_candidates(monkeypatch) -> None:
    """End-to-end: text input, full fan-out, mocked extractors → unified
    draft + match candidates + persisted Document row."""
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    _stub_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            text = "测试客户有限公司 王经理 13800000000 周五前发货 合同金额 12 万"
            result = await auto_ingest(
                session=session,
                text_content=text,
                source_hint="pasted_text",
                uploader="tester",
            )
            await session.commit()

            assert isinstance(result.document_id, UUID)
            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            assert result.draft.order is not None
            assert len(result.draft.events) == 1
            # Plan exposes all three dims.
            names = sorted(s.name for s in result.plan.extractors)
            assert names == ["commercial", "identity", "ops"]

            # Document row landed and carries the merged draft as raw_llm_response.
            doc = (
                await session.execute(select(Document).where(Document.id == result.document_id))
            ).scalar_one()
            assert doc.raw_llm_response is not None
            assert doc.review_status == DocumentReviewStatus.pending_review
            # The stored payload survived a round-trip.
            assert doc.raw_llm_response["customer"]["full_name"] == "测试客户有限公司"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_uses_separate_session_per_extractor(monkeypatch) -> None:
    """Each concurrent extractor must receive its own AsyncSession (call_claude
    writes the llm_calls table; concurrent writes on a shared session corrupt
    SQLAlchemy's identity map)."""
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    sessions_seen: list[AsyncSession] = []
    _stub_extractors(monkeypatch, session_counter=sessions_seen)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await auto_ingest(
                session=session,
                text_content="测试有限公司 王经理 13800000000 6 月底前付款",
                source_hint="pasted_text",
            )
            await session.commit()

            # Three extractors → three sessions, all distinct, none equal to
            # the orchestrator's main session.
            assert len(sessions_seen) == 3
            assert len({id(s) for s in sessions_seen}) == 3
            assert all(id(s) != id(session) for s in sessions_seen)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_extractor_failure_becomes_warning(monkeypatch) -> None:
    """If one extractor raises, the rest still run and the merged draft
    surfaces a warning rather than the request 500-ing."""
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    _stub_extractors(monkeypatch, raise_on="commercial")

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="测试有限公司 王经理 周五前发货",
                source_hint="pasted_text",
            )
            await session.commit()

            # Identity + ops drafts merged, commercial absent.
            assert result.draft.customer is not None
            assert result.draft.order is None
            assert result.draft.contract is None
            assert len(result.draft.events) == 1
            # Failure surfaced as a warning.
            assert any(
                "extractor 'commercial' failed" in w for w in result.draft.warnings
            )
    finally:
        await engine.dispose()


# ---------- commit_auto_extraction --------------------------------------


def _confirm_request_full() -> AutoConfirmRequest:
    return AutoConfirmRequest.model_validate(
        {
            "customer": {
                "mode": "new",
                "final": _identity_payload()["customer"],
            },
            "contacts": [
                {
                    "mode": "new",
                    "final": _identity_payload()["contacts"][0],
                }
            ],
            "order": _commercial_payload()["order"],
            "contract": _commercial_payload()["contract"],
            "events": _ops_payload()["events"],
            "commitments": _ops_payload()["commitments"],
            "tasks": _ops_payload()["tasks"],
            "risk_signals": _ops_payload()["risk_signals"],
            "memory_items": _ops_payload()["memory_items"],
            "field_provenance": [],
            "confidence_overall": 0.85,
            "parse_warnings": [],
        }
    )


@pytest.mark.asyncio
async def test_commit_auto_extraction_writes_all_tables() -> None:
    """A full draft persists customer + contacts + order + contract + the
    five ops tables, and stamps Document.review_status = confirmed."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            doc = Document(
                type=__import__("yinhu_brain.models", fromlist=["DocumentType"]).DocumentType.contract,
                file_url="/tmp/contract.pdf",
                original_filename="contract.pdf",
                file_sha256="0" * 64,
                file_size_bytes=123,
                ocr_text="测试客户有限公司 王经理 13800000000 合同金额 12 万",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.flush()

            request = _confirm_request_full()
            result = await commit_auto_extraction(
                session=session,
                document_id=doc.id,
                request=request,
            )
            await session.commit()

            assert result.customer_id is not None
            assert len(result.contact_ids) == 1
            assert result.order_id is not None
            assert result.contract_id is not None
            assert len(result.event_ids) == 1
            assert len(result.commitment_ids) == 1
            assert len(result.task_ids) == 1
            assert len(result.risk_signal_ids) == 1
            assert len(result.memory_item_ids) == 1

            customers = (await session.execute(select(Customer))).scalars().all()
            contacts = (await session.execute(select(Contact))).scalars().all()
            orders = (await session.execute(select(Order))).scalars().all()
            contracts = (await session.execute(select(Contract))).scalars().all()
            events = (await session.execute(select(CustomerEvent))).scalars().all()
            commitments = (await session.execute(select(CustomerCommitment))).scalars().all()
            tasks = (await session.execute(select(CustomerTask))).scalars().all()
            risks = (await session.execute(select(CustomerRiskSignal))).scalars().all()
            memories = (await session.execute(select(CustomerMemoryItem))).scalars().all()

            assert len(customers) == 1
            assert customers[0].full_name == "测试客户有限公司"
            assert len(contacts) == 1
            assert contacts[0].customer_id == customers[0].id
            assert len(orders) == 1
            assert len(contracts) == 1
            assert len(events) == 1
            assert events[0].customer_id == customers[0].id
            assert events[0].document_id == doc.id
            assert len(commitments) == 1
            assert len(tasks) == 1
            assert len(risks) == 1
            assert len(memories) == 1

            # Document was stamped.
            refreshed = (
                await session.execute(select(Document).where(Document.id == doc.id))
            ).scalar_one()
            assert refreshed.review_status == DocumentReviewStatus.confirmed
            assert refreshed.assigned_customer_id == customers[0].id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_commit_auto_extraction_requires_customer_when_ops_present() -> None:
    """Ops rows must attach to a customer; a draft with ops but no customer
    should reject rather than silently drop the rows."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yinhu_brain.models import DocumentType

            doc = Document(
                type=DocumentType.text_note,
                file_url="/tmp/note.txt",
                original_filename="note.txt",
                file_sha256="0" * 64,
                file_size_bytes=10,
                ocr_text="一些事件",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.flush()

            request = AutoConfirmRequest.model_validate(
                {
                    "customer": None,
                    "contacts": [],
                    "order": None,
                    "contract": None,
                    "events": _ops_payload()["events"],
                    "commitments": [],
                    "tasks": [],
                    "risk_signals": [],
                    "memory_items": [],
                    "field_provenance": [],
                    "confidence_overall": 0.6,
                    "parse_warnings": [],
                }
            )

            with pytest.raises(ValueError, match="customer is required"):
                await commit_auto_extraction(
                    session=session,
                    document_id=doc.id,
                    request=request,
                )
    finally:
        await engine.dispose()


# ---------- /api/ingest/auto endpoints ----------------------------------


def _build_app(engine):
    """Build a minimal FastAPI app wired to the auto endpoints + a fixed engine.

    We override ``get_session`` so the dependency yields against the in-memory
    SQLite engine rather than going through the platform middleware.
    """
    from fastapi import FastAPI

    from yinhu_brain.api.ingest import router
    from yinhu_brain.db import get_session

    async def _override_session():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = _override_session
    return app


@pytest.mark.asyncio
async def test_auto_endpoint_streams_ndjson(monkeypatch) -> None:
    """POST /api/ingest/auto returns NDJSON; final ``done`` line carries
    document_id + plan + draft + candidates."""
    from httpx import ASGITransport, AsyncClient

    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    _stub_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/ingest/auto",
                data={"text": "测试客户有限公司 王经理 13800000000", "source_hint": "pasted_text"},
            )
            assert resp.status_code == 200
            lines = [
                json.loads(line)
                for line in resp.text.split("\n")
                if line.strip()
            ]
            statuses = {l["status"] for l in lines}
            assert "progress" in statuses
            assert "done" in statuses
            done = next(l for l in lines if l["status"] == "done")
            assert "document_id" in done
            assert "plan" in done
            assert "draft" in done
            assert "candidates" in done
            assert done["draft"]["customer"]["full_name"] == "测试客户有限公司"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_endpoint_rejects_empty_input() -> None:
    """Neither file nor text → 400."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/ingest/auto", data={"source_hint": "file"})
            assert resp.status_code == 400
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_confirm_endpoint_writes_entities(monkeypatch) -> None:
    """POST /api/ingest/auto/{id}/confirm: persists the user-reviewed payload
    and returns created_entities."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yinhu_brain.models import DocumentType

            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/contract.pdf",
                original_filename="contract.pdf",
                file_sha256="0" * 64,
                file_size_bytes=123,
                ocr_text="测试客户有限公司",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.commit()
            doc_id = str(doc.id)

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = _confirm_request_full().model_dump(mode="json")
            resp = await client.post(
                f"/api/ingest/auto/{doc_id}/confirm",
                json=payload,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["document_id"] == doc_id
            ce = body["created_entities"]
            assert ce["customer_id"]
            assert len(ce["contact_ids"]) == 1
            assert ce["order_id"]
            assert ce["contract_id"]
            assert len(ce["event_ids"]) == 1

        # Reading from a fresh session confirms persistence survived the request.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1
            doc = (
                await session.execute(select(Document).where(Document.id == UUID(doc_id)))
            ).scalar_one()
            assert doc.review_status == DocumentReviewStatus.confirmed
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_cancel_endpoint_marks_ignored() -> None:
    """POST /api/ingest/auto/{id}/cancel: flips review_status to ignored."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yinhu_brain.models import DocumentType

            doc = Document(
                type=DocumentType.text_note,
                file_url="/tmp/note.txt",
                original_filename="note.txt",
                file_sha256="0" * 64,
                file_size_bytes=10,
                ocr_text="some text",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.commit()
            doc_id = str(doc.id)

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/ingest/auto/{doc_id}/cancel")
            assert resp.status_code == 200
            assert resp.json() == {"document_id": doc_id, "status": "ignored"}

        async with AsyncSession(engine, expire_on_commit=False) as session:
            doc = (
                await session.execute(select(Document).where(Document.id == UUID(doc_id)))
            ).scalar_one()
            assert doc.review_status == DocumentReviewStatus.ignored
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_cancel_endpoint_409_when_already_confirmed() -> None:
    """Cancelling a confirmed document → 409."""
    from httpx import ASGITransport, AsyncClient

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yinhu_brain.models import DocumentType

            doc = Document(
                type=DocumentType.text_note,
                file_url="/tmp/note.txt",
                original_filename="note.txt",
                file_sha256="0" * 64,
                file_size_bytes=10,
                ocr_text="some text",
                review_status=DocumentReviewStatus.confirmed,
            )
            session.add(doc)
            await session.commit()
            doc_id = str(doc.id)

        app = _build_app(engine)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/api/ingest/auto/{doc_id}/cancel")
            assert resp.status_code == 409
    finally:
        await engine.dispose()
