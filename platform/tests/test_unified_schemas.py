"""Schema-only tests for the unified ingest contracts.

Pure Pydantic round-trip / instantiation checks — no DB, no LLM. The
project-level autouse fixture truncates Postgres + flushes Redis, which we
don't need here, so we override it with a no-op at module scope.
"""

from __future__ import annotations

import pytest

# Override the project-level autouse fixture for this module so the tests
# don't require a running Postgres / Redis just to exercise pydantic models.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yinhu_brain.services.ingest.customer_memory_schema import (
    CommitmentDirectionEx,
    CustomerEventTypeEx,
    ExtractedCommitment,
    ExtractedEvent,
    ExtractedMemoryItem,
    ExtractedRiskSignal,
    ExtractedTask,
    MemoryKindEx,
    RiskKindEx,
    RiskSeverityEx,
    TaskPriorityEx,
)
from yinhu_brain.services.ingest.schemas import (
    ContactDecision,
    ContactExtraction,
    ContactRoleEx,
    ContractExtraction,
    CustomerDecision,
    CustomerExtraction,
    FieldProvenanceEntry,
    OrderExtraction,
    PaymentMilestone,
)
from yinhu_brain.services.ingest.unified_schemas import (
    AutoConfirmRequest,
    CommercialDraft,
    ExtractorSelection,
    IdentityDraft,
    IngestPlan,
    OpsDraft,
    UnifiedDraft,
)


# ---------- empty instantiation ------------------------------------------

def test_ingest_plan_empty_defaults():
    plan = IngestPlan()
    assert plan.targets == {}
    assert plan.extractors == []
    assert plan.reason == ""
    assert plan.review_required is False


def test_extractor_selection_basic():
    sel = ExtractorSelection(name="identity", confidence=0.9)
    assert sel.name == "identity"
    assert sel.confidence == 0.9


def test_extractor_selection_rejects_unknown_name():
    with pytest.raises(Exception):
        ExtractorSelection(name="bogus", confidence=0.5)


def test_extractor_selection_clamps_confidence_range():
    with pytest.raises(Exception):
        ExtractorSelection(name="ops", confidence=1.5)


def test_identity_draft_empty_defaults():
    d = IdentityDraft()
    assert d.customer is None
    assert d.contacts == []
    assert d.field_provenance == []
    assert d.confidence_overall == 0.5
    assert d.parse_warnings == []


def test_commercial_draft_empty_defaults():
    d = CommercialDraft()
    assert d.order is None
    assert d.contract is None
    assert d.field_provenance == []
    assert d.confidence_overall == 0.5
    assert d.parse_warnings == []


def test_ops_draft_empty_defaults():
    d = OpsDraft()
    assert d.summary == ""
    assert d.events == []
    assert d.commitments == []
    assert d.tasks == []
    assert d.risk_signals == []
    assert d.memory_items == []


def test_unified_draft_empty_defaults():
    u = UnifiedDraft()
    assert u.customer is None
    assert u.contacts == []
    assert u.order is None
    assert u.contract is None
    assert u.events == []
    assert u.summary == ""
    assert u.needs_review_fields == []
    assert u.warnings == []


def test_auto_confirm_request_empty_defaults():
    req = AutoConfirmRequest()
    assert req.customer is None
    assert req.contacts == []
    assert req.order is None
    assert req.contract is None


# ---------- realistic instantiation --------------------------------------

def _identity_draft_sample() -> IdentityDraft:
    return IdentityDraft(
        customer=CustomerExtraction(
            full_name="测试客户有限公司",
            short_name="测试客户",
            address="深圳市南山区",
            tax_id="91440300MA5XXXXXX",
        ),
        contacts=[
            ContactExtraction(
                name="张三",
                title="采购经理",
                phone="0755-12345678",
                mobile="13800138000",
                email="zs@example.com",
                role=ContactRoleEx.buyer,
            ),
        ],
        field_provenance=[
            FieldProvenanceEntry(
                path="customer.full_name",
                source_page=1,
                source_excerpt="甲方：测试客户有限公司",
            ),
        ],
        confidence_overall=0.82,
        parse_warnings=[],
    )


def _commercial_draft_sample() -> CommercialDraft:
    return CommercialDraft(
        order=OrderExtraction(
            amount_total="100,000.00",
            amount_currency="CNY",
            delivery_promised_date="2026-06-30",
            description="设备 + 售后",
        ),
        contract=ContractExtraction(
            contract_no_external="HT-2026-001",
            payment_milestones=[],
            signing_date="2026年5月10日",
        ),
        field_provenance=[
            FieldProvenanceEntry(path="order.amount_total", source_page=2),
        ],
        confidence_overall=0.74,
    )


