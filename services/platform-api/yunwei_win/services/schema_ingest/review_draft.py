"""Materialize a schema-first ReviewDraft from extractor output + catalog.

Invariant:
    For every selected table, the draft's cells == the active fields in
    ``company_schema_fields``. Extraction sparsity changes cell status,
    not cell existence.

Pipeline -> table mapping is the schema-first contract that decides which catalog
tables get materialized for a document. Mapping unknown pipelines is treated
as a soft warning (skip), not a fatal error — the extractor may evolve
faster than this map.

The pipeline_results payload format intentionally accepts a few shape
variants because the V1 extractor pipelines were written independently and
don't agree on naming. The materializer normalizes them; the rule is
"prefer the most specific key, then fall back".
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from yunwei_win.services.ingest.extractors.canonical_schema import PIPELINE_TABLES
from yunwei_win.services.schema_ingest.schemas import (
    ReviewCell,
    ReviewCellEvidence,
    ReviewDraft,
    ReviewDraftDocument,
    ReviewDraftRoutePlan,
    ReviewRow,
    ReviewTable,
)


_LOW_CONFIDENCE_THRESHOLD = 0.6


def materialize_review_draft(
    *,
    extraction_id: UUID,
    document_id: UUID,
    schema_version: int,
    document_filename: str,
    route_plan: dict[str, Any],
    pipeline_results: list[dict[str, Any]],
    catalog: dict[str, Any],
    document_summary: str | None = None,
    document_source_text: str | None = None,
    warnings: list[str] | None = None,
) -> ReviewDraft:
    """Build a complete table/cell ReviewDraft.

    Args:
        catalog: Output of ``services.company_schema.get_company_schema``.
        route_plan: ``{"selected_pipelines": [{name, confidence, reason}], ...}``
            Pipelines may be a list of dicts or bare strings.
        pipeline_results: ``[{"name"|"schema": pipeline_name, "result"|"data": {...}, "warnings": [...]}]``.
            Shapes vary by provider — we extract leniently.
    """

    catalog_tables: list[dict[str, Any]] = catalog.get("tables") or []
    catalog_by_name: dict[str, dict[str, Any]] = {
        t["table_name"]: t for t in catalog_tables
    }

    selected_pipelines = _normalize_selected_pipelines(route_plan)
    selected_table_names = _selected_table_names(selected_pipelines)

    extraction_by_table = _extraction_by_table(
        pipeline_results=pipeline_results,
        selected_table_names=selected_table_names,
    )

    schema_warnings = _flatten_pipeline_warnings(pipeline_results)

    tables: list[ReviewTable] = []
    # Iterate catalog order so the UI always renders tables in a stable
    # sequence; only include those the route plan selected.
    for table_spec in catalog_tables:
        table_name = table_spec["table_name"]
        if table_name not in selected_table_names:
            continue
        tables.append(_build_review_table(table_spec, extraction_by_table.get(table_name)))

    # Tables in route plan that don't exist in the catalog are dropped here;
    # surface that as a schema warning so a missing-schema bug isn't silent.
    for missing_table in sorted(selected_table_names - catalog_by_name.keys()):
        schema_warnings.append(
            f"selected_table {missing_table!r} not present in active catalog"
        )

    return ReviewDraft(
        extraction_id=extraction_id,
        document_id=document_id,
        schema_version=schema_version,
        status="pending_review",
        document=ReviewDraftDocument(
            filename=document_filename,
            summary=document_summary,
            source_text=document_source_text,
        ),
        route_plan=ReviewDraftRoutePlan(
            selected_pipelines=[
                {
                    "name": p["name"],
                    "confidence": p.get("confidence"),
                    "reason": p.get("reason"),
                }
                for p in selected_pipelines
            ]
        ),
        tables=tables,
        schema_warnings=schema_warnings,
        general_warnings=_collect_general_warnings(route_plan, warnings),
    )


# --- selected pipeline / table helpers -----------------------------------


def _normalize_selected_pipelines(route_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize ``route_plan["selected_pipelines"]`` to a list of dicts.

    Accepts either ``[{"name": ..., ...}]`` or ``["name1", "name2"]``.
    Items with no resolvable name are dropped.
    """

    raw = route_plan.get("selected_pipelines") or []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            normalized.append({"name": item})
        elif isinstance(item, dict):
            name = item.get("name") or item.get("schema") or item.get("pipeline")
            if not name:
                continue
            normalized.append({**item, "name": name})
    return normalized


