"""Materialize a schema-first ReviewDraft from extractor output + catalog.

Invariant:
    For every selected table, the draft's cells == the active fields in
    ``company_schema_fields``. Extraction sparsity changes cell status,
    not cell existence.

Pipeline -> table mapping is the schema-first contract that decides which catalog
tables get materialized for a document. Mapping unknown pipelines is treated
as a soft warning (skip), not a fatal error — the extractor may evolve
faster than this map.

Pipeline results are expected to be ``PipelineExtractResult.model_dump()``
items, with extracted table data under the canonical ``extraction`` key.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from yunwei_win.services.ingest.extractors.canonical_schema import PIPELINE_TABLES
from yunwei_win.services.schema_ingest.fk_links import FK_FIELD_PARENTS


def _is_parseable_uuid(value: Any) -> bool:
    """Cheap check used to disarm extractor cross-row placeholders.

    LLMs frequently emit synthetic FK strings like ``"customer-1"`` for uuid
    FK fields. We only want to keep an extracted value when it could plausibly
    be a real UUID; otherwise the FK is better handled by the same-confirm
    parent auto-link in writeback.
    """

    if value is None:
        return False
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False
from yunwei_win.services.schema_ingest.entity_resolution import (
    EntityResolutionProposal,
    EntityResolutionRow,
)
from yunwei_win.services.schema_ingest.extraction_normalize import (
    NormalizedExtraction,
    NormalizedFieldValue,
    NormalizedRow,
)
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact
from yunwei_win.services.schema_ingest.schemas import (
    ReviewCell,
    ReviewCellEvidence,
    ReviewDraft,
    ReviewDraftDocument,
    ReviewDraftRoutePlan,
    ReviewEntityCandidate,
    ReviewRow,
    ReviewRowDecision,
    ReviewSourceRef,
    ReviewStep,
    ReviewTable,
)


_LOW_CONFIDENCE_THRESHOLD = 0.6


# vNext progressive review wizard step plan. The order is fixed; empty steps
# are dropped at materialization time, and ``summary`` is always appended if
# any prior step survives.
_VNEXT_STEP_PLAN: list[tuple[str, str, list[str]]] = [
    ("customer", "客户", ["customers"]),
    ("contacts", "联系人", ["contacts"]),
    (
        "commercial",
        "合同 / 订单",
        ["contracts", "orders", "contract_payment_milestones"],
    ),
    ("finance", "发票 / 付款", ["invoices", "invoice_items", "payments"]),
    (
        "logistics_product",
        "物流 / 产品",
        ["shipments", "shipment_items", "products", "product_requirements"],
    ),
    ("memory", "时间线 / 待办", ["customer_journal_items", "customer_tasks"]),
]
_VNEXT_SUMMARY_STEP = ("summary", "总览确认", [])

# vNext presentation hints. Anything not listed falls back to "table".
_VNEXT_CARD_TABLES = {
    "customers",
    "contacts",
    "contracts",
    "orders",
    "invoices",
}
_VNEXT_TABLE_TABLES = {
    "invoice_items",
    "shipment_items",
    "contract_payment_milestones",
    "product_requirements",
}

_HIDDEN_FIELD_ROLES = {"system_link", "audit"}


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
        pipeline_results: ``[{"name": pipeline_name, "extraction": {...}, "warnings": [...]}]``.
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
        tables.append(
            _build_review_table(
                table_spec,
                extraction_by_table.get(table_name),
                selected_table_names=selected_table_names,
            )
        )

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
        payload = result_entry.get("extraction") or {}
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

    Extractors are constrained by the tenant company schema, so table names
    must match catalog table names exactly.
    """

    return payload.get(table_name)


# --- per-table materialization ------------------------------------------


