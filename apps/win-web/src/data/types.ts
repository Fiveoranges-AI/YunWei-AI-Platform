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
  owner: string;
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
  tag: string;
  updated: string;
  aiSummary: string;
  metrics: CustomerMetrics;
  risk: CustomerRisk;
};

export type CustomerDetail = CustomerListItem & {
  timeline?: TimelineEvent[];
  commitments?: Commitment[];
  tasks?: CustomerTask[];
  risks?: RiskSignal[];
  contacts?: Contact[];
  docs?: Document[];
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
