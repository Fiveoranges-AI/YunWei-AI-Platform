"""Pydantic API request/response schemas for the Super Customer Profile.

Distinct from `services/ingest/customer_memory_schema.py` (which is the
LLM tool-call schema). These shape the JSON the frontend talks to.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# -------- shared base config --------------------------------------------

class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -------- entity rows ---------------------------------------------------

class CustomerEventOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    occurred_at: datetime | None = None
    event_type: str
    title: str
    description: str | None = None
    raw_excerpt: str | None = None
    confidence: Decimal | None = None
    created_at: datetime


class CustomerCommitmentOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    direction: str
    summary: str
    description: str | None = None
    due_date: date | None = None
    status: str
    raw_excerpt: str | None = None
    confidence: Decimal | None = None
    created_at: datetime


class CustomerTaskOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    title: str
    description: str | None = None
    assignee: str | None = None
    due_date: date | None = None
    priority: str
    status: str
    raw_excerpt: str | None = None
    created_at: datetime


class CustomerRiskSignalOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    severity: str
    kind: str
    summary: str
    description: str | None = None
    detected_at: datetime
    status: str
    raw_excerpt: str | None = None
    confidence: Decimal | None = None
    created_at: datetime


class CustomerMemoryItemOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    kind: str
    content: str
    raw_excerpt: str | None = None
    confidence: Decimal | None = None
    created_at: datetime


class CustomerInboxItemOut(_Out):
    id: UUID
    customer_id: UUID
    document_id: UUID | None = None
    source_kind: str
    summary: str
    extracted_payload: dict[str, Any]
    status: str
    confidence: Decimal | None = None
    parse_warnings: list[str]
    decided_at: datetime | None = None
    decided_by: str | None = None
    created_at: datetime


# -------- timeline (merged stream) --------------------------------------

class TimelineEntry(BaseModel):
    """One row of the merged customer timeline. `kind` discriminates which
    sub-shape lives in `payload`. `at` is the canonical sort key."""

    kind: Literal["event", "commitment", "task", "risk", "memory", "document"]
    at: datetime
    title: str
    summary: str | None = None
    payload: dict[str, Any]


# -------- ingest request / response -------------------------------------

class CustomerIngestResponse(BaseModel):
    inbox_id: UUID
    document_id: UUID
    source_kind: str
    summary: str
    confidence_overall: float
    proposed_counts: dict[str, int]
    warnings: list[str]


class InboxDecisionRequest(BaseModel):
    by: str | None = Field(
        default=None,
        max_length=128,
        description="Operator identifier (email or name); audit trail.",
    )


class InboxConfirmResult(BaseModel):
    inbox_id: UUID
    status: str
    written_counts: dict[str, int]


# -------- customer Q&A --------------------------------------------------

class CustomerAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CustomerAskCitation(BaseModel):
    target_type: Literal[
        "customer",
        "contract",
        "order",
        "document",
        "event",
        "commitment",
        "task",
        "risk",
        "memory",
        "contact",
    ]
    target_id: str
    snippet: str | None = None


class CustomerAskResponse(BaseModel):
    answer: str
    citations: list[CustomerAskCitation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    no_relevant_info: bool = False


# -------- AI customer summary (for the profile card) --------------------

class CustomerSummaryOut(BaseModel):
    customer_id: UUID
    headline: str = Field(
        description="One-line snapshot: who they are + current relationship status."
    )
    open_commitments_count: int
    open_tasks_count: int
    open_risks_count: int
    recent_events_count: int
    last_interaction_at: datetime | None = None