def _ops_draft_sample() -> OpsDraft:
    return OpsDraft(
        summary="客户预计 6 月底交付",
        events=[
            ExtractedEvent(
                title="合同签订",
                event_type=CustomerEventTypeEx.contract_signed,
                description="主合同签订",
                confidence=0.9,
            ),
        ],
        commitments=[
            ExtractedCommitment(
                summary="6/30 前交付",
                direction=CommitmentDirectionEx.we_to_customer,
                due_date="2026-06-30",
            ),
        ],
        tasks=[
            ExtractedTask(
                title="排产",
                assignee="生产部",
                priority=TaskPriorityEx.high,
                due_date="2026-05-20",
            ),
        ],
        risk_signals=[
            ExtractedRiskSignal(
                summary="客户对交期敏感",
                severity=RiskSeverityEx.medium,
                kind=RiskKindEx.relationship,
            ),
        ],
        memory_items=[
            ExtractedMemoryItem(content="客户偏好微信沟通", kind=MemoryKindEx.preference),
        ],
        confidence_overall=0.66,
    )


def test_identity_draft_round_trip():
    original = _identity_draft_sample()
    payload = original.model_dump(mode="json")
    restored = IdentityDraft.model_validate(payload)
    assert restored.model_dump(mode="json") == payload
    assert restored.customer is not None
    assert restored.customer.full_name == "测试客户有限公司"
    assert restored.contacts[0].role == ContactRoleEx.buyer


def test_commercial_draft_round_trip():
    original = _commercial_draft_sample()
    payload = original.model_dump(mode="json")
    restored = CommercialDraft.model_validate(payload)
    assert restored.model_dump(mode="json") == payload
    # cleaned amount + cn-style date should have normalized in the original
    assert restored.order is not None
    assert restored.order.amount_total == 100000.0
    assert restored.contract is not None
    assert restored.contract.signing_date is not None
    assert restored.contract.signing_date.isoformat() == "2026-05-10"


def test_ops_draft_round_trip():
    original = _ops_draft_sample()
    payload = original.model_dump(mode="json")
    restored = OpsDraft.model_validate(payload)
    assert restored.model_dump(mode="json") == payload
    assert restored.events[0].event_type == CustomerEventTypeEx.contract_signed
    assert restored.commitments[0].direction == CommitmentDirectionEx.we_to_customer


def test_ingest_plan_round_trip():
    plan = IngestPlan(
        targets={"identity": 0.95, "commercial": 0.70, "ops": 0.20},
        extractors=[
            ExtractorSelection(name="identity", confidence=0.95),
            ExtractorSelection(name="commercial", confidence=0.70),
        ],
        reason="名片正面 + 合同首页都在视野，但 ops 只是寒暄",
        review_required=False,
    )
    payload = plan.model_dump(mode="json")
    restored = IngestPlan.model_validate(payload)
    assert restored.model_dump(mode="json") == payload
    assert {sel.name for sel in restored.extractors} == {"identity", "commercial"}


def test_unified_draft_assembled_from_three_drafts():
    """UnifiedDraft is the merge target — it must carry every field that
    each per-extractor draft contributes. We don't implement merge logic
    here (Agent G's job); we just assert the field surface is wide enough
    that a naive copy-over from each draft lands in UnifiedDraft.
    """

    identity = _identity_draft_sample()
    commercial = _commercial_draft_sample()
    ops = _ops_draft_sample()

    merged = UnifiedDraft(
        customer=identity.customer,
        contacts=list(identity.contacts),
        order=commercial.order,
        contract=commercial.contract,
        events=list(ops.events),
        commitments=list(ops.commitments),
        tasks=list(ops.tasks),
        risk_signals=list(ops.risk_signals),
        memory_items=list(ops.memory_items),
        summary=ops.summary,
        field_provenance=[
            *identity.field_provenance,
            *commercial.field_provenance,
            *ops.field_provenance,
        ],
        confidence_overall=min(
            identity.confidence_overall,
            commercial.confidence_overall,
            ops.confidence_overall,
        ),
        needs_review_fields=["order.amount_total"],
        warnings=["test warning"],
    )

    payload = merged.model_dump(mode="json")
    restored = UnifiedDraft.model_validate(payload)
    assert restored.model_dump(mode="json") == payload

    # Spot-check that data made it through every dimension.
    assert restored.customer is not None
    assert restored.customer.full_name == identity.customer.full_name
    assert restored.contacts and restored.contacts[0].name == "张三"
    assert restored.order is not None and restored.order.amount_total == 100000.0
    assert restored.contract is not None
    assert restored.events and restored.events[0].event_type == CustomerEventTypeEx.contract_signed
    assert restored.commitments[0].direction == CommitmentDirectionEx.we_to_customer
    assert restored.tasks[0].priority == TaskPriorityEx.high
    assert restored.risk_signals[0].kind == RiskKindEx.relationship
    assert restored.memory_items[0].kind == MemoryKindEx.preference
    assert len(restored.field_provenance) == 2  # identity(1) + commercial(1) + ops(0)
    assert restored.confidence_overall == 0.66
    assert restored.needs_review_fields == ["order.amount_total"]


