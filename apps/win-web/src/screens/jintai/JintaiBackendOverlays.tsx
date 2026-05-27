/**
 * Round 6: 每个 tab 顶部的 backend-mode-only "实时数据栏" overlay 组件.
 *
 * 设计原则:
 *  - 仅 state.mode === 'backend' 时渲染;mock 模式 return null,demo 路径 0 影响
 *  - 顶部 prominent banner 标注 "✨ backend live · GET /api/win/... · 拉取于 HH:MM:SS"
 *  - loading / error / empty 三态都明示
 *  - 不替代 mock UI,挂在每个 tab 最顶部 (mock 内容仍在下方做对照)
 *  - 用 useBackendQuery hook 拉数据;30s stale-while-revalidate
 *
 * 4 个 overlay 集中在一个文件减少 import 噪音:
 *   - JintaiFinanceBackendOverlay({ activeTab })
 *   - JintaiBriefingBackendOverlay()
 *   - JintaiPurchaseBackendOverlay()
 *   - JintaiProductionBomBackendOverlay()
 */

import type { ReactNode } from "react";
import {
  getBalanceSheet, getCashflow, getCostBreakdown, getDepreciation, getPnlDistribution,
  getBriefingKpi, listBoms, listPayables, listPurchaseOrders, listRequisitions,
  explodeBom,
  type BalanceSheetOut, type BomListItem, type BriefingKpiOut, type CashflowOut,
  type CostBreakdownOut, type DepreciationOut, type FinanceRow, type PayableOut,
  type PnlOut, type PurchaseOrderOut, type PurchaseRequisitionOut,
} from "../../api/jintai-backend";
import { useJintai } from "./state/store";
import { useBackendQuery } from "./state/useBackendQuery";


// ============================== shared chrome =========================

