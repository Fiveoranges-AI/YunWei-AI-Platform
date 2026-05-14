"""Selected-table router.

Asks an LLM which catalog tables a parse artifact actually contains
business data for, then keeps only those that are real catalog tables.
On any router failure (LLM exception or zero selected tables after
filtering) we fall back to a conservative core set so review still has
somewhere to land instead of silently dropping the document.

The router selects **table names**, never legacy pipeline names — the
downstream extraction schema builder is the only thing that mints
JSON schema, so the router's only job is "what's in this document".
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact


# Fallback table set when the router can't trust an LLM response. Picked
# to cover the bare minimum a reviewer can act on: who is the customer,
# who do we know there, and what notes are sitting on the timeline.
_FAIL_OPEN_TABLES: tuple[str, ...] = (
    "customers",
    "contacts",
    "customer_journal_items",
)

# Cap on how much markdown we ever send to the LLM. The router only needs
# a topical glance; full extraction happens downstream against the schema.
_MARKDOWN_BUDGET = 12000


class SelectedTable(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_name: str
    confidence: float | None = None
    reason: str | None = None


class RejectedTable(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_name: str
    reason: str | None = None


class TableRouteResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    selected_tables: list[SelectedTable] = Field(default_factory=list)
    rejected_tables: list[RejectedTable] = Field(default_factory=list)
    document_summary: str | None = None
    needs_human_attention: bool = False
    warnings: list[str] = Field(default_factory=list)


async def route_tables(
    *,
    parse_artifact: ParseArtifact,
    catalog: dict[str, Any],
    llm: Any | None = None,
) -> TableRouteResult:
    """Pick which catalog tables this document likely has data for."""

    active_tables = _active_tables(catalog)
    active_names = {t["table_name"] for t in active_tables}

    if llm is None:
        return _fail_open("router failed: no llm configured")

    prompt = _build_prompt(parse_artifact, active_tables)
    response_schema = _build_response_schema()

    try:
        raw = await llm.complete_json(prompt=prompt, response_schema=response_schema)
    except Exception as exc:
        return _fail_open(f"router failed: {type(exc).__name__}: {exc!s}")

    if not isinstance(raw, dict):
        return _fail_open("router failed: response was not an object")

    warnings: list[str] = []
    selected: list[SelectedTable] = []
    seen: set[str] = set()
    for entry in raw.get("selected_tables") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("table_name")
        if not isinstance(name, str) or not name:
            continue
        if name not in active_names:
            warnings.append(f"ignored unknown table from router: {name}")
            continue
        if name in seen:
            continue
        seen.add(name)
        selected.append(
            SelectedTable(
                table_name=name,
                confidence=_coerce_float(entry.get("confidence")),
                reason=_coerce_str(entry.get("reason")),
            )
        )

    rejected: list[RejectedTable] = []
    for entry in raw.get("rejected_tables") or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("table_name")
        if not isinstance(name, str) or not name:
            continue
        rejected.append(
            RejectedTable(table_name=name, reason=_coerce_str(entry.get("reason")))
        )

    if not selected:
        result = _fail_open("router failed: no tables selected")
        result.warnings = warnings + result.warnings
        return result

    return TableRouteResult(
        selected_tables=selected,
        rejected_tables=rejected,
        document_summary=_coerce_str(raw.get("document_summary")),
        needs_human_attention=bool(raw.get("needs_human_attention", False)),
        warnings=warnings,
    )


def _fail_open(reason: str) -> TableRouteResult:
    return TableRouteResult(
        selected_tables=[SelectedTable(table_name=name) for name in _FAIL_OPEN_TABLES],
        rejected_tables=[],
        document_summary=None,
        needs_human_attention=True,
        warnings=[reason],
    )


def _active_tables(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for table in catalog.get("tables") or []:
        if not isinstance(table, dict):
            continue
        if table.get("is_active", True) is False:
            continue
        name = table.get("table_name")
        if isinstance(name, str) and name:
            out.append(table)
    return out


def _build_prompt(parse_artifact: ParseArtifact, active_tables: list[dict[str, Any]]) -> str:
    markdown = (parse_artifact.markdown or "")[:_MARKDOWN_BUDGET]
    capabilities = parse_artifact.capabilities.model_dump()
    table_lines = [
        f"- {t.get('table_name')}: {t.get('label')} — {t.get('purpose') or ''}".rstrip(" —")
        for t in active_tables
    ]
    return (
        "你是合同/订单/财务文档的分类助手。下面是一份解析后的文档。\n"
        "请基于内容判断它包含哪些公司数据表的事实，并按下列 schema 返回 JSON。\n\n"
        f"## source_type\n{parse_artifact.source_type}\n\n"
        f"## parser_capabilities\n{json.dumps(capabilities, ensure_ascii=False)}\n\n"
        "## 候选数据表\n" + "\n".join(table_lines) + "\n\n"
        "## 文档内容（截断）\n" + markdown + "\n"
    )


def _build_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "selected_tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["table_name"],
                },
            },
            "rejected_tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["table_name"],
                },
            },
            "document_summary": {"type": "string"},
            "needs_human_attention": {"type": "boolean"},
        },
        "required": ["selected_tables"],
    }


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return str(value)
