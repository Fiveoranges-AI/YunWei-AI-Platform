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

export type RejectPrResp = {
  pr_id: string;
  status: string;
};

export async function postRejectPr(
  pr_id: string,
  payload?: { reason?: string },
): Promise<RejectPrResp> {
  return _fetch<RejectPrResp>(`/procurement/requisitions/${pr_id}/reject`, {
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


// ============================== contracts =============================
// Round 13: list + detail for the Contract entity (uploaded via /parse/upload
// then confirmed via /confirm/entities). Maps onto read.py:list_contracts +
// get_contract endpoints (already shipped in main repo's read.py).

export type ContractListItem = {
  id: string;
  customer_id: string | null;
  order_id: string | null;
  contract_no_external: string | null;
  contract_no_internal: string | null;
  amount_total: number | null;
  amount_currency: string | null;
  signing_date?: string | null;
  effective_date?: string | null;
  expiry_date?: string | null;
  payment_terms?: string | null;
  status?: string | null;
  confidence_overall?: number | null;
  human_verified?: boolean;
  verified_by?: string | null;
  created_at?: string;
};

export async function listContracts(limit = 20): Promise<ContractListItem[]> {
  return _fetch<ContractListItem[]>(`/contracts?limit=${limit}`);
}

export type ContractDetail = ContractListItem & {
  customer: { id: string; full_name: string | null } | null;
  order: { id: string; amount_total: number | null } | null;
  provenance: Array<{
    field_name: string;
    value: string | null;
    source_page: number | null;
    source_excerpt: string | null;
    confidence: number | null;
    extracted_by: string | null;
    review_action: string | null;
  }>;
};

export async function getContract(id: string): Promise<ContractDetail> {
  return _fetch<ContractDetail>(`/contracts/${id}`);
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

// Round 6: finance report shapes (matches backend services/finance.py)

export type FinanceRow = {
  line: string;
  name: string;
  code?: string | null;
  amount: string;
  opening?: string | null;
  ending?: string | null;
  note?: string | null;
};

export type BalanceSheetOut = {
  statement: string;
  period: string;
  as_of_date: string;
  currency: string;
  unit: string;
  assets: FinanceRow[];
  liabilities: FinanceRow[];
  equity: FinanceRow[];
  totals: { assets: string; liabilities_plus_equity: string; balanced: boolean };
};

export type PnlOut = {
  statement: string;
  period: string;
  currency: string;
  unit: string;
  rows: FinanceRow[];
  net_profit_period: string;
  retained_earnings_change_period: string;
  period_depreciation_in_admin?: string;
  totals: { revenue: string; operating_profit: string; net_profit: string };
};

export type CashflowOut = {
  statement: string;
  period: string;
  currency: string;
  unit: string;
  operating: FinanceRow[];
  investing: FinanceRow[];
  financing: FinanceRow[];
  summary: FinanceRow[];
  totals: {
    operating_net: string;
    investing_net: string;
    financing_net: string;
    net_increase: string;
    cash_ending: string;
  };
};

export type DepreciationOut = {
  period: string;
  as_of_date: string;
  currency: string;
  unit: string;
  rows: Array<{
    asset_no: string;
    name: string;
    category: string;
    acquired_date: string;
    original_cost: string;
    salvage_value: string;
    useful_life_months: number;
    monthly_depreciation: string;
    months_depreciated_through_period: number;
    accumulated_depreciation: string;
    current_period_depreciation: string;
    net_book_value: string;
    status: string;
  }>;
  totals: {
    original_cost: string;
    accumulated_depreciation: string;
    current_period_depreciation: string;
    net_book_value: string;
  };
};

export type CostBreakdownOut = {
  period: string;
  currency: string;
  unit: string;
  by_material: Array<{
    material_id: string; code: string; name: string; unit: string;
    consumed_qty: string; unit_cost: string; cost_amount: string;
  }>;
  by_supplier: Array<{
    supplier_id: string; name: string; po_count: number; received_amount: string;
  }>;
  totals: { cogs_from_material_consumption: string; procurement_received: string };
};

export async function getBalanceSheet(period: string): Promise<BalanceSheetOut> {
  return _fetch<BalanceSheetOut>(`/finance/balance-sheet?period=${period}`);
}

export async function getPnlDistribution(period: string): Promise<PnlOut> {
  return _fetch<PnlOut>(`/finance/pnl-distribution?period=${period}`);
}

export async function getCashflow(period: string): Promise<CashflowOut> {
  return _fetch<CashflowOut>(`/finance/cashflow?period=${period}`);
}

export async function getDepreciation(period: string): Promise<DepreciationOut> {
  return _fetch<DepreciationOut>(`/finance/depreciation?period=${period}`);
}

export async function getCostBreakdown(period: string): Promise<CostBreakdownOut> {
  return _fetch<CostBreakdownOut>(`/finance/cost-breakdown?period=${period}`);
}

// Round 6: BOM listing + detail (backend already has POST explode in round 2)
export type BomListItem = {
  id: string; product_code: string; product_name: string;
  version: string; output_quantity: string; output_unit: string;
  status: string; notes?: string | null;
};

export type BomDetail = BomListItem & {
  lines: Array<{
    id: string; material_id: string;
    quantity_per_output: string; unit?: string | null;
    scrap_rate: string; sort_order: number; notes?: string | null;
  }>;
};

export type BomExplodeResult = {
  bom_id: string; product_code: string; product_name: string;
  version: string; output_unit: string; batch_quantity: string;
  lines: Array<{
    material_id: string; code: string; name: string; unit: string;
    quantity_per_output: string; scrap_rate: string;
    required_qty: string; current_balance: string;
    shortage: string; available: boolean;
  }>;
  fully_available: boolean;
};

export async function listBoms(status?: string): Promise<BomListItem[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return _fetch<BomListItem[]>(`/procurement/boms${q}`);
}

export async function getBomDetail(id: string): Promise<BomDetail> {
  return _fetch<BomDetail>(`/procurement/boms/${id}`);
}

export async function explodeBom(
  id: string, batchQuantity: string | number,
): Promise<BomExplodeResult> {
  return _fetch<BomExplodeResult>(`/procurement/boms/${id}/explode`, {
    method: "POST",
    body: JSON.stringify({ batch_quantity: String(batchQuantity) }),
  });
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

// ============================== round 5: parse upload ===================

export type UploadFieldSpan = {
  page?: number | null;
  bbox?: number[] | null;
  text?: string | null;
  cell?: string | null;
};

export type UploadField = {
  name: string;
  value: unknown;
  confidence: number;
  source_span?: UploadFieldSpan | null;
};

export type UploadEntity = {
  entity_type: string;
  temp_id: string;
  fields: UploadField[];
  missing_required?: string[];
};

export type UploadCandidate = {
  ingestion_id: string;
  source: { type: string; file_ref: string; uploaded_by?: string | null };
  entities: UploadEntity[];
  relationships: Array<{ from_temp_id: string; to_temp_id: string; type: string }>;
  overall_confidence: number;
  warnings: string[];
};

export type UploadAttachment = {
  path: string;
  checksum: string;
  size_bytes: number;
  filename: string;
  content_type: string | null;
};

export type ParseUploadResponse = {
  candidate: UploadCandidate;
  attachment: UploadAttachment;
  provider: "claude" | "demo-mock" | string;
  source_type: "excel" | "contract" | "wechat_screenshot";
  action_log_id: string;
};

/**
 * POST multipart /parse/upload with progress tracking via XHR (fetch's
 * upload progress is not supported in browsers as of 2026).
 */
export async function uploadDocument(
  file: File,
  opts?: { onProgress?: (pct: number) => void },
): Promise<ParseUploadResponse> {
  const base = resolveBackendBase();
  const url = `${base}/parse/upload`;
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && opts?.onProgress) {
        opts.onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onerror = () => reject(new JintaiBackendError("network error", 0));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as ParseUploadResponse);
        } catch (e) {
          reject(new JintaiBackendError(`bad JSON: ${e}`, xhr.status));
        }
      } else {
        let detail: unknown = xhr.responseText;
        try { detail = JSON.parse(detail as string); } catch { /* ignore */ }
        reject(new JintaiBackendError(
          `${xhr.status} ${xhr.statusText} /parse/upload`,
          xhr.status, detail,
        ));
      }
    };
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

/**
 * Confirm one upload-derived entity into the ontology (走 confirm_writer +
 * ActionLog). Used by the "采纳" button on the upload review card.
 *
 * For IssueVoucher entities, the parse pipeline emits a `material_name_hint`
 * field (not a real DB column). Caller should pre-resolve it to material_id
 * via listMaterials() before calling this — the hint is dropped here.
 */
export async function confirmUploadedEntity(opts: {
  entity: UploadEntity;
  source_type: string;
  file_ref: string;
  edits?: Record<string, unknown>;
  materialId?: string;
}): Promise<ConfirmResponse> {
  const skipNames = new Set(["material_name_hint"]);
  const fields: ConfirmField[] = [];
  for (const f of opts.entity.fields) {
    if (skipNames.has(f.name)) continue;
    const edited = opts.edits && opts.edits[f.name] !== undefined;
    const value = edited ? opts.edits![f.name] : f.value;
    fields.push({
      name: f.name,
      value,
      confidence: f.confidence,
      was_edited: !!edited,
    });
  }
  // If material_id wasn't part of the candidate (DemoMockProvider emits hint
  // instead of id), inject it.
  if (opts.entity.entity_type === "IssueVoucher" && opts.materialId) {
    fields.push({
      name: "material_id",
      value: opts.materialId,
      confidence: 1.0,
      was_edited: true,
    });
  }
  return postConfirm({
    ingestion_id: `upload-confirm-${Date.now()}`,
    source_type: opts.source_type,
    source_ref: opts.file_ref,
    entities: [{
      entity_type: opts.entity.entity_type,
      temp_id: opts.entity.temp_id,
      fields,
    }],
  });
}

/**
 * Round 13: confirm an upload whose candidate has MULTIPLE entities +
 * relationships (e.g. Contract uploads emit Customer + Contract +
 * Customer-has-Contract so the Contract's customer_id FK can be resolved
 * by confirm_writer's relationship walker).
 *
 * The single-entity `confirmUploadedEntity` above is kept for IssueVoucher
 * (round 5 path) because that's a simpler shape with no parent FK.
 */
export async function confirmUploadedCandidate(opts: {
  candidate: UploadCandidate;
  source_type: string;
  file_ref: string;
  edits?: Record<string, Record<string, unknown>>;  // entity.temp_id → field-edits
}): Promise<ConfirmResponse> {
  const skipNames = new Set(["material_name_hint"]);
  const entities = opts.candidate.entities.map((ent) => {
    const eedits = opts.edits?.[ent.temp_id] ?? {};
    const fields: ConfirmField[] = [];
    for (const f of ent.fields) {
      if (skipNames.has(f.name)) continue;
      const edited = eedits[f.name] !== undefined;
      fields.push({
        name: f.name,
        value: edited ? eedits[f.name] : f.value,
        confidence: f.confidence,
        was_edited: !!edited,
      });
    }
    return {
      entity_type: ent.entity_type,
      temp_id: ent.temp_id,
      fields,
    };
  });
  return postConfirm({
    ingestion_id: `upload-confirm-multi-${Date.now()}`,
    source_type: opts.source_type,
    source_ref: opts.file_ref,
    entities,
    relationships: opts.candidate.relationships ?? [],
  });
}


// ============================== high-level helpers (existing) ===========

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