function _currentPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function _fmtTime(ms: number | null): string {
  if (!ms) return "—";
  const d = new Date(ms);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

function _fmtCny(s: string | number | null | undefined): string {
  if (s === null || s === undefined || s === "") return "—";
  const n = typeof s === "string" ? parseFloat(s) : s;
  if (!isFinite(n)) return String(s);
  return `¥${n.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
}


function OverlayChrome({
  endpoint, loadedAt, loading, error, refetch, children,
}: {
  endpoint: string; loadedAt: number | null; loading: boolean; error: string | null;
  refetch: () => void; children: ReactNode;
}) {
  return (
    <div
      data-jintai-backend-overlay
      style={{
        marginBottom: 18, padding: 14,
        background: "linear-gradient(180deg, #f0faf4 0%, #ffffff 100%)",
        border: "1px solid var(--ok-500)", borderLeft: "4px solid var(--ok-500)",
        borderRadius: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ok-700)" }}>
          ✨ backend live data
          <span style={{ color: "var(--ink-500)", fontWeight: 400, marginLeft: 6 }}>
            <code style={{ fontSize: 11 }}>GET {endpoint}</code>
            {" · "}拉取于 {_fmtTime(loadedAt)}
            {loading && " · 刷新中…"}
            {error && <span style={{ color: "var(--risk-700)" }}> · ⚠ {error}</span>}
          </span>
        </div>
        <button
          onClick={refetch}
          style={{
            padding: "3px 10px", fontSize: 11, fontFamily: "inherit",
            background: "var(--brand-100)", color: "var(--brand-700)",
            border: "1px solid var(--brand-300)", borderRadius: 4, cursor: "pointer",
          }}
        >
          ↻ 刷新
        </button>
      </div>
      {children}
    </div>
  );
}


function Empty({ msg }: { msg: string }) {
  return (
    <div style={{ padding: 14, fontSize: 12, color: "var(--ink-500)", textAlign: "center" }}>
      {msg}
    </div>
  );
}


// ============================== 1. Finance =============================

type FinanceSubtab = "balance" | "income" | "cashflow" | "cost" | "depreciation";

export function JintaiFinanceBackendOverlay({ activeTab }: { activeTab: FinanceSubtab }) {
  const { state } = useJintai();
  if (state.mode !== "backend") return null;

  const period = _currentPeriod();

  if (activeTab === "balance") {
    return <_FinanceBalance period={period} />;
  }
  if (activeTab === "income") {
    return <_FinancePnl period={period} />;
  }
  if (activeTab === "cashflow") {
    return <_FinanceCashflow period={period} />;
  }
  if (activeTab === "depreciation") {
    return <_FinanceDepreciation period={period} />;
  }
  if (activeTab === "cost") {
    return <_FinanceCost period={period} />;
  }
  return null;
}


function _FinanceBalance({ period }: { period: string }) {
  const q = useBackendQuery<BalanceSheetOut>(
    `balance-sheet-${period}`,
    () => getBalanceSheet(period),
  );
  return (
    <OverlayChrome
      endpoint={`/finance/balance-sheet?period=${period}`}
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            {q.data.statement} · {q.data.period} (as of {q.data.as_of_date}) · 元
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <_RowGroup title="资产" rows={q.data.assets} />
            <_RowGroup title="负债" rows={q.data.liabilities} />
            <_RowGroup title="所有者权益" rows={q.data.equity} />
          </div>
          <div style={{
            marginTop: 10, padding: 8,
            background: q.data.totals.balanced ? "var(--ok-100)" : "var(--risk-100)",
            color: q.data.totals.balanced ? "var(--ok-700)" : "var(--risk-700)",
            borderRadius: 4, fontSize: 12, textAlign: "center", fontWeight: 600,
          }}>
            {q.data.totals.balanced ? "✓ 借贷平衡: " : "⚠ 借贷不平衡: "}
            资产合计 {_fmtCny(q.data.totals.assets)} = 负债+权益合计 {_fmtCny(q.data.totals.liabilities_plus_equity)}
          </div>
        </div>
      )}
    </OverlayChrome>
  );
}


function _RowGroup({ title, rows }: { title: string; rows: FinanceRow[] }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 4 }}>
        {title}
      </div>
      <table style={{ width: "100%", fontSize: 11.5, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ color: "var(--ink-500)", fontSize: 10.5 }}>
            <th style={{ textAlign: "left", padding: "2px 4px" }}>行次/名称</th>
            <th style={{ textAlign: "right", padding: "2px 4px" }}>期初</th>
            <th style={{ textAlign: "right", padding: "2px 4px" }}>期末</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const subtotal = r.line === "subtotal";
            return (
              <tr key={i} style={{
                borderTop: subtotal ? "1px solid var(--ink-300)" : "none",
                background: subtotal ? "var(--ink-100)" : "transparent",
                fontWeight: subtotal ? 700 : 400,
              }}>
                <td style={{ padding: "3px 4px", color: "var(--ink-900)" }}>
                  {!subtotal && <code style={{ fontSize: 9.5, color: "var(--ink-400)", marginRight: 4 }}>{r.code || r.line}</code>}
                  {r.name}
                </td>
                <td style={{ padding: "3px 4px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {_fmtCny(r.opening ?? null)}
                </td>
                <td style={{ padding: "3px 4px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {_fmtCny(r.ending ?? r.amount)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


function _FinancePnl({ period }: { period: string }) {
  const q = useBackendQuery<PnlOut>(`pnl-${period}`, () => getPnlDistribution(period));
  return (
    <OverlayChrome
      endpoint={`/finance/pnl-distribution?period=${period}`}
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            {q.data.statement} · {q.data.period} · 元
          </div>
          <table style={{ width: "100%", fontSize: 11.5, borderCollapse: "collapse" }}>
            <tbody>
              {q.data.rows.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--ink-100)" }}>
                  <td style={{ padding: "4px 6px", color: "var(--ink-500)", width: 36 }}>{r.line}</td>
                  <td style={{ padding: "4px 6px", color: "var(--ink-900)" }}>
                    {r.name}
                    {r.note && <span style={{ fontSize: 10, color: "var(--ink-400)", marginLeft: 6 }}>{r.note}</span>}
                  </td>
                  <td style={{ padding: "4px 6px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {_fmtCny(r.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--ink-500)" }}>
            本期净利润 <b>{_fmtCny(q.data.totals.net_profit)}</b>
            {" · "}营业收入 {_fmtCny(q.data.totals.revenue)}
            {q.data.period_depreciation_in_admin && (
              <> · 含折旧 {_fmtCny(q.data.period_depreciation_in_admin)}(round 3 闭环)</>
            )}
          </div>
        </div>
      )}
    </OverlayChrome>
  );
}


function _FinanceCashflow({ period }: { period: string }) {
  const q = useBackendQuery<CashflowOut>(`cf-${period}`, () => getCashflow(period));
  return (
    <OverlayChrome
      endpoint={`/finance/cashflow?period=${period}`}
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            {q.data.statement} · {q.data.period} · 元
          </div>
          <_CfSection title="一、经营活动" rows={q.data.operating} />
          <_CfSection title="二、投资活动" rows={q.data.investing} />
          <_CfSection title="三、筹资活动" rows={q.data.financing} />
          <_CfSection title="汇总" rows={q.data.summary} />
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--ink-500)" }}>
            净增加 <b>{_fmtCny(q.data.totals.net_increase)}</b> · 期末现金 <b>{_fmtCny(q.data.totals.cash_ending)}</b>
          </div>
        </div>
      )}
    </OverlayChrome>
  );
}


function _CfSection({ title, rows }: { title: string; rows: FinanceRow[] }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 2 }}>{title}</div>
      <table style={{ width: "100%", fontSize: 11.5, borderCollapse: "collapse" }}>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td style={{ padding: "2px 6px", color: "var(--ink-400)", fontSize: 10, width: 50 }}>{r.line}</td>
              <td style={{ padding: "2px 6px" }}>{r.name}</td>
              <td style={{ padding: "2px 6px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {_fmtCny(r.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


function _FinanceDepreciation({ period }: { period: string }) {
  const q = useBackendQuery<DepreciationOut>(`dep-${period}`, () => getDepreciation(period));
  return (
    <OverlayChrome
      endpoint={`/finance/depreciation?period=${period}`}
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            折旧台账 · {q.data.period} ({q.data.rows.length} 项资产)
          </div>
          {q.data.rows.length === 0 ? (
            <Empty msg="后端无 FixedAsset 数据 — 可通过 /confirm/entities 写 FixedAsset 实体后再看" />
          ) : (
            <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "var(--ink-500)", fontSize: 10.5, borderBottom: "1px solid var(--ink-200)" }}>
                  <th style={{ textAlign: "left", padding: 3 }}>资产编号</th>
                  <th style={{ textAlign: "left", padding: 3 }}>名称</th>
                  <th style={{ textAlign: "right", padding: 3 }}>原值</th>
                  <th style={{ textAlign: "right", padding: 3 }}>累计折旧</th>
                  <th style={{ textAlign: "right", padding: 3 }}>本期折旧</th>
                  <th style={{ textAlign: "right", padding: 3 }}>净值</th>
                </tr>
              </thead>
              <tbody>
                {q.data.rows.map((r) => (
                  <tr key={r.asset_no} style={{ borderBottom: "1px solid var(--ink-100)" }}>
                    <td style={{ padding: 3 }}><code style={{ fontSize: 10 }}>{r.asset_no}</code></td>
                    <td style={{ padding: 3 }}>{r.name}</td>
                    <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(r.original_cost)}</td>
                    <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(r.accumulated_depreciation)}</td>
                    <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(r.current_period_depreciation)}</td>
                    <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--ok-700)" }}>{_fmtCny(r.net_book_value)}</td>
                  </tr>
                ))}
                <tr style={{ background: "var(--ink-100)", fontWeight: 700 }}>
                  <td colSpan={2} style={{ padding: 4 }}>合计</td>
                  <td style={{ padding: 4, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(q.data.totals.original_cost)}</td>
                  <td style={{ padding: 4, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(q.data.totals.accumulated_depreciation)}</td>
                  <td style={{ padding: 4, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(q.data.totals.current_period_depreciation)}</td>
                  <td style={{ padding: 4, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(q.data.totals.net_book_value)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      )}
    </OverlayChrome>
  );
}


function _FinanceCost({ period }: { period: string }) {
  const q = useBackendQuery<CostBreakdownOut>(`cost-${period}`, () => getCostBreakdown(period));
  return (
    <OverlayChrome
      endpoint={`/finance/cost-breakdown?period=${period}`}
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            成本拆分 · {q.data.period} · 元
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 4 }}>
                按物料 (出库 × WAC,共 {q.data.by_material.length} 物料)
              </div>
              {q.data.by_material.length === 0 ? <Empty msg="本期无出库" /> :
                <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
                  <tbody>
                    {q.data.by_material.slice(0, 8).map((m) => (
                      <tr key={m.material_id} style={{ borderBottom: "1px solid var(--ink-100)" }}>
                        <td style={{ padding: 3 }}>{m.name} <code style={{ fontSize: 9.5, color: "var(--ink-400)" }}>{m.code}</code></td>
                        <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{m.consumed_qty} {m.unit}</td>
                        <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--ok-700)" }}>{_fmtCny(m.cost_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>}
              <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4 }}>
                COGS 合计 <b>{_fmtCny(q.data.totals.cogs_from_material_consumption)}</b>
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 4 }}>
                按供应商 (本期入库,共 {q.data.by_supplier.length} 家)
              </div>
              {q.data.by_supplier.length === 0 ? <Empty msg="本期无入库" /> :
                <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
                  <tbody>
                    {q.data.by_supplier.slice(0, 8).map((s) => (
                      <tr key={s.supplier_id} style={{ borderBottom: "1px solid var(--ink-100)" }}>
                        <td style={{ padding: 3 }}>{s.name}</td>
                        <td style={{ padding: 3, textAlign: "right" }}>{s.po_count} PO</td>
                        <td style={{ padding: 3, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{_fmtCny(s.received_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>}
              <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 4 }}>
                本期采购入库 <b>{_fmtCny(q.data.totals.procurement_received)}</b>
              </div>
            </div>
          </div>
        </div>
      )}
    </OverlayChrome>
  );
}


// ============================== 2. Briefing KPI ========================

export function JintaiBriefingBackendOverlay() {
  const { state } = useJintai();
  const q = useBackendQuery<BriefingKpiOut>(
    "briefing-kpi", () => getBriefingKpi(),
    { enabled: state.mode === "backend", staleMs: 30_000 },
  );
  if (state.mode !== "backend") return null;
  return (
    <OverlayChrome
      endpoint="/briefing/kpi"
      loadedAt={q.loadedAt} loading={q.loading} error={q.error} refetch={q.refetch}
    >
      {!q.data && !q.error && <Empty msg="拉取中..." />}
      {q.data && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginBottom: 10 }}>
            <_Kpi label="应付总额" value={_fmtCny(q.data.payable_total)} hint={`${q.data.payable_count} 笔`} />
            <_Kpi label="应付逾期" value={_fmtCny(q.data.payable_overdue_total)} hint={`${q.data.payable_overdue_count} 笔`} risk={q.data.payable_overdue_count > 0} />
            <_Kpi label="低库存 SKU" value={String(q.data.low_stock_count)} risk={q.data.low_stock_count > 0} />
            <_Kpi label="缺货 SKU" value={String(q.data.out_of_stock_count)} risk={q.data.out_of_stock_count > 0} />
            <_Kpi label="待审批 PR" value={String(q.data.pending_pr_count)} hint="auto-draft 含" />
            <_Kpi label="未结 PO" value={String(q.data.open_po_count)} hint={`+${q.data.in_transit_po_count} 在途`} />
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 4 }}>
            最近 24h ActionLog (共 {q.data.today_event_count} 条)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11 }}>
            {q.data.today_events.slice(0, 5).map((ev, i) => (
              <div key={i} style={{ display: "flex", gap: 8, padding: "3px 0", borderBottom: "1px dashed var(--ink-100)" }}>
                <span style={{
                  padding: "1px 6px", borderRadius: 3, fontSize: 10, fontWeight: 600,
                  background: ev.actor_kind === "system" ? "var(--warn-100)" : "var(--brand-100)",
                  color: ev.actor_kind === "system" ? "var(--warn-700)" : "var(--brand-700)",
                  whiteSpace: "nowrap",
                }}>
                  {ev.actor_kind === "system" ? "AI" : "人"} · {ev.actor.split(":").pop()?.slice(0, 12)}
                </span>
                <span style={{ color: "var(--ink-500)", whiteSpace: "nowrap" }}>{ev.occurred_at.slice(11, 19)}</span>
                <code style={{ fontSize: 10, color: "var(--ink-700)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ev.summary}</code>
              </div>
            ))}
          </div>
        </div>
      )}
    </OverlayChrome>
  );
}


function _Kpi({ label, value, hint, risk }: { label: string; value: string; hint?: string; risk?: boolean }) {
  return (
    <div style={{
      padding: 8, borderRadius: 6,
      background: risk ? "var(--risk-100)" : "var(--ink-50)",
      border: `1px solid ${risk ? "var(--risk-500)" : "var(--ink-200)"}`,
      textAlign: "center",
    }}>
      <div style={{ fontSize: 10, color: "var(--ink-500)", marginBottom: 2 }}>{label}</div>
      <div style={{
        fontSize: 14, fontWeight: 700, fontVariantNumeric: "tabular-nums",
        color: risk ? "var(--risk-700)" : "var(--ink-900)",
      }}>{value}</div>
      {hint && <div style={{ fontSize: 10, color: "var(--ink-400)", marginTop: 1 }}>{hint}</div>}
    </div>
  );
}


// ============================== 3. Purchase ============================

export function JintaiPurchaseBackendOverlay() {
  const { state } = useJintai();
  const en = state.mode === "backend";
  const qPr = useBackendQuery<PurchaseRequisitionOut[]>("prs", () => listRequisitions(), { enabled: en });
  const qPo = useBackendQuery<PurchaseOrderOut[]>("pos", () => listPurchaseOrders(), { enabled: en });
  const qPay = useBackendQuery<PayableOut[]>("payables", () => listPayables(), { enabled: en });
  if (state.mode !== "backend") return null;

  const refetchAll = () => { qPr.refetch(); qPo.refetch(); qPay.refetch(); };
  const loading = qPr.loading || qPo.loading || qPay.loading;
  const error = qPr.error || qPo.error || qPay.error;
  const loadedAt = Math.max(qPr.loadedAt || 0, qPo.loadedAt || 0, qPay.loadedAt || 0) || null;

  return (
    <OverlayChrome
      endpoint="/procurement/{requisitions,purchase-orders,payables}"
      loadedAt={loadedAt} loading={loading} error={error} refetch={refetchAll}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <_PurchaseGroup title="申购单 (PR)" loading={qPr.loading} data={qPr.data} render={(prs) => (
          prs.length === 0 ? <Empty msg="无 PR" /> :
          prs.slice(0, 5).map((p) => (
            <div key={p.id} style={{ padding: 4, fontSize: 11, borderBottom: "1px solid var(--ink-100)" }}>
              <div style={{ fontWeight: 600 }}>{p.pr_no} <_Badge text={p.status} /></div>
              <div style={{ color: "var(--ink-500)", fontSize: 10 }}>
                {p.source} {p.human_verified ? "· ✓ 人审" : "· ⏳ 待审"}
                {p.po_ref && <> · → {p.po_ref}</>}
              </div>
            </div>
          ))
        )} />
        <_PurchaseGroup title="采购订单 (PO)" loading={qPo.loading} data={qPo.data} render={(pos) => (
          pos.length === 0 ? <Empty msg="无 PO" /> :
          pos.slice(0, 5).map((p) => (
            <div key={p.id} style={{ padding: 4, fontSize: 11, borderBottom: "1px solid var(--ink-100)" }}>
              <div style={{ fontWeight: 600 }}>{p.po_no} <_Badge text={p.status} /></div>
              <div style={{ color: "var(--ink-500)", fontSize: 10 }}>
                {_fmtCny(p.total_amount)} · {p.items.length} item · {p.warehouse || "未入库"}
              </div>
            </div>
          ))
        )} />
        <_PurchaseGroup title="应付台账" loading={qPay.loading} data={qPay.data} render={(pays) => (
          pays.length === 0 ? <Empty msg="无应付" /> :
          pays.slice(0, 5).map((p) => (
            <div key={p.id} style={{ padding: 4, fontSize: 11, borderBottom: "1px solid var(--ink-100)" }}>
              <div style={{ fontWeight: 600 }}>{p.source_ref} <_Badge text={p.aging_bucket} /></div>
              <div style={{ color: "var(--ink-500)", fontSize: 10 }}>
                {_fmtCny(p.amount)} · 到期 {p.due_date} ({p.days_to_due} 天)
              </div>
            </div>
          ))
        )} />
      </div>
    </OverlayChrome>
  );
}


function _PurchaseGroup<T>({ title, loading, data, render }: {
  title: string; loading: boolean; data: T[] | null;
  render: (data: T[]) => React.ReactNode;
}) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-700)", marginBottom: 4 }}>
        {title} {data && `(${data.length})`}
      </div>
      {loading && !data ? <Empty msg="拉取中..." /> : data ? render(data) : <Empty msg="—" />}
    </div>
  );
}


function _Badge({ text }: { text: string }) {
  const colors: Record<string, [string, string]> = {
    pending_approval: ["var(--warn-100)", "var(--warn-700)"],
    closed_to_po: ["var(--ok-100)", "var(--ok-700)"],
    open: ["var(--brand-100)", "var(--brand-700)"],
    closed: ["var(--ok-100)", "var(--ok-700)"],
    overdue: ["var(--risk-100)", "var(--risk-700)"],
    due_soon: ["var(--warn-100)", "var(--warn-700)"],
    future: ["var(--ink-100)", "var(--ink-700)"],
  };
  const [bg, fg] = colors[text] || ["var(--ink-100)", "var(--ink-700)"];
  return (
    <span style={{ marginLeft: 4, padding: "0 5px", fontSize: 9.5, background: bg, color: fg, borderRadius: 3 }}>
      {text}
    </span>
  );
}


// ============================== 4. BOM =================================

export function JintaiProductionBomBackendOverlay() {
  const { state } = useJintai();
  const en = state.mode === "backend";
  const qList = useBackendQuery<BomListItem[]>("boms", () => listBoms("active"), { enabled: en });
  if (state.mode !== "backend") return null;
  return (
    <OverlayChrome
      endpoint="/procurement/boms?status=active"
      loadedAt={qList.loadedAt} loading={qList.loading} error={qList.error} refetch={qList.refetch}
    >
      {!qList.data && !qList.error && <Empty msg="拉取中..." />}
      {qList.data && qList.data.length === 0 && <Empty msg="后端无 BOM — POST /api/win/confirm/entities entity_type=BillOfMaterials 创建" />}
      {qList.data && qList.data.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: "var(--ink-700)", marginBottom: 8 }}>
            {qList.data.length} 个 active BOM · 选一个看 explode 实时缺料分析:
          </div>
          {qList.data.slice(0, 5).map((b) => (
            <_BomRow key={b.id} bom={b} />
          ))}
        </div>
      )}
    </OverlayChrome>
  );
}


function _BomRow({ bom }: { bom: BomListItem }) {
  const q = useBackendQuery(
    `bom-explode-${bom.id}`,
    () => explodeBom(bom.id, "10"),
  );
  return (
    <div style={{ padding: 8, marginBottom: 6, background: "white", border: "1px solid var(--ink-200)", borderRadius: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 12 }}>
          {bom.product_name} <code style={{ fontSize: 10, color: "var(--ink-500)" }}>{bom.product_code} · {bom.version}</code>
        </span>
        <span style={{ fontSize: 10, color: "var(--ink-500)" }}>批量 10 单位 explode</span>
      </div>
      {!q.data && !q.error && <Empty msg="..." />}
      {q.data && (
        <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
          <tbody>
            {q.data.lines.map((l) => (
              <tr key={l.material_id} style={{ borderBottom: "1px solid var(--ink-100)" }}>
                <td style={{ padding: 2 }}>{l.name}</td>
                <td style={{ padding: 2, textAlign: "right" }}>需 <b>{l.required_qty}</b> {l.unit}</td>
                <td style={{ padding: 2, textAlign: "right" }}>有 {l.current_balance} {l.unit}</td>
                <td style={{ padding: 2, textAlign: "right" }}>
                  {l.available ? <span style={{ color: "var(--ok-700)" }}>✓ 够</span>
                    : <span style={{ color: "var(--risk-700)" }}>⚠ 缺 {l.shortage}</span>}
                </td>
              </tr>
            ))}
            <tr style={{ background: q.data.fully_available ? "var(--ok-100)" : "var(--risk-100)" }}>
              <td colSpan={4} style={{ padding: 4, fontSize: 11, fontWeight: 600 }}>
                {q.data.fully_available ? "✓ 库存全够 — 可开批" : "⚠ 有缺料 — 主线已 auto-draft PR"}
              </td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
