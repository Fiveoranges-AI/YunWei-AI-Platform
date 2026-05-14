"""Normalized extraction contract.

Both LandingAI Extract and DeepSeek produce a per-table/per-row payload,
but in different shapes:

  LandingAI:  ``{"orders": {"amount_total": "30000"}}``
              ``{"contacts": [{"name": "张三"}, ...]}``
  DeepSeek:   ``{"tables": {"orders": [{"amount_total": {"value": ...,
                                                       "confidence": ...,
                                                       "source_refs": [...]}}]}}``

``normalize_extraction`` collapses both into ``NormalizedExtraction`` so
the rest of the pipeline (validation, entity resolution, review draft,
confirm writeback) never has to branch on provider.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from yunwei_win.services.schema_ingest.parse_artifact import ParseSourceRef


Provider = Literal["landingai", "deepseek"]


class NormalizedFieldValue(BaseModel):
    """One extracted field — provider-agnostic.

    ``raw`` carries the unparsed provider payload so we can audit what the
    model originally returned even after coercion.
    """

    model_config = ConfigDict(extra="allow")

    value: Any | None = None
    confidence: float | None = None
    source_refs: list[ParseSourceRef] = Field(default_factory=list)
    raw: Any | None = None


class NormalizedRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    client_row_id: str
    fields: dict[str, NormalizedFieldValue] = Field(default_factory=dict)


class NormalizedExtraction(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: Provider
    tables: dict[str, list[NormalizedRow]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def normalize_extraction(
    raw: Any,
    *,
    selected_tables: list[str],
    provider: Provider,
    metadata: dict[str, Any] | None = None,
) -> NormalizedExtraction:
    """Collapse provider-specific output into ``NormalizedExtraction``."""

    selected = set(selected_tables)
    meta: dict[str, Any] = dict(metadata or {})
    out_tables: dict[str, list[NormalizedRow]] = {}

    if not isinstance(raw, dict):
        meta.setdefault("normalize_warnings", []).append(
            f"extraction payload was not an object, got {type(raw).__name__}"
        )
        return NormalizedExtraction(provider=provider, tables={}, metadata=meta)

    # DeepSeek wraps the per-table dict under "tables"; LandingAI does not.
    table_payload = raw.get("tables") if isinstance(raw.get("tables"), dict) else raw

    dropped: list[str] = []
    for table_name, table_value in table_payload.items():
        if not isinstance(table_name, str):
            continue
        if table_name not in selected:
            dropped.append(table_name)
            continue
        rows = _normalize_table(table_name, table_value)
        if rows:
            out_tables[table_name] = rows

    if dropped:
        meta.setdefault("dropped_tables", []).extend(dropped)

    return NormalizedExtraction(provider=provider, tables=out_tables, metadata=meta)


def _normalize_table(table_name: str, value: Any) -> list[NormalizedRow]:
    if isinstance(value, list):
        rows: list[NormalizedRow] = []
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            rows.append(_normalize_row(table_name, idx, item))
        return rows
    if isinstance(value, dict):
        return [_normalize_row(table_name, 0, value)]
    return []


def _normalize_row(table_name: str, idx: int, row: dict[str, Any]) -> NormalizedRow:
    fields: dict[str, NormalizedFieldValue] = {}
    for field_name, field_value in row.items():
        if not isinstance(field_name, str):
            continue
        fields[field_name] = _normalize_field(field_value)
    return NormalizedRow(
        client_row_id=f"{table_name}:{idx}",
        fields=fields,
    )


def _normalize_field(value: Any) -> NormalizedFieldValue:
    # DeepSeek-style envelope: {"value": ..., "confidence": ..., "source_refs": [...]}
    if isinstance(value, dict) and (
        "value" in value or "confidence" in value or "source_refs" in value
    ):
        return NormalizedFieldValue(
            value=value.get("value"),
            confidence=_coerce_float(value.get("confidence")),
            source_refs=_coerce_source_refs(value.get("source_refs")),
            raw=value,
        )
    # LandingAI-style scalar — the field is the value itself.
    return NormalizedFieldValue(value=value, raw=value)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_source_refs(value: Any) -> list[ParseSourceRef]:
    if not isinstance(value, list):
        return []
    refs: list[ParseSourceRef] = []
    for entry in value:
        ref = _coerce_source_ref(entry)
        if ref is not None:
            refs.append(ref)
    return refs


def _coerce_source_ref(entry: Any) -> ParseSourceRef | None:
    if isinstance(entry, ParseSourceRef):
        return entry
    if isinstance(entry, str):
        return ParseSourceRef(ref_type=_infer_ref_type(entry), ref_id=entry)
    if isinstance(entry, dict):
        ref_id = entry.get("ref_id") or entry.get("id")
        if not isinstance(ref_id, str) or not ref_id:
            return None
        ref_type = entry.get("ref_type") or _infer_ref_type(ref_id)
        data = {**entry, "ref_type": ref_type, "ref_id": ref_id}
        return ParseSourceRef.model_validate(data)
    return None


def _infer_ref_type(ref_id: str) -> str:
    if ref_id.startswith("sheet:"):
        return "spreadsheet_cell"
    if ref_id.startswith("docx:"):
        return "docx_ref"
    if ref_id.startswith("chunk:"):
        return "chunk"
    if ref_id.startswith("text:"):
        return "text_span"
    if ref_id.startswith("page:"):
        return "page"
    return "unknown"