def _selected_table_names(selected_pipelines: list[dict[str, Any]]) -> set[str]:
    """Union of catalog table names covered by the selected pipelines."""

    names: set[str] = set()
    for pipeline in selected_pipelines:
        tables = PIPELINE_TABLES.get(pipeline["name"])
        if not tables:
            # Unknown pipeline name — tolerate; spec says don't crash.
            continue
        names.update(tables)
    return names


# --- raw extraction extraction ------------------------------------------


def _extraction_by_table(
    *,
    pipeline_results: list[dict[str, Any]],
    selected_table_names: set[str],
) -> dict[str, Any]:
    """Walk pipeline_results and pull the sub-tree for each selected table.

    For singular tables, returns a dict (or ``None`` if not found).
    For array tables, returns a list of dicts (or ``None`` if not found).
    The materializer downstream uses the field metadata to decide which.
    """

    by_table: dict[str, Any] = {}
    for result_entry in pipeline_results or []:
        if not isinstance(result_entry, dict):
            continue
        pipeline_name = (
            result_entry.get("name")
            or result_entry.get("schema")
            or result_entry.get("pipeline")
        )
        if not pipeline_name:
            continue
        covered_tables = PIPELINE_TABLES.get(pipeline_name)
        if not covered_tables:
            continue
        payload = (
            result_entry.get("extraction")
            or result_entry.get("result")
            or result_entry.get("data")
            or result_entry.get("raw")
            or {}
        )
        if not isinstance(payload, dict):
            continue
        for table_name in covered_tables:
            if table_name not in selected_table_names:
                continue
            extracted = _extract_table_payload(payload, table_name)
            if extracted is None:
                continue
            # First non-empty extraction wins; pipelines covering the same
            # table shouldn't disagree in practice (e.g. ``identity`` and
            # ``contract_order`` both list ``customers``).
            by_table.setdefault(table_name, extracted)
    return by_table


def _extract_table_payload(payload: dict[str, Any], table_name: str) -> Any:
    """Find ``table_name`` data inside one pipeline result payload.

    Tries, in order:
      1. ``payload["data"][table_name]`` (LandingAI nested style)
      2. ``payload[table_name]``
      3. ``payload[singular(table_name)]``  (drop trailing 's')
      4. ``payload`` itself when no nesting matches AND the payload looks
         like a flat field dict (used when the pipeline only ever covers
         one table, e.g. ``orders``).
    """

    nested = payload.get("data")
    if isinstance(nested, dict) and table_name in nested:
        return nested[table_name]
    if table_name in payload:
        return payload[table_name]
    singular = table_name.rstrip("s")
    if singular and singular != table_name and singular in payload:
        return payload[singular]
    # Fall back to using the payload itself only if it looks like a record:
    # i.e. no envelope keys like ``result`` / ``data`` / ``warnings``.
    envelope_keys = {"data", "result", "raw", "warnings", "confidences", "evidence"}
    if isinstance(payload, dict) and not envelope_keys.intersection(payload.keys()):
        return payload
    return None


# --- per-table materialization ------------------------------------------


