"""Materialize a vNext ReviewDraft from normalized extraction + catalog.

Invariant:
    For every selected table, the draft's review cells are the active
    review-visible catalog fields (``field_role in {extractable,
    identity_key}``). Extraction sparsity changes cell status, not cell
    existence.

The legacy pipeline-shaped materializer (PIPELINE_TABLES / route_plan /
pipeline_results) was removed in Task 13 — see ``materialize_review_draft_vnext``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

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
