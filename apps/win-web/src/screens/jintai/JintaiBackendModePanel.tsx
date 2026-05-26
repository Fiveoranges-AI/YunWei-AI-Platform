/**
 * Round 4: backend-mode 指示 + toggle + 真实 KPI 快照.
 *
 * 设计原则:
 *  - 默认 mock,小且不显眼 (右上角 chip).
 *  - 点 chip 展开"Backend Reality Check"面板:
 *     · 后端 health
 *     · 已落库的 supplier/material/voucher/pr/po IDs (证明真写了)
 *     · /briefing/kpi 实时数字 (跟前端 demo 数字对比)
 *     · 上次错误 (如果有)
 *     · 刷新按钮
 *     · 切回 mock 按钮
 *  - 与 demo 主面不冲突,reviewer/老板可以一眼看到数据真实性.
 */

import { useState } from "react";
import { useJintai } from "./state/store";

function _readInspectDefault(): boolean {
  if (typeof window === "undefined") return false;
  const qp = new URLSearchParams(window.location.search);
  return qp.get("inspect") === "1" || qp.get("inspectPanel") === "1";
}

export function JintaiBackendModePanel() {
  const { state, setMode, refreshBackendKpi } = useJintai();
  const [expanded, setExpanded] = useState(_readInspectDefault);
  const mode = state.mode;
  const ids = state.backendIds;
  const kpi = state.backendKpi;
  const status = state.backendStatus;

  const chipBg = mode === "backend" ? "var(--ok-100)" : "var(--ink-100)";
  const chipFg = mode === "backend" ? "var(--ok-700)" : "var(--ink-700)";
  const chipBorder = mode === "backend" ? "var(--ok-500)" : "var(--ink-300)";
  const chipLabel = mode === "backend" ? "后端模式" : "MOCK 模式";

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        title={`Round 4: ${chipLabel}. 点开看后端真实数据 / 切换模式.`}
        style={{
          position: "fixed",
          top: 14,
          right: 16,
          zIndex: 9998,
          padding: "5px 10px",
          fontSize: 11,
          fontWeight: 700,
          color: chipFg,
          background: chipBg,
          border: `1px solid ${chipBorder}`,
          borderRadius: 14,
          cursor: "pointer",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
          fontFamily: "inherit",
        }}
      >
        {mode === "backend" ? "● " : "○ "}{chipLabel}
        {mode === "backend" && status.lastError && " ⚠"}
      </button>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        top: 14,
        right: 16,
        zIndex: 9998,
        width: 360,
        maxHeight: "calc(100vh - 28px)",
        overflow: "auto",
        padding: 14,
        background: "white",
        border: `1px solid ${chipBorder}`,
        borderTop: `3px solid ${chipFg}`,
        borderRadius: 8,
        boxShadow: "0 6px 20px rgba(0,0,0,0.12)",
        fontSize: 12,
        color: "var(--ink-700)",
        fontFamily: "inherit",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ fontWeight: 700, color: chipFg, fontSize: 13 }}>
          Round 4 · Backend Reality Check
        </div>
        <button
          onClick={() => setExpanded(false)}
          style={{
            border: "none", background: "none", color: "var(--ink-500)",
            cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1,
          }}
          aria-label="收起"
        >
          ×
        </button>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        <ModeButton current={mode} target="mock" onClick={() => setMode("mock")} />
        <ModeButton current={mode} target="backend" onClick={() => setMode("backend")} />
      </div>

      {mode === "mock" ? (
        <div style={{ padding: 10, background: "var(--ink-100)", borderRadius: 6, lineHeight: 1.5 }}>
          当前 <b>MOCK 模式</b>:demo 数据全部前端内存,刷新页面会复位。
          <br />
          <span style={{ color: "var(--ink-500)" }}>
            切到"后端模式"可证明数据真的落 SQLite,刷新页面持久。
          </span>
        </div>
      ) : (
        <>
          <Row label="后端 health">
            {status.health ? (
              <span style={{ color: "var(--ok-700)" }}>
                ● {status.health.status} (tenant={status.health.enterprise_id})
              </span>
            ) : status.seeding ? (
              <span style={{ color: "var(--warn-700)" }}>seeding...</span>
            ) : (
              <span style={{ color: "var(--risk-700)" }}>● 未连接</span>
            )}
          </Row>

          <Row label="已落库 IDs">
            <IdLine label="supplier" value={ids.supplierId} />
            <IdLine label="material" value={ids.materialId} />
            <IdLine label="voucher" value={ids.voucherId} />
            <IdLine label="PR" value={ids.prId} />
            <IdLine label="PO" value={ids.poId} />
          </Row>

          <Row label="GET /briefing/kpi (后端真实数字)">
            {kpi ? (
              <div style={{ lineHeight: 1.55 }}>
                <KpiCell label="应付总额" value={`¥${kpi.payable_total}`} />
                <KpiCell label="应付笔数" value={String(kpi.payable_count)} />
                <KpiCell label="低库存 SKU" value={String(kpi.low_stock_count)} />
                <KpiCell label="待审批 PR" value={String(kpi.pending_pr_count)} />
                <KpiCell label="未结 PO" value={String(kpi.open_po_count)} />
                <KpiCell label="今日事件" value={String(kpi.today_event_count)} />
              </div>
            ) : (
              <span style={{ color: "var(--ink-500)" }}>(未拉取 - 点 ↻ 刷新)</span>
            )}
          </Row>

          {status.lastError && (
            <Row label="⚠ 上次错误">
              <code style={{ fontSize: 10.5, color: "var(--risk-700)", wordBreak: "break-all" }}>
                {status.lastError}
              </code>
            </Row>
          )}

          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <button
              onClick={() => { void refreshBackendKpi(); }}
              style={{
                flex: 1, padding: "5px 10px", fontSize: 11, cursor: "pointer",
                background: "var(--brand-100)", color: "var(--brand-700)",
                border: "1px solid var(--brand-300)", borderRadius: 4,
              }}
            >
              ↻ refresh KPI
            </button>
          </div>

          <div style={{ marginTop: 10, padding: 8, background: "var(--ink-100)", borderRadius: 4, fontSize: 10.5, lineHeight: 1.55 }}>
            <b>验证持久化</b>:刷新页面 (F5) 后此面板的 KPI 数字 应保持不变 (因为数据在后端 SQLite,不是前端内存)。<br />
            <b>验证 DB</b>: <code>sqlite3 services/platform-api/yinhu_tenant_jintai_demo.db</code><br />
            <b>启动后端</b>: <code>bash scripts/jintai/dev-backend.sh</code>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ink-500)", marginBottom: 4, letterSpacing: 0.3 }}>
        {label.toUpperCase()}
      </div>
      <div>{children}</div>
    </div>
  );
}

