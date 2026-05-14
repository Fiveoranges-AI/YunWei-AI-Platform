"""Shared small schemas and JSON-schema helpers for current ingest features."""

from __future__ import annotations

import enum
import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_CN_DATE = re.compile(r"^(\d{4})\D{1,2}(\d{1,2})\D{1,2}(\d{1,2}).*$")


def _clean_date(v: Any) -> Any:
    if v is None or isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            pass
        m = _CN_DATE.match(s)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            return date(y, mo, d)
        s2 = s.replace("/", "-").replace(".", "-")
        try:
            return date.fromisoformat(s2[:10])
        except ValueError:
            return None
    return v


def _strip_titles(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop Pydantic ``title`` noise from tool JSON schemas."""

    if isinstance(schema, dict):
        schema.pop("title", None)
        for v in schema.values():
            if isinstance(v, dict):
                _strip_titles(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _strip_titles(item)
    return schema


class FieldProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(description="字段路径，如 customer.full_name")
    source_page: int | None = Field(default=None, description="原文页码，1-indexed")
    source_excerpt: str | None = Field(
        default=None,
        max_length=400,
        description="原文里能 substring-match 到的连续片段",
    )


QA_TOOL_NAME = "submit_qa_answer"


class CitationTarget(str, enum.Enum):
    customer = "customer"
    contract = "contract"
    order = "order"
    document = "document"


class QACitation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_type: CitationTarget
    target_id: str
    snippet: str | None = None


class QAAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str = Field(description="对用户问题的中文回答；事实声明都要带引用")
    citations: list[QACitation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    no_relevant_info: bool = Field(
        default=False,
        description="知识库里完全没相关信息时设 true",
    )


def qa_tool() -> dict[str, Any]:
    return {
        "name": QA_TOOL_NAME,
        "description": "Submit the answer to the user's question, with typed citations.",
        "input_schema": _strip_titles(QAAnswer.model_json_schema()),
    }
