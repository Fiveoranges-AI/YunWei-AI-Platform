// Backend API client for /api/win/. The backend (yunwei_win, integrated
// into platform_app) returns the raw yunwei-tools shape; this module
// translates each response into the design's shape (CustomerListItem,
// CustomerDetail, etc.). Mock fallback is limited to Vite dev mode; production
// surfaces API errors so stale demo data cannot mask persistence bugs.
//
// Backend → design shape mapping:
//   id            → id (string-as-uuid)
//   full_name     → name
//   short_name    → monogram (fallback: first 1-2 chars of name)
//                   color    (derived from name hash)
//                   tag      (default "客户" — yunwei-tools has no tag column)
//                   aiSummary (TODO: source from /summary headline)
//                   metrics  (separate /metrics call)
//                   risk     (derived from /risks count + max severity)

import { MOCK_ASK_SEED, MOCK_CUSTOMERS } from "../data/mock";
import type {
  AskAIBlock,
  AskSeed,
  Commitment,
  Contact,
  CustomerDetail,
  CustomerListItem,
  CustomerMetrics,
  CustomerRisk,
  RiskLevel,
  RiskSignal,
  CustomerTask,
  TimelineEvent,
} from "../data/types";
import { fmtRelative } from "../lib/format";
import { markCustomersChanged } from "../lib/customerRefresh";

const API_BASE = "/api/win";
const MOCK_DELAY_MS = 200;
const USE_MOCK_FALLBACK = import.meta.env.DEV;

export type CurrentUser = {
  id: string;
  username: string;
  display_name?: string | null;
  is_platform_admin: boolean;
  enterprises: Array<{
    id: string;
    display_name?: string | null;
    legal_name?: string | null;
    role?: string | null;
  }>;
};

type RawCustomer = {
  id: string;
  full_name: string;
  short_name?: string | null;
  address?: string | null;
  tax_id?: string | null;
  created_at: string;
  updated_at?: string;
};

type RawCustomerDetail = RawCustomer & {
  contacts?: Array<{
    id: string;
    name: string;
    role?: string | null;
    phone?: string | null;
    mobile?: string | null;
    last?: string | null;
    title?: string | null;
    email?: string | null;
    address?: string | null;
    wechat_id?: string | null;
  }>;
  orders?: Array<{ id: string; amount_total?: number | null }>;
};

type RawSummary = {
  customer_id: string;
  headline: string;
  open_commitments_count: number;
  open_tasks_count: number;
  open_risks_count: number;
  recent_events_count: number;
  last_interaction_at: string | null;
};

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path}`);
  return (await res.json()) as T;
}

async function fetchPlatformJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "same-origin", cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path}`);
  return (await res.json()) as T;
}

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

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as T;
}

type CustomerUpdateBody = {
  full_name?: string;
  short_name?: string | null;
  address?: string | null;
  tax_id?: string | null;
};

export type ContactInput = {
  id?: string;
  name: string;
  title?: string | null;
  phone?: string | null;
  mobile?: string | null;
  email?: string | null;
  role?: string;
  address?: string | null;
  wechat_id?: string | null;
};

