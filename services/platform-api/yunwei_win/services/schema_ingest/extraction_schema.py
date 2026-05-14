"""Selected-table extraction JSON schema builder.

Given a list of company-schema table names and the active catalog, emit
the JSON Schema an extractor model should follow. Only fields whose
``field_role`` is ``extractable`` or ``identity_key`` are included —
system links, audit fields, primary keys, timestamps, and workflow
fields stay out so the model is never asked to invent them.

The wire format mirrors the legacy ``canonical_schema`` shape (so old
review/confirm code continues to work):

    {
      "<table>": { "<field>": value, ... }                  // scalar table
      "<table>": [{"<field>": value, ... }, ...]            // array table
    }
"""

from __future__ import annotations

import json
from typing import Any, Iterable

_EXTRACTABLE_ROLES = {"extractable", "identity_key"}


def build_selected_tables_schema_json(
    selected_tables: Iterable[str],
    catalog: dict[str, Any],
) -> str:
    selected = list(selected_tables)
    tables_by_name = _active_tables_by_name(catalog)

    properties: dict[str, Any] = {}
    for table_name in selected:
        table = tables_by_name.get(table_name)
        if table is None:
            continue
        properties[table_name] = _table_schema(table)

    if not properties:
        schema: dict[str, Any] = {
            "type": "object",
            "description": (
                "No active catalog tables matched the selected_tables list. "
                "Return an empty object."
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
        if isinstance(table_name, str) and table_name:
            tables[table_name] = table
    return tables


def _table_schema(table: dict[str, Any]) -> dict[str, Any]:
    fields = _extractable_fields(table)
    row_schema = {
        "type": "object",
        "description": _table_description(table),
        "properties": {
            field["field_name"]: _field_schema(field)
            for field in fields
            if isinstance(field.get("field_name"), str)
        },
    }

    is_array_table = bool(table.get("is_array")) or any(
        bool(field.get("is_array")) for field in fields
    )
    if is_array_table:
        return {
            "type": "array",
            "description": _table_description(table),
            "items": row_schema,
        }
    return row_schema


def _extractable_fields(table: dict[str, Any]) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for field in table.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if field.get("is_active", True) is False:
            continue
        # Default to "extractable" when the field predates the field_role
        # column — never silently drop pre-vNext catalog rows or fields
        # added through add_field proposals without an explicit role.
        role = field.get("field_role") or "extractable"
        if role not in _EXTRACTABLE_ROLES:
            continue
        active.append(field)
    active.sort(key=lambda f: (f.get("sort_order", 0), f.get("field_name", "")))
    return active


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
        # Keep numeric data types as strings so OCR-style values like
        # "90 天" / "30,000.00" make it back to the user for normalization
        # instead of being dropped by the LLM.
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
