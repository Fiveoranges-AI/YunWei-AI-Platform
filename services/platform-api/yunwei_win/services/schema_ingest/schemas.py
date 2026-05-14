"""Pydantic schemas for the schema-first ReviewDraft contract.

Public surface returned by ``GET /api/win/ingest/extractions/{id}`` and
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

from datetime import datetime
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
ReviewCellSource = Literal["ai", "default", "edited", "empty", "linked"]
ReviewRowOperation = Literal["create", "update"]
ExtractionStatus = Literal["pending_review", "confirmed", "ignored", "failed"]

# vNext row decision (used by ReviewDraft to render create/update/link choices
# straight from ``entity_resolution.EntityResolutionProposal``).
ReviewRowDecisionOperation = Literal[
    "create", "update", "link_existing", "ignore"
]
ReviewMatchLevel = Literal["strong", "weak", "none"]


class ReviewEntityCandidate(BaseModel):
    """One existing entity proposed as a candidate for a row decision."""

    model_config = ConfigDict(extra="allow")

    entity_id: UUID
    label: str
    match_level: ReviewMatchLevel
    match_keys: list[str] = Field(default_factory=list)
    confidence: float | None = None
    reason: str | None = None


class ReviewRowDecision(BaseModel):
    """Server-proposed row decision aligned with EntityResolutionRow.

    ReviewDraft surfaces this verbatim; user edits replace selected_entity_id
    / operation as they walk the wizard, and confirm writeback consumes the
    final value to fill ``system_link`` FKs.
    """

    model_config = ConfigDict(extra="allow")

    operation: ReviewRowDecisionOperation
    selected_entity_id: UUID | None = None
    candidate_entities: list[ReviewEntityCandidate] = Field(default_factory=list)
    match_level: ReviewMatchLevel | None = None
    match_keys: list[str] = Field(default_factory=list)
    reason: str | None = None


class ReviewCellEvidence(BaseModel):
    """Where in the source document the AI said it found the value."""

    page: int | None = None
    excerpt: str | None = None


# vNext source ref carried on each ``ReviewCell`` so the wizard can highlight
# the originating chunk/cell/text span in the source viewer. Decoupled from
# ``ParseSourceRef`` so the review JSON does not pull in the parse artifact
# pydantic module — the shape is the same on the wire.
class ReviewSourceRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    ref_type: str
    ref_id: str
    page: int | None = None
    bbox: list[float] | None = None
    start: int | None = None
    end: int | None = None
    excerpt: str | None = None
    paragraph: int | None = None
    table_id: str | None = None
    sheet: str | None = None
    row: int | None = None
    col: int | None = None


ReviewTablePresentation = Literal["card", "table"]
ReviewStepStatus = Literal["empty", "in_progress", "complete"]


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
    # vNext additions — defaulted so legacy serializers/consumers keep working.
    source_refs: list[ReviewSourceRef] = Field(default_factory=list)
    review_visible: bool = True
    explicit_clear: bool = False


class ReviewRow(BaseModel):
    client_row_id: str
    entity_id: UUID | None = None
    operation: ReviewRowOperation = "create"
    cells: list[ReviewCell]
    # vNext additions — row decision proposed by entity resolution, and an
    # explicit "this row has nothing reviewable" flag to keep default-only
    # rows out of writeback.
    row_decision: ReviewRowDecision | None = None
    is_writable: bool = True


class ReviewTable(BaseModel):
    table_name: str
    label: str
    purpose: str | None = None
    category: str | None = None
    is_array: bool = False
    rows: list[ReviewRow]
    raw_extraction: dict[str, Any] | None = None
    # vNext additions — presentation hint for the wizard renderer, and the
    # progressive-review step this table belongs to.
    presentation: ReviewTablePresentation = "table"
    review_step: str | None = None


class ReviewStep(BaseModel):
    """One step in the progressive review wizard."""

    model_config = ConfigDict(extra="allow")

    key: str
    label: str
    table_names: list[str] = Field(default_factory=list)
    status: ReviewStepStatus = "empty"


class ReviewDraftDocument(BaseModel):
    filename: str
    summary: str | None = None
    source_text: str | None = None


class ReviewDraftRoutePlan(BaseModel):
    selected_pipelines: list[dict[str, Any]] = Field(default_factory=list)


class ReviewDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    extraction_id: UUID
    document_id: UUID
    # vNext: link the draft back to the parse attempt + lock state.
    parse_id: UUID | None = None
    schema_version: int = 1
    status: ExtractionStatus = "pending_review"
    review_version: int = 0
    current_step: str | None = None
    document: ReviewDraftDocument
    # Legacy route_plan kept for serialization compatibility; vNext drafts use
    # ``steps`` + ``tables`` directly.
    route_plan: ReviewDraftRoutePlan = Field(default_factory=ReviewDraftRoutePlan)
    steps: list[ReviewStep] = Field(default_factory=list)
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
    """Patches the server-stored draft.

    ``review_draft`` is accepted for backward compatibility but is no longer
    the source of truth: the server reads the canonical draft from the
    DB-stored ``DocumentExtraction.review_draft`` and applies patches against
    it. When ``review_draft`` is supplied, only its ``extraction_id`` is
    cross-checked against the URL path; the rest is ignored.
    """

    review_draft: ReviewDraft | None = None
    patches: list[ReviewCellPatch] = Field(default_factory=list)


class ConfirmExtractionResponse(BaseModel):
    extraction_id: UUID
    document_id: UUID
    status: ExtractionStatus
    written_rows: dict[str, list[UUID]] = Field(default_factory=dict)
    invalid_cells: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# vNext review lock / autosave / row-decision patch contracts.
# Implementations land in Task 7+; here only the wire shape is locked in so
# downstream code can start referencing it.
# ---------------------------------------------------------------------------


class ReviewRowDecisionPatch(BaseModel):
    """User-side change to a row's create/update/link decision."""

    model_config = ConfigDict(extra="allow")

    table_name: str
    client_row_id: str
    operation: ReviewRowDecisionOperation | None = None
    selected_entity_id: UUID | None = None
    match_level: ReviewMatchLevel | None = None
    match_keys: list[str] | None = None
    reason: str | None = None


class AutosaveReviewRequest(BaseModel):
    """PATCH payload for incremental review-draft saves."""

    model_config = ConfigDict(extra="allow")

    lock_token: UUID
    base_version: int
    current_step: str | None = None
    cell_patches: list[ReviewCellPatch] = Field(default_factory=list)
    row_patches: list[ReviewRowDecisionPatch] = Field(default_factory=list)


class AutosaveReviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    extraction_id: UUID
    review_version: int
    current_step: str | None = None
    lock_expires_at: datetime | None = None
    review_draft: ReviewDraft | None = None


ReviewLockMode = Literal["edit", "read_only"]


class AcquireReviewLockResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    extraction_id: UUID
    mode: ReviewLockMode
    lock_token: UUID | None = None
    locked_by: str | None = None
    lock_expires_at: datetime | None = None
    review_version: int = 0
