// POST /win/api/ingest/* — entity-first file intake.
//
// Routes per detected kind:
//   合同 (.pdf) → /contract           (returns draft + match candidates)
//   名片 (image) → /business_card     (creates Contact)
//   截图 (image) → /wechat_screenshot (ingests chat screenshot)
//
// Excel / 语音 / other types currently have no entity-first endpoint and
// return { ok: false, unsupported: true } so the UI can flag them without
// blocking the rest of the batch.
//
// After a batch settles, Upload.tsx calls setLastBatch(...) so the Review
// screen can render real backend data via batchToReview() instead of the
// hardcoded MOCK_REVIEW (which was the source of the "always 万华化学"
// problem).

import type {
  Confidence,
  Review,
  ReviewEvidence,
  ReviewExtraction,
  ReviewField,
} from "../data/types";

const API_BASE = "/win/api/ingest";

export type IngestSuccess = {
  ok: true;
  documentId: string;
  raw: unknown;
};

export type IngestFailure = {
  ok: false;
  error: string;
  unsupported?: boolean;
};

export type IngestResult = IngestSuccess | IngestFailure;

function endpointFor(kind: string): string | null {
  if (kind === "合同") return "/contract";
  if (kind === "名片") return "/business_card";
  if (kind === "截图") return "/wechat_screenshot";
  return null;
}

export async function uploadStagedFile(file: File, kind: string): Promise<IngestResult> {
  const endpoint = endpointFor(kind);
  if (!endpoint) {
    return { ok: false, error: "暂不支持该文件类型", unsupported: true };
  }
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
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
      return await readNdjsonResult(res);
    }
    // Backwards compat with non-streaming responses.
    const body = (await res.json()) as { document_id?: string };
    return { ok: true, documentId: body.document_id ?? "", raw: body };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "网络错误" };
  }
}

// The ingest endpoints stream NDJSON: zero or more {"status":"processing"}
// heartbeats keep Cloudflare's 100s edge timeout from firing during a long
// LLM call; the final non-empty line is either {"status":"done", ...result}
// or {"status":"error", "error": "..."}.
async function readNdjsonResult(res: Response): Promise<IngestResult> {
  if (!res.body) {
    return { ok: false, error: "无响应数据" };
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let last: { status?: string; error?: string; document_id?: string } | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl = buf.indexOf("\n");
    while (nl !== -1) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) {
        try {
          last = JSON.parse(line);
        } catch {
          /* ignore partial / malformed lines */
        }
      }
      nl = buf.indexOf("\n");
    }
  }
  // Drain any trailing line that lacked a terminator.
  const tail = buf.trim();
  if (tail) {
    try {
      last = JSON.parse(tail);
    } catch {
      /* ignore */
    }
  }
  if (!last) return { ok: false, error: "服务器未返回结果" };
  if (last.status === "done") {
    return { ok: true, documentId: last.document_id ?? "", raw: last };
  }
  if (last.status === "error") {
    return { ok: false, error: last.error ?? "服务器错误" };
  }
  return { ok: false, error: "未知响应状态" };
}

// ───────────── Batch state shared with Review screen ─────────────

