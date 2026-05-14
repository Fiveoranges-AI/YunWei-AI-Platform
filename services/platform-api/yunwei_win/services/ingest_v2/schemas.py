"""Pydantic schemas for the V2 schema-first ReviewDraft contract.

Public surface returned by ``GET /api/win/ingest/v2/extractions/{id}`` and
echoed back to ``POST .../confirm``. The frontend renders ``ReviewDraft.tables``
directly — these schemas are the contract.

Notes:
- Statuses use ``Literal[...]`` rather than SQLEnum: cleaner JSON for the
  frontend, no extra serialization helpers.
- ``ReviewCell.value`` is intentionally ``Any | None`` because catalog
  ``data_type`` covers text/uuid/date/decimal/integer/boolean/enum/json. The
  materializer keeps values as whatever the extractor produced; validation
  happens at confirm time.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReviewCellStatus = Literal[
    "extracted",
    "missing",
    "low_confidence",
    "edited",
    "rejected",
    "invalid",
]
ReviewCellSource = Literal["ai", "default", "edited", "empty"]
ReviewRowOperation = Literal["create", "update"]
ExtractionStatus = Literal["pending_review", "confirmed", "ignored", "failed"]


class ReviewCellEvidence(BaseModel):
    """Where in the source document the AI said it found the value."""

    page: int | None = None
    excerpt: str | None = None


class ReviewCell(BaseModel):
    field_name: str
    label: str
    data_type: str
    required: bool = False
    is_array: bool = False
    value: Any | None = None
    display_value: str = ""
    status: ReviewCellStatus
    confidence: float | None = None
    evidence: ReviewCellEvidence | None = None
    source: ReviewCellSource


class ReviewRow(BaseModel):
    client_row_id: str
    entity_id: UUID | None = None
    operation: ReviewRowOperation = "create"
    cells: list[ReviewCell]


class ReviewTable(BaseModel):
    table_name: str
    label: str
    purpose: str | None = None
    category: str | None = None
    is_array: bool = False
    rows: list[ReviewRow]
    raw_extraction: dict[str, Any] | None = None


class ReviewDraftDocument(BaseModel):
    filename: str
    summary: str | None = None


class ReviewDraftRoutePlan(BaseModel):
    selected_pipelines: list[dict[str, Any]] = Field(default_factory=list)


class ReviewDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    extraction_id: UUID
    document_id: UUID
    schema_version: int = 1
    status: ExtractionStatus = "pending_review"
    document: ReviewDraftDocument
    route_plan: ReviewDraftRoutePlan
    tables: list[ReviewTable]
    schema_warnings: list[str] = Field(default_factory=list)
    general_warnings: list[str] = Field(default_factory=list)


class ReviewCellPatch(BaseModel):
    """Frontend edit to one cell, applied during confirm.

    ``status`` is optional so the client can mark a cell ``rejected`` without
    changing the value, or accept the AI value as-is by omitting it.
    """

    table_name: str
    client_row_id: str
    field_name: str
    value: Any | None = None
    status: ReviewCellStatus | None = None
    entity_id: UUID | None = None
    operation: ReviewRowOperation | None = None


class ConfirmExtractionRequest(BaseModel):
    """Frontend echoes the server-stored draft (provides table/row identity)
    plus a list of cell-level patches it wants applied."""

    review_draft: ReviewDraft
    patches: list[ReviewCellPatch] = Field(default_factory=list)


class ConfirmExtractionResponse(BaseModel):
    extraction_id: UUID
    document_id: UUID
    status: ExtractionStatus
    written_rows: dict[str, list[UUID]] = Field(default_factory=dict)
    invalid_cells: list[dict[str, Any]] = Field(default_factory=list)