def test_auto_confirm_request_round_trip():
    req = AutoConfirmRequest(
        customer=CustomerDecision(
            mode="new",
            existing_id=None,
            final=CustomerExtraction(full_name="测试客户有限公司"),
        ),
        contacts=[
            ContactDecision(
                mode="merge",
                existing_id="00000000-0000-0000-0000-000000000001",
                final=ContactExtraction(name="张三", role=ContactRoleEx.buyer),
            ),
        ],
        order=OrderExtraction(amount_total=50000.0),
        contract=ContractExtraction(contract_no_external="HT-001"),
        events=[ExtractedEvent(title="kickoff")],
        commitments=[ExtractedCommitment(summary="跟进")],
        tasks=[ExtractedTask(title="发样")],
        risk_signals=[ExtractedRiskSignal(summary="支付风险")],
        memory_items=[ExtractedMemoryItem(content="偏好微信")],
        field_provenance=[FieldProvenanceEntry(path="customer.full_name")],
        confidence_overall=0.7,
        parse_warnings=["one warning"],
    )

    payload = req.model_dump(mode="json")
    restored = AutoConfirmRequest.model_validate(payload)
    assert restored.model_dump(mode="json") == payload
    assert restored.customer is not None
    assert restored.customer.mode == "new"
    assert restored.contacts[0].mode == "merge"
    assert str(restored.contacts[0].existing_id) == "00000000-0000-0000-0000-000000000001"
    assert restored.order is not None and restored.order.amount_total == 50000.0
    assert restored.events[0].title == "kickoff"


def test_extra_fields_ignored_per_codebase_style():
    """Every model in unified_schemas declares `extra="ignore"`; verify the
    behavior so the planner / extractors can be loose at the boundary."""
    plan = IngestPlan.model_validate(
        {
            "targets": {"identity": 0.5},
            "extractors": [],
            "reason": "x",
            "review_required": False,
            "spurious_extra_field": "should be dropped",
        }
    )
    assert "spurious_extra_field" not in plan.model_dump()


# ── PaymentMilestone.trigger_offset_days boundary tolerance ────────
# Regression for WHHX250922合同.pdf: LandingAI returns "" for offset
# days; model validation must coerce to None, not raise.


def test_payment_milestone_empty_offset_days_becomes_none():
    m = PaymentMilestone.model_validate(
        {"ratio": 0.3, "trigger_event": "contract_signed", "trigger_offset_days": ""}
    )
    assert m.trigger_offset_days is None


def test_payment_milestone_whitespace_offset_days_becomes_none():
    m = PaymentMilestone.model_validate(
        {"ratio": 0.3, "trigger_event": "contract_signed", "trigger_offset_days": "   "}
    )
    assert m.trigger_offset_days is None


def test_payment_milestone_string_offset_days_parses_to_int():
    m = PaymentMilestone.model_validate(
        {"ratio": 1.0, "trigger_event": "invoice_issued", "trigger_offset_days": "90"}
    )
    assert m.trigger_offset_days == 90


def test_payment_milestone_chinese_unit_offset_days_parses_to_int():
    m = PaymentMilestone.model_validate(
        {"ratio": 1.0, "trigger_event": "invoice_issued", "trigger_offset_days": "90 天"}
    )
    assert m.trigger_offset_days == 90


def test_payment_milestone_unparseable_offset_days_becomes_none():
    m = PaymentMilestone.model_validate(
        {"ratio": 1.0, "trigger_event": "other", "trigger_offset_days": "abc"}
    )
    assert m.trigger_offset_days is None


def test_payment_milestone_float_offset_days_truncates():
    m = PaymentMilestone.model_validate(
        {"ratio": 1.0, "trigger_event": "other", "trigger_offset_days": 90.7}
    )
    assert m.trigger_offset_days == 90


# ── bind_existing customer/contact decision mode ────────────────────


def test_customer_decision_accepts_bind_existing_mode():
    """bind_existing is the new explicit binding mode (no field update)."""
    from yinhu_brain.services.ingest.schemas import CustomerDecision
    from uuid import uuid4

    cd = CustomerDecision.model_validate(
        {
            "mode": "bind_existing",
            "existing_id": str(uuid4()),
            "final": {"full_name": "保留原值"},
        }
    )
    assert cd.mode == "bind_existing"


def test_customer_decision_rejects_unknown_mode():
    from yinhu_brain.services.ingest.schemas import CustomerDecision
    with pytest.raises(Exception):
        CustomerDecision.model_validate(
            {"mode": "wat", "final": {"full_name": "x"}}
        )


def test_auto_confirm_request_round_trips_bind_existing_mode():
    from yinhu_brain.services.ingest.unified_schemas import AutoConfirmRequest
    from uuid import uuid4

    existing = str(uuid4())
    req = AutoConfirmRequest.model_validate(
        {
            "customer": {
                "mode": "bind_existing",
                "existing_id": existing,
                "final": {"full_name": ""},
            },
        }
    )
    payload = req.model_dump(mode="json")
    restored = AutoConfirmRequest.model_validate(payload)
    assert restored.customer is not None
    assert restored.customer.mode == "bind_existing"
    assert str(restored.customer.existing_id) == existing
