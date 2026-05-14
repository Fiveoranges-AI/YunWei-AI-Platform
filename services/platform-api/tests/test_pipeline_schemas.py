from __future__ import annotations

import pytest

from yunwei_win.services.ingest.pipeline_schemas import (
    PIPELINE_NAMES,
    PipelineExtractResult,
    PipelineRoutePlan,
    PipelineSelection,
)


def test_pipeline_names_are_the_canonical_router_vocabulary():
    assert PIPELINE_NAMES == (
        "identity",
        "contract_order",
        "finance",
        "logistics",
        "manufacturing_requirement",
        "commitment_task_risk",
    )


def test_pipeline_route_plan_round_trips_selected_pipelines():
    plan = PipelineRoutePlan(
        primary_pipeline="contract_order",
        selected_pipelines=[
            PipelineSelection(
                name="contract_order",
                confidence=0.91,
                reason="合同/订单字段",
            )
        ],
        document_summary="采购合同",
        needs_human_review=True,
    )

    restored = PipelineRoutePlan.model_validate(plan.model_dump(mode="json"))
    assert restored.primary_pipeline == "contract_order"
    assert restored.selected_pipelines[0].name == "contract_order"
    assert restored.needs_human_review is True


def test_unknown_pipeline_name_is_rejected():
    with pytest.raises(ValueError):
        PipelineSelection(name="commercial", confidence=0.5)


def test_pipeline_extract_result_uses_extraction_envelope():
    result = PipelineExtractResult(
        name="contract_order",
        extraction={"orders": {"amount_total": "100"}},
        extraction_metadata={"provider": "test"},
    )

    payload = result.model_dump(mode="json")
    assert payload["extraction"]["orders"]["amount_total"] == "100"
    assert "result" not in payload
