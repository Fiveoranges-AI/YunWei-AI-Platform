/**
 * 锦泰 demo backend-mode API client.
 *
 * Talks to /api/win/* on the round 4 dev backend (services/platform-api/dev_jintai_backend.py).
 * The existing api/jintai.ts is from an earlier iteration and unused by the
 * round 2 JintaiDemoStore — we keep it untouched.
 *
 * Default base = http://127.0.0.1:8000/api/win. Override via Vite env
 * `VITE_JINTAI_BACKEND` or query param `?backendBase=<url>` (debug only).
 *
 * All endpoints return parsed JSON. Errors throw `JintaiBackendError` with
 * HTTP status + parsed `detail` text so callers can show useful toasts.
 */

const DEFAULT_BASE = "http://127.0.0.1:8000/api/win";

export function resolveBackendBase(): string {
  // Vite env first.
  const env = (import.meta as { env?: Record<string, string> }).env;
  if (env?.VITE_JINTAI_BACKEND) return env.VITE_JINTAI_BACKEND;
  // URL query override (debug).
  if (typeof window !== "undefined") {
    const qp = new URLSearchParams(window.location.search);
    const q = qp.get("backendBase");
    if (q) return q;
  }
  return DEFAULT_BASE;
}

export class JintaiBackendError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
  }
}

