import { useState } from "react";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { financeReports } from "./data";
import type { FinanceReport, FinanceRow } from "./data";
import { JintaiSourceCitation } from "./components";

type ReportId = FinanceReport["id"];

/**
 * iter 17: 把财务报表 mock 的"千元"基数 ×1000 展开为完整元数。
 * mock data 仍以千元字串存（"8,200" / "+870" / "−3,800"），display 层 append ",000"。
 * 0 / — 不变。
 */
function expandYuan(v: string): string {
  if (v === "—" || v === "0") return v;
  return v + ",000";
}

export function JintaiFinancePanel() {
  const [active, setActive] = useState<ReportId>("balance");
  const report = financeReports.find((r) => r.id === active) ?? financeReports[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 子 tab 切换 — 三张表 */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: 4,
          borderRadius: 12,
          background: "var(--surface-2)",
          border: "1px solid var(--ink-100)",
          width: "fit-content",
        }}
      >
        {financeReports.map((r) => {
          const isActive = r.id === active;
          return (
            <button
              key={r.id}
              onClick={() => setActive(r.id)}
              style={{
                padding: "8px 14px",
                borderRadius: 8,
                border: "none",
                background: isActive ? "var(--surface)" : "transparent",
                boxShadow: isActive ? "var(--shadow-card-soft)" : "none",
                color: isActive ? "var(--ink-900)" : "var(--ink-600)",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                lineHeight: 1.2,
                gap: 2,
                fontFamily: "var(--font)",
              }}
            >
              <span>{r.label}</span>
              <span style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 500 }}>
                {r.sub}
              </span>
            </button>
          );
        })}
      </div>

      <FinanceReportView report={report} />

      {/* 自洽提示：三张表互相对账 */}
      <CrossCheckHint />
    </div>
  );
}

function FinanceReportView({ report }: { report: FinanceReport }) {
  const isDesktop = useIsDesktop();
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: isDesktop ? "1fr 280px" : "1fr",
        gap: 16,
      }}
    >
      <div className="card" style={{ padding: 20 }}>
        {/* AI 草稿提示条 — 财务模块的核心信任锚点 */}
        <AIDraftBanner draft={report.aiDraft} confirmedBy={report.confirmedBy} />

        <div style={{ marginTop: 14, marginBottom: 14 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
            {report.label}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3 }}>
            报表期间：{report.period} · 单位：元 (¥)
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {report.sections.map((sec) => (
            <FinanceSection key={sec.title} title={sec.title} rows={sec.rows} subtotal={sec.subtotal} />
          ))}
        </div>

        {/* 底线：资产合计 / 净利润 / 期末余额 */}
        <div
          style={{
            marginTop: 16,
            padding: "14px 16px",
            borderRadius: 10,
            background: "var(--brand-100)",
            border: "1px solid #bddff3",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--brand-700)" }}>
            {report.bottomLine.key}
          </span>
          <span
            style={{
              fontSize: 18,
              fontWeight: 800,
              color: "var(--brand-700)",
              fontFamily: "ui-monospace, monospace",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {report.bottomLine.value === "—" ? "—" : `${expandYuan(report.bottomLine.value)} 元`}
          </span>
        </div>

        {/* 来源 chips — 按报表类型换 */}
        <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
          <ReportSources reportId={report.id} />
        </div>
      </div>

      {/* 右侧 AI 财务洞察 */}
      <AIInsightCard reportId={report.id} />
    </div>
  );
}

const REPORT_SOURCES: Record<ReportId, { kind: "合同" | "Excel" | "入库单" | "工艺单"; label: string }[]> = {
  balance: [
    { kind: "Excel", label: "Kingdee 月末科目余额表.xlsx" },
    { kind: "入库单", label: "本月 5 张采购入库 · 已记账" },
    { kind: "Excel", label: "招行 + 工行月末对账单" },
  ],
  income: [
    { kind: "合同", label: "本月 3 张销售合同（容百 / 横店 / 风华）" },
    { kind: "入库单", label: "5 张采购入库 · 计入成本" },
    { kind: "Excel", label: "本月期间费用凭证 12 张" },
  ],
  cashflow: [
    { kind: "Excel", label: "招行 / 工行月度流水 · 已对账" },
    { kind: "入库单", label: "采购付款凭证 5 张" },
    { kind: "合同", label: "客户回款明细（容百首付 + 横店尾款）" },
  ],
};

function ReportSources({ reportId }: { reportId: ReportId }) {
  return (
    <>
      {REPORT_SOURCES[reportId].map((s, i) => (
        <JintaiSourceCitation key={i} source={s} />
      ))}
    </>
  );
}

function AIDraftBanner({ draft, confirmedBy }: { draft: string; confirmedBy: string }) {
  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: 10,
        background: "var(--ai-100)",
        border: "1px solid #bddff3",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ai-700)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {I.spark(12)} AI 草稿
      </div>
      <div style={{ fontSize: 12.5, color: "var(--ink-800)", lineHeight: 1.55 }}>{draft}</div>
      <div
        style={{
          fontSize: 11,
          color: "var(--ok-700)",
          fontWeight: 600,
          paddingTop: 4,
          borderTop: "1px dashed #bddff3",
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        {/* iter 14：锦泰绿确认 dot — 强化"自己人复核"信号 */}
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: 4,
            background: "var(--jintai-green)",
            flexShrink: 0,
          }}
        />
        ✓ {confirmedBy}
      </div>
    </div>
  );
}

