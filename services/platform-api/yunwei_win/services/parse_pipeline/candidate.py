"""Candidate JSON shape.

The strict shape contracted by P0 task ②. Fields can be ADDED for richer
metadata but the documented keys can't be renamed or removed without a
spec bump — task ③ frontend depends on them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


EntityType = Literal[
    "Customer",
    "Contact",
    "Contract",
    "Order",
    "OrderLine",  # candidate-JSON / parse-pipeline canonical name
    "OrderItem",  # task ① ontology table name — accepted as alias for forward-compat
    "Product",
    "Invoice",
    "Payment",
]


SourceType = Literal["contract", "wechat_screenshot", "excel"]


class SourceSpan(BaseModel):
    """Pointer back into the input file for one extracted value.

    Visual sources (contract / screenshot) populate ``page`` + ``bbox`` +
    ``text``. Excel populates ``cell`` (e.g. ``"sheet:订单!R7C2"``) and
    sometimes ``text`` (the cell text). ``text`` always carries the
    matched excerpt, regardless of source — task ③ uses it as fallback
    when the visual span can't be rendered.
    """

    model_config = ConfigDict(extra="allow")

    page: int | None = None
    bbox: list[float] | None = None
    text: str | None = None
    cell: str | None = None


class FieldCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Any | None = None
    confidence: float = 0.0
    source_span: SourceSpan = Field(default_factory=SourceSpan)


class CandidateEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_type: EntityType
    temp_id: str
    fields: list[FieldCandidate] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_temp_id: str
    to_temp_id: str
    type: str  # e.g. "Customer-has-Contact", "Order-has-OrderLine"


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: SourceType
    file_ref: str
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None


class CandidateJSON(BaseModel):
    model_config = ConfigDict(extra="allow")

    ingestion_id: str = Field(default_factory=lambda: str(uuid4()))
    source: SourceInfo
    entities: list[CandidateEntity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    overall_confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
