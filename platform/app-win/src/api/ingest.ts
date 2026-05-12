// POST /win/api/ingest/auto — unified planner-driven file/text intake.
//
// The legacy per-kind endpoints (/contract, /business_card, /wechat_screenshot)
// have been replaced by a single `/auto` route. The backend planner inspects
// the document and decides which extractors to fan out to (identity /
// commercial / ops). The frontend no longer guesses the document kind from
// filename — every file (and every block of pasted text) goes to /auto, and
// the unified draft drives the Review screen.
//
// After a batch settles, Upload.tsx calls setLastBatch(...) so the Review
// screen renders the actual backend payload via batchToReview().

import type {
  Confidence,
  EditableDraftPath,
  EditableFieldMeta,
  Review,
  ReviewEvidence,
  ReviewExtraction,
  ReviewField,
  SchemaSummary,
  SchemaSummaryItem,
} from "../data/types";

const API_BASE = "/win/api/ingest";

// ───────────── Backend payload shapes (mirror unified_schemas.py) ─────────────

export type ExtractorName = "identity" | "commercial" | "ops";

export type ExtractorSelection = {
  name: ExtractorName;
  confidence: number;
};

export type IngestPlan = {
  targets: Partial<Record<ExtractorName, number>>;
  extractors: ExtractorSelection[];
  reason: string;
  review_required: boolean;
};

// LLM schema router output — multi-label selection of the six canonical
// pipelines. Surfaced by /auto as `route_plan`. Both LandingAI and Mistral
// branches populate this; the legacy ``plan.extractors`` is still set for
// backward compat (Mistral path) but is empty on the LandingAI path.
export type SchemaPipelineName =
  | "identity"
  | "contract_order"
  | "finance"
  | "logistics"
  | "manufacturing_requirement"
  | "commitment_task_risk";

export type RoutedPipelineSelection = {
  name: SchemaPipelineName;
  confidence: number;
  reason?: string;
};

export type RoutePlan = {
  primary_pipeline: SchemaPipelineName | null;
  selected_pipelines: RoutedPipelineSelection[];
  rejected_pipelines: RoutedPipelineSelection[];
  document_summary: string;
  needs_human_review: boolean;
};

// CustomerExtraction
export type IdentityCustomer = {
  full_name: string | null;
  short_name: string | null;
  address: string | null;
  tax_id: string | null;
};

// ContactExtraction
export type IdentityContact = {
  name: string | null;
  title: string | null;
  phone: string | null;
  mobile: string | null;
  email: string | null;
  role: ContactRole;
  address: string | null;
};

export type ContactRole =
  | "seller"
  | "buyer"
  | "delivery"
  | "acceptance"
  | "invoice"
  | "other";

// OrderExtraction
export type CommercialOrder = {
  amount_total: number | null;
  amount_currency: string;
  delivery_promised_date: string | null;
  delivery_address: string | null;
  description: string | null;
};

export type TriggerEvent =
  | "contract_signed"
  | "before_shipment"
  | "on_delivery"
  | "on_acceptance"
  | "invoice_issued"
  | "warranty_end"
  | "on_demand"
  | "other";

export type PaymentMilestone = {
  name: string | null;
  ratio: number;
  trigger_event: TriggerEvent;
  trigger_offset_days: number | null;
  raw_text: string | null;
};

// ContractExtraction
export type CommercialContract = {
  contract_no_external: string | null;
  payment_milestones: PaymentMilestone[];
  delivery_terms: string | null;
  penalty_terms: string | null;
  signing_date: string | null;
  effective_date: string | null;
  expiry_date: string | null;
};

export type FieldProvenanceEntry = {
  path: string;
  source_page: number | null;
  source_excerpt: string | null;
};

// ExtractedEvent / Commitment / Task / Risk / Memory — kept loose (fields land
// in the inbox payload as-is). Only the bits we actually render are typed.
export type ExtractedEvent = {
  title: string | null;
  event_type: string;
  occurred_at: string | null;
  description: string | null;
  raw_excerpt: string | null;
  confidence: number | null;
};

export type ExtractedCommitment = {
  summary: string | null;
  description: string | null;
  direction: "we_to_customer" | "customer_to_us" | "mutual";
  due_date: string | null;
  raw_excerpt: string | null;
  confidence: number | null;
};

export type ExtractedTask = {
  title: string | null;
  description: string | null;
  assignee: string | null;
  due_date: string | null;
  priority: "urgent" | "high" | "normal" | "low";
  raw_excerpt: string | null;
};

export type ExtractedRiskSignal = {
  summary: string | null;
  description: string | null;
  severity: "low" | "medium" | "high";
  kind: "payment" | "quality" | "churn" | "legal" | "supply" | "relationship" | "other";
  raw_excerpt: string | null;
  confidence: number | null;
};

export type ExtractedMemoryItem = {
  content: string | null;
  kind: "preference" | "persona" | "context" | "history" | "decision_maker" | "other";
  raw_excerpt: string | null;
  confidence: number | null;
};

// LandingAI schema-routed pipeline extraction results
export type PipelineName =
  | "identity"
  | "contract_order"
  | "finance"
  | "logistics"
  | "manufacturing_requirement"
  | "commitment_task_risk";

export type PipelineExtractResult = {
  name: PipelineName | string;
  extraction: Record<string, unknown>;
  extraction_metadata: Record<string, unknown>;
  warnings: string[];
};

// UnifiedDraft — merged output of all activated extractors
export type UnifiedDraft = {
  customer: IdentityCustomer | null;
  contacts: IdentityContact[];
  order: CommercialOrder | null;
  contract: CommercialContract | null;
  events: ExtractedEvent[];
  commitments: ExtractedCommitment[];
  tasks: ExtractedTask[];
  risk_signals: ExtractedRiskSignal[];
  memory_items: ExtractedMemoryItem[];
  summary: string;
  field_provenance: FieldProvenanceEntry[];
  confidence_overall: number;
  needs_review_fields: string[];
  warnings: string[];
  pipeline_results?: PipelineExtractResult[];
};

