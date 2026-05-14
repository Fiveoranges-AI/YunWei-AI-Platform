"""Validate extractor output against the tenant catalog.

The orchestrator runs the extractor providers and they emit one
``PipelineExtractResult`` per routed pipeline; each result's ``extraction``
payload is supposed to follow ``build_pipeline_schema_json``'s shape — a JSON
object keyed by company table names, with each value being a row object (or a
list of row objects for ``is_array`` tables), where every row key is a
catalog field on that table.

We don't want a hard dependency on ``jsonschema`` for one validation step, and
the JSON Schema builder already encodes the table/field set we care about, so
this module walks the catalog directly and reports human-readable warning
strings that flow into ``ReviewDraft.general_warnings``. The job still reaches
``extracted`` — mirrors the degrade-vs-crash policy at ``auto.py``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any
from uuid import UUID

from yunwei_win.services.ingest.extractors.canonical_schema import PIPELINE_TABLES

if TYPE_CHECKING:
    from yunwei_win.services.schema_ingest.extraction_normalize import (
        NormalizedExtraction,
    )
    from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact


_EXTRACTABLE_ROLES = {"extractable", "identity_key"}


def validate_pipeline_extraction(
    pipeline_name: str,
    extraction: Any,
    catalog: dict,
) -> list[str]:
    """Return human-readable warnings about the extractor payload shape.

    Empty list means the payload conforms to the catalog schema for
    ``pipeline_name``. Each warning is prefixed with ``"{pipeline}: "`` so the
    caller can join them straight into ``general_warnings``.
    """

    table_names = PIPELINE_TABLES.get(pipeline_name)
    if table_names is None:
        # Unknown pipeline names are handled separately by the materializer
        # (soft skip). Nothing to validate against here.
        return []

    if not isinstance(extraction, dict):
        return [
            f"{pipeline_name}: extraction did not match catalog schema: "
            f"top-level must be object, got {type(extraction).__name__}"
        ]

    catalog_by_table = _index_catalog(catalog)
    allowed_tables = set(table_names)

    warnings: list[str] = []

    for key in extraction.keys():
        if key not in allowed_tables:
            warnings.append(
                f"{pipeline_name}: extraction did not match catalog schema: "
                f"unknown top-level key {key!r}"
            )

    for table_name in table_names:
        if table_name not in extraction:
            continue
        value = extraction[table_name]
        table_spec = catalog_by_table.get(table_name)
        if table_spec is None:
            continue
        field_map = {
            f["field_name"]: f
            for f in table_spec.get("fields") or []
            if isinstance(f, dict) and isinstance(f.get("field_name"), str)
        }
        is_array_table = bool(table_spec.get("is_array")) or any(
            bool(f.get("is_array")) for f in table_spec.get("fields") or []
        )

        if is_array_table:
            if not isinstance(value, list):
                warnings.append(
                    f"{pipeline_name}: extraction did not match catalog "
                    f"schema: {table_name} must be a list of objects, got "
                    f"{type(value).__name__}"
                )
                continue
            for idx, row in enumerate(value):
                _validate_row(
                    pipeline_name=pipeline_name,
                    table_name=table_name,
                    row=row,
                    field_map=field_map,
                    row_index=idx,
                    warnings=warnings,
                )
        else:
            if isinstance(value, list):
                warnings.append(
                    f"{pipeline_name}: extraction did not match catalog "
                    f"schema: {table_name} must be a single object, got list"
                )
                continue
            _validate_row(
                pipeline_name=pipeline_name,
                table_name=table_name,
                row=value,
                field_map=field_map,
                row_index=None,
                warnings=warnings,
            )

    return warnings


def _index_catalog(catalog: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in catalog.get("tables") or []:
        if isinstance(t, dict) and isinstance(t.get("table_name"), str):
            out[t["table_name"]] = t
    return out


def _validate_row(
    *,
    pipeline_name: str,
    table_name: str,
    row: Any,
    field_map: dict[str, dict],
    row_index: int | None,
    warnings: list[str],
) -> None:
    """Append warnings for unknown / wrong-typed cells in a single row."""

    where = f"{table_name}" if row_index is None else f"{table_name}[{row_index}]"
    if not isinstance(row, dict):
        warnings.append(
            f"{pipeline_name}: extraction did not match catalog schema: "
            f"{where} must be an object, got {type(row).__name__}"
        )
        return
    for field_name, value in row.items():
        spec = field_map.get(field_name)
        if spec is None:
            warnings.append(
                f"{pipeline_name}: extraction did not match catalog schema: "
                f"unknown field {where}.{field_name}"
            )
            continue
        if value is None:
            continue
        if not _value_matches_type(spec, value):
            data_type = (spec.get("data_type") or "text").lower()
            warnings.append(
                f"{pipeline_name}: extraction did not match catalog schema: "
                f"{where}.{field_name} expected {data_type}, got "
                f"{type(value).__name__} ({value!r})"
            )


def _value_matches_type(field_spec: dict, value: Any) -> bool:
    """Lighter-weight twin of ``confirm._validate_value``.

    Empty strings are considered coercible — extractor output often has them
    where the model failed to fill a value; that's not a "wrong type" problem.
    """

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
