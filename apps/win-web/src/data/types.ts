// Frontend types — matching the design's shape.
// API client (src/api/client.ts) translates yunwei-tools backend payloads to these.

export type RiskLevel = "low" | "med" | "high";
export type Confidence = "high" | "med" | "low";

export type CustomerMetrics = {
  contractTotal: number;
  receivable: number;
  contracts: number;
  tasks: number;
  contacts: number;
};

export type CustomerRisk = {
  level: RiskLevel;
  label: string;
  note: string;
};

export type TimelineEvent = {
  kind: "upload" | "meet" | "wechat" | "invoice";
  title: string;
  when: string;
  by: string;
  src: string;
};

export type Commitment = {
  id: string;
  text: string;
  source: string;
  confidence: Confidence;
};

export type CustomerTask = {
  id: string;
  text: string;
  due: string;
  // Person currently responsible for the task. Backend canonical column is
  // ``assignee`` (vNext). ``owner`` stays as a write-through alias for the
  // legacy mock customer cards still in MOCK_CUSTOMERS — UI should read
  // ``assignee`` for confirmed-ingest tasks and fall back to ``owner`` only
  // for legacy data.
  assignee?: string | null;
  owner?: string;
  priority?: string | null;
  status?: string | null;
  documentId?: string | null;
};

export type RiskSignal = {
  id: string;
  level: RiskLevel;
  title: string;
  detail: string;
  sources: string[];
};

export type Contact = {
  id: string;
  name: string;
  role: string;
  initial: string;
  phone: string;
  last: string;
  title?: string;
  mobile?: string;
  email?: string;
  address?: string;
  wechatId?: string;
};

export type Document = {
  id: string;
  name: string;
  kind: string;
  date: string;
};

export type CustomerListItem = {
  id: string;
  name: string;
  shortName?: string | null;
  address?: string | null;
  taxId?: string | null;
  monogram: string;
  color: string;
  // ``tag`` is purely a UI/UX bucket label ("重点客户" / "潜在" / …). It is
  // not a vNext ingest fact and isn't part of the backend response —
  // listCustomers() defaults it to "客户". CustomerList still uses it as a
  // filter chip for legacy mock data; vNext confirmed facts go through the
  // dedicated arrays below.
  tag: string;
  updated: string;
  aiSummary: string;
  metrics: CustomerMetrics;
  risk: CustomerRisk;
};

// vNext ingest facts surfaced on GET /api/win/customers/{id}. Fields mirror
// the snake_case backend payload but UUID/date stay as strings on the wire.

export type CustomerProduct = {
  id: string;
  sku?: string | null;
  name: string;
  description?: string | null;
  specification?: string | null;
  unit?: string | null;
};

export type CustomerProductRequirement = {
  id: string;
  productId?: string | null;
  requirementType?: string | null;
  requirementText: string;
  tolerance?: string | null;
  sourceDocumentId?: string | null;
};

export type CustomerOrder = {
  id: string;
  amountTotal?: number | null;
  amountCurrency?: string | null;
  deliveryPromisedDate?: string | null;
  deliveryAddress?: string | null;
  description?: string | null;
};

export type CustomerContract = {
  id: string;
  contractNoExternal?: string | null;
  contractNoInternal?: string | null;
  amountTotal?: number | null;
  amountCurrency?: string | null;
  deliveryTerms?: string | null;
  penaltyTerms?: string | null;
  signingDate?: string | null;
  effectiveDate?: string | null;
  expiryDate?: string | null;
};

export type ContractPaymentMilestone = {
  id: string;
  contractId: string;
  name?: string | null;
  ratio?: number | null;
  amount?: number | null;
  triggerEvent?: string | null;
  triggerOffsetDays?: number | null;
  dueDate?: string | null;
  rawText?: string | null;
};

export type CustomerInvoice = {
  id: string;
  orderId?: string | null;
  invoiceNo?: string | null;
  issueDate?: string | null;
  amountTotal?: number | null;
  amountCurrency?: string | null;
  taxAmount?: number | null;
  status?: string | null;
};

export type CustomerInvoiceItem = {
  id: string;
  invoiceId: string;
  productId?: string | null;
  description?: string | null;
  quantity?: number | null;
  unitPrice?: number | null;
  amount?: number | null;
};

export type CustomerPayment = {
  id: string;
  invoiceId?: string | null;
  paymentDate?: string | null;
  amount?: number | null;
  currency?: string | null;
  method?: string | null;
  referenceNo?: string | null;
};

export type CustomerShipment = {
  id: string;
  orderId?: string | null;
  shipmentNo?: string | null;
  carrier?: string | null;
  trackingNo?: string | null;
  shipDate?: string | null;
  deliveryDate?: string | null;
  deliveryAddress?: string | null;
  status?: string | null;
};

export type CustomerShipmentItem = {
  id: string;
  shipmentId: string;
  productId?: string | null;
  description?: string | null;
  quantity?: number | null;
  unit?: string | null;
};