export type MatchCandidate<T> = {
  id: string;
  score?: number;
  reason?: string;
  fields?: Partial<T>;
};

export type AutoCandidates = {
  customer: MatchCandidate<IdentityCustomer>[];
  contacts: MatchCandidate<IdentityContact>[][];
};

// ───────────── Confirm payload ─────────────

export type CustomerDecision = {
  mode: "new" | "merge" | "bind_existing";
  existing_id?: string;
  final: IdentityCustomer;
};

export type ContactDecision = {
  mode: "new" | "merge" | "bind_existing";
  existing_id?: string;
  final: IdentityContact;
};

export type AutoConfirmRequest = {
  customer: CustomerDecision | null;
  contacts: ContactDecision[];
  order: CommercialOrder | null;
  contract: CommercialContract | null;
  events: ExtractedEvent[];
  commitments: ExtractedCommitment[];
  tasks: ExtractedTask[];
  risk_signals: ExtractedRiskSignal[];
  memory_items: ExtractedMemoryItem[];
  field_provenance: FieldProvenanceEntry[];
  confidence_overall: number;
  parse_warnings: string[];
};

export type AutoConfirmResponse = {
  document_id: string;
  created_entities?: {
    customer_id?: string | null;
    contact_ids?: string[];
    order_id?: string | null;
    contract_id?: string | null;
    event_ids?: string[];
    commitment_ids?: string[];
    task_ids?: string[];
    risk_signal_ids?: string[];
    memory_item_ids?: string[];
  };
  confidence_overall?: number;
  warnings?: string[];
  needs_review_fields?: string[];
};

// ───────────── Upload result types ─────────────

export type AutoIngestRaw = {
  plan: IngestPlan;
  route_plan?: RoutePlan | null;
  draft: UnifiedDraft;
  candidates: AutoCandidates;
  needs_review_fields: string[];
  pipeline_results?: PipelineExtractResult[];
};

export type AutoIngestSuccess = {
  ok: true;
  documentId: string;
  raw: AutoIngestRaw;
};

export type IngestFailure = {
  ok: false;
  error: string;
  unsupported?: boolean;
};

export type IngestResult = AutoIngestSuccess | IngestFailure;

export type IngestProgress = {
  stage: string;
  message: string;
  status: "uploading" | "progress" | "processing";
};

export type IngestProgressCallback = (event: IngestProgress) => void;

// ───────────── Upload entry points ─────────────

export async function uploadStagedFile(
  file: File,
  sourceHint: "file" | "camera",
  onProgress?: IngestProgressCallback,
): Promise<IngestResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("source_hint", sourceHint);
  return postAuto(fd, onProgress);
}

export async function uploadPastedText(
  text: string,
  onProgress?: IngestProgressCallback,
): Promise<IngestResult> {
  const fd = new FormData();
  fd.append("text", text);
  fd.append("source_hint", "pasted_text");
  return postAuto(fd, onProgress);
}