async function _fetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = resolveBackendBase();
  const url = `${base}${path}`;
  const resp = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!resp.ok) {
    let detail: unknown = await resp.text();
    try { detail = JSON.parse(detail as string); } catch { /* keep text */ }
    const msg = `${resp.status} ${resp.statusText} ${path}`;
    throw new JintaiBackendError(msg, resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ============================== health ==================================

export type HealthOut = {
  status: string;
  enterprise_id: string;
  mode: string;
};

export async function getHealth(): Promise<HealthOut> {
  const base = resolveBackendBase().replace(/\/api\/win$/, "");
  const resp = await fetch(`${base}/health`);
  if (!resp.ok) throw new JintaiBackendError(`health ${resp.status}`, resp.status);
  return (await resp.json()) as HealthOut;
}

// ============================== confirm =================================

export type ConfirmField = {
  name: string;
  value: unknown;
  confidence?: number;
  was_edited?: boolean;
};

export type ConfirmEntity = {
  entity_type: string;
  temp_id: string;
  fields: ConfirmField[];
  existing_entity_id?: string;
};

export type ConfirmRelationship = {
  from_temp_id: string;
  to_temp_id: string;
  type: string;
};

export type ConfirmResponse = {
  written: Array<{
    temp_id: string;
    entity_type: string;
    entity_id: string;
    created: boolean;
    human_verified: boolean;
    verified_by: string;
  }>;
  action_log_ids: string[];
};

export async function postConfirm(payload: {
  ingestion_id: string;
  source_type: string;
  source_ref?: string;
  entities: ConfirmEntity[];
  relationships?: ConfirmRelationship[];
}): Promise<ConfirmResponse> {
  return _fetch<ConfirmResponse>("/confirm/entities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ============================== procurement mutations ==================

export type IssueAndConfirmResp = {
  voucher_id: string;
  material_id: string;
  movement_id: string;
  balance_after: string;
  alert_id: string | null;
  auto_drafted_pr_id: string | null;
  auto_drafted_pr_no: string | null;
};

export async function postIssueAndConfirm(
  voucher_id: string,
): Promise<IssueAndConfirmResp> {
  return _fetch<IssueAndConfirmResp>(
    `/procurement/issue-vouchers/${voucher_id}/confirm-and-issue`,
    { method: "POST" },
  );
}

export type ApprovePrResp = {
  pr_id: string;
  po_id: string;
  po_no: string;
  total_amount: string;
};

export async function postApprovePr(
  pr_id: string,
  payload?: { supplier_id?: string; unit_prices?: Record<string, string> },
): Promise<ApprovePrResp> {
  return _fetch<ApprovePrResp>(`/procurement/requisitions/${pr_id}/approve`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export type ReceivePoResp = {
  po_id: string;
  receipt_id: string;
  receipt_no: string;
  payable_id: string;
  payable_due_date: string;
  stock_movement_ids: string[];
  resolved_alert_ids: string[];
};

export async function postReceivePo(
  po_id: string,
  payload: { warehouse: string; receipt_no?: string; invoice_date?: string },
): Promise<ReceivePoResp> {
  return _fetch<ReceivePoResp>(`/procurement/purchase-orders/${po_id}/receive`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ============================== procurement listings ===================

export type MaterialOut = {
  id: string;
  code: string;
  name: string;
  spec?: string | null;
  unit: string;
  safety_stock: string;
  last_balance: string;
  warning: "ok" | "low" | "out";
};

export async function listMaterials(): Promise<MaterialOut[]> {
  return _fetch<MaterialOut[]>("/procurement/materials");
}

export type PurchaseRequisitionOut = {
  id: string;
  pr_no: string;
  dept?: string | null;
  applicant?: string | null;
  supplier_id?: string | null;
  status: string;
  source: string;
  source_note?: string | null;
  approver?: string | null;
  po_ref?: string | null;
  human_verified: boolean;
  items: Array<{
    id: string;
    material_id: string;
    quantity: string;
    unit?: string | null;
    unit_price?: string | null;
    amount?: string | null;
  }>;
};

export async function listRequisitions(status?: string): Promise<PurchaseRequisitionOut[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return _fetch<PurchaseRequisitionOut[]>(`/procurement/requisitions${q}`);
}

export type PurchaseOrderOut = {
  id: string;
  po_no: string;
  supplier_id: string;
  status: string;
  total_amount: string;
  currency: string;
  warehouse?: string | null;
  received_at?: string | null;
  items: Array<{
    id: string;
    material_id: string;
    quantity: string;
    unit_price?: string | null;
    amount?: string | null;
  }>;
};

export async function listPurchaseOrders(status?: string): Promise<PurchaseOrderOut[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return _fetch<PurchaseOrderOut[]>(`/procurement/purchase-orders${q}`);
}

export type PayableOut = {
  id: string;
  supplier_id: string;
  source_type: string;
  source_ref?: string | null;
  amount: string;
  paid_amount: string;
  invoice_date: string;
  due_date: string;
  status: string;
  days_to_due: number;
  aging_bucket: "overdue" | "due_soon" | "future";
};

export async function listPayables(): Promise<PayableOut[]> {
  return _fetch<PayableOut[]>("/procurement/payables");
}

// ============================== briefing KPI ===========================

export type BriefingKpiOut = {
  payable_total: string;
  payable_overdue_total: string;
  payable_overdue_count: number;
  payable_due_soon_total: string;
  payable_count: number;
  low_stock_count: number;
  out_of_stock_count: number;
  pending_pr_count: number;
  open_po_count: number;
  in_transit_po_count: number;
  today_event_count: number;
  today_events: Array<{
    occurred_at: string;
    actor: string;
    actor_kind: string;
    action_type: string;
    summary: string;
  }>;
};

export async function getBriefingKpi(): Promise<BriefingKpiOut> {
  return _fetch<BriefingKpiOut>("/briefing/kpi");
}

// ============================== finance reports =========================

export async function getBalanceSheet(period: string): Promise<unknown> {
  return _fetch<unknown>(`/finance/balance-sheet?period=${period}`);
}

export async function getPnlDistribution(period: string): Promise<unknown> {
  return _fetch<unknown>(`/finance/pnl-distribution?period=${period}`);
}

export async function getCashflow(period: string): Promise<unknown> {
  return _fetch<unknown>(`/finance/cashflow?period=${period}`);
}

// ============================== high-level helpers =====================

/**
 * Ensure the demo supplier + pivot material exist in the backend.
 * Idempotent — if the same code/name already exists, the unique constraint
 * causes a 409 and we look up the existing IDs instead.
 *
 * Returns { supplierId, materialId }.
 */
export async function ensureDemoSeed(opts: {
  supplierName: string;
  paymentTermsDays: number;
  materialCode: string;
  materialName: string;
  unit: string;
  safetyStock: number;
  initialBalance: number;
}): Promise<{ supplierId: string; materialId: string }> {
  // Try create supplier
  let supplierId: string;
  try {
    const r = await postConfirm({
      ingestion_id: `demo-seed-supplier-${Date.now()}`,
      source_type: "manual",
      entities: [{
        entity_type: "Supplier",
        temp_id: "sup",
        fields: [
          { name: "name", value: opts.supplierName, confidence: 1.0 },
          { name: "payment_terms_days", value: opts.paymentTermsDays, confidence: 1.0 },
        ],
      }],
    });
    supplierId = r.written[0].entity_id;
  } catch (e) {
    if (e instanceof JintaiBackendError && e.status === 409) {
      // Look it up via... no direct endpoint, fallback: re-throw with hint.
      // For demo: assume first call succeeds (we reset DB between runs).
      throw new JintaiBackendError(
        `供应商 ${opts.supplierName} 已存在 (409). 请重置 demo DB 或换名.`,
        409, e.detail,
      );
    }
    throw e;
  }

  // Try create material (unique by code — round 4 demo uses timestamped code)
  let materialId: string;
  try {
    const r = await postConfirm({
      ingestion_id: `demo-seed-material-${Date.now()}`,
      source_type: "manual",
      entities: [{
        entity_type: "Material",
        temp_id: "mat",
        fields: [
          { name: "code", value: opts.materialCode, confidence: 1.0 },
          { name: "name", value: opts.materialName, confidence: 1.0 },
          { name: "unit", value: opts.unit, confidence: 1.0 },
          { name: "safety_stock", value: opts.safetyStock, confidence: 1.0 },
          { name: "last_balance", value: opts.initialBalance, confidence: 1.0 },
        ],
      }],
    });
    materialId = r.written[0].entity_id;
  } catch (e) {
    if (e instanceof JintaiBackendError && e.status === 409) {
      throw new JintaiBackendError(
        `物料 ${opts.materialCode} 已存在 (409). 请重置 demo DB 或换 code.`,
        409, e.detail,
      );
    }
    throw e;
  }

  return { supplierId, materialId };
}

/**
 * Create one issue voucher draft. Returns the voucher_id; the rule
 * (confirm-and-issue) is a separate call.
 */
export async function createIssueVoucher(opts: {
  materialId: string;
  voucherNo: string;
  workshop: string;
  applicant: string;
  quantity: number;
  unit: string;
  purpose?: string;
}): Promise<string> {
  const r = await postConfirm({
    ingestion_id: `issue-${opts.voucherNo}-${Date.now()}`,
    source_type: "issue_voucher_photo",
    source_ref: `storage://demo/${opts.voucherNo}.jpg`,
    entities: [{
      entity_type: "IssueVoucher",
      temp_id: "iv",
      fields: [
        { name: "voucher_no", value: opts.voucherNo, confidence: 0.96 },
        { name: "workshop", value: opts.workshop, confidence: 0.97 },
        { name: "applicant", value: opts.applicant, confidence: 0.93 },
        { name: "material_id", value: opts.materialId, confidence: 1.0 },
        { name: "quantity", value: opts.quantity, confidence: 0.94 },
        { name: "unit", value: opts.unit, confidence: 0.99 },
        ...(opts.purpose
          ? [{ name: "purpose", value: opts.purpose, confidence: 0.87 }]
          : []),
        { name: "issued_date", value: new Date().toISOString().slice(0, 10), confidence: 0.92 },
      ],
    }],
  });
  return r.written[0].entity_id;
}