export type CustomerJournalItem = {
  id: string;
  documentId?: string | null;
  itemType: string;
  title?: string | null;
  content?: string | null;
  occurredAt?: string | null;
  dueDate?: string | null;
  severity?: string | null;
  status?: string | null;
  confidence?: number | null;
  rawExcerpt?: string | null;
};

export type SourceDocumentRef = {
  id: string;
  type?: string | null;
  originalFilename?: string | null;
  contentType?: string | null;
  uploader?: string | null;
  reviewStatus?: string | null;
  createdAt?: string | null;
};

export type CustomerDetail = CustomerListItem & {
  // Profile fields newly exposed in vNext customer envelope.
  industry?: string | null;
  notes?: string | null;
  // Legacy memory-era streams (still populated for older drafts).
  timeline?: TimelineEvent[];
  commitments?: Commitment[];
  tasks?: CustomerTask[];
  risks?: RiskSignal[];
  contacts?: Contact[];
  docs?: Document[];
  // vNext confirmed-ingest facts.
  orders?: CustomerOrder[];
  contracts?: CustomerContract[];
  contractPaymentMilestones?: ContractPaymentMilestone[];
  invoices?: CustomerInvoice[];
  invoiceItems?: CustomerInvoiceItem[];
  payments?: CustomerPayment[];
  shipments?: CustomerShipment[];
  shipmentItems?: CustomerShipmentItem[];
  products?: CustomerProduct[];
  productRequirements?: CustomerProductRequirement[];
  journalItems?: CustomerJournalItem[];
  sourceDocuments?: SourceDocumentRef[];
};

export type AskMessage =
  | { role: "user"; text: string; when: string }
  | { role: "ai"; blocks: AskAIBlock };

export type AskAIBlock = {
  verdict: string;
  evidence: { id: string; type: string; label: string }[];
  next: string[];
  related: { kind: string; label: string }[];
};

export type AskSeed = {
  customerId: string;
  messages: AskMessage[];
  suggestions: string[];
};

// ============================================================
// Schema-first review types
// ============================================================

export type ReviewCellStatus =
  | "extracted"
  | "missing"
  | "low_confidence"
  | "edited"
  | "rejected"
  | "invalid";

export type ReviewCellSource = "ai" | "default" | "edited" | "empty" | "linked";

// vNext row decision covers create / update / link_existing / ignore. The
// legacy ``operation`` field is still emitted for backward compat with the
// older confirm path, but ``row_decision`` is the source of truth.
export type ReviewRowOperation =
  | "create"
  | "update"
  | "link_existing"
  | "ignore";

export type ReviewLockMode = "edit" | "read_only";
export type ReviewMatchLevel = "strong" | "weak" | "none";
export type ReviewPresentation = "card" | "table";
export type ReviewStepStatus = "empty" | "in_progress" | "complete";
export type ReviewStepKey =
  | "customer"
  | "contacts"
  | "commercial"
  | "finance"
  | "logistics_product"
  | "memory"
  | "summary";

export type ReviewCellEvidence = {
  page?: number | null;
  excerpt?: string | null;
};

export type ReviewSourceRef = {
  ref_type: string;
  ref_id: string;
  page?: number | null;
  bbox?: number[] | null;
  start?: number | null;
  end?: number | null;
  excerpt?: string | null;
  paragraph?: number | null;
  table_id?: string | null;
  sheet?: string | null;
  row?: number | null;
  col?: number | null;
};

export type ReviewCell = {
  field_name: string;
  label: string;
  data_type: string;
  required: boolean;
  is_array: boolean;
  value: unknown;
  display_value: string;
  status: ReviewCellStatus;
  confidence: number | null;
  evidence: ReviewCellEvidence | null;
  source: ReviewCellSource;
  source_refs?: ReviewSourceRef[];
  review_visible?: boolean;
  explicit_clear?: boolean;
};

export type ReviewEntityCandidate = {
  entity_id: string;
  label: string;
  match_level: ReviewMatchLevel;
  match_keys?: string[];
  confidence?: number | null;
  reason?: string | null;
};

export type ReviewRowDecision = {
  operation: ReviewRowOperation;
  selected_entity_id?: string | null;
  candidate_entities?: ReviewEntityCandidate[];
  match_level?: ReviewMatchLevel | null;
  match_keys?: string[];
  reason?: string | null;
};

export type ReviewRow = {
  client_row_id: string;
  entity_id: string | null;
  operation: ReviewRowOperation;
  cells: ReviewCell[];
  row_decision?: ReviewRowDecision | null;
  is_writable?: boolean;
};

export type ReviewTable = {
  table_name: string;
  label: string;
  purpose?: string | null;
  category?: string | null;
  is_array: boolean;
  rows: ReviewRow[];
  raw_extraction?: Record<string, unknown> | null;
  presentation?: ReviewPresentation;
  review_step?: string | null;
};

export type ReviewStep = {
  key: string;
  label: string;
  table_names: string[];
  status: ReviewStepStatus;
};

export type ReviewDraftDocument = {
  filename: string;
  summary?: string | null;
  source_text?: string | null;
};

