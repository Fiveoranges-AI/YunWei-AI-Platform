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

export type ExtractionKind = "commitment" | "task" | "risk" | "contact";

export type ReviewExtraction = {
  kind: ExtractionKind;
  title: string;
  text: string;
  source: { type: string; label: string };
  conf: Confidence;
};

export type ReviewField = {
  key: string;
  value: string;
  conf: Confidence;
};

export type ReviewEvidence = {
  id: string;
  type: string;
  label: string;
  preview: string;
};

export type SchemaSummaryItem = {
  schemaName: string;        // raw backend name, e.g. "contract_order"
  schemaLabel: string;       // Chinese display label, e.g. "合同/订单"
  confidence: number;        // 0-1 from router
  reason: string;            // why the router picked it
  extracted: string[];       // human-readable fields with values
  missing: string[];         // human-readable required fields without values
  warnings: string[];        // schema-level warnings (extract failures + extraction_warnings)
  pipelineResultMissing: boolean; // router selected it but pipeline_results didn't include it
};

export type SchemaSummary = {
  selectedSchemas: SchemaSummaryItem[];
  routePlanMissing: boolean;        // backend didn't return route_plan
  pipelineResultsMissing: boolean;  // backend didn't return pipeline_results
  // Final state on the merged UnifiedDraft after normalize.
  // Lets reviewers see whether contract_order's order actually survived
  // into draft.order — independent of what the schema extracted.
  finalDraftStatus: {
    hasCustomer: boolean;
    hasContacts: boolean;
    hasContract: boolean;
    hasOrder: boolean;
    hasOrderAmount: boolean;
    hasPaymentMilestones: boolean;
  };
  // Document-level warnings that aren't tied to a single schema.
  generalWarnings: string[];
};

export type Review = {
  customer: { name: string; isExisting: boolean; confidence: number };
  channel: string;
  docType: string;
  contact: { name: string; role: string; initial: string };
  confidence: number;
  fields: ReviewField[];
  extractions: ReviewExtraction[];
  missing: string[];
  evidence: ReviewEvidence[];
  schemaSummary?: SchemaSummary;
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
