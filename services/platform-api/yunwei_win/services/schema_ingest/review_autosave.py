"""Server-side review draft autosave.

PATCH /extractions/{id}/review goes through ``autosave_review`` which:

  1. loads the DocumentExtraction
  2. asserts the lock token + base_version match what's on disk
  3. validates the stored ``review_draft`` JSON back into a ``ReviewDraft``
  4. applies cell patches (value / status / source / explicit_clear)
  5. applies row-decision patches (operation / selected_entity_id / ...)
  6. applies the optional current_step
  7. bumps ``review_version`` on both extraction and draft
  8. refreshes the lock expiry and reviewer audit columns
  9. commits

Confirm and the read endpoint both consume this same shape, so the
on-disk JSON only ever moves through ``ReviewDraft.model_dump(mode="json")``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.services.schema_ingest.review_lock import (
    assert_valid_review_lock,
    refresh_review_lock_expiry,
)
from yunwei_win.services.schema_ingest.schemas import (
    AutosaveReviewRequest,
    AutosaveReviewResponse,
    ReviewCell,
    ReviewCellPatch,
    ReviewDraft,
    ReviewRow,
    ReviewRowDecision,
    ReviewRowDecisionPatch,
    ReviewTable,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def autosave_review(
    session: AsyncSession,
    *,
    extraction_id: UUID,
    request: AutosaveReviewRequest,
    reviewed_by: str | None,
) -> AutosaveReviewResponse:
    extraction = (
        await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
        )
    ).scalar_one_or_none()
    if extraction is None:
        raise HTTPException(status_code=404, detail="extraction not found")

    if extraction.status != DocumentExtractionStatus.pending_review:
        raise HTTPException(
            status_code=409,
            detail=f"extraction is {extraction.status.value}, not pending_review",
        )

    assert_valid_review_lock(
        extraction,
        lock_token=request.lock_token,
        base_version=request.base_version,
    )

    if extraction.review_draft is None:
        raise HTTPException(status_code=409, detail="review_draft missing on extraction")

    try:
        draft = ReviewDraft.model_validate(extraction.review_draft)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"stored review_draft is not valid: {exc!s}"
        ) from exc

    _apply_cell_patches(draft, request.cell_patches)
    _apply_row_patches(draft, request.row_patches)
    if request.current_step is not None:
        draft.current_step = request.current_step

    extraction.review_version += 1
    draft.review_version = extraction.review_version

    extraction.review_draft = draft.model_dump(mode="json")
    extraction.last_reviewed_by = reviewed_by
    extraction.last_reviewed_at = _utcnow()
    refresh_review_lock_expiry(extraction)

    await session.commit()
    await session.refresh(extraction)

    return AutosaveReviewResponse(
        extraction_id=extraction.id,
        review_version=extraction.review_version,
        current_step=draft.current_step,
        lock_expires_at=extraction.lock_expires_at,
        review_draft=draft,
    )


# ---------------------------------------------------------------------------
# Patch appliers
# ---------------------------------------------------------------------------


def _apply_cell_patches(draft: ReviewDraft, patches: list[ReviewCellPatch]) -> None:
    for patch in patches:
        table = _find_table(draft, patch.table_name)
        if table is None:
            continue
        row = _find_row(table, patch.client_row_id)
        if row is None:
            continue
        cell = _find_cell(row, patch.field_name)
        if cell is None:
            continue
        _apply_one_cell_patch(cell, patch)


def _apply_one_cell_patch(cell: ReviewCell, patch: ReviewCellPatch) -> None:
    value_provided = "value" in patch.model_fields_set
    status_provided = patch.status is not None

    if value_provided:
        cell.value = patch.value
        cell.display_value = "" if patch.value is None else str(patch.value)
        cell.explicit_clear = patch.value is None

    if status_provided:
        cell.status = patch.status  # type: ignore[assignment]
        if patch.status == "edited":
            cell.source = "edited"
        elif patch.status == "rejected":
            cell.source = "edited"
        elif patch.status == "missing":
            cell.source = "empty"
    elif value_provided:
        # Value mutated without an explicit status — treat as a user edit.
        cell.status = "edited"
        cell.source = "edited"


def _apply_row_patches(
    draft: ReviewDraft, patches: list[ReviewRowDecisionPatch]
) -> None:
    for patch in patches:
        table = _find_table(draft, patch.table_name)
        if table is None:
            continue
        row = _find_row(table, patch.client_row_id)
        if row is None:
            continue
        decision = row.row_decision or ReviewRowDecision(operation="create")
        _apply_one_row_patch(row, decision, patch)


def _apply_one_row_patch(
    row: ReviewRow,
    decision: ReviewRowDecision,
    patch: ReviewRowDecisionPatch,
) -> None:
    if patch.operation is not None:
        decision.operation = patch.operation
    if "selected_entity_id" in patch.model_fields_set:
        decision.selected_entity_id = patch.selected_entity_id
        row.entity_id = patch.selected_entity_id
    if patch.match_level is not None:
        decision.match_level = patch.match_level
    if patch.match_keys is not None:
        decision.match_keys = list(patch.match_keys)
    if patch.reason is not None:
        decision.reason = patch.reason
    row.row_decision = decision

    # An explicit operation other than "ignore" implies the reviewer wants
    # this row written — flip writable so confirm picks it up.
    if decision.operation in {"create", "update", "link_existing"}:
        row.is_writable = True
        if decision.operation == "update":
            row.operation = "update"
        else:
            row.operation = "create"
    elif decision.operation == "ignore":
        row.is_writable = False


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def _find_table(draft: ReviewDraft, table_name: str) -> ReviewTable | None:
    return next((t for t in draft.tables if t.table_name == table_name), None)


def _find_row(table: ReviewTable, client_row_id: str) -> ReviewRow | None:
    return next((r for r in table.rows if r.client_row_id == client_row_id), None)


def _find_cell(row: ReviewRow, field_name: str) -> ReviewCell | None:
    return next((c for c in row.cells if c.field_name == field_name), None)
