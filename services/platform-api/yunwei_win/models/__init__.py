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
from yunwei_win.models.document_parse import (
    DocumentParse,
    DocumentParseStatus,
)

# ---------------------------------------------------------------------------
# Customer-operations ontology (P0 task ①).
# ---------------------------------------------------------------------------
from yunwei_win.models.operations import (
    ActionLog,
    ActionTargetType,
    Delivery,
    DeliveryStatus,
    InvoicePaymentAllocation,
    NextAction,
    NextActionStatus,
    NextActionType,
    OrderItem,
)

# ---------------------------------------------------------------------------
# Procurement / inventory ontology (锦泰 主线 — supplier / material /
# stock movement / issue voucher / requisition / PO / receipt / payable /
# stock alert).
# ---------------------------------------------------------------------------
from yunwei_win.models.procurement import (
    GoodsReceipt,
    IssueVoucher,
    IssueVoucherStatus,
    Material,
    MaterialKind,
    Payable,
    PayableStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequisition,
    PurchaseRequisitionItem,
    PurchaseRequisitionSource,
    PurchaseRequisitionStatus,
    StockAlert,
    StockAlertLevel,
    StockMovement,
    StockMovementDirection,
    StockMovementReferenceType,
    Supplier,
)

# ---------------------------------------------------------------------------
# 光天耐火材料 · AI 库存管家 (SKU 台账 / 出入库 / 缺货预警 / AI 补产建议)
# ---------------------------------------------------------------------------
from yunwei_win.models.guangtian import (
    GuangtianCustomerOrder,
    GuangtianCustomerOrderItem,
    GuangtianInboundType,
    GuangtianInboundVoucher,
    GuangtianMovementOp,
    GuangtianMovementRefType,
    GuangtianOrderLevel,
    GuangtianOutboundType,
    GuangtianOutboundVoucher,
    GuangtianReplenishment,
    GuangtianReplenishPriority,
    GuangtianReplenishStatus,
    GuangtianSku,
    GuangtianSkuKind,
    GuangtianStockAlert,
    GuangtianStockAlertLevel,
    GuangtianStockMovement,
    GuangtianStockStatus,
    GuangtianVoucherStatus,
)

# ---------------------------------------------------------------------------
# Finance (会企 01/02/03 — chart of accounts + opening balances + fixed assets)
# ---------------------------------------------------------------------------
from yunwei_win.models.finance import (
    AccountClass,
    ChartOfAccount,
    DEFAULT_CHART_OF_ACCOUNTS,
    FixedAsset,
    FixedAssetCategory,
    FixedAssetStatus,
    NormalBalance,
    PeriodOpeningBalance,
    StatementSection,
)

# ---------------------------------------------------------------------------
# BOM (配料单) — 锦泰 demo "配料单 D" 用
# ---------------------------------------------------------------------------
from yunwei_win.models.bom import (
    BillOfMaterials,
    BillOfMaterialsLine,
    BomStatus,
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
    # Parse record
    "DocumentParse", "DocumentParseStatus",
    # Customer-operations ontology (P0 task ①)
    "OrderItem",
    "Delivery", "DeliveryStatus",
    "InvoicePaymentAllocation",
    "NextAction", "NextActionType", "NextActionStatus",
    "ActionLog", "ActionTargetType",
    # Procurement / inventory ontology (锦泰 主线)
    "Supplier",
    "Material", "MaterialKind",
    "StockMovement", "StockMovementDirection", "StockMovementReferenceType",
    "IssueVoucher", "IssueVoucherStatus",
    "PurchaseRequisition", "PurchaseRequisitionItem",
    "PurchaseRequisitionStatus", "PurchaseRequisitionSource",
    "PurchaseOrder", "PurchaseOrderItem", "PurchaseOrderStatus",
    "GoodsReceipt",
    "Payable", "PayableStatus",
    "StockAlert", "StockAlertLevel",
    # 光天 · AI 库存管家
    "GuangtianSku", "GuangtianSkuKind", "GuangtianStockStatus",
    "GuangtianStockMovement", "GuangtianMovementOp", "GuangtianMovementRefType",
    "GuangtianInboundVoucher", "GuangtianInboundType",
    "GuangtianOutboundVoucher", "GuangtianOutboundType",
    "GuangtianVoucherStatus",
    "GuangtianStockAlert", "GuangtianStockAlertLevel",
    "GuangtianCustomerOrder", "GuangtianCustomerOrderItem", "GuangtianOrderLevel",
    "GuangtianReplenishment", "GuangtianReplenishPriority", "GuangtianReplenishStatus",
    # Finance (会企 01/02/03)
    "ChartOfAccount", "AccountClass", "StatementSection", "NormalBalance",
    "PeriodOpeningBalance",
    "FixedAsset", "FixedAssetCategory", "FixedAssetStatus",
    "DEFAULT_CHART_OF_ACCOUNTS",
    # BOM (配料单)
    "BillOfMaterials", "BillOfMaterialsLine", "BomStatus",
]