async function postAuto(
  fd: FormData,
  onProgress?: IngestProgressCallback,
): Promise<IngestResult> {
  try {
    onProgress?.({ status: "uploading", stage: "upload", message: "正在上传内容" });
    const res = await fetch(`${API_BASE}/auto`, {
      method: "POST",
      body: fd,
      credentials: "include",
    });
    if (!res.ok) {
      // Pre-stream HTTP errors (validation, auth) — body is small JSON.
      let detail = `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* response wasn't JSON */
      }
      return { ok: false, error: detail };
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/x-ndjson")) {
      return await readNdjsonResult(res, onProgress);
    }
    // Backwards compat with non-streaming responses (shouldn't happen in
    // production, but keep the path so dev mocks don't break).
    const body = (await res.json()) as Partial<AutoIngestRaw> & { document_id?: string };
    return finalizeAutoResult(body);
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "网络错误" };
  }
}

// The /auto endpoint streams NDJSON: zero or more progress / processing
// events drive the UI pipeline; the final non-empty done/error line is the
// result payload. processing heartbeats keep Cloudflare's 100s edge timeout
// from firing during a long LLM call.
async function readNdjsonResult(
  res: Response,
  onProgress?: IngestProgressCallback,
): Promise<IngestResult> {
  if (!res.body) {
    return { ok: false, error: "无响应数据" };
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  type StreamMessage = {
    status?: string;
    stage?: string;
    message?: string;
    error?: string;
    document_id?: string;
    plan?: IngestPlan;
    route_plan?: RoutePlan | null;
    draft?: UnifiedDraft;
    candidates?: AutoCandidates;
    needs_review_fields?: string[];
    pipeline_results?: PipelineExtractResult[];
  };
  let last: StreamMessage | null = null;
  const handleLine = (line: string): StreamMessage | null => {
    try {
      const parsed = JSON.parse(line) as StreamMessage;
      if (parsed.status === "progress" || parsed.status === "processing") {
        onProgress?.({
          status: parsed.status,
          stage: parsed.stage ?? "processing",
          message: parsed.message ?? "处理中",
        });
      }
      if (parsed.status === "done" || parsed.status === "error") {
        return parsed;
      }
    } catch {
      /* ignore partial / malformed lines */
    }
    return null;
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl = buf.indexOf("\n");
    while (nl !== -1) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) {
        last = handleLine(line) ?? last;
      }
      nl = buf.indexOf("\n");
    }
  }
  // Drain any trailing line that lacked a terminator.
  const tail = buf.trim();
  if (tail) {
    last = handleLine(tail) ?? last;
  }
  if (!last) return { ok: false, error: "服务器未返回结果" };
  if (last.status === "done") return finalizeAutoResult(last);
  if (last.status === "error") return { ok: false, error: last.error ?? "服务器错误" };
  return { ok: false, error: "未知响应状态" };
}

function finalizeAutoResult(
  body:
    | (Partial<AutoIngestRaw> & {
        document_id?: string;
      })
    | null
    | undefined,
): IngestResult {
  if (!body || !body.document_id) {
    return { ok: false, error: "服务器响应缺少 document_id" };
  }
  return {
    ok: true,
    documentId: body.document_id,
    raw: {
      plan: body.plan ?? { targets: {}, extractors: [], reason: "", review_required: false },
      route_plan: body.route_plan ?? null,
      draft: body.draft ?? emptyDraft(),
      candidates: body.candidates ?? { customer: [], contacts: [] },
      needs_review_fields: body.needs_review_fields ?? body.draft?.needs_review_fields ?? [],
      pipeline_results: body.pipeline_results ?? body.draft?.pipeline_results ?? [],
    },
  };
}

function emptyDraft(): UnifiedDraft {
  return {
    customer: null,
    contacts: [],
    order: null,
    contract: null,
    events: [],
    commitments: [],
    tasks: [],
    risk_signals: [],
    memory_items: [],
    summary: "",
    field_provenance: [],
    confidence_overall: 0.5,
    needs_review_fields: [],
    warnings: [],
  };
}

// ───────────── Async job mode (RQ-backed) ─────────────
//
// The job endpoints return immediately with a queued IngestJob row; the
// worker runs OCR/route/extract/merge in the background and writes the
// final result_json onto the same row. The Upload screen polls
// listIngestJobs() while any job is queued/running, then opens Review for
// jobs that have reached `extracted`.

export type IngestJobStatus =
  | "queued"
  | "running"
  | "extracted"
  | "confirmed"
  | "failed"
  | "canceled";

export type IngestJobStage =
  | "received"
  | "stored"
  | "ocr"
  | "route"
  | "extract"
  | "merge"
  | "draft"
  | "done";

export type IngestJob = {
  id: string;
  batch_id: string;
  document_id: string | null;
  original_filename: string;
  content_type: string | null;
  source_hint: "file" | "camera" | "pasted_text";
  uploader: string | null;
  status: IngestJobStatus;
  stage: IngestJobStage;
  progress_message: string | null;
  error_message: string | null;
  attempts: number;
  result_json: AutoIngestRaw | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type CreateJobsResponse = {
  batch_id: string;
  jobs: IngestJob[];
};

/**
 * Stage one or more files / a pasted text into the async ingest queue.
 * Returns immediately with the created jobs. Caller polls GET /jobs/{id}
 * (or GET /jobs?status=active) to track progress.
 */
export async function createIngestJobs(input: {
  files: File[];
  text?: string;
  sourceHint: "file" | "camera" | "pasted_text";
  uploader?: string;
}): Promise<CreateJobsResponse> {
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  if (input.text && input.text.trim()) fd.append("text", input.text);
  fd.append("source_hint", input.sourceHint);
  if (input.uploader) fd.append("uploader", input.uploader);
  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body: fd,
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as CreateJobsResponse;
}

export async function listIngestJobs(
  status: "active" | "history" | "all" = "active",
  limit = 50,
): Promise<IngestJob[]> {
  const url = `${API_BASE}/jobs?status=${status}&limit=${limit}`;
  const res = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as IngestJob[];
}

export async function getIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as IngestJob;
}

export async function retryIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/retry`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as IngestJob;
}

export async function cancelIngestJob(jobId: string): Promise<IngestJob> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as IngestJob;
}

/** Job-aware confirm — same payload as /auto/{id}/confirm. */
export async function confirmIngestJob(
  jobId: string,
  payload: AutoConfirmRequest,
): Promise<AutoConfirmResponse & { job_id: string }> {
  return postJSON<AutoConfirmResponse & { job_id: string }>(
    `/jobs/${jobId}/confirm`,
    payload,
  );
}

// ───────────── Batch state shared with Review screen ─────────────

export type CustomerDecisionOverride =
  | {
      kind: "bind_existing";
      existing_id: string;
      existing_name: string;
      // when true → use mode=merge to update master fields
      updateMaster: boolean;
    }
  | { kind: "new" };

export type BatchEntry = {
  filename: string;
  result: IngestResult;
  customerDecisionOverride?: CustomerDecisionOverride;
};

export type Batch = { entries: BatchEntry[] };

let _last: Batch | null = null;

export function setLastBatch(b: Batch): void {
  _last = b;
}
export function getLastBatch(): Batch | null {
  return _last;
}
export function clearLastBatch(): void {
  _last = null;
}

/**
 * Convert an extracted IngestJob into the legacy Batch shape so the
 * Review screen can render it with batchToReview() without any changes.
 * Returns null when the job has not finished extraction yet (result_json
 * or document_id missing).
 */
export function jobToBatch(job: IngestJob): Batch | null {
  if (!job.result_json || !job.document_id) return null;
  const entry: BatchEntry = {
    filename: job.original_filename,
    result: {
      ok: true,
      documentId: job.document_id,
      raw: job.result_json,
    },
  };
  return { entries: [entry] };
}

// ───────────── Confirm / cancel API ─────────────

export type ArchiveResult = {
  confirmedDocuments: number;
  customerIds: string[];
  warnings: string[];
};

const CUSTOMER_MERGE_THRESHOLD = 0.95;
const CONTACT_MERGE_THRESHOLD = 0.99;

const VALID_ROLES = new Set<ContactRole>([
  "seller",
  "buyer",
  "delivery",
  "acceptance",
  "invoice",
  "other",
]);

const VALID_TRIGGERS = new Set<TriggerEvent>([
  "contract_signed",
  "before_shipment",
  "on_delivery",
  "on_acceptance",
  "invoice_issued",
  "warranty_end",
  "on_demand",
  "other",
]);

const ROLE_CN: Record<string, string> = {
  seller: "销售方",
  buyer: "采购方",
  delivery: "收货",
  acceptance: "验收",
  invoice: "开票",
  other: "其他",
};

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown; error?: unknown; message?: unknown };
    const detail = body.detail ?? body.error ?? body.message;
    if (typeof detail === "string") return detail;
    if (detail) return JSON.stringify(detail);
  } catch {
    /* response wasn't JSON */
  }
  return `HTTP ${res.status}`;
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as T;
}