export type ReviewDraftRoutePlanItem = {
  name: string;
  confidence?: number;
  reason?: string;
};

export type ReviewDraftRoutePlan = {
  selected_pipelines: ReviewDraftRoutePlanItem[];
};

export type ReviewDraftStatus = "pending_review" | "confirmed" | "ignored" | "failed";

export type ReviewDraft = {
  extraction_id: string;
  document_id: string;
  parse_id?: string | null;
  schema_version: number;
  status: ReviewDraftStatus;
  review_version?: number;
  current_step?: string | null;
  document: ReviewDraftDocument;
  // Kept optional for legacy job payloads still echoing selected_pipelines.
  route_plan?: ReviewDraftRoutePlan | null;
  steps?: ReviewStep[];
  tables: ReviewTable[];
  schema_warnings: string[];
  general_warnings: string[];
};

export type ReviewCellPatch = {
  table_name: string;
  client_row_id: string;
  field_name: string;
  value?: unknown;
  status?: ReviewCellStatus;
  entity_id?: string | null;
  operation?: ReviewRowOperation;
};

export type ReviewRowDecisionPatch = {
  table_name: string;
  client_row_id: string;
  operation?: ReviewRowOperation;
  selected_entity_id?: string | null;
  match_level?: ReviewMatchLevel | null;
  match_keys?: string[];
  reason?: string | null;
};

export type AutosaveReviewRequest = {
  lock_token: string;
  base_version: number;
  current_step?: string | null;
  cell_patches?: ReviewCellPatch[];
  row_patches?: ReviewRowDecisionPatch[];
};

export type AutosaveReviewResponse = {
  extraction_id: string;
  review_version: number;
  current_step: string | null;
  lock_expires_at?: string | null;
  review_draft: ReviewDraft | null;
};

export type AcquireReviewLockResponse = {
  extraction_id: string;
  mode: ReviewLockMode;
  lock_token?: string | null;
  locked_by?: string | null;
  lock_expires_at?: string | null;
  review_version: number;
};

export type ConfirmExtractionRequest = {
  lock_token: string;
  base_version: number;
};

export type IngestJobStatus =
  | "queued"
  | "running"
  | "extracted"
  | "confirmed"
  | "failed"
  | "canceled";

export type IngestJob = {
  id: string;
  batch_id: string;
  enterprise_id: string;
  status: IngestJobStatus;
  stage: string;
  original_filename: string;
  content_type?: string | null;
  uploader?: string | null;
  source_hint: string;
  progress_message?: string | null;
  error_message?: string | null;
  document_id?: string | null;
  extraction_id?: string | null;
  result_json?: ReviewDraft | null;
  review_draft?: ReviewDraft | null;
  attempts: number;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type ConfirmExtractionInvalidCell = {
  table_name: string;
  client_row_id: string;
  field_name: string;
  reason: string;
};

export type ConfirmExtractionResponse = {
  extraction_id: string;
  document_id: string;
  status: ReviewDraftStatus;
  written_rows: Record<string, string[]>;
  invalid_cells: ConfirmExtractionInvalidCell[];
};

// Returned by GET on /extractions/{id} and /extractions/{id}/review.
// Mirrors `_extraction_dict` in
// services/platform-api/yunwei_win/api/schema_ingest.py — an envelope
// around the ReviewDraft, NOT the bare draft. Legacy fields (warnings,
// route_plan, created_by, schema_version) are optional so old persisted
// rows don't break the type narrow.
export type ExtractionEnvelope = {
  id: string;
  document_id: string;
  parse_id?: string | null;
  provider: string | null;
  model?: string | null;
  status: ReviewDraftStatus;
  selected_tables?: unknown;
  extraction?: unknown;
  extraction_metadata?: unknown;
  validation_warnings?: string[] | null;
  entity_resolution?: unknown;
  review_draft: ReviewDraft | null;
  review_version?: number;
  locked_by?: string | null;
  lock_expires_at?: string | null;
  last_reviewed_by?: string | null;
  last_reviewed_at?: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  // Lock sub-envelope returned by GET /review (lock_token deliberately
  // omitted on generic GETs — it only comes back from /review/lock).
  lock?: {
    locked_by?: string | null;
    lock_expires_at?: string | null;
  };
  // Legacy compatibility — older endpoint versions may still return these.
  schema_version?: number;
  warnings?: unknown;
  route_plan?: ReviewDraftRoutePlan | null;
  created_by?: string | null;
};

export type CompanySchemaField = {
  id: string;
  field_name: string;
  label: string;
  data_type: string;
  required: boolean;
  is_array: boolean;
  enum_values?: string[] | null;
  default_value?: unknown;
  description?: string | null;
  extraction_hint?: string | null;
  sort_order: number;
  is_active: boolean;
};

export type CompanySchemaTable = {
  id: string;
  table_name: string;
  label: string;
  purpose?: string | null;
  category?: string | null;
  version: number;
  is_active: boolean;
  sort_order: number;
  fields: CompanySchemaField[];
};

export type CompanySchema = {
  tables: CompanySchemaTable[];
};
