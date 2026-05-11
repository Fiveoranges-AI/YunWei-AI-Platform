from __future__ import annotations

import json

import pytest

from yinhu_brain.services.ingest.landingai_schemas.registry import (
    PIPELINE_NAMES,
    load_schema_json,
    validate_landingai_schema,
)


def test_all_pipeline_schemas_load_as_json_objects():
    assert PIPELINE_NAMES == (
        "identity",
        "contract_order",
        "finance",
        "logistics",
        "manufacturing_requirement",
        "commitment_task_risk",
    )
    for name in PIPELINE_NAMES:
        raw = load_schema_json(name)
        schema = json.loads(raw)
        assert schema["type"] == "object"
        assert isinstance(schema["properties"], dict)


def test_contract_order_is_party_a_only():
    schema = json.loads(load_schema_json("contract_order"))
    props = schema["properties"]
    assert "seller" not in props
    assert "customer" in props
    desc = props["customer"]["description"]
    assert "Party A" in desc
    assert "Do not extract Party B" in desc


def test_schema_rejects_unsupported_keywords():
    with pytest.raises(ValueError, match="unsupported LandingAI schema keyword"):
        validate_landingai_schema(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"x": {"type": "string"}},
            }
        )