function asRole(role: string | null | undefined): ContactRole {
  return VALID_ROLES.has(role as ContactRole) ? (role as ContactRole) : "other";
}

function asTrigger(trigger: string | null | undefined): TriggerEvent {
  return VALID_TRIGGERS.has(trigger as TriggerEvent) ? (trigger as TriggerEvent) : "other";
}

function fallbackText(current: string | null, previous: string | null | undefined): string | null {
  return current && current.trim() ? current : previous ?? current;
}

function bestCandidate<T>(
  candidates: MatchCandidate<T>[] | undefined,
  threshold: number,
): MatchCandidate<T> | null {
  const sorted = [...(candidates ?? [])].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const best = sorted[0];
  return best && (best.score ?? 0) >= threshold ? best : null;
}

function normalizeCustomer(raw: IdentityCustomer | null | undefined): IdentityCustomer {
  return {
    full_name: raw?.full_name ?? null,
    short_name: raw?.short_name ?? null,
    address: raw?.address ?? null,
    tax_id: raw?.tax_id ?? null,
  };
}

function normalizeContact(raw: IdentityContact | undefined): IdentityContact {
  return {
    name: raw?.name ?? null,
    title: raw?.title ?? null,
    phone: raw?.phone ?? null,
    mobile: raw?.mobile ?? null,
    email: raw?.email ?? null,
    role: asRole(raw?.role),
    address: raw?.address ?? null,
  };
}

function normalizeOrder(raw: CommercialOrder | null | undefined): CommercialOrder | null {
  if (!raw) return null;
  return {
    amount_total: raw.amount_total ?? null,
    amount_currency: raw.amount_currency ?? "CNY",
    delivery_promised_date: raw.delivery_promised_date ?? null,
    delivery_address: raw.delivery_address ?? null,
    description: raw.description ?? null,
  };
}

function normalizeContract(
  raw: CommercialContract | null | undefined,
): CommercialContract | null {
  if (!raw) return null;
  return {
    contract_no_external: raw.contract_no_external ?? null,
    payment_milestones: (raw.payment_milestones ?? []).map((m) => ({
      name: m.name ?? null,
      ratio: typeof m.ratio === "number" ? m.ratio : 0,
      trigger_event: asTrigger(m.trigger_event),
      trigger_offset_days: m.trigger_offset_days ?? null,
      raw_text: m.raw_text ?? null,
    })),
    delivery_terms: raw.delivery_terms ?? null,
    penalty_terms: raw.penalty_terms ?? null,
    signing_date: raw.signing_date ?? null,
    effective_date: raw.effective_date ?? null,
    expiry_date: raw.expiry_date ?? null,
  };
}

function customerWithCandidate(
  final: IdentityCustomer,
  candidate: MatchCandidate<IdentityCustomer> | null,
): IdentityCustomer {
  if (!candidate?.fields) return final;
  return {
    full_name: fallbackText(final.full_name, candidate.fields.full_name),
    short_name: fallbackText(final.short_name, candidate.fields.short_name),
    address: fallbackText(final.address, candidate.fields.address),
    tax_id: fallbackText(final.tax_id, candidate.fields.tax_id),
  };
}

function contactWithCandidate(
  final: IdentityContact,
  candidate: MatchCandidate<IdentityContact> | null,
): IdentityContact {
  if (!candidate?.fields) return final;
  return {
    name: fallbackText(final.name, candidate.fields.name),
    title: fallbackText(final.title, candidate.fields.title),
    phone: fallbackText(final.phone, candidate.fields.phone),
    mobile: fallbackText(final.mobile, candidate.fields.mobile),
    email: fallbackText(final.email, candidate.fields.email),
    role: final.role === "other" ? asRole(candidate.fields.role) : final.role,
    address: fallbackText(final.address, candidate.fields.address),
  };
}

/**
 * Immutably apply a single field edit to a batch entry's raw draft.
 *
 * - Writes `value` into `raw.draft.<path>`, creating intermediate objects
 *   as needed.
 * - Strips `path` from `raw.needs_review_fields` and
 *   `raw.draft.needs_review_fields` if the new value is non-empty.
 * - Preserves the rest of the batch unchanged (other entries untouched).
 *
 * Returns the new batch. Caller is responsible for updating React state +
 * calling setLastBatch.
 */
export function applyDraftEdit(
  batch: Batch,
  entryIndex: number,
  path: EditableDraftPath,
  value: string | number | null,
): Batch {
  const entries = batch.entries.map((entry, i) => {
    if (i !== entryIndex) return entry;
    if (!entry.result.ok) return entry;

    const raw = entry.result.raw;
    const draft = raw.draft;

    // Apply value to nested path (2 levels: section.field).
    const [section, leaf] = path.split(".") as [string, string];
    const oldSection = (draft as Record<string, unknown>)[section];
    const sectionObj: Record<string, unknown> =
      oldSection && typeof oldSection === "object"
        ? { ...(oldSection as Record<string, unknown>) }
        : {};
    sectionObj[leaf] = value;

    const newDraft = { ...draft, [section]: sectionObj } as UnifiedDraft;

    // Prune needs_review_fields when the new value is non-empty.
    const isEmpty =
      value === null ||
      value === undefined ||
      (typeof value === "string" && value.trim() === "");
    const filterPath = (paths: string[] | undefined): string[] =>
      isEmpty ? paths ?? [] : (paths ?? []).filter((p) => p !== path);

    const newRaw: AutoIngestRaw = {
      ...raw,
      draft: {
        ...newDraft,
        needs_review_fields: filterPath(newDraft.needs_review_fields),
      },
      needs_review_fields: filterPath(raw.needs_review_fields),
    };

    return {
      ...entry,
      result: { ...entry.result, raw: newRaw },
    };
  });

  return { entries };
}

/**
 * Immutably set (or clear) the customer-decision override on a batch entry.
 * Pass `undefined` to revert to AI default (bind_existing for high-conf
 * candidate, new otherwise).
 */