def _build_review_table(
    table_spec: dict[str, Any],
    raw_extraction: Any,
) -> ReviewTable:
    fields: list[dict[str, Any]] = [
        f for f in table_spec.get("fields") or [] if f.get("is_active", True)
    ]
    is_array_table = any(bool(f.get("is_array")) for f in fields)

    rows: list[ReviewRow] = []
    items = _coerce_to_rows(raw_extraction, is_array_table)
    if is_array_table and not items:
        # Array table selected with no extracted items -> one empty row so
        # the reviewer can add values.
        items = [{}]
    if not is_array_table and not items:
        items = [{}]

    for idx, item_data in enumerate(items):
        cells = [_build_cell(field, item_data) for field in fields]
        rows.append(
            ReviewRow(
                client_row_id=f"{table_spec['table_name']}:{idx}",
                cells=cells,
            )
        )

    raw_dump: dict[str, Any] | None = None
    if isinstance(raw_extraction, dict):
        raw_dump = raw_extraction
    elif isinstance(raw_extraction, list):
        raw_dump = {"items": raw_extraction}

    return ReviewTable(
        table_name=table_spec["table_name"],
        label=table_spec.get("label") or table_spec["table_name"],
        purpose=table_spec.get("purpose"),
        category=table_spec.get("category"),
        is_array=is_array_table,
        rows=rows,
        raw_extraction=raw_dump,
    )


def _coerce_to_rows(raw_extraction: Any, is_array_table: bool) -> list[dict[str, Any]]:
    """Turn the raw extraction into a list of row dicts.

    - Array table + list -> the list itself (drop non-dict entries).
    - Array table + dict -> wrap in a single-item list (some pipelines emit
      one dict instead of ``[dict]``).
    - Non-array table + dict -> wrap.
    - Anything else -> empty list.
    """

    if raw_extraction is None:
        return []
    if is_array_table:
        if isinstance(raw_extraction, list):
            return [item for item in raw_extraction if isinstance(item, dict)]
        if isinstance(raw_extraction, dict):
            return [raw_extraction]
        return []
    if isinstance(raw_extraction, dict):
        return [raw_extraction]
    return []


# --- per-cell materialization -------------------------------------------


def _build_cell(field: dict[str, Any], item_data: dict[str, Any]) -> ReviewCell:
    """Decide value/status/source/confidence/evidence for one cell.

    Status decision tree:
      1. Raw value present (not None) -> ``extracted`` (or ``low_confidence``
         when confidence < threshold), source ``ai``.
      2. Field has a non-uuid, non-required ``default_value`` -> use it,
         status ``extracted``, source ``default``.
      3. Otherwise -> status ``missing``, source ``empty``.

    Per-field evidence/confidence may live two ways and we accept both:
      a) Wrapped: ``item_data[field_name] = {"value": ..., "confidence": ..., "evidence": {...}}``
      b) Side-channel: ``item_data["confidences"][field_name]`` /
         ``item_data["evidence"][field_name]``.
    """

    field_name = field["field_name"]
    label = field.get("label") or field_name
    data_type = field.get("data_type") or "text"
    required = bool(field.get("required", False))
    is_array_field = bool(field.get("is_array", False))

    raw_field = item_data.get(field_name)
    side_confidence = _lookup_side_channel(item_data, "confidences", field_name)
    side_evidence = _lookup_side_channel(item_data, "evidence", field_name)

    value, confidence, evidence_data = _unwrap_field_value(
        raw_field, side_confidence, side_evidence
    )

    if value is not None:
        if confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD:
            status: str = "low_confidence"
        else:
            status = "extracted"
        source: str = "ai"
        evidence = _coerce_evidence(evidence_data)
    elif _can_use_default(field):
        value = field.get("default_value")
        status = "extracted"
        source = "default"
        confidence = None
        evidence = None
    else:
        value = None
        status = "missing"
        source = "empty"
        confidence = None
        evidence = None

    return ReviewCell(
        field_name=field_name,
        label=label,
        data_type=data_type,
        required=required,
        is_array=is_array_field,
        value=value,
        display_value="" if value is None else str(value),
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
        evidence=evidence,
        source=source,  # type: ignore[arg-type]
    )


