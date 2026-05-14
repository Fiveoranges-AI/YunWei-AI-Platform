from __future__ import annotations

import json

import pytest

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.extraction_schema import (
    build_selected_tables_schema_json,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


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


def test_selected_table_schema_excludes_system_and_audit_fields():
    schema = json.loads(
        build_selected_tables_schema_json(
            ["orders", "customer_journal_items"], _catalog_from_default()
        )
    )
    assert "orders" in schema["properties"]
    order_props = schema["properties"]["orders"]["properties"]
    journal_props = schema["properties"]["customer_journal_items"]["items"][
        "properties"
    ]
    assert "amount_total" in order_props
    assert "customer_id" not in order_props
    assert "document_id" not in journal_props
    assert "confidence" not in journal_props


def test_selected_table_schema_keeps_identity_keys():
    schema = json.loads(
        build_selected_tables_schema_json(["customers"], _catalog_from_default())
    )
    props = schema["properties"]["customers"]["properties"]
    assert "full_name" in props
    assert "tax_id" in props
    assert props["full_name"]["description"].startswith("公司全称")


def test_selected_table_schema_renders_array_tables_as_arrays():
    schema = json.loads(
        build_selected_tables_schema_json(
            ["contacts", "contract_payment_milestones"], _catalog_from_default()
        )
    )
    contacts = schema["properties"]["contacts"]
    milestones = schema["properties"]["contract_payment_milestones"]
    assert contacts["type"] == "array"
    assert milestones["type"] == "array"
    assert "customer_id" not in contacts["items"]["properties"]
    assert "contract_id" not in milestones["items"]["properties"]


def test_selected_table_schema_drops_unknown_table_names():
    schema = json.loads(
        build_selected_tables_schema_json(
            ["customers", "ghost_table"], _catalog_from_default()
        )
    )
    assert "customers" in schema["properties"]
    assert "ghost_table" not in schema["properties"]


def test_selected_table_schema_treats_missing_field_role_as_extractable():
    """Fields seeded before vNext (e.g. via add_field proposals) may not have a
    field_role; the builder must keep them rather than silently dropping the
    data."""

    catalog = {
        "tables": [
            {
                "table_name": "customers",
                "label": "客户",
                "purpose": "客户主档",
                "is_active": True,
                "is_array": False,
                "fields": [
                    {
                        "field_name": "legacy_field",
                        "label": "旧字段",
                        "data_type": "text",
                        "is_active": True,
                        "is_array": False,
                        "required": False,
                        "sort_order": 0,
                        # no field_role on purpose
                    }
                ],
            }
        ]
    }
    schema = json.loads(build_selected_tables_schema_json(["customers"], catalog))
    assert "legacy_field" in schema["properties"]["customers"]["properties"]
