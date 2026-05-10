"""Customer-scoped read APIs: events, commitments, tasks, risks, memory,
timeline, and the high-level summary card."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.db import get_session
from yinhu_brain.models import (
    CommitmentStatus,
    CustomerCommitment,
    CustomerEvent,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    RiskSeverity,
    RiskStatus,
    TaskStatus,
)
from yinhu_brain.schemas.customer import (
    CustomerCommitmentOut,
    CustomerEventOut,
    CustomerMemoryItemOut,
    CustomerRiskSignalOut,
    CustomerSummaryOut,
    CustomerTaskOut,
    TimelineEntry,
)

from yinhu_brain.api.customer_profile._helpers import (
    exec_list,
    filter_by_status,
    load_customer,
)

router = APIRouter()


@router.get(
    "/{customer_id}/events", response_model=list[CustomerEventOut]
)
async def list_events(
    customer_id: UUID,
    limit: int = Query(default=200, le=500),
    session: AsyncSession = Depends(get_session),
):
    await load_customer(session, customer_id)
    stmt = (
        select(CustomerEvent)
        .where(CustomerEvent.customer_id == customer_id)
        .order_by(CustomerEvent.occurred_at.desc().nullslast(),
                  CustomerEvent.created_at.desc())
        .limit(limit)
    )
    return await exec_list(session, stmt, CustomerEventOut)


@router.get(
    "/{customer_id}/commitments", response_model=list[CustomerCommitmentOut]
)
async def list_commitments(
    customer_id: UUID,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    await load_customer(session, customer_id)
    stmt = (
        select(CustomerCommitment)
        .where(CustomerCommitment.customer_id == customer_id)
        .order_by(CustomerCommitment.due_date.asc().nullslast(),
                  CustomerCommitment.created_at.desc())
    )
    stmt = filter_by_status(
        stmt, CustomerCommitment.status, status, CommitmentStatus
    )
    return await exec_list(session, stmt, CustomerCommitmentOut)


@router.get(
    "/{customer_id}/tasks", response_model=list[CustomerTaskOut]
)
async def list_tasks(
    customer_id: UUID,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    await load_customer(session, customer_id)
    stmt = (
        select(CustomerTask)
        .where(CustomerTask.customer_id == customer_id)
        .order_by(CustomerTask.due_date.asc().nullslast(),
                  CustomerTask.created_at.desc())
    )
    stmt = filter_by_status(stmt, CustomerTask.status, status, TaskStatus)
    return await exec_list(session, stmt, CustomerTaskOut)


@router.get(
    "/{customer_id}/risks", response_model=list[CustomerRiskSignalOut]
)
async def list_risks(
    customer_id: UUID,
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    await load_customer(session, customer_id)
    stmt = (
        select(CustomerRiskSignal)
        .where(CustomerRiskSignal.customer_id == customer_id)
        .order_by(CustomerRiskSignal.detected_at.desc())
    )
    stmt = filter_by_status(
        stmt, CustomerRiskSignal.status, status, RiskStatus
    )
    return await exec_list(session, stmt, CustomerRiskSignalOut)


@router.get(
    "/{customer_id}/memory-items", response_model=list[CustomerMemoryItemOut]
)
async def list_memory_items(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    await load_customer(session, customer_id)
    stmt = (
        select(CustomerMemoryItem)
        .where(CustomerMemoryItem.customer_id == customer_id)
        .order_by(CustomerMemoryItem.created_at.desc())
    )
    return await exec_list(session, stmt, CustomerMemoryItemOut)


@router.get(
    "/{customer_id}/timeline", response_model=list[TimelineEntry]
)
async def list_timeline(
    customer_id: UUID,
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[TimelineEntry]:
    """Merge events / commitments / tasks / risks / memory_items / docs into
    one chronological stream. `at` = occurred_at (events) / detected_at (risks)
    / created_at (everything else)."""
    await load_customer(session, customer_id)
    entries: list[TimelineEntry] = []

    async def _scalars(stmt):
        return (await session.execute(stmt)).scalars().all()

    for e in await _scalars(
        select(CustomerEvent).where(CustomerEvent.customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="event",
            at=e.occurred_at or e.created_at,
            title=e.title,
            summary=e.description,
            payload=CustomerEventOut.model_validate(e).model_dump(mode="json"),
        ))

    for c in await _scalars(
        select(CustomerCommitment).where(CustomerCommitment.customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="commitment",
            at=c.created_at,
            title=c.summary,
            summary=c.description,
            payload=CustomerCommitmentOut.model_validate(c).model_dump(mode="json"),
        ))

    for t in await _scalars(
        select(CustomerTask).where(CustomerTask.customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="task",
            at=t.created_at,
            title=t.title,
            summary=t.description,
            payload=CustomerTaskOut.model_validate(t).model_dump(mode="json"),
        ))

    for r in await _scalars(
        select(CustomerRiskSignal).where(CustomerRiskSignal.customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="risk",
            at=r.detected_at,
            title=r.summary,
            summary=r.description,
            payload=CustomerRiskSignalOut.model_validate(r).model_dump(mode="json"),
        ))

    for m in await _scalars(
        select(CustomerMemoryItem).where(CustomerMemoryItem.customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="memory",
            at=m.created_at,
            title=m.content[:80],
            summary=None,
            payload=CustomerMemoryItemOut.model_validate(m).model_dump(mode="json"),
        ))

    for d in await _scalars(
        select(Document).where(Document.assigned_customer_id == customer_id)
    ):
        entries.append(TimelineEntry(
            kind="document",
            at=d.created_at,
            title=d.original_filename or d.type.value,
            summary=f"{d.type.value} · {d.processing_status.value}",
            payload={
                "id": str(d.id),
                "type": d.type.value,
                "original_filename": d.original_filename,
                "processing_status": d.processing_status.value,
                "review_status": d.review_status.value,
            },
        ))

    entries.sort(key=lambda e: e.at, reverse=True)
    return entries[:limit]


@router.get(
    "/{customer_id}/summary", response_model=CustomerSummaryOut
)
async def customer_summary(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> CustomerSummaryOut:
    cust = await load_customer(session, customer_id)

    open_commitments = (await session.execute(
        select(CustomerCommitment).where(
            CustomerCommitment.customer_id == customer_id,
            CustomerCommitment.status == CommitmentStatus.open,
        )
    )).scalars().all()
    open_tasks = (await session.execute(
        select(CustomerTask).where(
            CustomerTask.customer_id == customer_id,
            CustomerTask.status.in_([TaskStatus.open, TaskStatus.in_progress]),
        )
    )).scalars().all()
    open_risks = (await session.execute(
        select(CustomerRiskSignal).where(
            CustomerRiskSignal.customer_id == customer_id,
            CustomerRiskSignal.status == RiskStatus.open,
        )
    )).scalars().all()
    recent_events = (await session.execute(
        select(CustomerEvent).where(CustomerEvent.customer_id == customer_id)
    )).scalars().all()

    last_event_at = (
        max((e.occurred_at or e.created_at) for e in recent_events)
        if recent_events else None
    )

    parts: list[str] = []
    if open_commitments:
        parts.append(f"{len(open_commitments)} 项未完成承诺")
    if open_tasks:
        parts.append(f"{len(open_tasks)} 项待办")
    if open_risks:
        high_risk = sum(1 for r in open_risks if r.severity == RiskSeverity.high)
        parts.append(
            f"{len(open_risks)} 项风险" + (f"（{high_risk} 高）" if high_risk else "")
        )
    if not parts:
        parts.append("无待办无风险")

    return CustomerSummaryOut(
        customer_id=cust.id,
        headline=f"{cust.full_name} · " + "，".join(parts),
        open_commitments_count=len(open_commitments),
        open_tasks_count=len(open_tasks),
        open_risks_count=len(open_risks),
        recent_events_count=len(recent_events),
        last_interaction_at=last_event_at,
    )
