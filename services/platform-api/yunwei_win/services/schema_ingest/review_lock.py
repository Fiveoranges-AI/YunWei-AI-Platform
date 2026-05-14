"""Single-editor review lock helpers.

One reviewer at a time may edit a ``DocumentExtraction``. Locks live on
the extraction row (``locked_by``, ``lock_token``, ``lock_expires_at``)
plus the optimistic ``review_version`` counter. Locks expire after
``LOCK_TTL_SECONDS`` so a stale tab can never permanently block another
reviewer. autosave/confirm both verify the lock + version before
mutating the draft.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.services.schema_ingest.schemas import AcquireReviewLockResponse


LOCK_TTL_SECONDS = 15 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_expiry() -> datetime:
    return _utcnow() + timedelta(seconds=LOCK_TTL_SECONDS)


def _lock_is_live(extraction: DocumentExtraction) -> bool:
    if extraction.lock_expires_at is None or extraction.lock_token is None:
        return False
    expires = extraction.lock_expires_at
    if expires.tzinfo is None:
        # SQLite hands back naive datetimes; treat them as UTC for the TTL
        # check so we don't accidentally extend a stale lock.
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > _utcnow()


async def acquire_review_lock(
    session: AsyncSession,
    *,
    extraction_id: UUID,
    user: str | None,
) -> AcquireReviewLockResponse:
    """Acquire / refresh / inspect the review lock for one extraction."""

    user_label = user or "unknown"

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

    if _lock_is_live(extraction) and extraction.locked_by != user_label:
        return AcquireReviewLockResponse(
            extraction_id=extraction.id,
            mode="read_only",
            lock_token=None,
            locked_by=extraction.locked_by,
            lock_expires_at=extraction.lock_expires_at,
            review_version=extraction.review_version,
        )

    # Same user reacquires → keep existing token, just refresh expiry. Stale /
    # missing lock → mint a fresh token under the requesting user.
    if not _lock_is_live(extraction):
        extraction.lock_token = uuid.uuid4()
        extraction.locked_by = user_label
    elif extraction.lock_token is None:
        extraction.lock_token = uuid.uuid4()
        extraction.locked_by = user_label

    extraction.lock_expires_at = _new_expiry()
    await session.commit()
    await session.refresh(extraction)

    return AcquireReviewLockResponse(
        extraction_id=extraction.id,
        mode="edit",
        lock_token=extraction.lock_token,
        locked_by=extraction.locked_by,
        lock_expires_at=extraction.lock_expires_at,
        review_version=extraction.review_version,
    )


def assert_valid_review_lock(
    extraction: DocumentExtraction,
    *,
    lock_token: UUID,
    base_version: int,
) -> None:
    """Raise HTTP 409 if the caller's lock/version is stale."""

    if extraction.lock_token != lock_token:
        raise HTTPException(status_code=409, detail="review lock token mismatch")
    if not _lock_is_live(extraction):
        raise HTTPException(status_code=409, detail="review lock expired")
    if extraction.review_version != base_version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"review_version mismatch: client={base_version}, "
                f"server={extraction.review_version}"
            ),
        )


def refresh_review_lock_expiry(extraction: DocumentExtraction) -> None:
    """Push the lock expiry out by ``LOCK_TTL_SECONDS`` after a successful save."""

    extraction.lock_expires_at = _new_expiry()


def release_review_lock(extraction: DocumentExtraction) -> None:
    """Clear lock state. Used by confirm or explicit unlock."""

    extraction.locked_by = None
    extraction.lock_token = None
    extraction.lock_expires_at = None
