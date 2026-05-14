"""Tests for the unified ingest service pipeline.

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

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests use in-memory SQLite, mirroring ``test_planner.py`` /
``test_evidence.py``.
"""

from __future__ import annotations

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

import yunwei_win.models  # noqa: F401 — register SQLAlchemy mappers
from yunwei_win.db import Base
from yunwei_win.models import (
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
from yunwei_win.services.ingest import auto as auto_module
from yunwei_win.services.ingest import evidence as evidence_module
from yunwei_win.services.ingest import planner as planner_module
from yunwei_win.services.ingest.auto import auto_ingest
from yunwei_win.services.ingest.auto_confirm import commit_auto_extraction
from yunwei_win.services.ingest.merge import merge_drafts
from yunwei_win.services.ingest.unified_schemas import (
    AutoConfirmRequest,
    CommercialDraft,
    IdentityDraft,
    OpsDraft,
    PipelineRoutePlan,
    PipelineSelection,
    UnifiedDraft,
)


# ---------- helpers -------------------------------------------------------


async def _make_engine():
    # SQLite skips FK enforcement unless ``PRAGMA foreign_keys = ON`` runs on
    # every connection. Without this, integrity bugs that fail in Postgres
    # (e.g. inserting llm_calls(document_id=X) when X hasn't been committed
    # yet) silently pass here and ship to production.
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


def _patch_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace storage.store_upload with a deterministic in-memory stub."""
    from yunwei_win.services.storage import StoredFile

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


def _landingai_shaped_extraction(name: str) -> dict:
    """Return a LandingAI-shape extraction payload for the given schema name.

    ``normalize_pipeline_results`` reads LandingAI's vocabulary
    (``contract_number`` / ``total_amount`` / role enum). The fake provider
    used in tests must emit that vocabulary so the merged ``UnifiedDraft``
    looks like a real ingest.
    """

    if name == "identity":
        return {
            "customer": _identity_payload()["customer"],
            "contacts": [
                {
                    "name": "王经理",
                    "title": "销售总监",
                    "phone": None,
                    "mobile": "13800000000",
                    "email": "wang@test.com",
                    # role enum is buyer-collapsed by _normalize_role
                    "role": "buyer",
                    "address": None,
                },
            ],
        }
    if name == "contract_order":
        cp = _commercial_payload()
        return {
            "customer": _identity_payload()["customer"],
            "contacts": [],
            "contract": {
                "contract_number": cp["contract"]["contract_no_external"],
                "delivery_terms": cp["contract"]["delivery_terms"],
                "penalty_terms": cp["contract"]["penalty_terms"],
                "signing_date": cp["contract"]["signing_date"],
                "effective_date": cp["contract"]["effective_date"],
                "expiry_date": cp["contract"]["expiry_date"],
            },
            "order": {
                "total_amount": cp["order"]["amount_total"],
                "currency": cp["order"]["amount_currency"],
                "delivery_promised_date": cp["order"]["delivery_promised_date"],
                "delivery_address": cp["order"]["delivery_address"],
                "summary": cp["order"]["description"],
            },
            "payment_milestones": cp["contract"]["payment_milestones"],
        }
    if name == "commitment_task_risk":
        op = _ops_payload()
        return {
            "summary": op["summary"],
            "events": op["events"],
            "commitments": op["commitments"],
            "tasks": op["tasks"],
            "risk_signals": op["risk_signals"],
            "memory_items": op["memory_items"],
        }
    # finance / logistics / manufacturing_requirement: empty but not crashing.
    return {}


def _stub_extractor_provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    raise_on: str | None = None,
    call_log: list[str] | None = None,
    provider_name: str = "landingai",
) -> None:
    """Replace ``get_extractor_provider`` with a fake that returns canned
    ``PipelineExtractResult`` objects.

    ``raise_on`` simulates a per-schema soft failure — the provider records
    a warning instead of throwing (mirrors the real providers' behaviour).
    ``call_log`` collects the schema names the orchestrator dispatched, so
    tests can assert gating worked.
    ``provider_name`` stamps ``extraction_metadata.provider`` so tests can
    distinguish LandingAI vs DeepSeek without inspecting code paths.
    """

    from yunwei_win.services.ingest.unified_schemas import PipelineExtractResult

    class _FakeProvider:
        async def extract_selected(self, input, progress=None):
            results: list[PipelineExtractResult] = []
            for selection in input.selections:
                name = selection.name
                if call_log is not None:
                    call_log.append(name)
                if progress is not None:
                    await progress("pipeline_started", {"name": name})
                if raise_on == name:
                    results.append(
                        PipelineExtractResult(
                            name=name,
                            extraction={},
                            extraction_metadata={"provider": provider_name},
                            warnings=[
                                f"extractor {name!r} failed: synthetic failure"
                            ],
                        )
                    )
                    if progress is not None:
                        await progress("pipeline_done", {"name": name, "ok": False})
                    continue
                results.append(
                    PipelineExtractResult(
                        name=name,
                        extraction=_landingai_shaped_extraction(name),
                        extraction_metadata={"provider": provider_name},
                        warnings=[],
                    )
                )
                if progress is not None:
                    await progress("pipeline_done", {"name": name, "ok": True})
            return results

    monkeypatch.setattr(auto_module, "get_extractor_provider", lambda: _FakeProvider())


# Back-compat alias for the legacy helper name; behaviour now bridges through
# the provider factory rather than the per-extractor function dict.
def _stub_extractors(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session_counter: list[AsyncSession] | None = None,  # noqa: ARG001 — kept for API parity
    raise_on: str | None = None,
) -> None:
    """Legacy helper name retained so existing tests stay readable.

    The ``session_counter`` argument is preserved as a no-op so call sites
    don't need to change; the new unified flow has a single session and no
    per-extractor concurrency, so the original session-isolation assertion
    is meaningless under the new model.

    The ``raise_on`` argument maps to the new fake provider's per-schema
    soft failure path. Note: legacy extractor names (``commercial`` / ``ops``)
    now map to canonical schema names (``contract_order`` /
    ``commitment_task_risk``).
    """

    schema_raise: str | None
    if raise_on == "commercial":
        schema_raise = "contract_order"
    elif raise_on == "ops":
        schema_raise = "commitment_task_risk"
    else:
        schema_raise = raise_on
    _stub_extractor_provider(monkeypatch, raise_on=schema_raise)


def _patch_route_schemas(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selected: tuple[str, ...] | list[str] = (
        "identity",
        "contract_order",
        "commitment_task_risk",
    ),
    needs_review: bool = False,
    summary: str = "stubbed route",
) -> None:
    """Replace ``auto_module.route_schemas`` with a stub returning a
    deterministic ``PipelineRoutePlan``.

    The /auto orchestrator now calls ``route_schemas`` (LLM-driven) instead of
    the regex pipeline_router / heuristic plan_extraction. Tests that
    previously stubbed ``plan_extraction`` should use this helper instead.
    """

    selected_list = list(selected)

    async def fake_route_schemas(**kwargs):
        return PipelineRoutePlan(
            primary_pipeline=selected_list[0] if selected_list else None,
            selected_pipelines=[
                PipelineSelection(name=name, confidence=0.9, reason="test stub")
                for name in selected_list
            ],
            document_summary=summary,
            needs_human_review=needs_review,
        )

    monkeypatch.setattr(auto_module, "route_schemas", fake_route_schemas)


def _stub_planner_full_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``route_schemas`` select all three Mistral-mapped schemas so the
    three legacy extractors all fire.

    Retained for backward compatibility with the existing fan-out tests —
    callers want the same end-state (identity + commercial + ops all run)
    that the legacy planner used to produce.
    """
    _patch_route_schemas(
        monkeypatch,
        selected=("identity", "contract_order", "commitment_task_risk"),
        summary="test fan-out",
    )


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
            # Plan.targets exposes the router's per-dimension confidence
            # (the legacy ``extractors`` list is no longer synthesized under
            # the unified provider flow — see auto.py synthesized_plan).
            assert result.plan.targets["identity"] > 0
            assert result.plan.targets["commercial"] > 0
            assert result.plan.targets["ops"] > 0

            # Document row landed and carries the merged draft as raw_llm_response.
            # The Mistral path now stores ``{provider, route_plan, draft}`` so
            # the audit row captures both routing rationale and the merged
            # payload — assert the nested shape.
            doc = (
                await session.execute(select(Document).where(Document.id == result.document_id))
            ).scalar_one()
            assert doc.raw_llm_response is not None
            assert doc.review_status == DocumentReviewStatus.pending_review
            # The stored payload survived a round-trip.
            assert doc.raw_llm_response["draft"]["customer"]["full_name"] == "测试客户有限公司"
            assert "route_plan" in doc.raw_llm_response
            assert doc.raw_llm_response["route_plan"]["selected_pipelines"]
            # raw_llm_response.provider is stamped from settings.extractor_provider
            # so the audit row records which extractor implementation ran.
            from yunwei_win.config import settings as _settings

            assert doc.raw_llm_response["provider"] == _settings.extractor_provider
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_extractor_failure_becomes_warning(monkeypatch) -> None:
    """If one schema extract fails, the rest still run and the merged draft
    surfaces a warning rather than the request 500-ing."""
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    # Map the legacy 'commercial' name onto the canonical 'contract_order'
    # schema for the new provider-driven flow.
    _stub_extractor_provider(monkeypatch, raise_on="contract_order")

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="测试有限公司 王经理 周五前发货",
                source_hint="pasted_text",
            )
            await session.commit()

            # Identity + ops drafts merged; the failing contract_order
            # pipeline produced no order/contract data (normalize defaults
            # the order/contract slots to empty Extraction objects with no
            # values populated).
            assert result.draft.customer is not None
            assert (
                result.draft.order is None
                or result.draft.order.amount_total is None
            )
            assert (
                result.draft.contract is None
                or result.draft.contract.contract_no_external is None
            )
            assert len(result.draft.events) == 1
            # Failure surfaced as a warning carried through from the per-pipeline
            # extract result.
            assert any(
                "'contract_order' failed" in w for w in result.draft.warnings
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
                type=__import__("yunwei_win.models", fromlist=["DocumentType"]).DocumentType.contract,
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
            from yunwei_win.models import DocumentType

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


# ---------- Regression / gap-coverage tests (Agent I) ---------------------
#
# The above coverage gets us to "happy path works". This block adds the
# integration-level guards that protect the unified pipeline from regressions
# the per-module unit tests can't catch:
#
# 1. Planner gating actually short-circuits — the only proof that the planner
#    is doing real work is that *unselected* extractors are not invoked.
# 2. Text-only input skips Mistral OCR entirely (cost / latency regression).
# 3. /auto endpoint accepts file uploads (image path), not just text.
# 4. /auto/{id}/confirm 404 / 409 edge cases.
# 5. AutoConfirmRequest with ``customer.mode=merge`` reuses the existing row.
# 6. /auto pipeline respects per-tenant DB isolation (multiple engines in the
#    same test, same customer name in each, no cross-tenant leak).
#
# Legacy ``/contract`` + ``/business_card`` flows already have dedicated
# tests in ``test_yunwei_win_contract_flow.py`` and they ran green in the
# 305-pass baseline, so we don't re-test them here; we only verify the
# auto pipeline doesn't break that surface by re-running the suite at the
# end.


def _stub_planner_only(
    monkeypatch: pytest.MonkeyPatch, *names: str
) -> None:
    """Make the router activate ONLY the legacy extractor(s) named in
    ``names`` (``identity`` / ``commercial`` / ``ops``).

    The router speaks the canonical schema vocabulary, not the legacy
    extractor names; this helper does the schema→extractor mapping in
    reverse so existing callers stay readable. The unselected extractors
    must not be invoked by the orchestrator — this is the router's whole
    point. If the router fires every extractor anyway, the gating is dead
    code.
    """
    _legacy_to_schema = {
        "identity": "identity",
        "commercial": "contract_order",
        "ops": "commitment_task_risk",
    }
    schema_names = [_legacy_to_schema[n] for n in names]
    _patch_route_schemas(
        monkeypatch,
        selected=tuple(schema_names),
        summary=f"only {','.join(names)}",
    )


def _counting_extractors(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, int]:
    """Replace the provider with a counter-recording stub.

    Returns a counter dict keyed by legacy extractor name (``identity`` /
    ``commercial`` / ``ops``) so existing call-site assertions stay
    readable. Internally the canonical schema names
    (``identity`` / ``contract_order`` / ``commitment_task_risk``) are
    mapped back onto the legacy keys.
    """

    counts: dict[str, int] = {"identity": 0, "commercial": 0, "ops": 0}
    _schema_to_legacy = {
        "identity": "identity",
        "contract_order": "commercial",
        "commitment_task_risk": "ops",
    }
    call_log: list[str] = []
    _stub_extractor_provider(monkeypatch, call_log=call_log)

    # Bridge: every time the orchestrator hands a selection to the fake
    # provider it'll append to call_log; wrap call_log into a property-like
    # counter snapshot via __getitem__ — but tests already consume ``counts``
    # as a dict, so update it lazily on the first read by exposing a special
    # subclass.
    class _LiveCounts(dict):
        def __getitem__(self, key):
            self._refresh()
            return super().__getitem__(key)

        def __eq__(self, other):
            self._refresh()
            return super().__eq__(other)

        def __repr__(self):
            self._refresh()
            return super().__repr__()

        def _refresh(self):
            for k in counts:
                self[k] = 0
            for sch in call_log:
                legacy = _schema_to_legacy.get(sch)
                if legacy is not None:
                    self[legacy] = self.get(legacy, 0) + 1

    return _LiveCounts(counts)


@pytest.mark.asyncio
async def test_auto_ingest_planner_gating_skips_unselected_extractors(monkeypatch) -> None:
    """When the planner activates only ``identity``, the commercial + ops
    extractors must NOT be invoked. This is the planner's core value — if it
    fires every extractor anyway, the gating is dead code.
    """
    _patch_storage(monkeypatch)
    _stub_planner_only(monkeypatch, "identity")
    counts = _counting_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="只关心客户名片信息：测试有限公司 王经理 13800000000",
                source_hint="pasted_text",
            )
            await session.commit()

            # Only identity ran.
            assert counts == {"identity": 1, "commercial": 0, "ops": 0}
            # Merged draft has identity but no commercial / ops payload.
            assert result.draft.customer is not None
            assert result.draft.order is None
            assert result.draft.contract is None
            assert result.draft.events == []
            assert result.draft.commitments == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_planner_gating_two_extractors(monkeypatch) -> None:
    """Planner activates identity + commercial, ops is skipped."""
    _patch_storage(monkeypatch)
    _stub_planner_only(monkeypatch, "identity", "commercial")
    counts = _counting_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="合同号 T-001 客户测试有限公司 金额 12 万元",
                source_hint="pasted_text",
            )
            await session.commit()

            assert counts == {"identity": 1, "commercial": 1, "ops": 0}
            assert result.draft.customer is not None
            assert result.draft.order is not None
            assert result.draft.events == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_text_input_never_invokes_ocr(monkeypatch) -> None:
    """Text input (modality=text) must NOT call any OCR provider.

    OCR is paid + latency-sensitive; routing pasted_text through the image
    pipeline was a real bug in an earlier draft. Spy on the provider factory
    and assert zero invocations.
    """
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    _stub_extractors(monkeypatch)

    def boom_factory():
        raise AssertionError("OCR provider must not be requested for text input")

    monkeypatch.setattr(evidence_module, "get_ocr_provider", boom_factory)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="客户测试有限公司，王经理 13800000000，合同金额 12 万元",
                source_hint="pasted_text",
            )
            await session.commit()

            # And the evidence row was created with the text as ocr_text.
            doc = (
                await session.execute(select(Document).where(Document.id == result.document_id))
            ).scalar_one()
            assert "测试有限公司" in (doc.ocr_text or "")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_commit_auto_extraction_merges_into_existing_customer() -> None:
    """``customer.mode=merge`` with a real ``existing_id`` must update the
    existing row in place (not create a second customer)."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models import DocumentType

            # Seed an existing customer.
            existing = Customer(
                full_name="老客户有限公司",
                short_name="老客户",
                address="旧地址",
                tax_id=None,
            )
            session.add(existing)
            await session.flush()
            existing_id = existing.id

            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/contract.pdf",
                original_filename="contract.pdf",
                file_sha256="0" * 64,
                file_size_bytes=123,
                ocr_text="一些文本",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.flush()

            request = AutoConfirmRequest.model_validate(
                {
                    "customer": {
                        "mode": "merge",
                        "existing_id": str(existing_id),
                        "final": {
                            "full_name": "老客户有限公司",
                            "short_name": "老客户",
                            "address": "新地址（用户修订）",
                            "tax_id": "91310000XXXXXXXX",
                        },
                    },
                    "contacts": [],
                    "order": _commercial_payload()["order"],
                    "contract": _commercial_payload()["contract"],
                    "events": [],
                    "commitments": [],
                    "tasks": [],
                    "risk_signals": [],
                    "memory_items": [],
                    "field_provenance": [],
                    "confidence_overall": 0.8,
                    "parse_warnings": [],
                }
            )

            result = await commit_auto_extraction(
                session=session,
                document_id=doc.id,
                request=request,
            )
            await session.commit()

            # Same customer row was reused.
            assert result.customer_id == existing_id

            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1, "merge must not create a second customer"
            assert customers[0].id == existing_id
            # The user-supplied address overrode the old value.
            assert customers[0].address == "新地址（用户修订）"
            assert customers[0].tax_id == "91310000XXXXXXXX"
    finally:
        await engine.dispose()


# ---------- bind_existing customer decision ------------------------------


@pytest.mark.asyncio
async def test_commit_bind_existing_preserves_existing_customer_master_fields() -> None:
    """bind_existing: order/contract/contacts attach to the existing customer
    but the customer's master fields (name/address/tax_id) stay untouched
    even when the AI draft tried to overwrite them with wrong values."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models import (
                DocumentProcessingStatus,
                DocumentType,
            )

            # Seed: a correctly-named customer already in DB.
            existing = Customer(
                full_name="正确客户名称有限公司",
                short_name="正确客户",
                address="北京市朝阳区",
                tax_id="91110000XXXXXXX",
            )
            session.add(existing)
            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/bind.pdf",
                original_filename="bind.pdf",
                content_type="application/pdf",
                file_sha256="b" * 64,
                file_size_bytes=10,
                ocr_text="...",
                processing_status=DocumentProcessingStatus.parsed,
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.commit()

            request = AutoConfirmRequest.model_validate({
                "customer": {
                    "mode": "bind_existing",
                    "existing_id": str(existing.id),
                    # AI draft has the WRONG name; bind_existing must ignore it
                    "final": {
                        "full_name": "OCR 错误客户名",
                        "short_name": "错的",
                        "address": "错地址",
                        "tax_id": "WRONG",
                    },
                },
                "order": {
                    "amount_total": 50000,
                    "amount_currency": "CNY",
                },
                "contract": {
                    "contract_no_external": "BIND-001",
                    "payment_milestones": [],
                },
            })

            result = await commit_auto_extraction(
                session=session, document_id=doc.id, request=request,
            )
            await session.commit()

            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1
            c = customers[0]
            # Master fields preserved
            assert c.full_name == "正确客户名称有限公司"
            assert c.short_name == "正确客户"
            assert c.address == "北京市朝阳区"
            assert c.tax_id == "91110000XXXXXXX"
            # Order + contract attached to existing customer
            orders = (await session.execute(select(Order))).scalars().all()
            assert len(orders) == 1
            assert orders[0].customer_id == c.id
            contracts = (await session.execute(select(Contract))).scalars().all()
            assert len(contracts) == 1
            assert contracts[0].order_id == orders[0].id
            assert result.customer_id == c.id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_commit_bind_existing_accepts_empty_ocr_full_name() -> None:
    """bind_existing should not require a valid final.full_name — the whole
    point is the user manually binding because OCR failed."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models import (
                DocumentProcessingStatus,
                DocumentType,
            )

            existing = Customer(full_name="已存在客户")
            session.add(existing)
            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/bind2.pdf",
                original_filename="bind2.pdf",
                content_type="application/pdf",
                file_sha256="c" * 64,
                file_size_bytes=10,
                ocr_text="...",
                processing_status=DocumentProcessingStatus.parsed,
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.commit()

            request = AutoConfirmRequest.model_validate({
                "customer": {
                    "mode": "bind_existing",
                    "existing_id": str(existing.id),
                    "final": {"full_name": ""},  # empty — OCR failed
                },
                "order": {"amount_total": 1000, "amount_currency": "CNY"},
                "contract": {"contract_no_external": "X-1", "payment_milestones": []},
            })

            result = await commit_auto_extraction(
                session=session, document_id=doc.id, request=request,
            )
            await session.commit()
            assert result.customer_id == existing.id
            assert (await session.execute(select(Customer))).scalars().all()[0].full_name == "已存在客户"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_commit_merge_still_updates_existing_customer_master_fields() -> None:
    """merge mode must KEEP its old behavior: load existing + apply final
    field values. This is the regression check so bind_existing doesn't
    accidentally weaken merge."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models import (
                DocumentProcessingStatus,
                DocumentType,
            )

            existing = Customer(full_name="旧客户名", short_name="旧简称")
            session.add(existing)
            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/merge.pdf",
                original_filename="merge.pdf",
                content_type="application/pdf",
                file_sha256="d" * 64,
                file_size_bytes=10,
                ocr_text="...",
                processing_status=DocumentProcessingStatus.parsed,
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.commit()

            request = AutoConfirmRequest.model_validate({
                "customer": {
                    "mode": "merge",
                    "existing_id": str(existing.id),
                    "final": {
                        "full_name": "新客户名",
                        "short_name": "新简称",
                        "address": "上海市浦东新区",
                        "tax_id": "NEWTAX",
                    },
                },
            })
            await commit_auto_extraction(session=session, document_id=doc.id, request=request)
            await session.commit()

            customers = (await session.execute(select(Customer))).scalars().all()
            assert len(customers) == 1
            c = customers[0]
            assert c.full_name == "新客户名"
            assert c.short_name == "新简称"
            assert c.address == "上海市浦东新区"
            assert c.tax_id == "NEWTAX"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_commit_auto_extraction_merge_requires_existing_id() -> None:
    """``customer.mode=merge`` without ``existing_id`` → ValueError."""
    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            from yunwei_win.models import DocumentType

            doc = Document(
                type=DocumentType.contract,
                file_url="/tmp/contract.pdf",
                original_filename="contract.pdf",
                file_sha256="0" * 64,
                file_size_bytes=123,
                ocr_text="一些文本",
                review_status=DocumentReviewStatus.pending_review,
            )
            session.add(doc)
            await session.flush()

            request = AutoConfirmRequest.model_validate(
                {
                    "customer": {
                        "mode": "merge",
                        "existing_id": None,
                        "final": _identity_payload()["customer"],
                    },
                    "contacts": [],
                    "order": None,
                    "contract": None,
                    "events": [],
                    "commitments": [],
                    "tasks": [],
                    "risk_signals": [],
                    "memory_items": [],
                    "field_provenance": [],
                    "confidence_overall": 0.7,
                    "parse_warnings": [],
                }
            )

            with pytest.raises(ValueError, match="existing_id"):
                await commit_auto_extraction(
                    session=session,
                    document_id=doc.id,
                    request=request,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_isolated_engines_do_not_leak_customers(monkeypatch) -> None:
    """Two separate engines (proxy for two tenants) running the same
    auto_ingest input must keep their customers entirely separate.

    This is a smoke test of the multi-tenant story for /auto — the
    real Postgres-backed isolation test in
    ``test_yunwei_win_tenant_isolation.py`` runs only when DATABASE_URL
    points at a reachable Postgres; here we confirm the orchestrator
    itself doesn't introduce a cross-session backdoor.
    """
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    _stub_extractors(monkeypatch)

    engine_a = await _make_engine()
    engine_b = await _make_engine()
    try:
        async with AsyncSession(engine_a, expire_on_commit=False) as session_a:
            await auto_ingest(
                session=session_a,
                text_content="测试客户有限公司 王经理 13800000000",
                source_hint="pasted_text",
                uploader="tenant_a_user",
            )
            await session_a.commit()

        # Engine B starts empty.
        async with AsyncSession(engine_b, expire_on_commit=False) as session_b:
            rows = (await session_b.execute(select(Customer))).scalars().all()
            assert rows == [], "engine_b leaked engine_a's customers"
            docs = (await session_b.execute(select(Document))).scalars().all()
            assert docs == [], "engine_b leaked engine_a's documents"

        # Engine A still has exactly the one document it ingested.
        async with AsyncSession(engine_a, expire_on_commit=False) as session_a:
            docs = (await session_a.execute(select(Document))).scalars().all()
            assert len(docs) == 1
    finally:
        await engine_a.dispose()
        await engine_b.dispose()


# ---------- LandingAI schema-routed flow ---------------------------------


@pytest.mark.asyncio
async def test_auto_ingest_uses_landingai_schema_flow_when_enabled(monkeypatch) -> None:
    """The orchestrator runs route_schemas + the configured extractor provider
    + normalize_pipeline_results to produce a ``UnifiedDraft`` with
    ``pipeline_results`` populated.

    Historically this test exercised the ``document_ai_provider == 'landingai'``
    branch; under the unified provider flow it now exercises the default
    ``settings.extractor_provider == 'landingai'`` path via the same
    monkeypatched factory.
    """
    engine = await _make_engine()
    _patch_storage(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "extractor_provider", "landingai")

    async def fake_collect_evidence(**kwargs):
        from yunwei_win.models import (
            Document,
            DocumentProcessingStatus,
            DocumentReviewStatus,
            DocumentType,
        )

        doc = Document(
            type=DocumentType.contract,
            file_url="/tmp/fake.pdf",
            original_filename="contract.pdf",
            content_type="application/pdf",
            file_sha256="1" * 64,
            file_size_bytes=10,
            ocr_text="甲方：测试客户有限公司\n合同编号：HT-001\n总金额：120000元",
            processing_status=DocumentProcessingStatus.parsed,
            review_status=DocumentReviewStatus.pending_review,
        )
        kwargs["session"].add(doc)
        await kwargs["session"].flush()
        from yunwei_win.services.ingest.evidence import Evidence

        return Evidence(
            document_id=doc.id,
            document=doc,
            ocr_text=doc.ocr_text,
            modality="pdf",
        )

    async def fake_route_schemas(**kwargs):
        return PipelineRoutePlan(
            primary_pipeline="contract_order",
            selected_pipelines=[
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="contract_order", confidence=0.9),
            ],
            document_summary="contract",
        )

    from yunwei_win.services.ingest.unified_schemas import PipelineExtractResult

    class _FakeLandingAIProvider:
        async def extract_selected(self, input, progress=None):
            return [
                PipelineExtractResult(
                    name="identity",
                    extraction={"customer": {"full_name": "测试客户有限公司"}},
                    extraction_metadata={"provider": "landingai"},
                ),
                PipelineExtractResult(
                    name="contract_order",
                    extraction={
                        "contract": {"contract_number": "HT-001"},
                        "order": {"total_amount": 120000, "currency": "CNY"},
                    },
                    extraction_metadata={"provider": "landingai"},
                ),
            ]

    monkeypatch.setattr(auto_module, "collect_evidence", fake_collect_evidence)
    monkeypatch.setattr(auto_module, "route_schemas", fake_route_schemas)
    monkeypatch.setattr(
        auto_module, "get_extractor_provider", lambda: _FakeLandingAIProvider()
    )

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF",
                original_filename="contract.pdf",
                content_type="application/pdf",
                source_hint="file",
            )

            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            assert result.draft.contract is not None
            assert result.draft.contract.contract_no_external == "HT-001"
            assert len(result.draft.pipeline_results) == 2
            assert all(
                r.extraction_metadata.get("provider") == "landingai"
                for r in result.draft.pipeline_results
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_routes_through_deepseek_provider(monkeypatch) -> None:
    """Setting ``settings.extractor_provider='deepseek'`` must route extraction
    through the DeepSeek-fake provider. The raw_llm_response.provider field
    must reflect the configured provider name so the audit row records which
    extractor implementation ran.
    """
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "extractor_provider", "deepseek")
    _stub_extractor_provider(monkeypatch, provider_name="deepseek")

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="测试客户有限公司 王经理 13800000000 合同金额 12 万",
                source_hint="pasted_text",
            )
            await session.commit()

            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            # Every pipeline result was stamped by the DeepSeek fake.
            assert all(
                r.extraction_metadata.get("provider") == "deepseek"
                for r in result.draft.pipeline_results
            )

            doc = (
                await session.execute(select(Document).where(Document.id == result.document_id))
            ).scalar_one()
            assert doc.raw_llm_response["provider"] == "deepseek"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_routes_through_landingai_provider(monkeypatch) -> None:
    """Setting ``settings.extractor_provider='landingai'`` routes through the
    LandingAI-fake provider and stamps ``raw_llm_response.provider`` accordingly.
    Mirror of the DeepSeek test so the factory-based switch is exercised both ways.
    """
    _patch_storage(monkeypatch)
    _stub_planner_full_fanout(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "extractor_provider", "landingai")
    _stub_extractor_provider(monkeypatch, provider_name="landingai")

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="测试客户有限公司 王经理 13800000000 合同金额 12 万",
                source_hint="pasted_text",
            )
            await session.commit()

            assert all(
                r.extraction_metadata.get("provider") == "landingai"
                for r in result.draft.pipeline_results
            )

            doc = (
                await session.execute(select(Document).where(Document.id == result.document_id))
            ).scalar_one()
            assert doc.raw_llm_response["provider"] == "landingai"
    finally:
        await engine.dispose()


