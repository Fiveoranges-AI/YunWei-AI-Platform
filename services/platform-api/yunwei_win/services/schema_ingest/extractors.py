"""vNext extractor provider dispatch.

Single entry point — ``extract_from_parse_artifact`` — that picks the
right provider, builds the field-role-filtered JSON schema, calls the
provider, and returns a ``NormalizedExtraction``.

Provider matrix (mirrors ``schema_ingest/file_type.py``):

  PDF / image / PPTX  ->  LandingAI Parse + LandingAI Extract
  text / DOCX / xlsx  ->  native parser   + DeepSeek Extract

LandingAI extract is called through the existing ADE client; DeepSeek is
called through any object exposing ``async complete_json(prompt,
response_schema)``. ``auto_ingest`` wires the production adapter
``schema_ingest.llm_adapter.DeepSeekCompleteJsonLLM`` and passes it in.
Tests inject their own fake so no network call happens.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.services.landingai_ade_client import extract_with_schema
from yunwei_win.services.schema_ingest.extraction_normalize import (
    NormalizedExtraction,
    normalize_extraction,
)
from yunwei_win.services.schema_ingest.extraction_schema import (
    build_selected_tables_schema_json,
)
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact


Provider = Literal["landingai", "deepseek"]


_DEEPSEEK_MARKDOWN_BUDGET = 30000


async def extract_from_parse_artifact(
    *,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    catalog: dict[str, Any],
    provider: Provider,
    session: AsyncSession | None = None,
    llm: Any | None = None,
) -> NormalizedExtraction:
    """Run the chosen extractor against a parse artifact + catalog slice."""

    schema_json = build_selected_tables_schema_json(selected_tables, catalog)

    if provider == "landingai":
        return await _extract_landingai(
            parse_artifact=parse_artifact,
            selected_tables=selected_tables,
            schema_json=schema_json,
        )
    if provider == "deepseek":
        if llm is None:
            raise RuntimeError(
                "deepseek extractor requires an llm with complete_json(); "
                "auto_ingest injects DeepSeekCompleteJsonLLM — pass one in "
                "when calling this function directly"
            )
        return await _extract_deepseek(
            parse_artifact=parse_artifact,
            selected_tables=selected_tables,
            schema_json=schema_json,
            llm=llm,
        )
    raise ValueError(f"unsupported extractor provider: {provider!r}")


async def _extract_landingai(
    *,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    schema_json: str,
) -> NormalizedExtraction:
    response = await extract_with_schema(
        schema_json=schema_json, markdown=parse_artifact.markdown or ""
    )

    normalized = normalize_extraction(
        getattr(response, "extraction", {}) or {},
        selected_tables=selected_tables,
        provider="landingai",
        metadata={
            "extraction_metadata": dict(getattr(response, "extraction_metadata", {}) or {}),
            "landingai_metadata": dict(getattr(response, "metadata", {}) or {}),
        },
    )

    _enrich_with_landingai_metadata(normalized)
    return normalized


def _enrich_with_landingai_metadata(normalized: NormalizedExtraction) -> None:
    """Copy LandingAI's chunk_references into each field's source_refs.

    LandingAI's extract response carries grounding under
    ``extraction_metadata`` keyed by JSON pointer-like strings such as
    ``"orders.amount_total"`` or ``"contacts[0].name"``. The values look
    like ``{"chunk_references": ["c1", ...]}``. We map them onto the
    matching NormalizedFieldValue so downstream review can render
    evidence regardless of which extractor produced it.
    """

    from yunwei_win.services.schema_ingest.extraction_normalize import (
        _coerce_source_refs,
    )

    extraction_metadata = normalized.metadata.get("extraction_metadata") or {}
    if not isinstance(extraction_metadata, dict):
        return

    for key, meta in extraction_metadata.items():
        if not isinstance(meta, dict):
            continue
        chunk_refs = meta.get("chunk_references")
        if not isinstance(chunk_refs, list) or not chunk_refs:
            continue
        table_name, row_idx, field_name = _parse_extraction_metadata_key(key)
        if table_name is None or field_name is None:
            continue
        rows = normalized.tables.get(table_name)
        if not rows:
            continue
        if row_idx is None:
            row_idx = 0
        if row_idx >= len(rows):
            continue
        field = rows[row_idx].fields.get(field_name)
        if field is None:
            continue
        if not field.source_refs:
            field.source_refs = _coerce_source_refs(chunk_refs)


def _parse_extraction_metadata_key(
    key: str,
) -> tuple[str | None, int | None, str | None]:
    """Parse ``"orders.amount_total"`` or ``"contacts[0].name"``."""

    if not isinstance(key, str) or "." not in key:
        return None, None, None
    head, _, field_name = key.rpartition(".")
    if "[" in head and head.endswith("]"):
        table_name, _, idx_str = head[:-1].partition("[")
        try:
            return table_name or None, int(idx_str), field_name or None
        except ValueError:
            return table_name or None, None, field_name or None
    return head or None, None, field_name or None


async def _extract_deepseek(
    *,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    schema_json: str,
    llm: Any,
) -> NormalizedExtraction:
    prompt = _build_deepseek_prompt(
        parse_artifact=parse_artifact,
        selected_tables=selected_tables,
        schema_json=schema_json,
    )
    response_schema = _deepseek_response_schema()

    raw = await llm.complete_json(prompt=prompt, response_schema=response_schema)

    return normalize_extraction(
        raw or {},
        selected_tables=selected_tables,
        provider="deepseek",
        metadata={"llm_prompt_chars": len(prompt)},
    )


def _build_deepseek_prompt(
    *,
    parse_artifact: ParseArtifact,
    selected_tables: list[str],
    schema_json: str,
) -> str:
    markdown = (parse_artifact.markdown or "")[:_DEEPSEEK_MARKDOWN_BUDGET]
    return (
        "你是结构化抽取助手。请只从下面给定的文档中抽取真实存在的事实，"
        "不要编造。\n\n"
        f"## 目标表\n{', '.join(selected_tables)}\n\n"
        f"## 抽取 schema\n{schema_json}\n\n"
        "返回 JSON，键为 `tables`，每张表是行数组，每个字段必须以"
        " `{value, confidence, source_refs}` 形式给出。\n"
        "- `value`：和 schema 一致的字符串/数字。\n"
        "- `confidence`：0~1 的浮点数，表示该值的把握。\n"
        "- `source_refs`：来源 ID 列表，必须取自 parse artifact 的"
        " chunks/grounding/table cell IDs。\n\n"
        f"## source_type\n{parse_artifact.source_type}\n\n"
        f"## 文档内容（截断）\n{markdown}\n"
    )


def _deepseek_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "tables": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "value": {},
                                "confidence": {"type": "number"},
                                "source_refs": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        },
        "required": ["tables"],
    }
