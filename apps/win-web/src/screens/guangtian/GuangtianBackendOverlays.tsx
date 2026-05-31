/**
 * 光天 backend-mode-only "实时数据栏" overlay 组件.
 *
 * 设计同锦泰 (JintaiBackendOverlays):
 *  - 仅 backend 模式渲染;mock 模式 return null → demo 路径 0 影响
 *  - 顶部 banner "✨ backend live · GET /api/win/guangtian/... · 拉取于 HH:MM:SS"
 *  - loading / error / data 三态明示, 不替代下方 mock UI (做对照)
 *  - 用 useBackendQuery 拉数据, 30s stale-while-revalidate
 */

import type { ReactNode } from "react";
import {
  getBriefingKpi, listCustomerOrders, listMovements, listReplenishments,
  listSkus, listStockAlerts,
  type KpiOut, type OrderOut, type ReplenishmentOut, type SkuOut,
} from "../../api/guangtian-backend";
import { useBackendQuery } from "./state/useBackendQuery";

const STATUS_LABEL: Record<string, { t: string; c: string }> = {
  normal: { t: "正常", c: "var(--ok-600, #1a7f37)" },
  low: { t: "低库存", c: "var(--warn-600, #b45309)" },
  shortage_risk: { t: "缺货风险", c: "var(--guangtian-red, #D92020)" },
  out: { t: "已缺货", c: "var(--guangtian-red, #D92020)" },
  anomaly: { t: "数据异常", c: "var(--ink-500)" },
};

