"""DeepSeek / Anthropic ``complete_json`` adapter for vNext ingest.

``route_tables`` and ``extract_from_parse_artifact(provider="deepseek")``
both accept an object exposing::

    async def complete_json(prompt: str, response_schema: dict) -> dict

so tests can inject fakes without going through ``call_claude``.
Production code wants the real LLM, with the response constrained to a
JSON object that matches ``response_schema``. This adapter does exactly
that:

  * wraps the schema as an Anthropic tool ``input_schema``;
  * forces ``tool_choice`` so the model has to call the tool;
  * unwraps the tool input back to a plain ``dict``.

On DeepSeek-compatible endpoints ``call_claude`` automatically rewrites
the tool spec into a "reply with JSON only" prompt and
``extract_tool_use_input`` picks the JSON out of the assistant text —
the call site here doesn't have to special-case that.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.services.llm import call_claude, extract_tool_use_input


_DEFAULT_TOOL_NAME = "submit_schema_ingest_json"


class DeepSeekCompleteJsonLLM:
    """Adapter exposing ``complete_json(prompt, response_schema)``."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        document_id: UUID | None = None,
        purpose_prefix: str = "schema_ingest",
        model: str | None = None,
        tool_name: str = _DEFAULT_TOOL_NAME,
    ) -> None:
        self._session = session
        self._document_id = document_id
        self._purpose_prefix = purpose_prefix
        self._model = model
        self._tool_name = tool_name

    async def complete_json(
        self,
        *,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        tool = {
            "name": self._tool_name,
            "description": "Return the requested schema ingest JSON object.",
            "input_schema": response_schema,
        }
        messages = [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]

        response = await call_claude(
            messages,
            purpose=f"{self._purpose_prefix}:complete_json",
            session=self._session,
            model=self._model or settings.model_parse,
            tools=[tool],
            tool_choice={"type": "tool", "name": self._tool_name},
            max_tokens=8192,
            temperature=0,
            document_id=self._document_id,
        )

        parsed = extract_tool_use_input(response, self._tool_name)
        if not isinstance(parsed, dict):
            raise ValueError(
                "complete_json expected dict from tool input, got "
                f"{type(parsed).__name__}"
            )
        return parsed