export async function updateCustomer(id: string, body: CustomerUpdateBody): Promise<void> {
  const res = await fetch(`${API_BASE}/customers/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  markCustomersChanged();
}

export async function replaceCustomerContacts(id: string, contacts: ContactInput[]): Promise<void> {
  const res = await fetch(`${API_BASE}/customers/${id}/contacts`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contacts }),
  });
  if (!res.ok) throw new Error(await readError(res));
  markCustomersChanged();
}

export async function deleteCustomer(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/customers/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(await readError(res));
  markCustomersChanged();
}

export async function deleteAllCustomers(): Promise<{ deleted_customers: number }> {
  const res = await fetch(
    `${API_BASE}/customers?confirm=DELETE_ALL_IMPORTED_CUSTOMERS`,
    { method: "DELETE", credentials: "include" },
  );
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { deleted_customers: number };
  markCustomersChanged();
  return body;
}

async function fetchOrNull<T>(path: string): Promise<T | null> {
  try {
    return await fetchJSON<T>(path);
  } catch {
    return null;
  }
}

const PALETTE = ["#1f6c8a", "#3a6ea5", "#5a7d8c", "#8a5a3a", "#7a3a3a", "#3f6e3f", "#6a3a7a"];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function deriveColor(name: string): string {
  return PALETTE[hashStr(name) % PALETTE.length];
}

function deriveMonogram(name: string, shortName?: string | null): string {
  if (shortName && shortName.length > 0) return shortName.slice(0, 2);
  // For Chinese names, take first 2 chars (counts as 2 visible chars).
  return name.slice(0, 2);
}

function emptyMetrics(): CustomerMetrics {
  return { contractTotal: 0, receivable: 0, contracts: 0, tasks: 0, contacts: 0 };
}

function defaultRisk(): CustomerRisk {
  return { level: "low", label: "低风险", note: "" };
}

function deriveRisk(risks: RiskSignal[] | undefined): CustomerRisk {
  if (!risks?.length) return defaultRisk();
  const has = (lvl: RiskLevel) => risks.some((r) => r.level === lvl);
  if (has("high")) return { level: "high", label: "高风险", note: `${risks.length} 项风险线索` };
  if (has("med")) return { level: "med", label: "中风险", note: `${risks.length} 项风险线索` };
  return { level: "low", label: "低风险", note: `${risks.length} 项风险线索` };
}

function transformCustomerBase(raw: RawCustomer, summary: RawSummary | null): CustomerListItem {
  const aiSummary = summary?.headline ?? "暂无 AI 摘要";
  return {
    id: raw.id,
    name: raw.full_name,
    shortName: raw.short_name ?? null,
    address: raw.address ?? null,
    taxId: raw.tax_id ?? null,
    monogram: deriveMonogram(raw.full_name, raw.short_name),
    color: deriveColor(raw.full_name),
    tag: "客户",
    updated: fmtRelative(raw.updated_at ?? raw.created_at),
    aiSummary,
    metrics: emptyMetrics(),
    risk: defaultRisk(),
  };
}

function transformContacts(raw: RawCustomerDetail["contacts"]): Contact[] {
  if (!raw) return [];
  return raw.map((c) => ({
    id: c.id,
    name: c.name,
    role: c.role ?? "",
    initial: c.name.slice(0, 1),
    phone: c.phone ?? c.mobile ?? "",
    last: c.last ?? "",
    title: c.title ?? undefined,
    mobile: c.mobile ?? undefined,
    email: c.email ?? undefined,
    address: c.address ?? undefined,
    wechatId: c.wechat_id ?? undefined,
  }));
}

export async function listCustomers(): Promise<CustomerDetail[]> {
  try {
    const raw = await fetchJSON<RawCustomer[]>("/customers");
    if (!raw.length) return [];
    // Fetch summaries and metrics in parallel — degrade gracefully if any fail.
    const enriched = await Promise.all(
      raw.map(async (c) => {
        const [summary, metrics] = await Promise.all([
          fetchOrNull<RawSummary>(`/customers/${c.id}/summary`),
          fetchOrNull<CustomerMetrics>(`/customers/${c.id}/metrics`),
        ]);
        const base = transformCustomerBase(c, summary);
        return { ...base, metrics: metrics ?? emptyMetrics() } satisfies CustomerListItem;
      }),
    );
    return enriched;
  } catch (e) {
    if (USE_MOCK_FALLBACK) {
      await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
      return MOCK_CUSTOMERS;
    }
    throw e;
  }
}

/** Lightweight variant: just id + name + tag, no per-customer enrichment.
 *
 * Used by Ask AI's customer picker, which needs to render a list of names
 * but doesn't show metrics or AI summary in the picker itself. Avoids the
 * 1+2N round-trip pattern of {@link listCustomers}; first paint goes from
 * ~5s (5 customers) to ~0.5s. Metrics come in via getCustomer() when the
 * user actually selects a customer. */
export async function listCustomersBasic(): Promise<CustomerListItem[]> {
  try {
    const raw = await fetchJSON<RawCustomer[]>("/customers");
    return raw.map((c) => transformCustomerBase(c, null));
  } catch (e) {
    if (USE_MOCK_FALLBACK) {
      await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
      return MOCK_CUSTOMERS;
    }
    throw e;
  }
}

export async function getCustomer(id: string): Promise<CustomerDetail | undefined> {
  try {
    const [raw, summary, metrics, events, commitments, tasks, risks] = await Promise.all([
      fetchJSON<RawCustomerDetail>(`/customers/${id}`),
      fetchOrNull<RawSummary>(`/customers/${id}/summary`),
      fetchOrNull<CustomerMetrics>(`/customers/${id}/metrics`),
      fetchOrNull<unknown[]>(`/customers/${id}/events`),
      fetchOrNull<unknown[]>(`/customers/${id}/commitments`),
      fetchOrNull<unknown[]>(`/customers/${id}/tasks`),
      fetchOrNull<unknown[]>(`/customers/${id}/risks`),
    ]);

    const base = transformCustomerBase(raw, summary);
    const transformed: CustomerDetail = {
      ...base,
      metrics: metrics ?? emptyMetrics(),
      timeline: transformTimeline(events),
      commitments: transformCommitments(commitments),
      tasks: transformTasks(tasks),
      risks: transformRisks(risks),
      contacts: transformContacts(raw.contacts),
      docs: [],
    };
    transformed.risk = deriveRisk(transformed.risks);
    return transformed;
  } catch (e) {
    if (USE_MOCK_FALLBACK) {
      await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
      return MOCK_CUSTOMERS.find((c) => c.id === id);
    }
    throw e;
  }
}

function transformTimeline(events: unknown[] | null): TimelineEvent[] {
  if (!events) return [];
  return events.slice(0, 8).map((e: any) => {
    const evt = e as { event_type?: string; title?: string; occurred_at?: string; created_at?: string; description?: string };
    return {
      kind: mapEventKind(evt.event_type ?? ""),
      title: evt.title ?? "事件",
      when: fmtRelative(evt.occurred_at ?? evt.created_at ?? new Date().toISOString()),
      by: "",
      src: evt.description ?? "",
    } satisfies TimelineEvent;
  });
}

function mapEventKind(et: string): TimelineEvent["kind"] {
  if (et.includes("payment") || et.includes("invoice")) return "invoice";
  if (et.includes("message") || et.includes("call")) return "wechat";
  if (et.includes("meeting") || et.includes("introduction")) return "meet";
  return "upload";
}

function transformCommitments(rows: unknown[] | null): Commitment[] {
  if (!rows) return [];
  return rows.map((r: any) => ({
    id: r.id,
    text: r.summary ?? r.description ?? "",
    source: r.raw_excerpt ?? "—",
    confidence: r.confidence > 0.85 ? "high" : r.confidence > 0.6 ? "med" : "low",
  }));
}

function transformTasks(rows: unknown[] | null): CustomerTask[] {
  if (!rows) return [];
  return rows.map((r: any) => ({
    id: r.id,
    text: r.title ?? "",
    due: r.due_date ?? "无截止",
    owner: r.assignee ?? "未分配",
  }));
}

function transformRisks(rows: unknown[] | null): RiskSignal[] {
  if (!rows) return [];
  return rows.map((r: any) => ({
    id: r.id,
    level: r.severity === "high" ? "high" : r.severity === "medium" ? "med" : "low",
    title: r.summary ?? "风险",
    detail: r.description ?? "",
    sources: r.raw_excerpt ? [r.raw_excerpt] : [],
  }));
}

export async function getMe(): Promise<CurrentUser> {
  return fetchPlatformJSON<CurrentUser>("/api/me");
}

export async function getAskSeed(customerId: string): Promise<AskSeed> {
  // No backend endpoint for "seed" — the real answer path is askAI(); this
  // only seeds first-paint suggestions.
  await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
  return { customerId, messages: [], suggestions: MOCK_ASK_SEED.suggestions };
}

type RawAskCitation = {
  target_type: string;
  target_id: string;
  snippet?: string | null;
};

type RawAskResponse = {
  answer: string;
  citations?: RawAskCitation[];
  confidence?: number;
  no_relevant_info?: boolean;
};

const CITATION_LABEL: Record<string, string> = {
  customer: "客户",
  contact: "联系人",
  contract: "合同",
  order: "订单",
  document: "文档",
  event: "动态",
  commitment: "承诺",
  task: "待办",
  risk: "风险",
  memory: "记忆",
};

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

function citationLabel(c: RawAskCitation): string {
  const kind = CITATION_LABEL[c.target_type] ?? c.target_type;
  const shortId = c.target_id ? c.target_id.slice(0, 8) : "";
  return c.snippet ? truncate(c.snippet, 48) : `${kind}${shortId ? ` · ${shortId}` : ""}`;
}

function askResponseToBlock(raw: RawAskResponse): AskAIBlock {
  const citations = raw.citations ?? [];
  const evidence = citations.slice(0, 8).map((c, i) => ({
    id: `${c.target_type}-${c.target_id || i}`,
    type: CITATION_LABEL[c.target_type] ?? c.target_type,
    label: citationLabel(c),
  }));
  const related = citations.slice(0, 6).map((c) => ({
    kind: CITATION_LABEL[c.target_type] ?? c.target_type,
    label: c.target_id ? `${c.target_id.slice(0, 8)}…` : citationLabel(c),
  }));
  return {
    verdict: raw.answer,
    evidence,
    next: raw.no_relevant_info
      ? ["这条问题在当前客户档案里没有足够依据，先补充相关合同、聊天记录或备注。"]
      : [],
    related,
  };
}

export async function askAI(customerId: string, question: string): Promise<AskAIBlock> {
  // Free/Lite/Pro all hit the shared assistant endpoint; the server
  // reads enterprise scope from the session cookie (never the body).
  // customer_id="all" → cross-customer Q&A; a UUID → single-customer KB.
  const raw = await postJSON<RawAskResponse>("/assistant/chat", {
    question,
    customer_id: customerId,
  });
  return askResponseToBlock(raw);
}