export function setCustomerOverride(
  batch: Batch,
  entryIndex: number,
  override: CustomerDecisionOverride | undefined,
): Batch {
  const entries = batch.entries.map((entry, i) => {
    if (i !== entryIndex) return entry;
    if (override === undefined) {
      // Strip the field cleanly.
      const { customerDecisionOverride: _omit, ...rest } = entry;
      return rest;
    }
    return { ...entry, customerDecisionOverride: override };
  });
  return { entries };
}

/**
 * Parse a user-entered amount string. Returns:
 * - { ok: true, value: null } for empty input
 * - { ok: true, value: <number> } for a valid number
 * - { ok: false, error: "..." } for invalid input
 *
 * Strips commas, ¥/￥/RMB prefixes, "元" suffix.
 */
export function parseAmountInput(
  raw: string,
): { ok: true; value: number | null } | { ok: false; error: string } {
  const stripped = raw
    .replace(/[,，]/g, "")
    .replace(/[¥￥]/g, "")
    .replace(/\bRMB\b/gi, "")
    .replace(/元/g, "")
    .trim();
  if (stripped === "") return { ok: true, value: null };
  const n = Number(stripped);
  if (!Number.isFinite(n)) return { ok: false, error: "金额必须是数字" };
  if (n < 0) return { ok: false, error: "金额不能为负数" };
  return { ok: true, value: n };
}

export function buildAutoConfirmRequest(
  raw: AutoIngestRaw,
  override?: CustomerDecisionOverride,
): AutoConfirmRequest {
  const draft = raw.draft;
  const customerCandidate = bestCandidate(raw.candidates?.customer, CUSTOMER_MERGE_THRESHOLD);

  // Customer is required by the backend's confirm even on identity-less
  // documents — sending null tells the backend "no customer dimension".
  const hasCustomer = Boolean(
    draft.customer && (draft.customer.full_name || draft.customer.short_name),
  );

  let customer: CustomerDecision | null = null;
  if (override) {
    if (override.kind === "bind_existing") {
      customer = {
        mode: override.updateMaster ? "merge" : "bind_existing",
        existing_id: override.existing_id,
        final: normalizeCustomer(draft.customer),
      };
    } else {
      // override.kind === "new"
      customer = {
        mode: "new",
        final: normalizeCustomer(draft.customer),
      };
    }
  } else if (hasCustomer) {
    // No user override — default to bind_existing for high-confidence
    // matches (was merge before; merge silently overwrote DB master fields).
    customer = {
      mode: customerCandidate ? "bind_existing" : "new",
      existing_id: customerCandidate?.id,
      final: customerWithCandidate(normalizeCustomer(draft.customer), customerCandidate),
    };
  }

  const contacts: ContactDecision[] = (draft.contacts ?? []).map((c, i) => {
    const candidate = bestCandidate(raw.candidates?.contacts?.[i], CONTACT_MERGE_THRESHOLD);
    return {
      mode: candidate ? "merge" : "new",
      existing_id: candidate?.id,
      final: contactWithCandidate(normalizeContact(c), candidate),
    };
  });

  return {
    customer,
    contacts,
    order: normalizeOrder(draft.order),
    contract: normalizeContract(draft.contract),
    events: draft.events ?? [],
    commitments: draft.commitments ?? [],
    tasks: draft.tasks ?? [],
    risk_signals: draft.risk_signals ?? [],
    memory_items: draft.memory_items ?? [],
    field_provenance: draft.field_provenance ?? [],
    confidence_overall: typeof draft.confidence_overall === "number" ? draft.confidence_overall : 0.5,
    parse_warnings: draft.warnings ?? [],
  };
}

export async function confirmAutoDocument(
  documentId: string,
  raw: AutoIngestRaw,
  override?: CustomerDecisionOverride,
): Promise<AutoConfirmResponse> {
  if (!documentId) throw new Error("缺少文档 ID，无法归档");
  return postJSON<AutoConfirmResponse>(
    `/auto/${documentId}/confirm`,
    buildAutoConfirmRequest(raw, override),
  );
}

export async function cancelAutoDocument(documentId: string): Promise<void> {
  if (!documentId) return;
  await postJSON(`/auto/${documentId}/cancel`);
}

export async function archiveBatch(batch: Batch): Promise<ArchiveResult> {
  const result: ArchiveResult = {
    confirmedDocuments: 0,
    customerIds: [],
    warnings: [],
  };
  for (const entry of batch.entries) {
    if (!entry.result.ok) continue;
    const confirmed = await confirmAutoDocument(
      entry.result.documentId,
      entry.result.raw,
      entry.customerDecisionOverride,
    );
    result.confirmedDocuments += 1;
    const cid = confirmed.created_entities?.customer_id;
    if (cid) result.customerIds.push(cid);
    result.warnings.push(...(confirmed.warnings ?? []));
  }
  result.customerIds = Array.from(new Set(result.customerIds));
  return result;
}

export async function ignoreBatch(batch: Batch): Promise<void> {
  await Promise.all(
    batch.entries.map((entry) =>
      entry.result.ok ? cancelAutoDocument(entry.result.documentId) : Promise.resolve(),
    ),
  );
}

// ───────────── Translator: backend response → Review shape ─────────────

const PATH_LABEL: Record<string, string> = {
  "customer.full_name": "客户名称",
  "customer.short_name": "简称",
  "customer.address": "地址",
  "customer.tax_id": "税号",
  "contract.contract_no_external": "合同号",
  "contract.signing_date": "签订日期",
  "contract.effective_date": "生效日期",
  "contract.expiry_date": "到期日期",
  "order.amount_total": "合同金额",
  "order.amount_currency": "币种",
  "order.delivery_promised_date": "承诺交期",
  "order.delivery_address": "交货地址",
};

