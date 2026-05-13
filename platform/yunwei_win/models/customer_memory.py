"""Customer-memory tables (events / commitments / tasks / risk_signals / memory_items).

These layer on top of the structured profile (customers / contacts / orders /
contracts) and capture *temporal*, *actionable*, and *factual* knowledge
distilled from incoming inputs (text notes, screenshots, contracts, etc.).

Writes go through the inbox review queue (customer_inbox_items) — the AI
proposes, a human confirms before rows land here.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin

if TYPE_CHECKING:
    pass


# ============================== enums =====================================

class CustomerEventType(str, enum.Enum):
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


class CommitmentDirection(str, enum.Enum):
    we_to_customer = "we_to_customer"
    customer_to_us = "customer_to_us"
    mutual = "mutual"


class CommitmentStatus(str, enum.Enum):
    open = "open"
    fulfilled = "fulfilled"
    overdue = "overdue"
    cancelled = "cancelled"


class TaskPriority(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    normal = "normal"
    low = "low"


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class RiskSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskKind(str, enum.Enum):
    payment = "payment"
    quality = "quality"
    churn = "churn"
    legal = "legal"
    supply = "supply"
    relationship = "relationship"
    other = "other"


class RiskStatus(str, enum.Enum):
    open = "open"
    mitigated = "mitigated"
    resolved = "resolved"
    dismissed = "dismissed"


class MemoryKind(str, enum.Enum):
    preference = "preference"
    persona = "persona"
    context = "context"
    history = "history"
    decision_maker = "decision_maker"
    other = "other"


class InboxSourceKind(str, enum.Enum):
    contract = "contract"
    business_card = "business_card"
    wechat_screenshot = "wechat_screenshot"
    text_note = "text_note"
    other = "other"


class InboxStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    ignored = "ignored"


class DocumentProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    parsed = "parsed"
    failed = "failed"


class DocumentReviewStatus(str, enum.Enum):
    pending_review = "pending_review"
    confirmed = "confirmed"
    ignored = "ignored"
    not_applicable = "not_applicable"


class InputChannel(str, enum.Enum):
    web_upload = "web_upload"
    dingtalk = "dingtalk"
    email = "email"
    api = "api"
    other = "other"


class InputModality(str, enum.Enum):
    pdf = "pdf"
    image = "image"
    text = "text"
    voice = "voice"
    other = "other"


# ============================== tables ====================================


class CustomerEvent(Base, TimestampMixin):
    """Significant happenings about a customer: contracts signed, payments,
    complaints, meetings, etc. Drives the timeline view."""

    __tablename__ = "customer_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    event_type: Mapped[CustomerEventType] = mapped_column(
        SQLEnum(CustomerEventType, name="customer_event_type"),
        nullable=False,
        default=CustomerEventType.other,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)


class CustomerCommitment(Base, TimestampMixin):
    """A promise — either we to customer (will deliver / will refund) or
    customer to us (will pay by date / will sign by date)."""

    __tablename__ = "customer_commitments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    direction: Mapped[CommitmentDirection] = mapped_column(
        SQLEnum(CommitmentDirection, name="commitment_direction"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[CommitmentStatus] = mapped_column(
        SQLEnum(CommitmentStatus, name="commitment_status"),
        nullable=False,
        default=CommitmentStatus.open,
        index=True,
    )
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)


class CustomerTask(Base, TimestampMixin):
    """Actionable next step for our team. Generated from commitments,
    risk signals, or pasted "follow up" notes."""

    __tablename__ = "customer_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    priority: Mapped[TaskPriority] = mapped_column(
        SQLEnum(TaskPriority, name="task_priority"),
        nullable=False,
        default=TaskPriority.normal,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.open,
        index=True,
    )
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerRiskSignal(Base, TimestampMixin):
    """A flag that something might go wrong: late payment pattern, quality
    complaint, decision-maker churn, etc."""

    __tablename__ = "customer_risk_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[RiskSeverity] = mapped_column(
        SQLEnum(RiskSeverity, name="risk_severity"), nullable=False
    )
    kind: Mapped[RiskKind] = mapped_column(
        SQLEnum(RiskKind, name="risk_kind"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[RiskStatus] = mapped_column(
        SQLEnum(RiskStatus, name="risk_status"),
        nullable=False,
        default=RiskStatus.open,
        index=True,
    )
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)


class CustomerMemoryItem(Base, TimestampMixin):
    """A factual / preferential note about a customer. Used by Q&A as a
    long-term memory store — "客户更喜欢周一开会"、"决策人是 CTO 王总" etc."""

    __tablename__ = "customer_memory_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[MemoryKind] = mapped_column(
        SQLEnum(MemoryKind, name="memory_kind"),
        nullable=False,
        default=MemoryKind.context,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)


class CustomerInboxItem(Base, TimestampMixin):
    """Pending review row — AI-extracted memory that hasn't been written to
    the official tables yet. On confirm, the contents of `extracted_payload`
    fan out into customer_events / commitments / tasks / risks / memory_items."""

    __tablename__ = "customer_inbox_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_kind: Mapped[InboxSourceKind] = mapped_column(
        SQLEnum(InboxSourceKind, name="inbox_source_kind"),
        nullable=False,
        default=InboxSourceKind.other,
    )
    summary: Mapped[str] = mapped_column(
        String(1000), nullable=False, default=""
    )
    extracted_payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    status: Mapped[InboxStatus] = mapped_column(
        SQLEnum(InboxStatus, name="inbox_status"),
        nullable=False,
        default=InboxStatus.pending,
        index=True,
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    parse_warnings: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
