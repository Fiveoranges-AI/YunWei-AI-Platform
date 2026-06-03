"""ClaudeProvider — wraps services.llm.call_claude for the pipeline.

Two extraction modes:

  text mode      — prompt + markdown, expects JSON-in-text reply.
                   Used by the contract adapter for text-extractable PDFs.

  vision mode    — prompt + image (base64), expects JSON-in-text reply.
                   Used by the contract adapter when OCR was needed, and
                   by the WeChat screenshot adapter.

The provider is intentionally NOT used in tests; tests inject
MockProvider. Wired-up runtime callers construct one of these with an
explicit ``AsyncSession`` (call_claude logs to ``llm_calls``).

If ``ANTHROPIC_API_KEY`` is unset, instantiation succeeds but the first
.extract() call raises LLMCallFailed from the underlying client — same
behaviour as every other call site in the repo.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.services.llm import call_claude, extract_text
from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ProviderEntity,
    ProviderField,
    ProviderResult,
)


logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "你是一个负责把销售文档/截图解析成结构化候选档案的助手。"
    "**只输出 JSON**(不要 markdown 代码块、不要解释文字)。"
    "JSON 必须严格符合下面的 schema:\n"
    """{
  "entities": [
    {
      "entity_type": "Customer|Contact|Contract|Order|OrderLine|Product|Invoice|Payment",
      "temp_id": "本次解析临时ID,字符串,需要在 relationships 中复用",
      "fields": [
        {
          "name": "字段名",
          "value": "抽取值(字符串/数字/null)",
          "confidence": 0.0,
          "source_excerpt": "命中的原文片段",
          "source_page": 1
        }
      ]
    }
  ],
  "relationships": [
    {"from_temp_id": "...", "to_temp_id": "...", "type": "Customer-has-Contact|Order-has-OrderLine|..."}
  ],
  "warnings": ["可疑/不确定的点"]
}
"""
    "字段名必须使用本体规定的英文 snake_case(full_name / amount_total / signing_date 等),"
    "不要用中文 key。"
    "每一个字段都要带 confidence(0~1) 和 source_excerpt(原文片段)。"
    "如果某字段是猜的(没有明确原文),confidence 给 0.4 以下,并加入 warnings 一条说明。"
)


class ClaudeProvider:
    name = "claude"

    def __init__(self, *, session: AsyncSession, model: str | None = None) -> None:
        self._session = session
        self._model = model

    async def extract(self, payload: ExtractionPayload) -> ProviderResult:
        user_blocks: list[dict[str, Any]] = []
        if payload.image_b64:
            user_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": payload.image_media_type or "image/png",
                    "data": payload.image_b64,
                },
            })
        instructions = (
            _SYSTEM_PROMPT
            + f"\n\nsource_type: {payload.source_type}\n"
            + f"filename: {payload.filename}\n\n"
            + "请把下面这份文档解析成候选实体 JSON。\n"
        )
        user_blocks.append({
            "type": "text",
            "text": instructions + (payload.markdown or ""),
        })

        messages = [
            {"role": "user", "content": user_blocks},
        ]
        response = await call_claude(
            messages,
            purpose=f"parse_pipeline:{payload.source_type}",
            session=self._session,
            model=self._model,
            max_tokens=4096,
        )
        text = extract_text(response)
        return _parse_response_json(text)


def _parse_response_json(text: str) -> ProviderResult:
    raw = _try_parse_json(text)
    if raw is None:
        logger.warning("ClaudeProvider: could not parse JSON from response")
        return ProviderResult(
            entities=[],
            warnings=["LLM 响应未能解析为 JSON"],
            provider_name="claude",
        )

    entities_raw = raw.get("entities") or []
    relationships_raw = raw.get("relationships") or []
    warnings_raw = raw.get("warnings") or []

    entities: list[ProviderEntity] = []
    for ent in entities_raw:
        if not isinstance(ent, dict):
            continue
        fields: list[ProviderField] = []
        for f in ent.get("fields") or []:
            if not isinstance(f, dict) or "name" not in f:
                continue
            fields.append(ProviderField(**{
                "name": str(f["name"]),
                "value": f.get("value"),
                "confidence": _coerce_float(f.get("confidence")),
                "source_excerpt": f.get("source_excerpt"),
                "source_ref_id": f.get("source_ref_id"),
                "source_page": _coerce_int(f.get("source_page")),
                "source_bbox": f.get("source_bbox"),
            }))
        entities.append(ProviderEntity(
            entity_type=str(ent.get("entity_type", "")),
            temp_id=str(ent.get("temp_id", "")),
            fields=fields,
        ))

    return ProviderResult(
        entities=entities,
        relationships=[r for r in relationships_raw if isinstance(r, dict)],
        warnings=[str(w) for w in warnings_raw if w],
        provider_name="claude",
    )


def _try_parse_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    # Fall back to scanning for a balanced top-level object.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
                    break
        start = text.find("{", start + 1)
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