const EDITABLE_FIELD_META: Record<EditableDraftPath, EditableFieldMeta> = {
  "customer.full_name":            { path: "customer.full_name",            label: "客户名称", kind: "text" },
  "customer.short_name":           { path: "customer.short_name",           label: "简称",     kind: "text" },
  "customer.address":              { path: "customer.address",              label: "地址",     kind: "text" },
  "customer.tax_id":               { path: "customer.tax_id",               label: "税号",     kind: "text" },
  "contract.contract_no_external": { path: "contract.contract_no_external", label: "合同号",   kind: "text" },
  "contract.signing_date":         { path: "contract.signing_date",         label: "签订日期", kind: "date" },
  "contract.effective_date":       { path: "contract.effective_date",       label: "生效日期", kind: "date" },
  "contract.expiry_date":          { path: "contract.expiry_date",          label: "到期日期", kind: "date" },
  "order.amount_total":            { path: "order.amount_total",            label: "合同金额", kind: "amount" },
  "order.amount_currency":         { path: "order.amount_currency",         label: "币种",     kind: "text" },
  "order.delivery_promised_date":  { path: "order.delivery_promised_date",  label: "承诺交期", kind: "date" },
  "order.delivery_address":        { path: "order.delivery_address",        label: "交付地址", kind: "text" },
  "order.description":             { path: "order.description",             label: "订单描述", kind: "text" },
};

export const EDITABLE_FIELDS: ReadonlyArray<EditableFieldMeta> =
  Object.values(EDITABLE_FIELD_META);

// Reverse map: backend needs_review_fields paths → label. Existing
// PATH_LABEL handles display already; extend so any path with editable
// metadata uses its EditableFieldMeta label.
function metaForPath(path: string): EditableFieldMeta | null {
  return (EDITABLE_FIELD_META as Record<string, EditableFieldMeta | undefined>)[path] ?? null;
}

function planChannel(
  plan: IngestPlan,
  routePlan?: RoutePlan | null,
): { channel: string; docType: string } {
  // Prefer the new schema-level route plan when available; fall back to
  // legacy extractor names for backward compatibility. The LandingAI path
  // leaves ``plan.extractors`` empty, so without ``route_plan`` the banner
  // would degrade to a generic "上传" tag.
  const schemaNames = new Set<string>(
    routePlan?.selected_pipelines.map((s) => s.name) ?? [],
  );
  const legacyNames = new Set<string>(plan.extractors.map((e) => e.name));

  const has = (schemaName: string, legacyName: string): boolean =>
    schemaNames.has(schemaName) || legacyNames.has(legacyName);

  const docTypeParts: string[] = [];
  if (has("identity", "identity")) docTypeParts.push("客户档案");
  if (has("contract_order", "commercial")) docTypeParts.push("合同/订单");
  if (schemaNames.has("manufacturing_requirement")) docTypeParts.push("生产要求");
  if (schemaNames.has("finance")) docTypeParts.push("发票/对账");
  if (schemaNames.has("logistics")) docTypeParts.push("送货/库存");
  if (has("commitment_task_risk", "ops")) docTypeParts.push("客户记忆");
  const docType = docTypeParts.length ? docTypeParts.join(" + ") : "上传";

  // Channel tag — most prominent dimension first.
  const channel = has("contract_order", "commercial")
    ? "合同 / 订单"
    : schemaNames.has("finance")
      ? "发票 / 回款"
      : schemaNames.has("logistics")
        ? "送货 / 库存"
        : schemaNames.has("manufacturing_requirement")
          ? "规格 / 验收"
          : has("identity", "identity")
            ? "客户 / 名片"
            : has("commitment_task_risk", "ops")
              ? "聊天 / 备注"
              : "上传";
  return { channel, docType };
}

// ───────────── Schema route + extract summary ─────────────

const SCHEMA_LABEL: Record<string, string> = {
  identity: "客户身份",
  contract_order: "合同/订单",
  finance: "发票/对账",
  logistics: "送货/库存",
  manufacturing_requirement: "规格/验收",
  commitment_task_risk: "客户记忆",
};

// Per-schema "key fields the reviewer cares about". Stored as
// (path, human label) tuples. `path` is a dot/array path applied to the
// raw extraction.* object via pickExtractionValue.
type FieldSpec = readonly [path: string, label: string];

const SCHEMA_KEY_FIELDS: Record<string, readonly FieldSpec[]> = {
  identity: [
    ["customer", "客户公司"],
    ["customer.full_name", "客户名称"],
    ["customer.tax_id", "税号"],
    ["contacts", "联系人列表"],
  ],
  contract_order: [
    ["customer", "客户公司"],
    ["contacts", "买方联系人"],
    ["contract", "合同信息"],
    ["order", "订单信息"],
    ["order.total_amount", "订单金额"],
    ["order.delivery_promised_date", "承诺交期"],
    ["payment_milestones", "付款节点"],
    ["items", "商品明细"],
  ],
  finance: [
    ["invoice", "发票信息"],
    ["invoice.invoice_number", "发票号码"],
    ["invoice.amount_total", "发票金额"],
    ["payment", "回款记录"],
    ["items", "明细行"],
  ],
  logistics: [
    ["shipment", "发货单"],
    ["shipment.shipment_number", "发货单号"],
    ["shipment.receiver_name", "收货人"],
    ["items", "发货明细"],
  ],
  manufacturing_requirement: [
    ["product", "产品"],
    ["spec", "规格参数"],
    ["customer_requirement", "客户要求"],
    ["safety_stock_rule", "安全库存"],
  ],
  commitment_task_risk: [
    ["events", "事件"],
    ["commitments", "承诺"],
    ["tasks", "待办"],
    ["risk_signals", "风险"],
    ["memory_items", "客户记忆"],
  ],
};

