from __future__ import annotations

from yinhu_brain.services.ingest.landingai_normalize import normalize_pipeline_results
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult


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