def _build_review_table(
    table_spec: dict[str, Any],
    raw_extraction: Any,
    *,
    selected_table_names: set[str],
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
        cells = [
            _build_cell(field, item_data, selected_table_names=selected_table_names)
            for field in fields
        ]
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


def _build_cell(
    field: dict[str, Any],
    item_data: dict[str, Any],
    *,
    selected_table_names: set[str],
) -> ReviewCell:
    """Decide value/status/source/confidence/evidence for one cell.

    Status decision tree:
      1. Raw value present (not None) -> ``extracted`` (or ``low_confidence``
         when confidence < threshold), source ``ai``.
      2. Field has a non-uuid, non-required ``default_value`` -> use it,
         status ``extracted``, source ``default``.
      3. FK field whose parent table is also being materialized in this
         draft -> status ``missing``, source ``linked``. Confirm fills the
         UUID at writeback; the UI shows a "auto-linked" chip instead of a
         "missing required" warning.
      4. Otherwise -> status ``missing``, source ``empty``.

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

    # Disarm synthetic FK placeholders ("customer-1", "contract-1", ...) the
    # LLM emits for uuid FK fields whose parent table is also in this draft.
    # Falling through to the "auto-linked" branch below means confirm fills
    # the real UUID at writeback instead of failing UUID validation.
    if (
        value is not None
        and (field.get("data_type") or "").lower() == "uuid"
        and field_name in FK_FIELD_PARENTS
        and _is_auto_linked_fk(field_name, selected_table_names)
        and not _is_parseable_uuid(value)
    ):
        value = None
        confidence = None
        evidence_data = None

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
    elif _is_auto_linked_fk(field_name, selected_table_names):
        # Parent table is being confirmed in the same draft; confirm
        # writeback fills this UUID — the reviewer should not be asked to
        # provide it.
        value = None
        status = "missing"
        source = "linked"
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


def _is_auto_linked_fk(field_name: str, selected_table_names: set[str]) -> bool:
    """True when ``field_name`` is an FK whose parent is in the same draft."""

    parent_table = FK_FIELD_PARENTS.get(field_name)
    if parent_table is None:
        return False
    return parent_table in selected_table_names


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


# ---------------------------------------------------------------------------
# vNext materializer.
#
# Produces a ``ReviewDraft`` from:
#   - normalized extraction (provider-agnostic table -> rows -> fields)
#   - entity resolution proposal (per-row create / update / link decision)
#   - parse artifact (source refs we copy onto each cell)
#   - active catalog (drives table order, field role, presentation)
# ---------------------------------------------------------------------------


def materialize_review_draft_vnext(
    *,
    extraction_id: UUID,
    document_id: UUID,
    parse_id: UUID,
    document_filename: str,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    normalized_extraction: NormalizedExtraction,
    entity_resolution: EntityResolutionProposal,
    catalog: dict[str, Any],
    document_summary: str | None,
    warnings: list[str],
) -> ReviewDraft:
    """Build a vNext progressive ReviewDraft.

    Rules (see plan Task 6 for the canonical list):
      - only ``selected_tables`` make it into ``draft.tables``;
      - only fields with ``review_visible`` and a non-system role become
        ``ReviewCell``s — ``system_link`` / ``audit`` never appear;
      - extracted values become ``status=extracted`` (or ``low_confidence``);
      - rows with neither AI values nor an explicit row decision are non-
        writable and their row decision is forced to ``ignore``;
      - tables are routed into the fixed progressive-review step plan;
        empty steps are dropped, and a final ``summary`` step is appended
        whenever any other step survives.
    """

    selected_set = {t for t in selected_tables if isinstance(t, str)}
    catalog_tables = catalog.get("tables") or []
    catalog_by_name = {
        t["table_name"]: t
        for t in catalog_tables
        if isinstance(t, dict) and isinstance(t.get("table_name"), str)
    }

    resolution_by_row = _index_entity_resolution(entity_resolution)

    schema_warnings: list[str] = []
    for missing in sorted(selected_set - catalog_by_name.keys()):
        schema_warnings.append(
            f"selected_table {missing!r} not present in active catalog"
        )

    tables: list[ReviewTable] = []
    for table_spec in catalog_tables:
        if not isinstance(table_spec, dict):
            continue
        table_name = table_spec.get("table_name")
        if not isinstance(table_name, str) or table_name not in selected_set:
            continue
        tables.append(
            _build_vnext_table(
                table_spec=table_spec,
                normalized_rows=normalized_extraction.tables.get(table_name) or [],
                resolution_by_row=resolution_by_row,
            )
        )

    steps = _build_steps(tables)
    current_step = steps[0].key if steps else None

    return ReviewDraft(
        extraction_id=extraction_id,
        document_id=document_id,
        parse_id=parse_id,
        schema_version=1,
        status="pending_review",
        review_version=0,
        current_step=current_step,
        document=ReviewDraftDocument(
            filename=document_filename,
            summary=document_summary,
            source_text=parse_artifact.markdown or None,
        ),
        route_plan=ReviewDraftRoutePlan(),
        steps=steps,
        tables=tables,
        schema_warnings=schema_warnings,
        general_warnings=list(warnings or []),
    )


# ---------------------------------------------------------------------------
# vNext helpers
# ---------------------------------------------------------------------------


def _index_entity_resolution(
    proposal: EntityResolutionProposal,
) -> dict[tuple[str, str], EntityResolutionRow]:
    return {
        (row.table_name, row.client_row_id): row for row in proposal.rows or []
    }


def _build_vnext_table(
    *,
    table_spec: dict[str, Any],
    normalized_rows: list[NormalizedRow],
    resolution_by_row: dict[tuple[str, str], EntityResolutionRow],
) -> ReviewTable:
    table_name = str(table_spec["table_name"])
    is_array_table = bool(table_spec.get("is_array"))
    field_specs = _active_visible_field_specs(table_spec)

    # Scalar / master tables always render one row so the reviewer has somewhere
    # to fill in master fields. Array tables only render rows that came back
    # from extraction; empty arrays just show a "nothing extracted" presentation
    # and stay non-writable.
    rows_source: list[NormalizedRow]
    if normalized_rows:
        rows_source = list(normalized_rows)
    elif not is_array_table:
        rows_source = [NormalizedRow(client_row_id=f"{table_name}:0", fields={})]
    else:
        rows_source = []

    rows: list[ReviewRow] = []
    for row in rows_source:
        rows.append(
            _build_vnext_row(
                table_name=table_name,
                normalized_row=row,
                field_specs=field_specs,
                resolution=resolution_by_row.get((table_name, row.client_row_id)),
            )
        )

    return ReviewTable(
        table_name=table_name,
        label=str(table_spec.get("label") or table_name),
        purpose=table_spec.get("purpose"),
        category=table_spec.get("category"),
        is_array=is_array_table,
        rows=rows,
        presentation=_presentation_for(table_name),
        review_step=_step_for(table_name),
    )


def _active_visible_field_specs(table_spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for field in table_spec.get("fields") or []:
        if not isinstance(field, dict):
            continue
        if field.get("is_active", True) is False:
            continue
        if field.get("review_visible") is False:
            continue
        # Default missing field_role to extractable so legacy seed data and
        # add_field proposals from before vNext don't silently vanish.
        role = field.get("field_role") or "extractable"
        if role in _HIDDEN_FIELD_ROLES:
            continue
        out.append(field)
    out.sort(key=lambda f: (f.get("sort_order", 0), f.get("field_name", "")))
    return out


def _build_vnext_row(
    *,
    table_name: str,
    normalized_row: NormalizedRow,
    field_specs: list[dict[str, Any]],
    resolution: EntityResolutionRow | None,
) -> ReviewRow:
    cells: list[ReviewCell] = []
    has_ai_value = False
    for field in field_specs:
        normalized_value = normalized_row.fields.get(field["field_name"])
        cell = _build_vnext_cell(field, normalized_value)
        cells.append(cell)
        if cell.status in {"extracted", "low_confidence"}:
            has_ai_value = True

    decision_source = resolution or EntityResolutionRow(
        table_name=table_name,
        client_row_id=normalized_row.client_row_id,
        proposed_operation="create",
        match_level="none",
    )

    has_explicit_link = (
        decision_source.proposed_operation in {"update", "link_existing"}
        and decision_source.selected_entity_id is not None
    )
    is_writable = has_ai_value or has_explicit_link

    if is_writable:
        row_decision = _build_row_decision(decision_source)
    else:
        # Default-only / empty row — confirm must skip it.
        row_decision = ReviewRowDecision(
            operation="ignore",
            selected_entity_id=None,
            candidate_entities=[
                ReviewEntityCandidate(
                    entity_id=c.entity_id,
                    label=c.label,
                    match_level=c.match_level,
                    match_keys=list(c.match_keys),
                    confidence=c.confidence,
                    reason=c.reason,
                )
                for c in (decision_source.candidates or [])
            ],
            match_level=decision_source.match_level,
            match_keys=list(decision_source.match_keys),
            reason=decision_source.reason
            or "row has no extracted values or explicit decision",
        )

    return ReviewRow(
        client_row_id=normalized_row.client_row_id,
        entity_id=(
            decision_source.selected_entity_id if has_explicit_link else None
        ),
        operation=(
            "update"
            if decision_source.proposed_operation == "update"
            else "create"
        ),
        cells=cells,
        row_decision=row_decision,
        is_writable=is_writable,
    )


def _build_row_decision(decision: EntityResolutionRow) -> ReviewRowDecision:
    return ReviewRowDecision(
        operation=decision.proposed_operation,
        selected_entity_id=decision.selected_entity_id,
        candidate_entities=[
            ReviewEntityCandidate(
                entity_id=c.entity_id,
                label=c.label,
                match_level=c.match_level,
                match_keys=list(c.match_keys),
                confidence=c.confidence,
                reason=c.reason,
            )
            for c in (decision.candidates or [])
        ],
        match_level=decision.match_level,
        match_keys=list(decision.match_keys),
        reason=decision.reason,
    )


def _build_vnext_cell(
    field_spec: dict[str, Any],
    normalized_value: NormalizedFieldValue | None,
) -> ReviewCell:
    field_name = str(field_spec["field_name"])
    label = str(field_spec.get("label") or field_name)
    data_type = str(field_spec.get("data_type") or "text")
    required = bool(field_spec.get("required", False))
    is_array = bool(field_spec.get("is_array", False))

    if normalized_value is None or normalized_value.value in (None, ""):
        return ReviewCell(
            field_name=field_name,
            label=label,
            data_type=data_type,
            required=required,
            is_array=is_array,
            value=None,
            display_value="",
            status="missing",
            confidence=None,
            evidence=None,
            source="empty",
            source_refs=[],
            review_visible=True,
            explicit_clear=False,
        )

    confidence = normalized_value.confidence
    status: str = "extracted"
    if confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD:
        status = "low_confidence"

    value = normalized_value.value
    display_value = "" if value is None else str(value)

    return ReviewCell(
        field_name=field_name,
        label=label,
        data_type=data_type,
        required=required,
        is_array=is_array,
        value=value,
        display_value=display_value,
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
        evidence=None,
        source="ai",
        source_refs=[
            ReviewSourceRef(**ref.model_dump()) for ref in normalized_value.source_refs
        ],
        review_visible=True,
        explicit_clear=False,
    )


def _presentation_for(table_name: str) -> str:
    if table_name in _VNEXT_CARD_TABLES:
        return "card"
    if table_name in _VNEXT_TABLE_TABLES:
        return "table"
    return "table"


def _step_for(table_name: str) -> str | None:
    for key, _label, names in _VNEXT_STEP_PLAN:
        if table_name in names:
            return key
    return None


def _build_steps(tables: list[ReviewTable]) -> list[ReviewStep]:
    """Build the progressive step list, skipping steps with no tables."""

    tables_by_step: dict[str, list[str]] = {}
    for table in tables:
        if table.review_step:
            tables_by_step.setdefault(table.review_step, []).append(table.table_name)

    steps: list[ReviewStep] = []
    for key, label, _names in _VNEXT_STEP_PLAN:
        if key in tables_by_step:
            steps.append(
                ReviewStep(
                    key=key,
                    label=label,
                    table_names=tables_by_step[key],
                    status="in_progress",
                )
            )

    if steps:
        steps.append(
            ReviewStep(
                key=_VNEXT_SUMMARY_STEP[0],
                label=_VNEXT_SUMMARY_STEP[1],
                table_names=[],
                status="empty",
            )
        )

    return steps
