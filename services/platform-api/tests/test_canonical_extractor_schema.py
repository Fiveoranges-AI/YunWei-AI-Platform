from __future__ import annotations

import json

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.ingest.extractors.canonical_schema import (
    build_pipeline_schema_json,
)


def _catalog_from_default() -> dict:
    tables: list[dict] = []
    for table_idx, table in enumerate(DEFAULT_COMPANY_SCHEMA):
        table_is_array = bool(table.get("is_array", False))
        fields = []
        for field_idx, field in enumerate(table["fields"]):
            fields.append(
                {
                    **field,
                    "required": bool(field.get("required", False)),
                    "is_array": bool(field.get("is_array", table_is_array)),
                    "is_active": True,
                    "sort_order": field.get("sort_order", field_idx),
                }
            )
        tables.append(
            {
                **table,
                "fields": fields,
                "is_active": True,
                "sort_order": table.get("sort_order", table_idx),
            }
        )
    return {"tables": tables}


def test_contract_order_schema_is_generated_from_company_catalog():
    schema = json.loads(build_pipeline_schema_json("contract_order", _catalog_from_default()))

    props = schema["properties"]
    assert set(props) == {
        "customers",
        "contacts",
        "contracts",
        "contract_payment_milestones",
        "orders",
    }
    assert props["orders"]["properties"]["amount_total"]["description"].startswith("订单金额")
    assert "total_amount" not in props["orders"]["properties"]
    assert "contract_number" not in props["contracts"]["properties"]
    assert "contract_no_external" in props["contracts"]["properties"]
    assert props["contacts"]["type"] == "array"
    assert props["contract_payment_milestones"]["type"] == "array"


def test_unknown_pipeline_generates_empty_object_schema():
    schema = json.loads(build_pipeline_schema_json("unknown", _catalog_from_default()))
    assert schema == {
        "type": "object",
        "description": "No active company schema tables are selected for pipeline unknown.",
        "properties": {},
    }
