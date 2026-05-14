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

export type ReviewCellSource = "ai" | "default" | "edited" | "empty";

export type ReviewRowOperation = "create" | "update";

export type ReviewCellEvidence = {
  page?: number | null;
  excerpt?: string | null;
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
};

export type ReviewRow = {
  client_row_id: string;
  entity_id: string | null;
  operation: ReviewRowOperation;
  cells: ReviewCell[];
};

export type ReviewTable = {
  table_name: string;
  label: string;
  purpose?: string | null;
  category?: string | null;
  is_array: boolean;
  rows: ReviewRow[];
  raw_extraction?: Record<string, unknown> | null;
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
  schema_version: number;
  status: ReviewDraftStatus;
  document: ReviewDraftDocument;
  route_plan: ReviewDraftRoutePlan;
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