def _unwrap_field_value(
    raw_field: Any,
    side_confidence: float | None,
    side_evidence: Any,
) -> tuple[Any, float | None, Any]:
    """Return (value, confidence, evidence_data) tolerating wrapped/raw shapes.

    Wrapped shape: ``{"value": x, "confidence": 0.9, "evidence": {...}}``.
    Anything else is treated as the raw value.
    """

    if isinstance(raw_field, dict) and "value" in raw_field and _looks_wrapped(raw_field):
        value = raw_field.get("value")
        confidence = _coerce_confidence(raw_field.get("confidence"))
        evidence_data = raw_field.get("evidence")
        return value, confidence, evidence_data
    return raw_field, _coerce_confidence(side_confidence), side_evidence


def _looks_wrapped(raw_field: dict[str, Any]) -> bool:
    """Heuristic: a wrapped cell is keyed ``value`` + at least one of
    ``confidence`` / ``evidence`` (or carries no other arbitrary keys).

    This avoids treating a real ``json`` payload that happens to contain
    ``value`` as a wrapped cell.
    """

    metadata_keys = {"confidence", "evidence", "score"}
    if metadata_keys.intersection(raw_field.keys()):
        return True
    # If the only key is "value", treat as wrapped.
    return set(raw_field.keys()) == {"value"}


def _lookup_side_channel(
    item_data: dict[str, Any], channel: str, field_name: str
) -> Any:
    """Pull confidence/evidence from a side-channel map if present."""

    channel_data = item_data.get(channel)
    if isinstance(channel_data, dict):
        return channel_data.get(field_name)
    return None


def _coerce_confidence(raw: Any) -> float | None:
    """Best-effort float coercion; non-numeric -> ``None``."""

    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _coerce_evidence(raw: Any) -> ReviewCellEvidence | None:
    """Normalize raw evidence into ``ReviewCellEvidence``.

    Accepts:
      - ``None`` -> None
      - dict with ``page`` / ``excerpt`` -> use them.
      - dict with other keys -> excerpt = str(dict), page = None.
      - string -> treat as excerpt.
    """

    if raw is None:
        return None
    if isinstance(raw, ReviewCellEvidence):
        return raw
    if isinstance(raw, dict):
        page_raw = raw.get("page")
        page: int | None
        try:
            page = int(page_raw) if page_raw is not None else None
        except (TypeError, ValueError):
            page = None
        excerpt = raw.get("excerpt") or raw.get("text") or raw.get("quote")
        excerpt_str = str(excerpt) if excerpt is not None else None
        if page is None and excerpt_str is None:
            return None
        return ReviewCellEvidence(page=page, excerpt=excerpt_str)
    if isinstance(raw, str):
        return ReviewCellEvidence(excerpt=raw)
    return None


def _can_use_default(field: dict[str, Any]) -> bool:
    """Whether the cell can fall back to ``default_value``.

    UUIDs and required fields must not be auto-filled — those are real
    decisions, not safe defaults.
    """

    default = field.get("default_value")
    if default is None:
        return False
    if field.get("required"):
        return False
    if (field.get("data_type") or "").lower() == "uuid":
        return False
    return True


# --- warnings ------------------------------------------------------------


def _flatten_pipeline_warnings(
    pipeline_results: list[dict[str, Any]],
) -> list[str]:
    """Flatten any per-pipeline warnings into a single string list."""

    out: list[str] = []
    for entry in pipeline_results or []:
        if not isinstance(entry, dict):
            continue
        warnings = entry.get("warnings") or []
        if not isinstance(warnings, list):
            continue
        for w in warnings:
            if w is None:
                continue
            out.append(str(w))
    return out


def _collect_general_warnings(
    route_plan: dict[str, Any], warnings: list[str] | None
) -> list[str]:
    out: list[str] = list(warnings or [])
    plan_warnings = route_plan.get("general_warnings") or []
    if isinstance(plan_warnings, list):
        out.extend(str(w) for w in plan_warnings if w is not None)
    return out
