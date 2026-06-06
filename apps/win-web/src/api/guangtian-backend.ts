/**
 * 光天 · AI 库存管家 backend-mode API client.
 *
 * Talks to /api/win/guangtian/* on the dev backend
 * (services/platform-api/dev_guangtian_backend.py, tenant guangtian_demo).
 *
 * Default base = http://127.0.0.1:8000/api/win. Override via Vite env
 * `VITE_GUANGTIAN_BACKEND` or query `?backendBase=<url>` (debug only).
 *
 * Mirrors the api/jintai-backend.ts shape (same _fetch + error class style).
 */

const DEFAULT_BASE = "http://127.0.0.1:8000/api/win";

export function resolveBackendBase(): string {
  const env = (import.meta as { env?: Record<string, string> }).env;
  if (env?.VITE_GUANGTIAN_BACKEND) return env.VITE_GUANGTIAN_BACKEND;
  if (typeof window !== "undefined") {
    const qp = new URLSearchParams(window.location.search);
    const q = qp.get("backendBase");
    if (q) return q;
  }
  return DEFAULT_BASE;
}

export class GuangtianBackendError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
  }
}

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${resolveBackendBase()}${path}`;
  const resp = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!resp.ok) {
    let detail: unknown = await resp.text();
    try { detail = JSON.parse(detail as string); } catch { /* keep text */ }
    throw new GuangtianBackendError(`${resp.status} ${resp.statusText} ${path}`, resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ============================== health ==================================

export type HealthOut = { status: string; enterprise_id: string; db: string; mode: string };

export async function getHealth(): Promise<HealthOut> {
  const base = resolveBackendBase().replace(/\/api\/win$/, "");
  const resp = await fetch(`${base}/health`);
  if (!resp.ok) throw new GuangtianBackendError(`health ${resp.status}`, resp.status);
  return (await resp.json()) as HealthOut;
}

// ============================== types ===================================

export type SkuOut = {
  id: string; code: string; name: string; spec: string | null; category: string | null;
  unit: string; location: string | null; safety_stock: string; last_balance: string;
  status: "normal" | "low" | "shortage_risk" | "out" | "anomaly";
  last_in_at: string | null; last_out_at: string | null;
};

export type KpiOut = {
  sku_total: number; low_stock_count: number; out_of_stock_count: number;
  shortage_order_count: number; skus_with_open_gap: number;
  today_inbound: number; today_outbound: number; open_alerts: number;
};

export type MovementOut = {
  id: string; sku_id: string; op: string; quantity: string;
  balance_before: string; balance_after: string; reference_no: string | null;
  operator: string | null; occurred_at: string; confidence: number | null;
  confirmed: boolean; note: string | null;
};

export type OrderItemOut = {
  sku_id: string | null; sku_code: string | null; name: string | null;
  needed: string; stock: string; gap: string; unit: string | null;
};
export type OrderOut = {
  id: string; order_no: string; customer: string; delivery_date: string | null;
  delivery_note: string | null; level: string; total_value: string | null;
  ai_suggestion: string | null; items: OrderItemOut[]; fulfillment_pct: number;
};

export type AlertOut = {
  id: string; sku_id: string; level: string; balance_at_trigger: string;
  safety_stock_at_trigger: string; triggered_at: string; resolved_at: string | null; note: string | null;
};

export type ReplenishmentOut = {
  id: string; sku_id: string; current_stock: string; safety_stock: string;
  suggest_qty: string; unit: string | null; priority: string; reason: string | null;
  est_date: string | null; status: string; source: string; work_order_no: string | null;
};

export type AskOut = {
  conclusion: string; evidence: { label: string; count: number }[];
  risk: string; actions: string[]; links: { label: string; target: string }[]; engine: string;
};

// ============================== reads ===================================

export const listSkus = () => _fetch<SkuOut[]>("/guangtian/skus");
export const getBriefingKpi = () => _fetch<KpiOut>("/guangtian/briefing/kpi");
export const listMovements = (skuId?: string) =>
  _fetch<MovementOut[]>(`/guangtian/stock-movements${skuId ? `?sku_id=${skuId}` : ""}`);
export const listCustomerOrders = () => _fetch<OrderOut[]>("/guangtian/customer-orders");
export const listStockAlerts = (onlyOpen = false) =>
  _fetch<AlertOut[]>(`/guangtian/stock-alerts${onlyOpen ? "?only_open=true" : ""}`);
export const listReplenishments = () => _fetch<ReplenishmentOut[]>("/guangtian/replenishments");
export const getDailyReport = () => _fetch<Record<string, unknown>>("/guangtian/daily-report");

// ============================== writes ==================================

export type MovementResultOut = {
  sku_id: string; voucher_id: string; movement_id: string;
  balance_before: string; balance_after: string; alert_id: string | null; resolved_alerts: number;
};

export const postOutbound = (body: {
  sku_id: string; quantity: number; customer?: string; order_no?: string;
  outbound_type?: string; confidence?: number;
}) => _fetch<MovementResultOut>("/guangtian/outbound", { method: "POST", body: JSON.stringify(body) });

export const postInbound = (body: {
  sku_id: string; quantity: number; source_ref?: string; inbound_type?: string; confidence?: number;
}) => _fetch<MovementResultOut>("/guangtian/inbound", { method: "POST", body: JSON.stringify(body) });

export const generateReplenishments = () =>
  _fetch<{ created: string[]; skipped_existing: number }>("/guangtian/replenishments/generate", { method: "POST" });

export const adoptReplenishment = (id: string) =>
  _fetch<{ work_order_no: string }>(`/guangtian/replenishments/${id}/adopt`, { method: "POST" });

export const askInventory = (question: string) =>
  _fetch<AskOut>("/guangtian/ask", { method: "POST", body: JSON.stringify({ question }) });
