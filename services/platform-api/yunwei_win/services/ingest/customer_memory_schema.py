"""Pydantic schemas for the customer-memory extraction tool call + the
inbox payload it produces.

Customer-scoped ingest persists this memory/event-log shape as inbox
``extracted_payload`` for human review.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from yunwei_win.services.ingest.common_schemas import (
    _strip_titles,
    _clean_date,
    FieldProvenanceEntry,
)


# -------- enums (mirror the SQL ENUMs but kept loose for LLM output) -----

class CustomerEventTypeEx(str, enum.Enum):
    contract_signed = "contract_signed"
    order_placed = "order_placed"
    payment_received = "payment_received"
    payment_due = "payment_due"
    shipment = "shipment"
    delivery = "delivery"
    acceptance = "acceptance"
    quality_issue = "quality_issue"
    complaint = "complaint"
    meeting = "meeting"
    call = "call"
    message = "message"
    introduction = "introduction"
    dispute = "dispute"
    other = "other"


class CommitmentDirectionEx(str, enum.Enum):
    we_to_customer = "we_to_customer"
    customer_to_us = "customer_to_us"
    mutual = "mutual"


class TaskPriorityEx(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    normal = "normal"
    low = "low"


class RiskSeverityEx(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskKindEx(str, enum.Enum):
    payment = "payment"
    quality = "quality"
    churn = "churn"
    legal = "legal"
    supply = "supply"
    relationship = "relationship"
    other = "other"


class MemoryKindEx(str, enum.Enum):
    preference = "preference"
    persona = "persona"
    context = "context"
    history = "history"
    decision_maker = "decision_maker"
    other = "other"


# -------- per-row payload pieces -----------------------------------------

class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, max_length=500)
    event_type: CustomerEventTypeEx = CustomerEventTypeEx.other
    occurred_at: datetime | str | None = None
    description: str | None = None
    raw_excerpt: str | None = Field(default=None, max_length=400)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ExtractedCommitment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    direction: CommitmentDirectionEx = CommitmentDirectionEx.mutual
    due_date: date | str | None = None
    raw_excerpt: str | None = Field(default=None, max_length=400)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("due_date", mode="before")
    @classmethod
    def _date(cls, v):
        return _clean_date(v)


class ExtractedTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    assignee: str | None = Field(default=None, max_length=128)
    due_date: date | str | None = None
    priority: TaskPriorityEx = TaskPriorityEx.normal
    raw_excerpt: str | None = Field(default=None, max_length=400)

    @field_validator("due_date", mode="before")
    @classmethod
    def _date(cls, v):
        return _clean_date(v)


class ExtractedRiskSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    severity: RiskSeverityEx = RiskSeverityEx.medium
    kind: RiskKindEx = RiskKindEx.other
    raw_excerpt: str | None = Field(default=None, max_length=400)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ExtractedMemoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = Field(default=None, max_length=2000)
    kind: MemoryKindEx = MemoryKindEx.context
    raw_excerpt: str | None = Field(default=None, max_length=400)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# -------- top-level extraction result ------------------------------------

class CustomerMemoryExtractionResult(BaseModel):
    """What the customer-memory extraction LLM call returns.

    `summary` is the human-friendly preview shown in the inbox.
    `confidence_overall` lets the operator triage which inbox items to
    review first.
    """

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(default="", max_length=1000)
    events: list[ExtractedEvent] = Field(default_factory=list)
    commitments: list[ExtractedCommitment] = Field(default_factory=list)
    tasks: list[ExtractedTask] = Field(default_factory=list)
    risk_signals: list[ExtractedRiskSignal] = Field(default_factory=list)
    memory_items: list[ExtractedMemoryItem] = Field(default_factory=list)
    field_provenance: list[FieldProvenanceEntry] = Field(default_factory=list)
    confidence_overall: float = Field(ge=0.0, le=1.0, default=0.5)
    parse_warnings: list[str] = Field(default_factory=list)


# -------- tool descriptors fed to the LLM -------------------------------

CUSTOMER_MEMORY_TOOL_NAME = "submit_customer_memory_extraction"


def customer_memory_tool() -> dict[str, Any]:
    return {
        "name": CUSTOMER_MEMORY_TOOL_NAME,
        "description": (
            "Submit the structured customer-memory extracted from an input "
            "(text note, screenshot, contract page, etc.) attached to a "
            "specific customer."
        ),
        "input_schema": _strip_titles(
            CustomerMemoryExtractionResult.model_json_schema()
        ),
    }
