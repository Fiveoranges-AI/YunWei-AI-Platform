"""Build extractor JSON Schemas from the tenant company schema catalog.

Extractor providers should ask models to emit the same table/field shape that
``ReviewDraft`` renders and confirm writes. This keeps LandingAI and DeepSeek
behind one canonical contract:

    { "<company_table_name>": { "<company_field_name>": value } }

Array tables use a list of row objects. Missing scalar fields should be null;
missing array tables should be [].
"""

from __future__ import annotations

import json
from typing import Any

from yunwei_win.services.ingest.pipeline_schemas import PipelineName


PIPELINE_TABLES: dict[PipelineName, list[str]] = {
    "identity": ["customers", "contacts"],
    "contract_order": [
        "customers",
        "contacts",
        "contracts",
        "contract_payment_milestones",
        "orders",
    ],
    "finance": ["invoices", "invoice_items", "payments"],
    "logistics": ["shipments", "shipment_items"],
    "manufacturing_requirement": ["products", "product_requirements"],
    "commitment_task_risk": ["customer_journal_items", "customer_tasks"],
}


def build_pipeline_schema_json(pipeline_name: str, catalog: dict[str, Any]) -> str:
    """Return a JSON Schema for one routed pipeline using active catalog fields."""

    table_names = PIPELINE_TABLES.get(pipeline_name, [])
    tables = _active_tables_by_name(catalog)
    properties: dict[str, Any] = {}

    for table_name in table_names:
        table = tables.get(table_name)
        if table is None:
            continue
        properties[table_name] = _table_schema(table)

    if not properties:
        schema = {
            "type": "object",
            "description": (
                "No active company schema tables are selected for pipeline "
                f"{pipeline_name}."
            ),
            "properties": {},
        }
    else:
        schema = {
            "type": "object",
            "description": (
                "Extract only these company data tables. Use the exact table "
                "and field names. Use null for missing scalar fields and [] "
                "for missing array tables."
            ),
            "properties": properties,
        }
    return json.dumps(schema, ensure_ascii=False, sort_keys=True)


def _active_tables_by_name(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for table in catalog.get("tables") or []:
        if not isinstance(table, dict):
            continue
        if table.get("is_active", True) is False:
            continue
        table_name = table.get("table_name")
        if not isinstance(table_name, str) or not table_name:
            continue
        tables[table_name] = table
    return tables


def _table_schema(table: dict[str, Any]) -> dict[str, Any]:
    active_fields = [
        f for f in table.get("fields") or []
        if isinstance(f, dict) and f.get("is_active", True) is not False
    ]
    active_fields.sort(key=lambda f: (f.get("sort_order", 0), f.get("field_name", "")))

    row_schema = {
        "type": "object",
        "description": _table_description(table),
        "properties": {
            field["field_name"]: _field_schema(field)
            for field in active_fields
            if isinstance(field.get("field_name"), str)
        },
    }

    is_array_table = bool(table.get("is_array")) or any(
        bool(field.get("is_array")) for field in active_fields
    )
    if is_array_table:
        return {
            "type": "array",
            "description": _table_description(table),
            "items": row_schema,
        }
    return row_schema


def _table_description(table: dict[str, Any]) -> str:
    label = table.get("label") or table.get("table_name") or "table"
    purpose = table.get("purpose")
    if purpose:
        return f"{label}：{purpose}"
    return str(label)


def _field_schema(field: dict[str, Any]) -> dict[str, Any]:
    data_type = str(field.get("data_type") or "text").lower()
    schema: dict[str, Any]
    if data_type in {"integer", "int"}:
        # Keep as string so OCR amounts like "90 天" can be captured and
        # normalized/validated later instead of being dropped by the model.
        schema = {"type": "string"}
    elif data_type in {"decimal", "number", "float"}:
        schema = {"type": "string"}
    elif data_type == "boolean":
        schema = {"type": "boolean"}
    elif data_type == "json":
        schema = {"type": "object"}
    else:
        schema = {"type": "string"}
        if data_type == "date":
            schema["format"] = "date"
        elif data_type == "datetime":
            schema["format"] = "date-time"

    enum_values = field.get("enum_values")
    if isinstance(enum_values, list) and enum_values:
        schema["enum"] = [str(v) for v in enum_values if v is not None]

    schema["description"] = _field_description(field, data_type)
    return schema


def _field_description(field: dict[str, Any], data_type: str) -> str:
    label = str(field.get("label") or field.get("field_name") or "field")
    parts = [label]
    description = field.get("description")
    if description:
        parts.append(str(description))
    extraction_hint = field.get("extraction_hint")
    if extraction_hint:
        parts.append(str(extraction_hint))
    parts.append(f"data_type={data_type}")
    if field.get("required"):
        parts.append("required")
    return "；".join(parts)
