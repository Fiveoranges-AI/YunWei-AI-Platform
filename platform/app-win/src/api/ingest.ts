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
      let detail = `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        /* response wasn't JSON */
      }
      return { ok: false, error: detail };
    }
    const body = (await res.json()) as { document_id?: string };
    return { ok: true, documentId: body.document_id ?? "", raw: body };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "网络错误" };
  }
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
    payment_milestones?: Array<{
      name?: string | null;
      ratio: number;
      trigger_event: string;
    }>;
  };
  confidence_overall?: number;
};

type ContractEnvelope = {
  draft?: ContractDraft;
  candidates?: { customer?: unknown[]; contacts?: unknown[][] };
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

const ROLE_CN: Record<string, string> = {
  seller: "销售方",
  buyer: "采购方",
  delivery: "收货",
  acceptance: "验收",
  invoice: "开票",
  other: "其他",
};

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
