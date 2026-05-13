"""Inbox APIs — list/confirm/ignore extraction candidates pending human review."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.models import (
    CommitmentDirection,
    CommitmentStatus,
    CustomerCommitment,
    CustomerEvent,
    CustomerEventType,
    CustomerInboxItem,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    DocumentReviewStatus,
    InboxStatus,
    MemoryKind,
    RiskKind,
    RiskSeverity,
    RiskStatus,
    TaskPriority,
    TaskStatus,
)
from yunwei_win.schemas.customer import (
    CustomerInboxItemOut,
    InboxConfirmResult,
    InboxDecisionRequest,
)

from yunwei_win.api.customer_profile._helpers import load_customer

logger = logging.getLogger(__name__)
router = APIRouter()


def _enum_or_default(enum_cls, raw: Any, default):
    if raw is None:
        return default
    try:
        return enum_cls(raw)
    except (ValueError, TypeError):
        return default


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_date(raw: Any):
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw[:10]).date()
        except ValueError:
            return None
    return raw


def _first_nonempty(*candidates: Any) -> str:
    """Return the first non-empty candidate (after stripping); '' if all empty.

    DeepSeek sometimes leaves the structured `title` null and stuffs the
    substance into description / raw_excerpt. Used by both events and tasks
    so we recover those rather than dropping the whole row.
    """
    for c in candidates:
        s = (c or "").strip().split("\n", 1)[0]
        if s:
            return s
    return ""


async def _load_inbox_or_409(
    session: AsyncSession, customer_id: UUID, inbox_id: UUID
) -> CustomerInboxItem:
    """Load an inbox row that's still pending; raise the right HTTP error
    on miss / wrong customer / already-decided."""
    inbox = (
        await session.execute(
            select(CustomerInboxItem).where(
                CustomerInboxItem.id == inbox_id,
                CustomerInboxItem.customer_id == customer_id,
            )
        )
    ).scalar_one_or_none()
    if inbox is None:
        raise HTTPException(404, "inbox item not found")
    if inbox.status != InboxStatus.pending:
        raise HTTPException(409, f"already {inbox.status.value}")
    return inbox


async def _stamp_document_review(
    session: AsyncSession, document_id: UUID | None, status: DocumentReviewStatus
) -> None:
    if document_id is None:
        return
    doc = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if doc is not None:
        doc.review_status = status


@router.get(
    "/{customer_id}/inbox", response_model=list[CustomerInboxItemOut]
)
async def list_inbox(
    customer_id: UUID,
    status: str = Query(default="pending"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[CustomerInboxItemOut]:
    await load_customer(session, customer_id)
    try:
        s = InboxStatus(status)
    except ValueError as exc:
        raise HTTPException(400, f"unknown status {status!r}") from exc
    rows = (
        await session.execute(
            select(CustomerInboxItem)
            .where(
                CustomerInboxItem.customer_id == customer_id,
                CustomerInboxItem.status == s,
            )
            .order_by(CustomerInboxItem.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [CustomerInboxItemOut.model_validate(r) for r in rows]


@router.post(
    "/{customer_id}/inbox/{inbox_id}/confirm",
    response_model=InboxConfirmResult,
)
async def confirm_inbox(
    customer_id: UUID,
    inbox_id: UUID,
    payload: InboxDecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> InboxConfirmResult:
    await load_customer(session, customer_id)
    inbox = await _load_inbox_or_409(session, customer_id, inbox_id)

    p = inbox.extracted_payload or {}
    written = {"events": 0, "commitments": 0, "tasks": 0,
               "risk_signals": 0, "memory_items": 0}
    doc_id = inbox.document_id

    for ev in p.get("events") or []:
        title = _first_nonempty(
            ev.get("title"), ev.get("description"), ev.get("raw_excerpt")
        )
        if not title:
            continue
        session.add(CustomerEvent(
            customer_id=customer_id,
            document_id=doc_id,
            occurred_at=_parse_dt(ev.get("occurred_at")),
            event_type=_enum_or_default(
                CustomerEventType, ev.get("event_type"), CustomerEventType.other
            ),
            title=title[:500],
            description=ev.get("description"),
            raw_excerpt=ev.get("raw_excerpt"),
            confidence=ev.get("confidence"),
        ))
        written["events"] += 1

    for cm in p.get("commitments") or []:
        if not (cm.get("summary") and str(cm["summary"]).strip()):
            continue
        session.add(CustomerCommitment(
            customer_id=customer_id,
            document_id=doc_id,
            direction=_enum_or_default(
                CommitmentDirection, cm.get("direction"),
                CommitmentDirection.mutual,
            ),
            summary=str(cm["summary"])[:500],
            description=cm.get("description"),
            due_date=_parse_date(cm.get("due_date")),
            status=CommitmentStatus.open,
            raw_excerpt=cm.get("raw_excerpt"),
            confidence=cm.get("confidence"),
        ))
        written["commitments"] += 1

    for tk in p.get("tasks") or []:
        title = _first_nonempty(
            tk.get("title"), tk.get("description"), tk.get("raw_excerpt")
        )
        if not title:
            continue
        session.add(CustomerTask(
            customer_id=customer_id,
            document_id=doc_id,
            title=title[:500],
            description=tk.get("description"),
            assignee=tk.get("assignee"),
            due_date=_parse_date(tk.get("due_date")),
            priority=_enum_or_default(
                TaskPriority, tk.get("priority"), TaskPriority.normal
            ),
            status=TaskStatus.open,
            raw_excerpt=tk.get("raw_excerpt"),
        ))
        written["tasks"] += 1

    for r in p.get("risk_signals") or []:
        if not (r.get("summary") and str(r["summary"]).strip()):
            continue
        session.add(CustomerRiskSignal(
            customer_id=customer_id,
            document_id=doc_id,
            severity=_enum_or_default(
                RiskSeverity, r.get("severity"), RiskSeverity.medium
            ),
            kind=_enum_or_default(RiskKind, r.get("kind"), RiskKind.other),
            summary=str(r["summary"])[:500],
            description=r.get("description"),
            status=RiskStatus.open,
            raw_excerpt=r.get("raw_excerpt"),
            confidence=r.get("confidence"),
        ))
        written["risk_signals"] += 1

    for m in p.get("memory_items") or []:
        if not (m.get("content") and str(m["content"]).strip()):
            continue
        session.add(CustomerMemoryItem(
            customer_id=customer_id,
            document_id=doc_id,
            kind=_enum_or_default(MemoryKind, m.get("kind"), MemoryKind.context),
            content=str(m["content"]),
            raw_excerpt=m.get("raw_excerpt"),
            confidence=m.get("confidence"),
        ))
        written["memory_items"] += 1

    inbox.status = InboxStatus.confirmed
    inbox.decided_at = datetime.now(timezone.utc)
    inbox.decided_by = payload.by
    await _stamp_document_review(session, doc_id, DocumentReviewStatus.confirmed)

    await session.commit()
    return InboxConfirmResult(
        inbox_id=inbox.id, status="confirmed", written_counts=written
    )


@router.post(
    "/{customer_id}/inbox/{inbox_id}/ignore",
    response_model=InboxConfirmResult,
)
async def ignore_inbox(
    customer_id: UUID,
    inbox_id: UUID,
    payload: InboxDecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> InboxConfirmResult:
    await load_customer(session, customer_id)
    inbox = await _load_inbox_or_409(session, customer_id, inbox_id)

    inbox.status = InboxStatus.ignored
    inbox.decided_at = datetime.now(timezone.utc)
    inbox.decided_by = payload.by
    await _stamp_document_review(
        session, inbox.document_id, DocumentReviewStatus.ignored
    )

    await session.commit()
    return InboxConfirmResult(
        inbox_id=inbox.id, status="ignored",
        written_counts={"events": 0, "commitments": 0, "tasks": 0,
                        "risk_signals": 0, "memory_items": 0},
    )