function FinanceSection({
  title,
  rows,
  subtotal,
}: {
  title: string;
  rows: FinanceRow[];
  subtotal?: FinanceRow;
}) {
  return (
    <div
      style={{
        padding: 14,
        borderRadius: 10,
        background: "var(--surface-2)",
        border: "1px solid var(--ink-100)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ink-700)",
          letterSpacing: "0.04em",
          marginBottom: 8,
          textTransform: "uppercase",
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {rows.map((r) => (
          <FinanceRowItem key={r.key} row={r} />
        ))}
        {subtotal && (
          <>
            <div style={{ height: 1, background: "var(--ink-100)", margin: "6px 0 4px" }} />
            <FinanceRowItem row={subtotal} />
          </>
        )}
      </div>
    </div>
  );
}

function FinanceRowItem({ row }: { row: FinanceRow }) {
  const indent = (row.indent ?? 0) * 12;
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        fontSize: row.bold ? 13 : 12,
        padding: "4px 0",
        paddingLeft: indent,
      }}
    >
      <span
        style={{
          color: row.bold ? "var(--ink-900)" : "var(--ink-700)",
          fontWeight: row.bold ? 700 : 500,
        }}
      >
        {row.key}
      </span>
      <span
        style={{
          color: row.value.startsWith("−") ? "var(--risk-700)" : "var(--ink-900)",
          fontWeight: row.bold ? 700 : 600,
          fontFamily: "ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {row.value === "—" ? "—" : expandYuan(row.value)}
      </span>
    </div>
  );
}

/* ---------------- 右侧 AI 洞察 ---------------- */

const AI_INSIGHTS: Record<ReportId, { headline: string; body: string; suggestion: string }> = {
  balance: {
    headline: "资产结构健康，应收占比偏高",
    body:
      "总资产 4,700 万元，流动资产 62%、固定资产 38%。应收账款 1,250 万元 占流动资产 43%，主要集中在容百锂电（520 万元）和横店东磁（310 万元），账期未到 ≤ 60 天的占 78%。",
    suggestion: "AI 建议：本月底前与容百对接确认 2 张到期发票回款节奏，避免应收账款挤压本季现金。",
  },
  income: {
    headline: "本月利润 1,189,000 元，毛利率 35.0%",
    body:
      "营业收入 6,800,000 元，环比上月 +8.6%；锂电承烧板 (容百) 占收入 47%，是利润主引擎。期间费用 795,000 元 控制平稳，研发费用 120,000 元 持续投入工业陶瓷新品。",
    suggestion: "AI 建议：横店东磁匣钵单价下行压力 −2.1%，本月毛利率被拉低 0.4 个点，可在 Q3 谈判时提示成本压力。",
  },
  cashflow: {
    headline: "经营现金流 +870,000 元，期末余额回升至 8,200,000",
    body:
      "经营活动净流入 870,000 元，主要来自容百 + 厦钨集中回款；投资支出 200,000 元 为等静压辅机升级。本月偿还短期借款 500,000 元，符合年度去杠杆计划。",
    suggestion: "AI 建议：下月初有 3 张原料采购付款（合计 ¥327,000）到期，建议预留 ¥400,000 经营备用金。",
  },
};

function AIInsightCard({ reportId }: { reportId: ReportId }) {
  const ins = AI_INSIGHTS[reportId];
  return (
    <div
      className="ai-surface"
      style={{
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ai-700)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {I.spark(12)} AI 财务洞察
      </div>
      <div style={{ fontSize: 13.5, color: "var(--ink-900)", lineHeight: 1.55, fontWeight: 600 }}>
        {ins.headline}
      </div>
      <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>{ins.body}</div>
      <div
        style={{
          marginTop: 4,
          padding: "10px 12px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.7)",
          border: "1px solid #bddff3",
          fontSize: 11.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
        }}
      >
        {ins.suggestion}
      </div>
    </div>
  );
}

function CrossCheckHint() {
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 10,
        background: "var(--surface-2)",
        border: "1px dashed var(--ink-200)",
        fontSize: 11.5,
        color: "var(--ink-600)",
        lineHeight: 1.6,
      }}
    >
      <span style={{ fontWeight: 700, color: "var(--ok-700)", marginRight: 6 }}>✓ 三表自洽：</span>
      资产负债表 货币资金 <strong>8,200,000 元</strong> = 现金流量表 期末余额 <strong>8,200,000 元</strong> ·
      损益表 净利润 <strong>+1,189,000 元</strong> 已结转至 资产负债表 留存收益 ·
      所有数字均由 AI 自三方账套数据 (Kingdee / 支付宝 / 银行流水) 自动归集，不修改任何原始凭证。
    </div>
  );
}
