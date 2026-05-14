"""DeepSeek schema-routed extractor provider.

For every ``PipelineSelection`` the orchestrator hands in, this provider:

1. Builds a canonical company table/field JSON Schema from the tenant catalog.
2. Builds a schema-extraction prompt that bundles the schema, shared
   extraction rules, and the OCR markdown.
3. Calls the configured DeepSeek parse model through ``call_claude`` (the
   Anthropic-compatible wrapper). ``call_claude`` already handles the
   DeepSeek-compat endpoint quirk where tool_use is unreliable and silently
   downgrades the tool spec to "reply with JSON only".
4. Parses the tool-use input via ``extract_tool_use_input``.
5. Validates that the parsed result is a ``dict`` (not a list or string).
6. Returns one :class:`PipelineExtractResult` per schema.

Per-schema failures are soft: an empty ``extraction`` plus a warning, so a
single bad LLM response cannot poison the entire batch. ``input.session`` is
always forwarded to ``call_claude`` so the ``llm_calls`` audit row is
persisted — we intentionally do not hide that DB dependency.
"""

from __future__ import annotations

import logging

from yunwei_win.config import settings
from yunwei_win.services.ingest.extractors.canonical_schema import (
    build_pipeline_schema_json,
)
from yunwei_win.services.ingest.progress import emit_progress
from yunwei_win.services.ingest.pipeline_schemas import PipelineExtractResult
from yunwei_win.services.llm import call_claude, extract_tool_use_input
from yunwei_win.services.prompts import find_prompt

from .base import ExtractionInput, ExtractorProvider, ProgressCallback

logger = logging.getLogger(__name__)


# How much OCR markdown we hand to the LLM per schema call. Mirrors the cap
# used by the identity/commercial extractors so behavior is consistent.
_LLM_CONTEXT_CHARS = 30000

_PROMPT_PATH = find_prompt("schema_extraction.md")


def _tool_name_for(schema_name: str) -> str:
    return f"submit_{schema_name}_extraction"


def _build_tool(schema_name: str, schema_json: str) -> dict:
    """Anthropic-format tool descriptor that wraps the static schema JSON.

    The schema JSON is parsed and embedded as ``input_schema``. On
    DeepSeek-compat upstreams ``call_claude`` will convert this into a
    "reply with JSON only" prompt automatically.
    """
    import json

    schema_obj = json.loads(schema_json)
    return {
        "name": _tool_name_for(schema_name),
        "description": (
            f"Submit the {schema_name} fields extracted from the document's "
            "OCR markdown. Fill missing fields with null; do not fabricate."
        ),
        "input_schema": schema_obj,
    }


def _build_prompt(schema_name: str, schema_json: str, markdown: str) -> str:
    """Substitute the placeholders into the shared schema-extraction prompt.

    We use ``str.replace`` rather than ``str.format`` because the prompt body
    contains JSON snippets with ``{...}`` braces that ``format`` would
    mis-interpret as positional fields.
    """
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    truncated_md = (markdown or "(no text extracted)")[:_LLM_CONTEXT_CHARS]
    return (
        template.replace("{schema_name}", schema_name)
        .replace("{schema_json}", schema_json)
        .replace("{markdown}", truncated_md)
    )


class DeepSeekSchemaExtractorProvider(ExtractorProvider):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]:
        results: list[PipelineExtractResult] = []
        model = settings.model_parse

        for selection in input.selections:
            schema_name = selection.name
            await emit_progress(
                progress,
                "schema_extract",
                f"DeepSeek 抽取 {schema_name}",
            )

            metadata: dict = {"provider": "deepseek", "model": model}

            try:
                schema_json = build_pipeline_schema_json(
                    schema_name, input.company_schema
                )
                tool = _build_tool(schema_name, schema_json)
                tool_name = tool["name"]
                prompt = _build_prompt(schema_name, schema_json, input.markdown)
                messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ]

                response = await call_claude(
                    messages,
                    purpose=f"deepseek_schema_extract:{schema_name}",
                    session=input.session,
                    model=model,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool_name},
                    max_tokens=8192,
                    temperature=0,
                    document_id=input.document_id,
                )
                tool_input = extract_tool_use_input(response, tool_name)

                if not isinstance(tool_input, dict):
                    raise ValueError(
                        f"expected dict from extract_tool_use_input, got "
                        f"{type(tool_input).__name__}"
                    )

                results.append(
                    PipelineExtractResult(
                        name=schema_name,
                        extraction=tool_input,
                        extraction_metadata=metadata,
                        warnings=[],
                    )
                )
            except Exception as exc:  # noqa: BLE001 — per-schema soft failure
                logger.warning(
                    "DeepSeek schema extract failed for %s: %r",
                    schema_name,
                    exc,
                )
                results.append(
                    PipelineExtractResult(
                        name=schema_name,
                        extraction={},
                        extraction_metadata=metadata,
                        warnings=[
                            f"DeepSeek extract failed for {schema_name}: {exc}"
                        ],
                    )
                )

        await emit_progress(progress, "schema_extract_done", "DeepSeek 抽取完成")
        return results
