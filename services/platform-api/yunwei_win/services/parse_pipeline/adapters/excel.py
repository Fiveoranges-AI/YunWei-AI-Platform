"""Excel adapter — sheet → SpreadsheetParser → candidate JSON.

Header detection strategy (kept deterministic, no LLM call):

  1. Reuse SpreadsheetParser to break the workbook into cells + grounding.
  2. For each sheet, treat the **first non-empty row** as the header row.
  3. For each header cell, ask ``ontology.find_canonical_field`` whether
     the header text matches a canonical ontology field — across every
     entity_type we know. Multiple entities can share the same sheet
     (e.g. an orders sheet whose columns include "customer name").
  4. Group columns by entity_type. Each data row produces one
     CandidateEntity per group that has at least one header hit.
  5. Confidence per cell = header-alias confidence (1.0 exact / 0.85
     substring) × value-presence factor (1.0 if value parses cleanly,
     0.7 if blank). source_span carries the cell id.
  6. Relationships: when a sheet contains both an Order entity and a
     Customer entity from the same row, emit Customer-has-Order. Same
     for Order/OrderLine (when an Order header appears next to OrderLine
     columns on the same row).

This is intentionally conservative — when a sheet doesn't match any
header alias, the adapter emits zero entities and adds a warning so
task ③ can route the file to a different adapter (e.g. contract / vision).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yunwei_win.services.parse_pipeline.candidate import (
    CandidateEntity,
    CandidateJSON,
    FieldCandidate,
    Relationship,
    SourceInfo,
    SourceSpan,
)
from yunwei_win.services.parse_pipeline.ontology import (
    find_canonical_field,
    header_match_confidence,
    required_fields,
)
from yunwei_win.services.schema_ingest.parsers.spreadsheet import SpreadsheetParser


logger = logging.getLogger(__name__)


# Which entity types the Excel adapter looks for, in priority order
# (used to break ties when a header matches multiple entities — e.g.
# "amount" could be Order.amount_total or Payment.amount; we prefer the
# entity already inferred from a stronger header elsewhere in the row).
_CANDIDATE_ENTITY_TYPES = (
    "Customer", "Contact", "Order", "OrderLine",
    "Contract", "Invoice", "Payment", "Product",
)


async def parse_excel(
    *,
    file_path: Path,
    filename: str,
    content_type: str | None = None,
    file_ref: str = "",
    uploaded_by: str | None = None,
    existing_customer_names: list[str] | None = None,
) -> CandidateJSON:
    parser = SpreadsheetParser()
    artifact = await parser.parse_file(
        file_path,
        filename=filename,
        content_type=content_type,
        source_type="spreadsheet",
    )

    entities: list[CandidateEntity] = []
    relationships: list[Relationship] = []
    warnings: list[str] = []
    field_confidences: list[float] = []

    for table in artifact.tables:
        sheet_name = table.sheet or table.id
        if not table.cells:
            continue

        # Group cells by row, indexed by col. cells row=1 is the
        # header row (or whichever first row has any text).
        rows: dict[int, dict[int, Any]] = {}
        for cell in table.cells:
            rows.setdefault(cell.row, {})[cell.col] = cell

        if not rows:
            continue
        first_row_idx = min(rows.keys())
        header_row = rows.pop(first_row_idx)

        # Map: col -> (entity_type, field_name, header_confidence)
        col_map: dict[int, tuple[str, str, float]] = {}
        for col_idx, hcell in header_row.items():
            header_text = str(hcell.text or "")
            best: tuple[str, str, float] | None = None
            for ent_type in _CANDIDATE_ENTITY_TYPES:
                conf = header_match_confidence(ent_type, header_text)
                if conf <= 0.0:
                    continue
                field_name = find_canonical_field(ent_type, header_text)
                if field_name is None:
                    continue
                if best is None or conf > best[2]:
                    best = (ent_type, field_name, conf)
            if best is not None:
                col_map[col_idx] = best

        if not col_map:
            warnings.append(
                f"工作表 '{sheet_name}' 未识别到本体字段表头,跳过"
            )
            continue

        entity_types_in_sheet = {ent for ent, _, _ in col_map.values()}

        # Per data row, produce one entity per entity_type seen on header row.
        for r_idx in sorted(rows.keys()):
            row_cells = rows[r_idx]
            if not any((str(c.text or "").strip()) for c in row_cells.values()):
                continue

            row_entities: dict[str, CandidateEntity] = {}

            for col_idx, (ent_type, field_name, header_conf) in col_map.items():
                cell = row_cells.get(col_idx)
                if cell is None:
                    continue
                raw_value = cell.text or ""
                raw_str = str(raw_value).strip()
                value_present_factor = 1.0 if raw_str else 0.4
                confidence = round(header_conf * value_present_factor, 3)

                ent = row_entities.setdefault(
                    ent_type,
                    CandidateEntity(
                        entity_type=ent_type,  # type: ignore[arg-type]
                        temp_id=f"{ent_type.lower()}-{sheet_name}-r{r_idx}",
                    ),
                )
                ent.fields.append(FieldCandidate(
                    name=field_name,
                    value=raw_str if raw_str else None,
                    confidence=confidence,
                    source_span=SourceSpan(cell=cell.ref_id or f"sheet:{sheet_name}!R{r_idx}C{col_idx}", text=raw_str or None),
                ))
                field_confidences.append(confidence)

            # Compute missing_required + emit.
            for ent_type, ent in row_entities.items():
                present_field_names = {f.name for f in ent.fields if f.value not in (None, "")}
                req = required_fields(ent_type)
                ent.missing_required = sorted(req - present_field_names)
                entities.append(ent)

            # Implicit relationships within a single row.
            row_temp_ids = {
                ent_type: ent.temp_id for ent_type, ent in row_entities.items()
            }
            if "Customer" in row_temp_ids and "Order" in row_temp_ids:
                relationships.append(Relationship(
                    from_temp_id=row_temp_ids["Customer"],
                    to_temp_id=row_temp_ids["Order"],
                    type="Customer-has-Order",
                ))
            if "Order" in row_temp_ids and "OrderLine" in row_temp_ids:
                relationships.append(Relationship(
                    from_temp_id=row_temp_ids["Order"],
                    to_temp_id=row_temp_ids["OrderLine"],
                    type="Order-has-OrderLine",
                ))
            if "Customer" in row_temp_ids and "Contact" in row_temp_ids:
                relationships.append(Relationship(
                    from_temp_id=row_temp_ids["Customer"],
                    to_temp_id=row_temp_ids["Contact"],
                    type="Customer-has-Contact",
                ))
            if "Customer" in row_temp_ids and "Payment" in row_temp_ids:
                relationships.append(Relationship(
                    from_temp_id=row_temp_ids["Customer"],
                    to_temp_id=row_temp_ids["Payment"],
                    type="Customer-has-Payment",
                ))

        if "Customer" not in entity_types_in_sheet and "Order" in entity_types_in_sheet:
            warnings.append(
                f"工作表 '{sheet_name}' 含订单字段但未识别客户列,后续需手工指定客户"
            )

    # Customer dedup warnings (fuzzy match against existing names).
    if existing_customer_names:
        _add_dedup_warnings(entities, existing_customer_names, warnings)

    overall = _overall_confidence(field_confidences, entities)

    if not entities:
        warnings.append("未从该 Excel 抽取到任何候选实体")

    logger.info(
        "parse_pipeline.excel filename=%s sheets=%d entities=%d overall_conf=%.3f",
        filename, len(artifact.tables), len(entities), overall,
    )

    return CandidateJSON(
        source=SourceInfo(
            type="excel",
            file_ref=file_ref or filename,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
        ),
        entities=entities,
        relationships=relationships,
        overall_confidence=overall,
        warnings=warnings,
    )


def _add_dedup_warnings(
    entities: list[CandidateEntity],
    existing: list[str],
    warnings: list[str],
) -> None:
    """Flag candidate Customers whose full_name fuzzy-matches an existing row."""
    import difflib

    for ent in entities:
        if ent.entity_type != "Customer":
            continue
        name_field = next((f for f in ent.fields if f.name == "full_name"), None)
        if not name_field or not name_field.value:
            continue
        new_name = str(name_field.value).strip().lower()
        for existing_name in existing:
            existing_norm = existing_name.strip().lower()
            if new_name == existing_norm:
                warnings.append(
                    f"客户 '{name_field.value}' 与已有客户完全同名,疑似重复"
                )
                break
            ratio = difflib.SequenceMatcher(None, new_name, existing_norm).ratio()
            if ratio >= 0.85:
                warnings.append(
                    f"客户 '{name_field.value}' 与已有 '{existing_name}' 高度相似 (相似度 {ratio:.2f})"
                )
                break


def _overall_confidence(
    confidences: list[float],
    entities: list[CandidateEntity],
) -> float:
    if not confidences:
        return 0.0
    weighted_sum = sum(confidences)
    n = len(confidences)
    base = weighted_sum / n
    # Penalty when any entity is missing required fields.
    missing_count = sum(len(e.missing_required) for e in entities)
    if missing_count:
        base *= max(0.4, 1.0 - 0.05 * missing_count)
    return round(min(1.0, max(0.0, base)), 3)