function pickExtractionValue(
  extraction: Record<string, unknown>,
  path: string,
): unknown {
  if (!path) return undefined;
  const parts = path.split(".");
  let cur: unknown = extraction;
  for (const p of parts) {
    if (cur === null || cur === undefined) return undefined;
    if (typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

function isPresent(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

function summarizePipeline(
  schemaName: string,
  confidence: number,
  reason: string,
  pipeline: PipelineExtractResult | undefined,
): SchemaSummaryItem {
  const label = SCHEMA_LABEL[schemaName] ?? schemaName;
  if (!pipeline) {
    return {
      schemaName,
      schemaLabel: label,
      confidence,
      reason,
      extracted: [],
      missing: [],
      warnings: [],
      pipelineResultMissing: true,
    };
  }

  const extraction = (pipeline.extraction ?? {}) as Record<string, unknown>;
  const keyFields = SCHEMA_KEY_FIELDS[schemaName];
  const extracted: string[] = [];
  const missing: string[] = [];

  if (keyFields) {
    for (const [path, fieldLabel] of keyFields) {
      const value = pickExtractionValue(extraction, path);
      if (isPresent(value)) extracted.push(fieldLabel);
      else missing.push(fieldLabel);
    }
  } else {
    // Fallback: any non-empty top-level key counts as "extracted"
    for (const [key, value] of Object.entries(extraction)) {
      if (key === "extraction_warnings") continue;
      if (isPresent(value)) extracted.push(key);
    }
  }

  const schemaWarnings: string[] = [];
  for (const w of pipeline.warnings ?? []) {
    if (typeof w === "string" && w.trim().length > 0) schemaWarnings.push(w);
  }
  const inlineWarnings = extraction["extraction_warnings"];
  if (Array.isArray(inlineWarnings)) {
    for (const w of inlineWarnings) {
      if (typeof w === "string" && w.trim().length > 0) schemaWarnings.push(w);
    }
  }

  return {
    schemaName,
    schemaLabel: label,
    confidence,
    reason,
    extracted,
    missing,
    warnings: schemaWarnings,
    pipelineResultMissing: false,
  };
}

/**
 * Build the schema route + extraction summary block shown on the Review page.
 *
 * Pure function (no DOM, no fetch). Tolerates missing route_plan or
 * pipeline_results so the Review page can degrade gracefully when the
 * backend returns a partial response.
 */
export function buildSchemaSummary(raw: AutoIngestRaw): SchemaSummary {
  const routePlan = raw.route_plan ?? null;
  const pipelineResults = raw.pipeline_results ?? [];

  const byName = new Map<string, PipelineExtractResult>();
  for (const r of pipelineResults) {
    if (typeof r?.name === "string") byName.set(r.name, r);
  }

  const selectedSchemas: SchemaSummaryItem[] = [];
  if (routePlan?.selected_pipelines?.length) {
    for (const sel of routePlan.selected_pipelines) {
      selectedSchemas.push(
        summarizePipeline(
          sel.name,
          typeof sel.confidence === "number" ? sel.confidence : 0,
          sel.reason ?? "",
          byName.get(sel.name),
        ),
      );
    }
  }

  // Schemas that returned pipeline_results but weren't in route_plan
  // (shouldn't happen in normal flow, but surface for debugging).
  for (const r of pipelineResults) {
    if (!routePlan?.selected_pipelines?.some((s) => s.name === r.name)) {
      selectedSchemas.push(summarizePipeline(r.name, 0, "(未在路由计划内)", r));
    }
  }

  const draft = raw.draft;
  const finalDraftStatus = {
    hasCustomer: !!draft?.customer && isPresent(draft.customer),
    hasContacts: Array.isArray(draft?.contacts) && draft.contacts.length > 0,
    hasContract: !!draft?.contract && isPresent(draft.contract),
    hasOrder: !!draft?.order && isPresent(draft.order),
    hasOrderAmount:
      !!draft?.order &&
      typeof (draft.order as { amount_total?: unknown }).amount_total ===
        "number",
    hasPaymentMilestones:
      Array.isArray(
        (draft?.contract as { payment_milestones?: unknown[] } | undefined)
          ?.payment_milestones,
      ) &&
      ((draft?.contract as { payment_milestones?: unknown[] } | undefined)
        ?.payment_milestones?.length ?? 0) > 0,
  };

  const generalWarnings: string[] = [];
  for (const w of draft?.warnings ?? []) {
    if (typeof w === "string" && w.trim().length > 0) generalWarnings.push(w);
  }

  return {
    selectedSchemas,
    routePlanMissing: routePlan === null || routePlan === undefined,
    pipelineResultsMissing: pipelineResults.length === 0,
    finalDraftStatus,
    generalWarnings,
  };
}

export function batchToReview(batch: Batch): Review | null {
  const successes = batch.entries.filter(
    (e): e is BatchEntry & { result: AutoIngestSuccess } => e.result.ok,
  );
  if (!successes.length) return null;

  // Aggregate across all entries — when the user uploads a contract PDF + a
  // chat screenshot in one batch we want the Review screen to show everything.
  const primary = successes[0]!;
  const draft = primary.result.raw.draft;
  const plan = primary.result.raw.plan;
  const candidates = primary.result.raw.candidates;
  const needsReview = primary.result.raw.needs_review_fields ?? draft.needs_review_fields ?? [];

  const isLow = (path: string): Confidence => (needsReview.includes(path) ? "med" : "high");

  // ── Customer ──────────────────────────────────────────────
  const customerName = draft.customer?.full_name?.trim() || "未识别客户";
  const candidateCount = candidates?.customer?.length ?? 0;
  const isExisting = candidateCount > 0;
  const overall =
    typeof draft.confidence_overall === "number" ? draft.confidence_overall : 0.7;

  // ── Channel / docType ─────────────────────────────────────
  const { channel, docType } = planChannel(plan, primary.result.raw.route_plan);

  // ── Contact (first identified contact, if any) ────────────
  const firstContact = draft.contacts?.[0];
  const contact = firstContact?.name
    ? {
        name: firstContact.name,
        role: firstContact.role ? ROLE_CN[firstContact.role] ?? firstContact.role : "联系人",
        initial: firstContact.name.slice(0, 1),
      }
    : { name: "—", role: "未识别", initial: "?" };

  // ── Fields from unified draft ─────────────────────────────
  const fields: ReviewField[] = [];
  const c = draft.customer;
  if (c?.full_name)
    fields.push({
      key: "客户名称", value: c.full_name,
      conf: isLow("customer.full_name"),
      path: "customer.full_name", kind: "text",
    });
  if (c?.short_name)
    fields.push({
      key: "简称", value: c.short_name,
      conf: isLow("customer.short_name"),
      path: "customer.short_name", kind: "text",
    });
  if (c?.address)
    fields.push({
      key: "地址", value: c.address,
      conf: isLow("customer.address"),
      path: "customer.address", kind: "text",
    });
  if (c?.tax_id)
    fields.push({
      key: "税号", value: c.tax_id,
      conf: isLow("customer.tax_id"),
      path: "customer.tax_id", kind: "text",
    });
  const co = draft.contract;
  if (co?.contract_no_external)
    fields.push({
      key: "合同号", value: co.contract_no_external,
      conf: isLow("contract.contract_no_external"),
      path: "contract.contract_no_external", kind: "text",
    });
  if (co?.signing_date)
    fields.push({
      key: "签订日期", value: co.signing_date,
      conf: isLow("contract.signing_date"),
      path: "contract.signing_date", kind: "date",
    });
  const o = draft.order;
  if (o?.amount_total != null) {
    const v = `${o.amount_total} ${o.amount_currency ?? ""}`.trim();
    fields.push({
      key: "合同金额", value: v,
      conf: isLow("order.amount_total"),
      path: "order.amount_total", kind: "amount",
    });
  }
  if (o?.delivery_promised_date)
    fields.push({
      key: "承诺交期", value: o.delivery_promised_date,
      conf: isLow("order.delivery_promised_date"),
      path: "order.delivery_promised_date", kind: "date",
    });

  if (!fields.length) {
    successes.forEach((e, i) =>
      fields.push({ key: `文件 ${i + 1}`, value: e.filename, conf: "high" }),
    );
  }

  // ── Extractions ───────────────────────────────────────────
  const extractions: ReviewExtraction[] = [];
  draft.contacts?.forEach((cc, i) => {
    if (!cc.name) return;
    const phone = cc.mobile || cc.phone || cc.email || "";
    const tail = phone ? ` · ${phone}` : "";
    extractions.push({
      kind: "contact",
      title: "联系人",
      text: `${cc.name}${cc.title ? ` · ${cc.title}` : ""}${tail}`,
      source: { type: "客户档案", label: primary.filename },
      conf: isLow(`contacts[${i}].name`),
    });
  });
  draft.contract?.payment_milestones?.forEach((m, i) => {
    extractions.push({
      kind: "commitment",
      title: "付款节点",
      text: `${m.name || `阶段 ${i + 1}`} · ${(m.ratio * 100).toFixed(0)}% · ${m.trigger_event}`,
      source: { type: "合同", label: primary.filename },
      conf: isLow(`contract.payment_milestones[${i}]`),
    });
  });
  draft.commitments?.forEach((cm) => {
    if (!cm.summary) return;
    extractions.push({
      kind: "commitment",
      title: "承诺事项",
      text: cm.summary,
      source: { type: "客户记忆", label: primary.filename },
      conf: (cm.confidence ?? 0.7) >= 0.85 ? "high" : "med",
    });
  });
  draft.tasks?.forEach((t) => {
    if (!t.title) return;
    const due = t.due_date ? ` · ${t.due_date}` : "";
    extractions.push({
      kind: "task",
      title: "待办任务",
      text: `${t.title}${due}`,
      source: { type: "客户记忆", label: primary.filename },
      conf: "high",
    });
  });
  draft.risk_signals?.forEach((r) => {
    if (!r.summary) return;
    extractions.push({
      kind: "risk",
      title: "风险线索",
      text: r.summary,
      source: { type: "客户记忆", label: primary.filename },
      conf: (r.confidence ?? 0.7) >= 0.85 ? "high" : "med",
    });
  });
  draft.memory_items?.forEach((m) => {
    if (!m.content) return;
    extractions.push({
      kind: "task",
      title: "客户记忆",
      text: m.content,
      source: { type: "客户记忆", label: primary.filename },
      conf: (m.confidence ?? 0.7) >= 0.85 ? "high" : "med",
    });
  });
  draft.events?.forEach((e) => {
    if (!e.title) return;
    extractions.push({
      kind: "task",
      title: "事件",
      text: `${e.title}${e.occurred_at ? ` · ${e.occurred_at}` : ""}`,
      source: { type: "客户记忆", label: primary.filename },
      conf: (e.confidence ?? 0.7) >= 0.85 ? "high" : "med",
    });
  });

  // ── Missing — paths the backend flagged low-confidence we didn't field ──
  const fieldKeys = new Set(fields.map((f) => f.key));
  const missing = needsReview
    .map((p) => PATH_LABEL[p] ?? p)
    .filter((label) => !fieldKeys.has(label))
    .slice(0, 8);

  // Build structured missingFields with stable paths so the editor can
  // open the right input. Falls back to plain string `missing` for paths
  // without editable metadata.
  const missingFields: EditableFieldMeta[] = [];
  for (const path of needsReview) {
    const m = metaForPath(path);
    if (!m) continue;
    if (fieldKeys.has(m.label)) continue;
    missingFields.push(m);
  }

  // ── Evidence — original filenames + warning previews ─────
  const warnings = draft.warnings ?? [];
  const evidence: ReviewEvidence[] = successes.map((e, i) => {
    const entryDraft = e.result.raw.draft;
    const entryWarnings = entryDraft?.warnings ?? [];
    let preview = "已上传";
    if (entryWarnings.length) preview = entryWarnings.join(" · ").slice(0, 80);
    else if (entryDraft?.summary) preview = entryDraft.summary.slice(0, 80);
    else if (warnings.length && i === 0) preview = warnings.join(" · ").slice(0, 80);
    return {
      id: `ev${i}`,
      type: docType.split(" + ")[0] ?? "上传",
      label: e.filename,
      preview,
    };
  });

  return {
    customer: { name: customerName, isExisting, confidence: overall },
    channel,
    docType,
    contact,
    confidence: overall,
    fields,
    extractions,
    missing,
    missingFields,
    evidence,
    schemaSummary: buildSchemaSummary(primary.result.raw),
  };
}