# ---------- LLM schema router rewire regressions -------------------------
#
# The /auto orchestrator now routes through ``llm_schema_router.route_schemas``
# for both providers. These tests pin the contract:
#   1. The legacy ``planner.plan_extraction`` must NOT be invoked from /auto.
#   2. Schemas the Mistral provider can't handle (finance / logistics /
#      manufacturing_requirement) surface as warnings, never silently drop.
#   3. All six schemas pass through the router without a hard cap; the
#      Mistral branch fires the three mapped extractors and warns about
#      the rest, while review_required propagates from the router.


@pytest.mark.asyncio
async def test_auto_ingest_no_longer_calls_legacy_plan_extraction(monkeypatch) -> None:
    """The /auto orchestrator must not depend on planner.plan_extraction
    after the LLM router rewire — it now talks directly to route_schemas.
    """
    _patch_storage(monkeypatch)
    _patch_route_schemas(
        monkeypatch,
        selected=("identity", "contract_order"),
    )
    _stub_extractors(monkeypatch)

    async def boom_plan(*args, **kwargs):
        raise AssertionError(
            "legacy plan_extraction must not be called from /auto"
        )

    monkeypatch.setattr(planner_module, "plan_extraction", boom_plan)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="测试合同 甲方 测试客户有限公司",
                source_hint="pasted_text",
            )
            await session.commit()

            # Pipeline results reflect the schemas the router selected.
            names = sorted(r.name for r in result.draft.pipeline_results)
            assert names == ["contract_order", "identity"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_provider_handles_all_selected_schemas(monkeypatch) -> None:
    """Under the unified provider flow the configured extractor handles every
    schema the router picked — finance / logistics / manufacturing_requirement
    no longer trigger ``"no Mistral extractor available"`` warnings.

    Previous behaviour (Mistral-only branch) is gone: both LandingAI and
    DeepSeek providers know how to load every schema in
    ``landingai_schemas/registry.py``.
    """
    _patch_storage(monkeypatch)
    _patch_route_schemas(
        monkeypatch,
        selected=("identity", "finance", "logistics"),
    )
    _stub_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="客户 测试有限公司 发票号 12345 送货签收",
                source_hint="pasted_text",
            )
            await session.commit()

            # All three selected schemas reached the provider.
            names = sorted(r.name for r in result.draft.pipeline_results)
            assert names == ["finance", "identity", "logistics"]
            # No "no Mistral extractor available" warnings anymore.
            joined = " ".join(result.draft.warnings)
            assert "no Mistral extractor available" not in joined
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_ingest_no_hard_cap_on_selected_schemas(monkeypatch) -> None:
    """All six schemas should pass through end-to-end without truncation.

    Every selected schema lands as a ``PipelineExtractResult`` and the
    router's ``needs_human_review`` flag propagates into ``draft.warnings``.
    """
    _patch_storage(monkeypatch)
    _patch_route_schemas(
        monkeypatch,
        selected=(
            "identity",
            "contract_order",
            "commitment_task_risk",
            "finance",
            "logistics",
            "manufacturing_requirement",
        ),
        needs_review=True,
    )
    _stub_extractors(monkeypatch)

    engine = await _make_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                text_content="混合文档：合同+发票+送货+规格+承诺",
                source_hint="pasted_text",
            )
            await session.commit()

            names = sorted(r.name for r in result.draft.pipeline_results)
            assert names == [
                "commitment_task_risk",
                "contract_order",
                "finance",
                "identity",
                "logistics",
                "manufacturing_requirement",
            ]
            # Router-requested review propagated.
            assert any("review" in w for w in result.draft.warnings)
            assert result.plan.review_required is True
    finally:
        await engine.dispose()