export type BatchEntry = {
  filename: string;
  kind: string;
  result: IngestResult;
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

// ───────────── Translator: backend response → Review shape ─────────────

type ContractDraft = {
  customer?: {
    full_name?: string | null;
    short_name?: string | null;
    address?: string | null;
    tax_id?: string | null;
  };
  contacts?: Array<{
    name?: string | null;
    title?: string | null;
    phone?: string | null;
    mobile?: string | null;
    email?: string | null;
    role?: string | null;
  }>;
  order?: {
    amount_total?: number | null;
    amount_currency?: string | null;
    delivery_promised_date?: string | null;
  };
  contract?: {
    contract_no_external?: string | null;
    signing_date?: string | null;
    effective_date?: string | null;
    expiry_date?: string | null;
    delivery_terms?: string | null;
    penalty_terms?: string | null;
    payment_milestones?: Array<{
      name?: string | null;
      ratio: number;
      trigger_event: string;
      trigger_offset_days?: number | null;
      raw_text?: string | null;
    }>;
  };
  field_provenance?: Array<{
    path: string;
    source_page: number | null;
    source_excerpt: string | null;
  }>;
  confidence_overall?: number;
  field_confidence?: Record<string, number>;
  parse_warnings?: string[];
};

type ContractEnvelope = {
  draft?: ContractDraft;
  candidates?: {
    customer?: MatchCandidate<CustomerFinal>[];
    contacts?: Array<MatchCandidate<ContactFinal>[]>;
  };
  needs_review_fields?: string[];
  warnings?: string[];
};

type WeChatEnvelope = {
  summary?: string;
  message_count?: number;
  extracted_entity_count?: number;
  confidence_overall?: number;
  warnings?: string[];
};

type BusinessCardEnvelope = {
  contact_id?: string;
  needs_review?: boolean;
  warnings?: string[];
};

type MatchCandidate<T> = {
  id: string;
  score?: number;
  reason?: string;
  fields?: Partial<T>;
};

type CustomerFinal = {
  full_name: string | null;
  short_name: string | null;
  address: string | null;
  tax_id: string | null;
};

type ContactFinal = {
  name: string | null;
  title: string | null;
  phone: string | null;
  mobile: string | null;
  email: string | null;
  role: "seller" | "buyer" | "delivery" | "acceptance" | "invoice" | "other";
  address: string | null;
};

type OrderFinal = {
  amount_total: number | null;
  amount_currency: string;
  delivery_promised_date: string | null;
  delivery_address: string | null;
  description: string | null;
};

type MilestoneFinal = {
  name: string | null;
  ratio: number;
  trigger_event:
    | "contract_signed"
    | "before_shipment"
    | "on_delivery"
    | "on_acceptance"
    | "invoice_issued"
    | "warranty_end"
    | "on_demand"
    | "other";
  trigger_offset_days: number | null;
  raw_text: string | null;
};

type ContractFinal = {
  contract_no_external: string | null;
  payment_milestones: MilestoneFinal[];
  delivery_terms: string | null;
  penalty_terms: string | null;
  signing_date: string | null;
  effective_date: string | null;
  expiry_date: string | null;
};

type ContractConfirmRequest = {
  customer: {
    mode: "new" | "merge";
    existing_id?: string;
    final: CustomerFinal;
  };
  contacts: Array<{
    mode: "new" | "merge";
    existing_id?: string;
    final: ContactFinal;
  }>;
  order: OrderFinal;
  contract: ContractFinal;
  field_provenance: NonNullable<ContractDraft["field_provenance"]>;
  confidence_overall: number;
  field_confidence: Record<string, number>;
  parse_warnings: string[];
};

type ContractConfirmResponse = {
  document_id: string;
  created_entities?: {
    customer_id?: string;
    contact_ids?: string[];
    order_id?: string;
    contract_id?: string;
  };
  warnings?: string[];
};

export type ArchiveResult = {
  confirmedContracts: number;
  passthroughDocuments: number;
  customerIds: string[];
  warnings: string[];
};

const ROLE_CN: Record<string, string> = {
  seller: "销售方",
  buyer: "采购方",
  delivery: "收货",
  acceptance: "验收",
  invoice: "开票",
  other: "其他",
};

const VALID_ROLES = new Set<ContactFinal["role"]>([
  "seller",
  "buyer",
  "delivery",
  "acceptance",
  "invoice",
  "other",
]);

const VALID_TRIGGERS = new Set<MilestoneFinal["trigger_event"]>([
  "contract_signed",
  "before_shipment",
  "on_delivery",
  "on_acceptance",
  "invoice_issued",
  "warranty_end",
  "on_demand",
  "other",
]);

const CUSTOMER_MERGE_THRESHOLD = 0.95;
const CONTACT_MERGE_THRESHOLD = 0.99;

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

function asContractEnvelope(raw: unknown): ContractEnvelope {
  return (raw ?? {}) as ContractEnvelope;
}

function asRole(role: string | null | undefined): ContactFinal["role"] {
  return VALID_ROLES.has(role as ContactFinal["role"]) ? (role as ContactFinal["role"]) : "other";
}

function asTrigger(trigger: string | null | undefined): MilestoneFinal["trigger_event"] {
  return VALID_TRIGGERS.has(trigger as MilestoneFinal["trigger_event"])
    ? (trigger as MilestoneFinal["trigger_event"])
    : "other";
}

function normalizeCustomer(raw: ContractDraft["customer"] | undefined): CustomerFinal {
  return {
    full_name: raw?.full_name ?? null,
    short_name: raw?.short_name ?? null,
    address: raw?.address ?? null,
    tax_id: raw?.tax_id ?? null,
  };
}

function normalizeContact(raw: NonNullable<ContractDraft["contacts"]>[number] | undefined): ContactFinal {
  return {
    name: raw?.name ?? null,
    title: raw?.title ?? null,
    phone: raw?.phone ?? null,
    mobile: raw?.mobile ?? null,
    email: raw?.email ?? null,
    role: asRole(raw?.role),
    address: null,
  };
}

function normalizeOrder(raw: ContractDraft["order"] | undefined): OrderFinal {
  return {
    amount_total: raw?.amount_total ?? null,
    amount_currency: raw?.amount_currency ?? "CNY",
    delivery_promised_date: raw?.delivery_promised_date ?? null,
    delivery_address: null,
    description: null,
  };
}

function normalizeContract(raw: ContractDraft["contract"] | undefined): ContractFinal {
  return {
    contract_no_external: raw?.contract_no_external ?? null,
    payment_milestones: (raw?.payment_milestones ?? []).map((m) => ({
      name: m.name ?? null,
      ratio: typeof m.ratio === "number" ? m.ratio : 0,
      trigger_event: asTrigger(m.trigger_event),
      trigger_offset_days: m.trigger_offset_days ?? null,
      raw_text: m.raw_text ?? null,
    })),
    delivery_terms: raw?.delivery_terms ?? null,
    penalty_terms: raw?.penalty_terms ?? null,
    signing_date: raw?.signing_date ?? null,
    effective_date: raw?.effective_date ?? null,
    expiry_date: raw?.expiry_date ?? null,
  };
}

function fallbackText(current: string | null, previous: string | null | undefined): string | null {
  return current && current.trim() ? current : previous ?? current;
}

function customerWithCandidate(final: CustomerFinal, candidate: MatchCandidate<CustomerFinal> | null): CustomerFinal {
  if (!candidate?.fields) return final;
  return {
    full_name: fallbackText(final.full_name, candidate.fields.full_name),
    short_name: fallbackText(final.short_name, candidate.fields.short_name),
    address: fallbackText(final.address, candidate.fields.address),
    tax_id: fallbackText(final.tax_id, candidate.fields.tax_id),
  };
}

function contactWithCandidate(final: ContactFinal, candidate: MatchCandidate<ContactFinal> | null): ContactFinal {
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

function bestCandidate<T>(candidates: MatchCandidate<T>[] | undefined, threshold: number): MatchCandidate<T> | null {
  const sorted = [...(candidates ?? [])].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const best = sorted[0];
  return best && (best.score ?? 0) >= threshold ? best : null;
}

function buildConfirmRequest(envelope: ContractEnvelope): ContractConfirmRequest {
  const draft = envelope.draft;
  const customerCandidate = bestCandidate(envelope.candidates?.customer, CUSTOMER_MERGE_THRESHOLD);
  return {
    customer: {
      mode: customerCandidate ? "merge" : "new",
      existing_id: customerCandidate?.id,
      final: customerWithCandidate(normalizeCustomer(draft?.customer), customerCandidate),
    },
    contacts: (draft?.contacts ?? []).map((c, i) => {
      const candidate = bestCandidate(envelope.candidates?.contacts?.[i], CONTACT_MERGE_THRESHOLD);
      return {
        mode: candidate ? "merge" : "new",
        existing_id: candidate?.id,
        final: contactWithCandidate(normalizeContact(c), candidate),
      };
    }),
    order: normalizeOrder(draft?.order),
    contract: normalizeContract(draft?.contract),
    field_provenance: draft?.field_provenance ?? [],
    confidence_overall: draft?.confidence_overall ?? 0.5,
    field_confidence: draft?.field_confidence ?? {},
    parse_warnings: draft?.parse_warnings ?? [],
  };
}

export async function confirmContractDocument(documentId: string, raw: unknown): Promise<ContractConfirmResponse> {
  if (!documentId) throw new Error("缺少合同文档 ID，无法归档");
  const envelope = asContractEnvelope(raw);
  if (!envelope.draft) throw new Error("缺少合同抽取草稿，无法归档");
  return postJSON<ContractConfirmResponse>(`/contract/${documentId}/confirm`, buildConfirmRequest(envelope));
}

export async function cancelContractDocument(documentId: string): Promise<void> {
  if (!documentId) return;
  await postJSON(`/contract/${documentId}/cancel`);
}

export async function archiveBatch(batch: Batch): Promise<ArchiveResult> {
  const result: ArchiveResult = {
    confirmedContracts: 0,
    passthroughDocuments: 0,
    customerIds: [],
    warnings: [],
  };
  for (const entry of batch.entries) {
    if (!entry.result.ok) continue;
    if (entry.kind !== "合同") {
      result.passthroughDocuments += 1;
      continue;
    }
    const confirmed = await confirmContractDocument(entry.result.documentId, entry.result.raw);
    result.confirmedContracts += 1;
    if (confirmed.created_entities?.customer_id) {
      result.customerIds.push(confirmed.created_entities.customer_id);
    }
    result.warnings.push(...(confirmed.warnings ?? []));
  }
  return result;
}

export async function ignoreBatch(batch: Batch): Promise<void> {
  await Promise.all(
    batch.entries.map((entry) =>
      entry.result.ok && entry.kind === "合同"
        ? cancelContractDocument(entry.result.documentId)
        : Promise.resolve(),
    ),
  );
}

export function batchToReview(batch: Batch): Review | null {
  const successes = batch.entries.filter(
    (e): e is BatchEntry & { result: IngestSuccess } => e.result.ok,
  );
  if (!successes.length) return null;

  const contractEntry = successes.find((e) => e.kind === "合同");
  const contractRaw = contractEntry?.result.raw as ContractEnvelope | undefined;
  const draft = contractRaw?.draft;
  const needsReview = contractRaw?.needs_review_fields ?? [];
  const contractWarnings = contractRaw?.warnings ?? [];
  const isLow = (path: string): Confidence =>
    needsReview.includes(path) ? "med" : "high";

  // ── Customer ───────────────────────────────────────────────
  const customerName = draft?.customer?.full_name?.trim() || "未识别客户";
  const candidateCount = contractRaw?.candidates?.customer?.length ?? 0;
  const isExisting = candidateCount > 0;
  const overall =
    typeof draft?.confidence_overall === "number" ? draft.confidence_overall : 0.7;

  // ── Channel / docType ─────────────────────────────────────
  const kinds = new Set(successes.map((e) => e.kind));
  const channel = kinds.has("合同")
    ? "合同 PDF"
    : kinds.has("截图")
      ? "微信截图"
      : kinds.has("名片")
        ? "名片拍照"
        : "上传";
  const docType = Array.from(kinds).join(" + ");

  // ── Contact (first identified contact, if any) ────────────
  const firstContact = draft?.contacts?.[0];
  const contact = firstContact?.name
    ? {
        name: firstContact.name,
        role: firstContact.role ? ROLE_CN[firstContact.role] ?? firstContact.role : "联系人",
        initial: firstContact.name.slice(0, 1),
      }
    : { name: "—", role: "未识别", initial: "?" };

  // ── Fields from contract draft ────────────────────────────
  const fields: ReviewField[] = [];
  if (draft) {
    const c = draft.customer;
    if (c?.full_name) fields.push({ key: "客户名称", value: c.full_name, conf: isLow("customer.full_name") });
    if (c?.short_name) fields.push({ key: "简称", value: c.short_name, conf: isLow("customer.short_name") });
    if (c?.address) fields.push({ key: "地址", value: c.address, conf: isLow("customer.address") });
    if (c?.tax_id) fields.push({ key: "税号", value: c.tax_id, conf: isLow("customer.tax_id") });
    const co = draft.contract;
    if (co?.contract_no_external)
      fields.push({ key: "合同号", value: co.contract_no_external, conf: isLow("contract.contract_no_external") });
    if (co?.signing_date)
      fields.push({ key: "签订日期", value: co.signing_date, conf: isLow("contract.signing_date") });
    const o = draft.order;
    if (o?.amount_total != null) {
      const v = `${o.amount_total} ${o.amount_currency ?? ""}`.trim();
      fields.push({ key: "合同金额", value: v, conf: isLow("order.amount_total") });
    }
    if (o?.delivery_promised_date)
      fields.push({ key: "承诺交期", value: o.delivery_promised_date, conf: isLow("order.delivery_promised_date") });
  }
  if (!fields.length) {
    successes.forEach((e, i) =>
      fields.push({ key: `文件 ${i + 1}`, value: `${e.filename} · ${e.kind}`, conf: "high" }),
    );
  }

  // ── Extractions ────────────────────────────────────────────
  const extractions: ReviewExtraction[] = [];
  draft?.contacts?.forEach((c, i) => {
    if (!c.name) return;
    const phone = c.mobile || c.phone || c.email || "";
    const tail = phone ? ` · ${phone}` : "";
    extractions.push({
      kind: "contact",
      title: "联系人",
      text: `${c.name}${c.title ? ` · ${c.title}` : ""}${tail}`,
      source: { type: "合同", label: contractEntry?.filename ?? "合同 PDF" },
      conf: isLow(`contacts[${i}].name`),
    });
  });
  draft?.contract?.payment_milestones?.forEach((m, i) => {
    extractions.push({
      kind: "commitment",
      title: "付款节点",
      text: `${m.name || `阶段 ${i + 1}`} · ${(m.ratio * 100).toFixed(0)}% · ${m.trigger_event}`,
      source: { type: "合同", label: contractEntry?.filename ?? "合同 PDF" },
      conf: isLow(`contract.payment_milestones[${i}]`),
    });
  });
  successes
    .filter((e) => e.kind === "截图")
    .forEach((e) => {
      const raw = e.result.raw as WeChatEnvelope;
      if (raw?.summary) {
        extractions.push({
          kind: "task",
          title: "微信摘要",
          text: raw.summary,
          source: { type: "微信截图", label: e.filename },
          conf: (raw.confidence_overall ?? 0.7) >= 0.85 ? "high" : "med",
        });
      }
    });
  successes
    .filter((e) => e.kind === "名片")
    .forEach((e) => {
      const raw = e.result.raw as BusinessCardEnvelope;
      const id = raw?.contact_id ? raw.contact_id.slice(0, 8) : "";
      extractions.push({
        kind: "contact",
        title: "联系人（名片）",
        text: `已新增联系人${id ? ` · ${id}` : ""}`,
        source: { type: "名片", label: e.filename },
        conf: raw?.needs_review ? "med" : "high",
      });
    });

  // ── Missing — paths the LLM flagged low-confidence but we didn't field ──
  const fieldKeys = new Set(fields.map((f) => f.key));
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
  const missing = needsReview
    .map((p) => PATH_LABEL[p] ?? p)
    .filter((label) => !fieldKeys.has(label))
    .slice(0, 8);

  // ── Evidence — original filenames + warning previews ──────
  const evidence: ReviewEvidence[] = successes.map((e, i) => {
    let preview = "已上传";
    const raw = e.result.raw as { warnings?: string[]; summary?: string } | undefined;
    if (raw?.warnings?.length) preview = raw.warnings.join(" · ").slice(0, 80);
    else if (raw?.summary) preview = raw.summary.slice(0, 80);
    else if (contractWarnings.length && e.kind === "合同")
      preview = contractWarnings.join(" · ").slice(0, 80);
    return {
      id: `ev${i}`,
      type: e.kind,
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
    evidence,
  };
}