function IdLine({ label, value }: { label: string; value?: string }) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 2 }}>
      <span style={{ minWidth: 60, fontSize: 10.5, color: "var(--ink-500)" }}>{label}</span>
      {value ? (
        <code style={{ fontSize: 10.5, color: "var(--ok-700)" }}>{value.slice(0, 8)}…</code>
      ) : (
        <span style={{ fontSize: 10.5, color: "var(--ink-400)" }}>—</span>
      )}
    </div>
  );
}

function KpiCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--ink-500)" }}>{label}</span>
      <code style={{ color: "var(--ink-900)", fontWeight: 600 }}>{value}</code>
    </div>
  );
}

function ModeButton({
  current, target, onClick,
}: {
  current: string; target: "mock" | "backend"; onClick: () => void;
}) {
  const active = current === target;
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1, padding: "6px 10px", fontSize: 11.5, fontWeight: active ? 700 : 500,
        background: active ? "var(--ok-100)" : "var(--ink-50)",
        color: active ? "var(--ok-700)" : "var(--ink-700)",
        border: `1px solid ${active ? "var(--ok-500)" : "var(--ink-200)"}`,
        borderRadius: 4, cursor: "pointer",
      }}
    >
      {target === "mock" ? "MOCK" : "BACKEND"}
    </button>
  );
}
