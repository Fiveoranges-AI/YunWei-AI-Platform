"""Re-export all models so SQLAlchemy's mapper registry sees them.

Three layers:
  Entity layer:  customers / contacts / orders / contracts / documents
                 + field_provenance / llm_calls
  Memory layer:  customer_events / commitments / tasks / risk_signals
                 / memory_items / inbox_items
  Schema layer: company_schema_tables / company_schema_fields /
                   schema_change_proposals + foundation business tables
                   (products / invoices / payments / shipments / ...)
"""

# Customer-memory module first because document.py now imports its enums.
from yunwei_win.models.customer_memory import (
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
from yunwei_win.models.contact import Contact, ContactRole
from yunwei_win.models.contract import Contract
from yunwei_win.models.customer import Customer
from yunwei_win.models.document import Document, DocumentType
from yunwei_win.models.field_provenance import EntityType, FieldProvenance
from yunwei_win.models.ingest_job import (
    IngestBatch,
    IngestJob,
    IngestJobStage,
    IngestJobStatus,
)
from yunwei_win.models.llm_call import LLMCall
from yunwei_win.models.order import Order

# ---------------------------------------------------------------------------
# Schema-first company data layer.
# ---------------------------------------------------------------------------
from yunwei_win.models.company_schema import (
    CompanySchemaField,
    CompanySchemaTable,
    SchemaChangeProposal,
)
from yunwei_win.models.company_data import (
    ContractPaymentMilestone,
    CustomerJournalItem,
    Invoice,
    InvoiceItem,
    Payment,
    Product,
    ProductRequirement,
    Shipment,
    ShipmentItem,
)
from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)

__all__ = [
    # profile
    "Contact", "ContactRole",
    "Contract",
    "Customer",
    "Document", "DocumentType",
    "EntityType", "FieldProvenance",
    "LLMCall",
    "Order",
    # ingest jobs
    "IngestBatch", "IngestJob", "IngestJobStage", "IngestJobStatus",
    # customer-memory
    "CustomerEvent", "CustomerEventType",
    "CustomerCommitment", "CommitmentDirection", "CommitmentStatus",
    "CustomerTask", "TaskPriority", "TaskStatus",
    "CustomerRiskSignal", "RiskSeverity", "RiskKind", "RiskStatus",
    "CustomerMemoryItem", "MemoryKind",
    "CustomerInboxItem", "InboxSourceKind", "InboxStatus",
    "DocumentProcessingStatus", "DocumentReviewStatus",
    "InputChannel", "InputModality",
    # Schema catalog
    "CompanySchemaTable", "CompanySchemaField", "SchemaChangeProposal",
    # Company data foundation
    "Product", "ProductRequirement", "ContractPaymentMilestone",
    "Invoice", "InvoiceItem", "Payment",
    "Shipment", "ShipmentItem",
    "CustomerJournalItem",
    # Extraction record
    "DocumentExtraction", "DocumentExtractionStatus",
]