function _fmtTime(ms: number | null): string {
  if (!ms) return "—";
  const d = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function OverlayChrome({
  endpoint, loadedAt, loading, error, refetch, children,
}: {
  endpoint: string; loadedAt: number | null; loading: boolean;
  error: string | null; refetch: () => void; children: ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid var(--guangtian-blue, #1A3F8E)",
        borderRadius: 12,
        background: "linear-gradient(180deg, rgba(26,63,142,0.06), rgba(26,63,142,0.02))",
        padding: 14,
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--guangtian-blue, #1A3F8E)" }}>
          ✨ backend live
        </span>
        <code style={{ fontSize: 11, color: "var(--ink-600)" }}>GET {endpoint}</code>
        <span style={{ fontSize: 11, color: "var(--ink-400)" }}>· 拉取于 {_fmtTime(loadedAt)}</span>
        <button
          onClick={refetch}
          style={{
            marginLeft: "auto", fontSize: 11, padding: "3px 10px", borderRadius: 7,
            border: "1px solid var(--ink-200)", background: "var(--surface-1)",
            color: "var(--ink-700)", cursor: "pointer", fontFamily: "var(--font)",
          }}
        >
          {loading ? "刷新中…" : "刷新"}
        </button>
      </div>
      {error ? (
        <div style={{ fontSize: 12, color: "var(--guangtian-red, #D92020)" }}>
          ⚠ 后端未连通: {error}（确认 dev_guangtian_backend 在 :8000 运行）
        </div>
      ) : (
        children
      )}
    </div>
  );
}

const td: React.CSSProperties = { padding: "5px 10px", fontSize: 12, borderBottom: "1px solid var(--ink-100)" };
const th: React.CSSProperties = { ...td, fontWeight: 700, color: "var(--ink-600)", textAlign: "left" };

// ============================== KPI (工作台) ============================

export function GuangtianKpiOverlay({ enabled }: { enabled: boolean }) {
  const q = useBackendQuery<KpiOut>("gt-kpi", getBriefingKpi, { enabled });
  if (!enabled) return null;
  const k = q.data;
  const cells: [string, number | string][] = k
    ? [["SKU 总数", k.sku_total], ["低库存", k.low_stock_count], ["已缺货", k.out_of_stock_count],
       ["缺货订单", k.shortage_order_count], ["今日入库", k.today_inbound],
       ["今日出库", k.today_outbound], ["未解除预警", k.open_alerts]]
    : [];
  return (
    <OverlayChrome endpoint="/guangtian/briefing/kpi" {...q}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {cells.map(([label, val]) => (
          <div key={label} style={{ minWidth: 84, padding: "8px 12px", borderRadius: 9, background: "var(--surface-1)", border: "1px solid var(--ink-100)" }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: "var(--guangtian-blue, #1A3F8E)" }}>{val}</div>
            <div style={{ fontSize: 11, color: "var(--ink-500)" }}>{label}</div>
          </div>
        ))}
        {!k && !q.error && <span style={{ fontSize: 12, color: "var(--ink-400)" }}>加载中…</span>}
      </div>
    </OverlayChrome>
  );
}

// ============================== SKU 台账 ================================

export function GuangtianSkuOverlay({ enabled }: { enabled: boolean }) {
  const q = useBackendQuery<SkuOut[]>("gt-skus", listSkus, { enabled });
  if (!enabled) return null;
  const rows = q.data ?? [];
  return (
    <OverlayChrome endpoint="/guangtian/skus" {...q}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 640 }}>
          <thead><tr>
            {["SKU 编码", "名称", "库位", "现库存", "安全线", "状态"].map((h) => <th key={h} style={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((s) => {
              const st = STATUS_LABEL[s.status] ?? { t: s.status, c: "var(--ink-500)" };
              return (
                <tr key={s.id}>
                  <td style={{ ...td, fontFamily: "monospace" }}>{s.code}</td>
                  <td style={td}>{s.name}</td>
                  <td style={td}>{s.location ?? "—"}</td>
                  <td style={{ ...td, fontWeight: 700 }}>{Number(s.last_balance)}</td>
                  <td style={td}>{Number(s.safety_stock)}</td>
                  <td style={{ ...td, color: st.c, fontWeight: 700 }}>{st.t}</td>
                </tr>
              );
            })}
            {!rows.length && !q.error && <tr><td style={td} colSpan={6}>加载中…</td></tr>}
          </tbody>
        </table>
      </div>
    </OverlayChrome>
  );
}

// ============================== 缺货预警 (订单 + alert) =================

export function GuangtianShortageOverlay({ enabled }: { enabled: boolean }) {
  const q = useBackendQuery<OrderOut[]>("gt-orders", listCustomerOrders, { enabled });
  const alertsQ = useBackendQuery("gt-alerts", () => listStockAlerts(true), { enabled });
  if (!enabled) return null;
  const orders = q.data ?? [];
  const alerts = (alertsQ.data ?? []) as { id: string }[];
  return (
    <OverlayChrome endpoint="/guangtian/customer-orders" {...q}>
      <div style={{ fontSize: 12, color: "var(--ink-600)", marginBottom: 8 }}>
        未解除缺货预警 <b style={{ color: "var(--guangtian-red, #D92020)" }}>{alerts.length}</b> 条 · 客户订单 {orders.length} 张
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 560 }}>
          <thead><tr>{["订单号", "客户", "等级", "可发率", "缺口 SKU"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {orders.map((o) => {
              const gaps = o.items.filter((it) => Number(it.gap) > 0);
              return (
                <tr key={o.id}>
                  <td style={{ ...td, fontFamily: "monospace" }}>{o.order_no}</td>
                  <td style={td}>{o.customer}</td>
                  <td style={td}>{o.level}</td>
                  <td style={{ ...td, fontWeight: 700, color: o.fulfillment_pct >= 100 ? "var(--ok-600, #1a7f37)" : "var(--guangtian-red, #D92020)" }}>{o.fulfillment_pct}%</td>
                  <td style={td}>{gaps.map((g) => `${g.sku_code}(缺${Number(g.gap)})`).join("、") || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </OverlayChrome>
  );
}

// ============================== AI 补产建议 =============================

export function GuangtianReplenishOverlay({ enabled }: { enabled: boolean }) {
  const q = useBackendQuery<ReplenishmentOut[]>("gt-reps", listReplenishments, { enabled });
  if (!enabled) return null;
  const reps = q.data ?? [];
  return (
    <OverlayChrome endpoint="/guangtian/replenishments" {...q}>
      <div style={{ fontSize: 12, color: "var(--ink-600)", marginBottom: 8 }}>
        AI 补产建议 {reps.length} 条（source=ai_autodraft，待人工采纳）。生成: <code>POST /guangtian/replenishments/generate</code>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 560 }}>
          <thead><tr>{["现库存", "安全线", "建议补产", "优先级", "状态", "理由"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {reps.map((r) => (
              <tr key={r.id}>
                <td style={td}>{Number(r.current_stock)}</td>
                <td style={td}>{Number(r.safety_stock)}</td>
                <td style={{ ...td, fontWeight: 700, color: "var(--ai-purple, #6D28D9)" }}>{Number(r.suggest_qty)}</td>
                <td style={td}>{r.priority}</td>
                <td style={td}>{r.status}{r.work_order_no ? ` · ${r.work_order_no}` : ""}</td>
                <td style={td}>{r.reason}</td>
              </tr>
            ))}
            {!reps.length && !q.error && <tr><td style={td} colSpan={6}>暂无 — 点工作台/缺货页可触发生成</td></tr>}
          </tbody>
        </table>
      </div>
    </OverlayChrome>
  );
}

// ============================== 库存流水 ================================

export function GuangtianLedgerOverlay({ enabled }: { enabled: boolean }) {
  const q = useBackendQuery("gt-mov", () => listMovements(), { enabled });
  if (!enabled) return null;
  const movs = (q.data ?? []) as Awaited<ReturnType<typeof listMovements>>;
  return (
    <OverlayChrome endpoint="/guangtian/stock-movements" {...q}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 600 }}>
          <thead><tr>{["时间", "类型", "数量", "余额", "单号", "操作人", "置信度"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {movs.slice(0, 30).map((m) => (
              <tr key={m.id}>
                <td style={td}>{m.occurred_at.slice(0, 16).replace("T", " ")}</td>
                <td style={td}>{m.op}</td>
                <td style={{ ...td, fontWeight: 700, color: Number(m.quantity) >= 0 ? "var(--ok-600, #1a7f37)" : "var(--guangtian-red, #D92020)" }}>{Number(m.quantity)}</td>
                <td style={td}>{Number(m.balance_after)}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{m.reference_no ?? "—"}</td>
                <td style={td}>{m.operator ?? "—"}</td>
                <td style={td}>{m.confidence ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </OverlayChrome>
  );
}
