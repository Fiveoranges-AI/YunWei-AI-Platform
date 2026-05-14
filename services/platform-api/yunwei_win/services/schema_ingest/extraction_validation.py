"""Validate extractor output against the tenant catalog (vNext).

The vNext orchestrator hands ``validate_normalized_extraction`` a
``NormalizedExtraction`` (provider-agnostic table → rows → fields) and
the active catalog. We walk the catalog directly — no ``jsonschema``
runtime dependency — and return human-readable warning strings that
flow into ``ReviewDraft.general_warnings`` and
``DocumentExtraction.validation_warnings``. The job still reaches
``extracted``; shape mismatches degrade to warnings, never crash the
ingest run (mirrors ``auto.py``'s degrade-vs-crash policy).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from yunwei_win.services.schema_ingest.extraction_normalize import (
        NormalizedExtraction,
    )
    from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact


_EXTRACTABLE_ROLES = {"extractable", "identity_key"}


def validate_normalized_extraction(
    normalized: "NormalizedExtraction",
    *,
    selected_tables: list[str],
    catalog: dict[str, Any],
    parse_artifact: "ParseArtifact",
) -> list[str]:
    """Validate a vNext NormalizedExtraction against catalog + parse artifact.

    Returns human-readable warning strings (empty list means clean). Catches
    four classes of issues:

      - tables outside the router's selection (ignored but logged),
      - unknown tables, unknown fields, and non-extractable fields
        (``system_link`` / ``audit`` must never come from the extractor),
      - primitive type / enum violations on extracted values,
      - ``source_refs`` that don't point at any ref the parser actually
        emitted (chunks, table cells, grounding keys, page ids).
    """

    selected = set(selected_tables)
    catalog_by_table = _index_catalog(catalog)
    valid_refs = _collect_parse_ref_ids(parse_artifact)

    warnings: list[str] = []

    for table_name, rows in normalized.tables.items():
        if table_name not in selected:
            warnings.append(
                f"table {table_name} not in router selection"
            )
            continue
        table_spec = catalog_by_table.get(table_name)
        if table_spec is None:
            warnings.append(
                f"unknown or non-extractable field {table_name}.* "
                f"(table not in catalog)"
            )
            continue
        field_specs = _extractable_field_map(table_spec)

        for row_idx, row in enumerate(rows):
            row_label = f"{table_name}[{row_idx}]"
            for field_name, normalized_value in row.fields.items():
                spec = field_specs.get(field_name)
                if spec is None:
                    warnings.append(
                        f"unknown or non-extractable field "
                        f"{table_name}.{field_name}"
                    )
                    continue
                value = normalized_value.value
                if value is not None and not _value_matches_type(spec, value):
                    data_type = (spec.get("data_type") or "text").lower()
                    warnings.append(
                        f"{row_label}.{field_name} expected {data_type}, "
                        f"got {type(value).__name__} ({value!r})"
                    )
                for ref in normalized_value.source_refs:
                    if ref.ref_id and ref.ref_id not in valid_refs:
                        warnings.append(
                            f"source ref {ref.ref_id} not found in parse artifact"
                        )

    return warnings


def _index_catalog(catalog: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in catalog.get("tables") or []:
        if isinstance(t, dict) and isinstance(t.get("table_name"), str):
            out[t["table_name"]] = t
    return out


def _extractable_field_map(table_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field in table_spec.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if field.get("is_active", True) is False:
            continue
        name = field.get("field_name")
        if not isinstance(name, str):
            continue
        role = field.get("field_role") or "extractable"
        if role not in _EXTRACTABLE_ROLES:
            continue
        out[name] = field
    return out


def _collect_parse_ref_ids(parse_artifact: "ParseArtifact") -> set[str]:
    refs: set[str] = set()
    for chunk in parse_artifact.chunks or []:
        if chunk.id:
            refs.add(chunk.id)
    for key in (parse_artifact.grounding or {}).keys():
        if isinstance(key, str):
            refs.add(key)
    for table in parse_artifact.tables or []:
        if table.id:
            refs.add(table.id)
        for cell in table.cells or []:
            if cell.ref_id:
                refs.add(cell.ref_id)
    for page in parse_artifact.pages or []:
        if isinstance(page, dict):
            page_id = page.get("id")
            if isinstance(page_id, str):
                refs.add(page_id)
    return refs


def _value_matches_type(field_spec: dict, value: Any) -> bool:
    """Lighter-weight primitive coercion check for extracted cell values."""

    data_type = (field_spec.get("data_type") or "text").lower()
    try:
        if data_type == "text":
            return isinstance(value, (str, int, float))
        if data_type == "uuid":
            UUID(str(value))
            return True
        if data_type == "date":
            if isinstance(value, date):
                return True
            datetime.strptime(str(value), "%Y-%m-%d")
            return True
        if data_type == "datetime":
            if isinstance(value, datetime):
                return True
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return True
        if data_type == "decimal":
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float, Decimal)):
                return True
            Decimal(str(value))
            return True
        if data_type == "integer":
            if isinstance(value, bool):
                return False
            if isinstance(value, int):
                return True
            s = str(value)
            try:
                int(s)
                return True
            except ValueError:
                return float(s).is_integer()
        if data_type == "boolean":
            if isinstance(value, bool):
                return True
            if isinstance(value, (int, float)):
                return value in (0, 1)
            return str(value).lower() in ("true", "false", "0", "1")
        if data_type == "enum":
            enum_values = field_spec.get("enum_values") or []
            if not enum_values:
                return True
            return value in enum_values
        if data_type == "json":
            return True
        return True
    except (ValueError, InvalidOperation, TypeError):
        return False
