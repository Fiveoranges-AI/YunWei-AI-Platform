"""Centralised re-export of every business enum used by the customer-
operations ontology.

The actual ``enum.Enum`` definitions live next to the model that owns
them (so that the SQLAlchemy ``Enum`` column and the Python ``enum``
stay in sync). This module is the single import point that callers
(API handlers, prompts, frontend codegen, tests) should use instead of
reaching into individual model modules:

    from yunwei_win.enums import (
        ContactRole,
        NextActionType,
        RiskKind,
        ...
    )

If you add a new ontology enum, define it in the relevant model module
*and* re-export it here so the index stays complete.
"""

from __future__ import annotations

from yunwei_win.models.contact import ContactRole
from yunwei_win.models.customer_memory import (
    CommitmentDirection,
    CommitmentStatus,
    CustomerEventType,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    InboxSourceKind,
    InboxStatus,
    InputChannel,
    InputModality,
    MemoryKind,
    RiskKind,
    RiskSeverity,
    RiskStatus,
    TaskPriority,
    TaskStatus,
)
from yunwei_win.models.document import DocumentType
from yunwei_win.models.document_extraction import DocumentExtractionStatus
from yunwei_win.models.document_parse import DocumentParseStatus
from yunwei_win.models.field_provenance import EntityType
from yunwei_win.models.ingest_job import IngestJobStage, IngestJobStatus
from yunwei_win.models.operations import (
    ActionTargetType,
    DeliveryStatus,
    NextActionStatus,
    NextActionType,
)

__all__ = [
    # contact / customer
    "ContactRole",
    # memory layer
    "CommitmentDirection", "CommitmentStatus",
    "CustomerEventType",
    "TaskPriority", "TaskStatus",
    "RiskSeverity", "RiskKind", "RiskStatus",
    "MemoryKind",
    "InboxSourceKind", "InboxStatus",
    "DocumentProcessingStatus", "DocumentReviewStatus",
    "InputChannel", "InputModality",
    # document layer
    "DocumentType",
    "DocumentExtractionStatus",
    "DocumentParseStatus",
    "EntityType",
    "IngestJobStage", "IngestJobStatus",
    # operations layer (P0 task ①)
    "NextActionType", "NextActionStatus",
    "ActionTargetType",
    "DeliveryStatus",
]
