from __future__ import annotations

from yunwei_win.services.ingest.landingai_normalize import normalize_pipeline_results
from yunwei_win.services.ingest.unified_schemas import PipelineExtractResult


def test_normalize_identity_and_contract_order_into_unified_draft():
    draft = normalize_pipeline_results(
        [
            PipelineExtractResult(
                name="identity",
                extraction={
                    "customer": {"full_name": "测试客户有限公司", "short_name": "测试"},
                    "contacts": [{"name": "王经理", "mobile": "13800000000", "role": "primary_business"}],
                },
            ),
            PipelineExtractResult(
                name="contract_order",
                extraction={
                    "contract": {"contract_number": "HT-001", "signing_date": "2026-05-01"},
                    "order": {"total_amount": 120000, "currency": "CNY", "delivery_promised_date": "2026-06-30"},
                    "payment_milestones": [{"name": "预付款", "ratio": 30, "trigger_event": "contract_signed"}],
                },
            ),
        ]
    )

    assert draft.customer is not None
    assert draft.customer.full_name == "测试客户有限公司"
    assert draft.contacts[0].role == "buyer"
    assert draft.contract is not None
    assert draft.contract.contract_no_external == "HT-001"
    assert draft.order is not None
    assert draft.order.amount_total == 120000
    assert len(draft.pipeline_results) == 2


def test_normalize_handles_empty_trigger_offset_days():
    """LandingAI declares trigger_offset_days as string in its schema; on
    real PDFs it occasionally returns ``""``. PaymentMilestone's int field
    must NOT explode the whole ingest. WHHX250922合同.pdf regression."""
    draft = normalize_pipeline_results(
        [
            PipelineExtractResult(
                name="contract_order",
                extraction={
                    "payment_milestones": [
                        {
                            "name": "预付款",
                            "ratio": 0.3,
                            "trigger_event": "contract_signed",
                            "trigger_offset_days": "",
                        },
                    ],
                },
            ),
        ]
    )
    assert draft.contract is not None
    assert len(draft.contract.payment_milestones) == 1
    assert draft.contract.payment_milestones[0].trigger_offset_days is None


def test_normalize_parses_numeric_string_offset():
    draft = normalize_pipeline_results(
        [
            PipelineExtractResult(
                name="contract_order",
                extraction={
                    "payment_milestones": [
                        {"name": "尾款", "ratio": 0.7, "trigger_event": "invoice_issued", "trigger_offset_days": "90"},
                    ],
                },
            ),
        ]
    )
    assert draft.contract is not None
    assert draft.contract.payment_milestones[0].trigger_offset_days == 90


def test_normalize_parses_chinese_unit_offset():
    draft = normalize_pipeline_results(
        [
            PipelineExtractResult(
                name="contract_order",
                extraction={
                    "payment_milestones": [
                        {"name": "尾款", "ratio": 0.7, "trigger_event": "invoice_issued", "trigger_offset_days": "90 天"},
                    ],
                },
            ),
        ]
    )
    assert draft.contract is not None
    assert draft.contract.payment_milestones[0].trigger_offset_days == 90
