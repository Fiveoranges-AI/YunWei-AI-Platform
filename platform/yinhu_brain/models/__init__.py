"""Re-export all models so SQLAlchemy's mapper registry sees them.

Two layers:
  Entity layer:  customers / contacts / orders / contracts / documents
                 + field_provenance / llm_calls
  Memory layer:  customer_events / commitments / tasks / risk_signals
                 / memory_items / inbox_items
"""

# Customer-memory module first because document.py now imports its enums.
from yinhu_brain.models.customer_memory import (
    CommitmentDirection,
    CommitmentStatus,
    CustomerCommitment,
    CustomerEvent,
    CustomerEventType,
    CustomerInboxItem,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
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
from yinhu_brain.models.contact import Contact, ContactRole
from yinhu_brain.models.contract import Contract
from yinhu_brain.models.customer import Customer
from yinhu_brain.models.document import Document, DocumentType
from yinhu_brain.models.field_provenance import EntityType, FieldProvenance
from yinhu_brain.models.llm_call import LLMCall
from yinhu_brain.models.order import Order

__all__ = [
    # profile
    "Contact", "ContactRole",
    "Contract",
    "Customer",
    "Document", "DocumentType",
    "EntityType", "FieldProvenance",
    "LLMCall",
    "Order",
    # customer-memory
    "CustomerEvent", "CustomerEventType",
    "CustomerCommitment", "CommitmentDirection", "CommitmentStatus",
    "CustomerTask", "TaskPriority", "TaskStatus",
    "CustomerRiskSignal", "RiskSeverity", "RiskKind", "RiskStatus",
    "CustomerMemoryItem", "MemoryKind",
    "CustomerInboxItem", "InboxSourceKind", "InboxStatus",
    "DocumentProcessingStatus", "DocumentReviewStatus",
    "InputChannel", "InputModality",
]
