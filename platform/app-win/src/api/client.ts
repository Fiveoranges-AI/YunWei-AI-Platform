// Backend API client for /win/api/. The backend (yinhu_brain, integrated
// into platform_app) returns the raw yunwei-tools shape; this module
// translates each response into the design's shape (CustomerListItem,
// CustomerDetail, etc.). On any network/HTTP error it falls back to mock
// data so the UI keeps rendering during local dev.
//
// Backend → design shape mapping:
//   id            → id (string-as-uuid)
//   full_name     → name
//   short_name    → monogram (fallback: first 1-2 chars of name)
//                   color    (derived from name hash)
//                   tag      (default "客户" — yunwei-tools has no tag column)
//                   aiSummary (TODO: source from /summary headline; v1 placeholder)
//                   metrics  (separate /metrics call)
//                   risk     (derived from /risks count + max severity)

import { MOCK_ASK_SEED, MOCK_CUSTOMERS, MOCK_REVIEW } from "../data/mock";
import type {
  AskSeed,
  Commitment,
  Contact,
  CustomerDetail,
  CustomerListItem,
  CustomerMetrics,
  CustomerRisk,
  Review,
  RiskLevel,
  RiskSignal,
  CustomerTask,
  TimelineEvent,
} from "../data/types";
import { fmtRelative } from "../lib/format";

const API_BASE = "/win/api";
const MOCK_DELAY_MS = 200;

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
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path}`);
  return (await res.json()) as T;
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
  } catch {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
    return MOCK_CUSTOMERS;
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
  } catch {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
    return MOCK_CUSTOMERS.find((c) => c.id === id);
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

export async function getReview(_uploadId: string): Promise<Review> {
  // TODO: wire to /win/api/customers/{id}/inbox/{id}/* once we have a real
  // upload flow. For now, mock data is the only source.
  await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
  return MOCK_REVIEW;
}

export async function getAskSeed(customerId: string): Promise<AskSeed> {
  // No backend endpoint for "seed" — frontend just uses an empty conversation
  // and the suggestions list. v1 returns mock; replace with real seed logic
  // when the Ask UI is wired to /win/api/customers/{id}/ask end-to-end.
  await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
  return { ...MOCK_ASK_SEED, customerId };
}
