import { useState } from "react";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { costBreakdown, depreciationLedger, financeReports } from "./data";
import type {
  BalanceSheet,
  CashFlowStatement,
  FinanceReport,
  IncomeStatement,
  ReportLine,
} from "./data";
import { JintaiSourceCitation } from "./components";
import { JintaiFinanceBackendOverlay } from "./JintaiBackendOverlays";

type ReportId = FinanceReport["id"];
type FinanceTabKey = ReportId | "cost" | "depreciation";

const COMPANY_NAME = "宜兴市锦泰耐火材料有限公司";

const TAB_LABELS: Record<FinanceTabKey, { label: string; sub: string }> = {
  balance: { label: "资产负债表", sub: "会企01表 · 2026-05-31" },
  income: { label: "利润及利润分配表", sub: "会企02表 · 2026-05" },
  cashflow: { label: "现金流量表", sub: "会企03表 · 2026-05" },
  cost: { label: "成本拆分", sub: "材料 / 人工 / 水电气 / 折旧" },
  depreciation: { label: "折旧台账", sub: "5 项固定资产 · 月折计提" },
};

const TAB_ORDER: FinanceTabKey[] = ["balance", "income", "cashflow", "cost", "depreciation"];

export function JintaiFinancePanel() {
  const [active, setActive] = useState<FinanceTabKey>("balance");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Round 6: backend mode overlay — 实时拉对应 /finance/* endpoint */}
      <JintaiFinanceBackendOverlay activeTab={active} />

      {/* iter 19.1：AI-native 模式定位条 — "脱离金蝶也能跑" */}
      <AINativeBanner />

      {/* 子 tab — 三表 + 成本拆分 + 折旧台账 (iter 20 补附件需求 6) */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: 4,
          borderRadius: 12,
          background: "var(--surface-2)",
          border: "1px solid var(--ink-100)",
          width: "fit-content",
          flexWrap: "wrap",
        }}
      >
        {TAB_ORDER.map((k) => {
          const meta = TAB_LABELS[k];
          const isActive = k === active;
          return (
            <button
              key={k}
              onClick={() => setActive(k)}
              aria-current={isActive ? "true" : undefined}
              style={{
                padding: "8px 14px",
                borderRadius: 8,
                border: "none",
                background: isActive ? "var(--surface)" : "transparent",
                // iter: active 子 tab 与近白容器底色几乎无差 → 加 jintai-green inset
                // 环 + 较实阴影，选中态一眼可见（无 1px border 的布局位移）。
                boxShadow: isActive
                  ? "0 1px 3px rgba(11,34,50,0.12), inset 0 0 0 1.5px var(--jintai-green)"
                  : "none",
                color: isActive ? "var(--jintai-green-dark)" : "var(--ink-600)",
                fontSize: 13,
                fontWeight: isActive ? 700 : 600,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                lineHeight: 1.2,
                gap: 2,
                fontFamily: "var(--font)",
              }}
            >
              <span>{meta.label}</span>
              <span style={{ fontSize: 10.5, color: isActive ? "var(--ink-600)" : "var(--ink-500)", fontWeight: 500 }}>
                {meta.sub}
              </span>
            </button>
          );
        })}
      </div>

      {active === "cost" ? (
        <CostBreakdownView />
      ) : active === "depreciation" ? (
        <DepreciationLedgerView />
      ) : (
        <FinanceReportView
          report={financeReports.find((r) => r.id === active) ?? financeReports[0]}
        />
      )}

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
        <AIDraftBanner draft={report.aiDraft} confirmedBy={report.confirmedBy} />

        {/* 表头：标题 / 编号 / 编制单位 / 期间 / 单位 — 对齐 xls 模版 */}
        <ReportHeader report={report} />

        {/* 表体：按报表类型分别渲染 */}
        {report.id === "balance" && <BalanceSheetTable report={report} />}
        {report.id === "income" && <IncomeStatementTable report={report} />}
        {report.id === "cashflow" && <CashFlowTable report={report} />}

        {/* 表尾签字栏 — 对齐 xls 模版 */}
        <SignatureRow />

        <div style={{ display: "flex", gap: 6, marginTop: 14, flexWrap: "wrap" }}>
          <ReportSources reportId={report.id} />
        </div>
      </div>

      <AIInsightCard reportId={report.id} />
    </div>
  );
}

function ReportHeader({ report }: { report: FinanceReport }) {
  return (
    <div style={{ marginTop: 14, marginBottom: 14, textAlign: "center" }}>
      <div
        style={{
          fontSize: 17,
          fontWeight: 800,
          color: "var(--ink-900)",
          letterSpacing: "0.12em",
        }}
      >
        {report.label}
      </div>
      <div
        style={{
          fontSize: 10.5,
          color: "var(--ink-500)",
          marginTop: 4,
          fontWeight: 600,
          letterSpacing: "0.05em",
        }}
      >
        {report.sub}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginTop: 10,
          fontSize: 11.5,
          color: "var(--ink-700)",
          borderBottom: "1px solid var(--ink-200)",
          paddingBottom: 6,
        }}
      >
        <span>
          <strong style={{ color: "var(--ink-800)" }}>编制单位：</strong>
          {COMPANY_NAME}　　{report.period}
        </span>
        <span style={{ color: "var(--ink-500)" }}>{report.unit}</span>
      </div>
    </div>
  );
}

/* ============== 资产负债表 — 左右两栏 ============== */

function BalanceSheetTable({ report }: { report: BalanceSheet }) {
  const isDesktop = useIsDesktop();
  if (!isDesktop) {
    // 移动端：堆叠（资产在上，负债+权益在下）
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <BSHalf title="资 产" lines={report.assets} />
        <BSHalf title="负债及所有者权益" lines={report.liabEquity} />
        <BSGrandTotal totalAssets={report.totalAssets} totalLiabEquity={report.totalLiabEquity} />
      </div>
    );
  }
  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          border: "1px solid var(--ink-200)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <BSHalf title="资 产" lines={report.assets} bordered />
        <BSHalf title="负债及所有者权益" lines={report.liabEquity} />
      </div>
      <BSGrandTotal totalAssets={report.totalAssets} totalLiabEquity={report.totalLiabEquity} />
    </div>
  );
}

function BSHalf({
  title,
  lines,
  bordered,
}: {
  title: string;
  lines: ReportLine[];
  bordered?: boolean;
}) {
  return (
    <div
      style={{
        borderRight: bordered ? "1px solid var(--ink-200)" : undefined,
      }}
    >
      <BSTableHead title={title} />
      <div>
        {lines.map((l, idx) => (
          <BSRow key={`${l.name}-${idx}`} line={l} />
        ))}
      </div>
    </div>
  );
}

function BSTableHead({ title }: { title: string }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 110px 110px",
        background: "var(--surface-3)",
        borderBottom: "1.5px solid var(--ink-300)",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--ink-800)",
        letterSpacing: "0.04em",
      }}
    >
      <div style={{ padding: "8px 10px" }}>{title}</div>
      <div style={{ padding: "8px 6px", textAlign: "center" }}>行次</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>年初数</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>期末数</div>
    </div>
  );
}

function BSRow({ line }: { line: ReportLine }) {
  const isSection = !line.lineNo && line.bold;
  const indent = (line.indent ?? 0) * 10;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 110px 110px",
        borderTop: line.underline ? "1px solid var(--ink-200)" : "1px solid var(--ink-100)",
        background: isSection ? "rgba(15,69,42,0.04)" : line.bold ? "rgba(199,228,210,0.18)" : "transparent",
        fontSize: 11.5,
      }}
    >
      <div
        style={{
          padding: "5px 10px",
          paddingLeft: 10 + indent,
          color: isSection ? "var(--jintai-green-dark)" : line.bold ? "var(--ink-900)" : "var(--ink-800)",
          fontWeight: line.bold ? 700 : 500,
        }}
      >
        {line.name}
      </div>
      <div
        style={{
          padding: "5px 6px",
          textAlign: "center",
          color: "var(--ink-500)",
          fontFamily: "ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {line.lineNo ?? ""}
      </div>
      <NumCell value={line.col1} bold={line.bold} />
      <NumCell value={line.col2} bold={line.bold} />
    </div>
  );
}

function BSGrandTotal({
  totalAssets,
  totalLiabEquity,
}: {
  totalAssets: ReportLine;
  totalLiabEquity: ReportLine;
}) {
  const isDesktop = useIsDesktop();
  return (
    <div
      style={{
        marginTop: 14,
        padding: "14px 18px",
        borderRadius: 10,
        background: "var(--brand-100)",
        border: "1px solid #bddff3",
        display: "grid",
        gridTemplateColumns: isDesktop ? "1fr 1fr" : "1fr",
        gap: isDesktop ? 16 : 8,
      }}
    >
      <TotalSide line={totalAssets} />
      <TotalSide line={totalLiabEquity} />
    </div>
  );
}

function TotalSide({ line }: { line: ReportLine }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--brand-700)" }}>
        {line.name}　<span style={{ color: "var(--ink-500)", fontSize: 10.5, fontWeight: 500 }}>行次 {line.lineNo}</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <Mono small label="年初数" value={line.col1} />
        <Mono label="期末数" value={line.col2} highlight />
      </div>
    </div>
  );
}

function Mono({
  value,
  label,
  small,
  highlight,
}: {
  value: string;
  label?: string;
  small?: boolean;
  highlight?: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
      {label && (
        <span style={{ fontSize: 10, color: "var(--ink-500)", fontWeight: 500 }}>{label}</span>
      )}
      <span
        style={{
          fontSize: small ? 13 : 16,
          fontWeight: 800,
          color: highlight ? "var(--brand-700)" : "var(--ink-800)",
          fontFamily: "ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value === "—" ? "—" : value}
      </span>
    </div>
  );
}

/* ============== 利润及利润分配表 — 单栏 + 利润分配段 ============== */

function IncomeStatementTable({ report }: { report: IncomeStatement }) {
  return (
    <div>
      <div
        style={{
          border: "1px solid var(--ink-200)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      >
        <ISHead />
        {/* 利润形成段 */}
        {report.formation.map((l, idx) => (
          <ISRow key={`f-${idx}`} line={l} />
        ))}
        {/* 利润分配段：上方加分隔条 */}
        <div
          style={{
            padding: "8px 12px",
            background: "rgba(15,69,42,0.06)",
            fontSize: 11,
            fontWeight: 700,
            color: "var(--jintai-green-dark)",
            letterSpacing: "0.05em",
            borderTop: "2px solid var(--jintai-green)",
          }}
        >
          利 润 分 配
        </div>
        {report.distribution.map((l, idx) => (
          <ISRow key={`d-${idx}`} line={l} />
        ))}
        {/* 末未分配利润 (高亮) */}
        <ISRow line={report.endingRetained} highlight />
      </div>

      {/* 期末未分配利润 高亮卡 (= 资产负债表期末未分配利润) */}
      <div
        style={{
          marginTop: 14,
          padding: "14px 18px",
          borderRadius: 10,
          background: "var(--brand-100)",
          border: "1px solid #bddff3",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--brand-700)" }}>
          本月净利润　<span style={{ color: "var(--ink-500)", fontSize: 10.5, fontWeight: 500 }}>行次 17</span>
        </div>
        <span
          style={{
            fontSize: 18,
            fontWeight: 800,
            color: "var(--brand-700)",
            fontFamily: "ui-monospace, monospace",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {report.formation.find((l) => l.lineNo === 17)?.col2 ?? "—"}
        </span>
      </div>
    </div>
  );
}

function ISHead() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 130px 130px",
        background: "var(--surface-2)",
        borderBottom: "1px solid var(--ink-200)",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--ink-700)",
        letterSpacing: "0.04em",
      }}
    >
      <div style={{ padding: "8px 10px" }}>项　　目</div>
      <div style={{ padding: "8px 6px", textAlign: "center" }}>行次</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>本年累计数</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>本月数</div>
    </div>
  );
}

function ISRow({ line, highlight }: { line: ReportLine; highlight?: boolean }) {
  const indent = (line.indent ?? 0) * 12;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 130px 130px",
        borderTop: "1px solid var(--ink-100)",
        background: highlight
          ? "rgba(199,228,210,0.35)"
          : line.bold
          ? "rgba(199,228,210,0.18)"
          : "transparent",
        fontSize: 11.5,
      }}
    >
      <div
        style={{
          padding: "6px 10px",
          paddingLeft: 10 + indent,
          color: line.bold ? "var(--ink-900)" : "var(--ink-800)",
          fontWeight: line.bold ? 700 : 500,
        }}
      >
        {line.name}
      </div>
      <div
        style={{
          padding: "6px 6px",
          textAlign: "center",
          color: "var(--ink-500)",
          fontFamily: "ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {line.lineNo ?? ""}
      </div>
      <NumCell value={line.col1} bold={line.bold} wider />
      <NumCell value={line.col2} bold={line.bold} wider />
    </div>
  );
}

/* ============== 现金流量表 — 主表 + 补充资料 ============== */

function CashFlowTable({ report }: { report: CashFlowStatement }) {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* 主表 */}
      <div style={{ border: "1px solid var(--ink-200)", borderRadius: 8, overflow: "hidden" }}>
        <CFHead label="项　　目" />
        {report.mainFlow.map((l, idx) => (
          <CFRow key={`m-${idx}`} line={l} />
        ))}
        <CFRow line={report.netIncrease} highlight />
      </div>

      {/* 补充资料 */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 6,
            fontSize: 11.5,
            fontWeight: 700,
            color: "var(--ink-700)",
            letterSpacing: "0.05em",
          }}
        >
          <span
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              background: "var(--jintai-green)",
              color: "#fff",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.08em",
            }}
          >
            补充资料
          </span>
          <span style={{ color: "var(--ink-500)", fontWeight: 500 }}>
            将净利润调节为经营活动现金流量 · 行次 57–83
          </span>
        </div>
        <div style={{ border: "1px solid var(--ink-200)", borderRadius: 8, overflow: "hidden" }}>
          <CFHead label="补 充 资 料" />
          {report.supplement.map((l, idx) => (
            <CFRow key={`s-${idx}`} line={l} />
          ))}
        </div>
      </div>

      {/* 期末现金 高亮 (= 资产负债表 货币资金) */}
      <div
        style={{
          padding: "14px 18px",
          borderRadius: 10,
          background: "var(--brand-100)",
          border: "1px solid #bddff3",
          display: isDesktop ? "grid" : "flex",
          gridTemplateColumns: isDesktop ? "1fr 1fr" : undefined,
          flexDirection: isDesktop ? undefined : "column",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--brand-700)" }}>
            五、现金及现金等价物净增加额
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: "var(--brand-700)",
              fontFamily: "ui-monospace, monospace",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {report.netIncrease.col2}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--brand-700)" }}>
            期末现金余额 (= 资产负债表 货币资金)
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: "var(--brand-700)",
              fontFamily: "ui-monospace, monospace",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            8,200,000
          </span>
        </div>
      </div>
    </div>
  );
}

function CFHead({ label }: { label: string }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 120px 120px",
        background: "var(--surface-2)",
        borderBottom: "1px solid var(--ink-200)",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--ink-700)",
        letterSpacing: "0.04em",
      }}
    >
      <div style={{ padding: "8px 10px" }}>{label}</div>
      <div style={{ padding: "8px 6px", textAlign: "center" }}>行次</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>累计金额</div>
      <div style={{ padding: "8px 10px", textAlign: "right" }}>本月金额</div>
    </div>
  );
}

function CFRow({ line, highlight }: { line: ReportLine; highlight?: boolean }) {
  const isSection = !line.lineNo && line.bold;
  const indent = (line.indent ?? 0) * 10;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 44px 120px 120px",
        borderTop: line.underline ? "1px solid var(--ink-200)" : "1px solid var(--ink-100)",
        background: highlight
          ? "rgba(199,228,210,0.35)"
          : isSection
          ? "rgba(15,69,42,0.04)"
          : line.bold
          ? "rgba(199,228,210,0.15)"
          : "transparent",
        fontSize: 11.5,
      }}
    >
      <div
        style={{
          padding: "5px 10px",
          paddingLeft: 10 + indent,
          color: isSection ? "var(--jintai-green-dark)" : line.bold ? "var(--ink-900)" : "var(--ink-800)",
          fontWeight: line.bold ? 700 : 500,
        }}
      >
        {line.name}
      </div>
      <div
        style={{
          padding: "5px 6px",
          textAlign: "center",
          color: "var(--ink-500)",
          fontFamily: "ui-monospace, monospace",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {line.lineNo ?? ""}
      </div>
      <NumCell value={line.col1} bold={line.bold} />
      <NumCell value={line.col2} bold={line.bold} />
    </div>
  );
}

/* ============== 数字单元格 + 签字栏 + 通用组件 ============== */

function NumCell({
  value,
  bold,
  wider,
}: {
  value: string;
  bold?: boolean;
  wider?: boolean;
}) {
  const isNeg = value.startsWith("−") || value.startsWith("-");
  return (
    <div
      style={{
        padding: wider ? "6px 12px" : "5px 10px",
        textAlign: "right",
        color: isNeg ? "var(--risk-700)" : bold ? "var(--ink-900)" : "var(--ink-800)",
        fontFamily: "ui-monospace, monospace",
        fontWeight: bold ? 700 : 500,
        fontVariantNumeric: "tabular-nums",
        fontSize: bold ? 12 : 11.5,
      }}
    >
      {value === "—" ? <span style={{ color: "var(--ink-300)" }}>—</span> : value}
    </div>
  );
}

function SignatureRow() {
  return (
    <div
      style={{
        marginTop: 12,
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: 12,
        fontSize: 10.5,
        color: "var(--ink-500)",
        paddingTop: 8,
        borderTop: "1px dashed var(--ink-100)",
      }}
    >
      <span>企业负责人：<span style={{ color: "var(--ink-700)" }}>陈总</span></span>
      <span>财务负责人：<span style={{ color: "var(--ink-700)" }}>王会计</span></span>
      <span>制表人：<span style={{ color: "var(--ink-700)" }}>智通 AI · 王会计复核</span></span>
    </div>
  );
}

/* ============== AI 草稿 / 来源 / 洞察 / 自洽提示 (复用 iter 17) ============== */

// iter 19.1：来源 chip 不再以"Kingdee"作为唯一/必需数据源。
// AI 直接从业务单据(发票/合同/入库/出库/银行流水/工资表/抄表)聚合 → 客户即便不用金蝶也能跑。
// 金蝶导入 仅作为"可选额外数据源",展示"共生"姿态。
const REPORT_SOURCES: Record<ReportId, { kind: "合同" | "Excel" | "入库单" | "工艺单"; label: string }[]> = {
  balance: [
    { kind: "入库单", label: "本月 5 张采购入库 · AI 自动归集" },
    { kind: "合同", label: "本月 8 张应收 / 应付台账 · AI 抽取" },
    { kind: "Excel", label: "招行 + 工行月末对账单 · AI 比对" },
    { kind: "Excel", label: "金蝶月末科目余额表 (可选)" },
  ],
  income: [
    { kind: "合同", label: "本月 3 张销售合同（容百 / 横店 / 风华）· AI 抽取" },
    { kind: "入库单", label: "5 张采购入库 · AI 自动计成本" },
    { kind: "Excel", label: "工资表 + 水电气抄表 · AI 归并" },
    { kind: "Excel", label: "本月期间费用 12 张发票 · AI OCR" },
  ],
  cashflow: [
    { kind: "Excel", label: "招行 / 工行月度流水 · AI 已对账" },
    { kind: "入库单", label: "采购付款凭证 5 张 · AI 抽自发票" },
    { kind: "合同", label: "客户回款明细（容百首付 + 横店尾款）" },
    { kind: "Excel", label: "支付宝 / 微信收款 月度账单" },
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
        padding: "14px 16px",
        borderRadius: 10,
        background:
          "linear-gradient(135deg, rgba(186,224,247,0.6) 0%, rgba(232,242,251,0.85) 100%)",
        border: "1.5px solid var(--ai-500)",
        boxShadow: "0 2px 8px rgba(56,138,210,0.10)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {/* 阶段标识：AI 先填 → 人工确认 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ai-700)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 9px",
            borderRadius: 5,
            background: "var(--ai-500)",
            color: "#fff",
            fontSize: 10.5,
            letterSpacing: "0.06em",
          }}
        >
          {I.spark(11)} 第 1 步 · AI 先填
        </span>
        <span style={{ color: "var(--ink-300)", fontSize: 13 }}>→</span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 9px",
            borderRadius: 5,
            background: "var(--jintai-green)",
            color: "#fff",
            fontSize: 10.5,
            letterSpacing: "0.06em",
          }}
        >
          ✓ 第 2 步 · 王会计 确认
        </span>
        <span style={{ marginLeft: "auto", color: "var(--ink-500)", fontSize: 10, fontWeight: 600 }}>
          AI 不直接入账 · 人工最终拍板
        </span>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--ink-800)", lineHeight: 1.6 }}>{draft}</div>
      <div
        style={{
          fontSize: 11,
          color: "var(--ok-700)",
          fontWeight: 600,
          paddingTop: 6,
          borderTop: "1px dashed rgba(56,138,210,0.4)",
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
        }}
      >
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

/* iter 21: AI-native 定位条精简到 1 行 */
function AINativeBanner() {
  return (
    <div
      style={{
        padding: "8px 14px",
        borderRadius: 8,
        background:
          "linear-gradient(90deg, rgba(173,30,38,0.04) 0%, rgba(15,69,42,0.06) 50%, rgba(56,138,210,0.06) 100%)",
        border: "1px solid var(--ink-100)",
        display: "flex",
        gap: 10,
        alignItems: "center",
        flexWrap: "wrap",
        fontSize: 11.5,
      }}
    >
      <span
        style={{
          padding: "3px 9px",
          borderRadius: 5,
          background: "var(--jintai-red)",
          color: "#fff",
          fontSize: 10.5,
          fontWeight: 700,
          letterSpacing: "0.06em",
        }}
      >
        AI-NATIVE
      </span>
      <span style={{ color: "var(--ink-700)" }}>
        本套三表<strong style={{ color: "var(--jintai-green-dark)" }}>不依赖金蝶</strong> ·
        AI 自 发票/合同/入库/流水/工资/抄表 自动归集 → 王会计 1 步确认。
      </span>
    </div>
  );
}

/* iter 21: AI 财务洞察长段落 → KPI 大数字 + 1 组成结构条 + 1 句话建议 */
type InsightSegment = { label: string; value: number; color: string };
type InsightSpec = {
  metric: string;
  metricValue: string;
  metricUnit: string;
  trend: string;
  trendTone: "positive" | "neutral" | "warn";
  segments: InsightSegment[]; // 横向组成条
  segmentsLabel: string;
  suggestion: string;
};
const AI_INSIGHTS: Record<ReportId, InsightSpec> = {
  balance: {
    metric: "期末资产总计",
    metricValue: "49,000,000",
    metricUnit: "元",
    trend: "较月初 +1,060,000 · 账期平",
    trendTone: "positive",
    segmentsLabel: "权益结构 (期末)",
    segments: [
      { label: "实收资本", value: 10_000_000, color: "var(--brand-700)" },
      { label: "盈余公积", value: 720_000, color: "var(--brand-500)" },
      { label: "未分配利润", value: 19_300_000, color: "var(--jintai-green)" },
    ],
    suggestion:
      "本月底前与容百对账 SO-2026-001 验收回款 (下月到期 1,800,000),把应收占流动资产 40.5% 压回 38% 以下。",
  },
  income: {
    metric: "本月净利润",
    metricValue: "1,189,000",
    metricUnit: "元 · 毛利率 35.0%",
    trend: "营收环比 +8.6% · 期间费用控平",
    trendTone: "positive",
    segmentsLabel: "营业收入结构 (本月)",
    segments: [
      { label: "容百承烧板", value: 3_200_000, color: "var(--jintai-red)" },
      { label: "横店匣钵", value: 1_800_000, color: "var(--jintai-red-40)" },
      { label: "风华 MLCC", value: 950_000, color: "var(--warn-700)" },
      { label: "其他", value: 850_000, color: "var(--ink-300)" },
    ],
    suggestion:
      "横店匣钵单价 −2.1% 拉低毛利 0.4 个点;Q3 谈判提示电熔白刚玉 +6.7% 的原料成本压力。",
  },
  cashflow: {
    metric: "经营活动净现金流",
    metricValue: "+870,000",
    metricUnit: "元 · 期末 8,200,000",
    trend: "容百首付 1,200K + 横店尾款 800K",
    trendTone: "positive",
    segmentsLabel: "三大现金流活动 (本月净额)",
    segments: [
      { label: "经营 +870K", value: 870_000, color: "var(--ok-500)" },
      { label: "投资 −200K", value: 200_000, color: "var(--warn-500)" },
      { label: "筹资 −500K", value: 500_000, color: "var(--risk-500)" },
    ],
    suggestion:
      "下月初 3 张原料采购付款合计 327,000 到期,建议预留 400,000 备用金 + 提前催容百 1,800,000。",
  },
};

function AIInsightCard({ reportId }: { reportId: ReportId }) {
  const ins = AI_INSIGHTS[reportId];
  const trendColor =
    ins.trendTone === "positive"
      ? "var(--ok-700)"
      : ins.trendTone === "warn"
      ? "var(--warn-700)"
      : "var(--ink-500)";
  return (
    <div
      className="ai-surface"
      style={{
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
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

      {/* KPI 大数字 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 600 }}>{ins.metric}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
          <span
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: "var(--ink-900)",
              fontFamily: "ui-monospace, monospace",
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.01em",
            }}
          >
            {ins.metricValue}
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-500)" }}>{ins.metricUnit}</span>
        </div>
        <div style={{ fontSize: 11, color: trendColor, fontWeight: 500, marginTop: 2 }}>
          {ins.trend}
        </div>
      </div>

      {/* 组成结构条 — 自绘 SVG/CSS 堆叠条 */}
      <div>
        <div
          style={{
            fontSize: 10.5,
            color: "var(--ink-500)",
            fontWeight: 600,
            marginBottom: 5,
            letterSpacing: "0.04em",
          }}
        >
          {ins.segmentsLabel}
        </div>
        <CompositionBar segments={ins.segments} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
          {ins.segments.map((s) => (
            <span
              key={s.label}
              style={{ fontSize: 10.5, color: "var(--ink-600)", display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* AI 建议 */}
      <div
        style={{
          padding: "9px 11px",
          borderRadius: 8,
          background: "rgba(255,255,255,0.7)",
          border: "1px solid #bddff3",
          fontSize: 11.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
        }}
      >
        <strong style={{ color: "var(--ai-700)", marginRight: 4 }}>AI 建议</strong>·{" "}
        {ins.suggestion}
      </div>
    </div>
  );
}

/* iter 21: 横向堆叠组成条 (复用于 AI 洞察 + 成本 + 折旧) */
function CompositionBar({
  segments,
  height = 14,
}: {
  segments: { label: string; value: number; color: string }[];
  height?: number;
}) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  return (
    <div
      style={{
        display: "flex",
        height,
        borderRadius: 4,
        overflow: "hidden",
        border: "1px solid var(--ink-100)",
      }}
    >
      {segments.map((s) => (
        <div
          key={s.label}
          style={{
            flex: s.value,
            background: s.color,
            minWidth: s.value > 0 ? 2 : 0,
          }}
          title={`${s.label}: ${s.value.toLocaleString()} (${((s.value / total) * 100).toFixed(1)}%)`}
        />
      ))}
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
      <span style={{ fontWeight: 700, color: "var(--ok-700)", marginRight: 6 }}>✓ 五表自洽：</span>
      资产负债表 期末货币资金 <strong>8,200,000 元</strong> = 现金流量表 现金期末余额 ·
      利润分配表 八、未分配利润 <strong>19,300,000 元</strong> = 资产负债表 行 121 未分配利润 ·
      利润分配表 净利润 <strong>1,189,000 元</strong> = 现金流量表 补充资料 净利润 ·
      成本拆分合计 <strong>4,420,000 元</strong> = 损益表 行 2 主营业务成本 ·
      折旧台账 月折合计 <strong>260,000 元</strong> = 资产负债表 行 40 累计折旧 期初→期末 增量 (8,540 → 8,800) ·
      所有数字均由 AI 自业务单据 (发票/合同/入库/工资/抄表) 自动归集，不修改任何原始凭证。
    </div>
  );
}

/* ============== 成本拆分视图 (iter 20 · 附件需求 6 "材料/水电气/工资") ============== */

function CostBreakdownView() {
  const isDesktop = useIsDesktop();
  return (
    <div className="card" style={{ padding: 20 }}>
      <AIDraftBanner draft={costBreakdown.aiDraft} confirmedBy={costBreakdown.confirmedBy} />

      <div style={{ marginTop: 14, marginBottom: 14, textAlign: "center" }}>
        <div style={{ fontSize: 17, fontWeight: 800, color: "var(--ink-900)", letterSpacing: "0.12em" }}>
          营业成本拆分
        </div>
        <div
          style={{
            fontSize: 10.5,
            color: "var(--ink-500)",
            marginTop: 4,
            fontWeight: 600,
            letterSpacing: "0.05em",
          }}
        >
          (打通损益表 行 2 主营业务成本 4,420,000 元 → 5 类成本 + 4 类产品)
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginTop: 10,
            fontSize: 11.5,
            color: "var(--ink-700)",
            borderBottom: "1px solid var(--ink-200)",
            paddingBottom: 6,
          }}
        >
          <span>
            <strong style={{ color: "var(--ink-800)" }}>编制单位：</strong>
            {COMPANY_NAME}　　{costBreakdown.period}
          </span>
          <span style={{ color: "var(--ink-500)" }}>单位：元 (¥)</span>
        </div>
      </div>

      {/* 第一块：按类型拆分 */}
      <div style={{ marginBottom: 18 }}>
        <SectionLabel>① 按成本要素</SectionLabel>

        {/* iter 21: 5 段堆叠条 — 一眼看比例,而不是读 5 行表 */}
        <div style={{ marginBottom: 10 }}>
          <CompositionBar
            height={20}
            segments={[
              { label: "直接材料 71.5%", value: 3_160_000, color: "var(--jintai-red)" },
              { label: "直接人工 14.7%", value: 650_000, color: "var(--jintai-red-40)" },
              { label: "水电气 5.2%", value: 230_000, color: "var(--warn-500)" },
              { label: "折旧 5.9%", value: 260_000, color: "var(--brand-500)" },
              { label: "制造费用 2.7%", value: 120_000, color: "var(--ink-300)" },
            ]}
          />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 6 }}>
            {[
              { label: "直接材料 71.5%", color: "var(--jintai-red)" },
              { label: "直接人工 14.7%", color: "var(--jintai-red-40)" },
              { label: "水电气 5.2%", color: "var(--warn-500)" },
              { label: "折旧 5.9%", color: "var(--brand-500)" },
              { label: "制造费用 2.7%", color: "var(--ink-300)" },
            ].map((l) => (
              <span
                key={l.label}
                style={{ fontSize: 10.5, color: "var(--ink-600)", display: "inline-flex", alignItems: "center", gap: 4 }}
              >
                <span style={{ width: 8, height: 8, borderRadius: 2, background: l.color }} />
                {l.label}
              </span>
            ))}
          </div>
        </div>

        <div style={{ border: "1px solid var(--ink-200)", borderRadius: 8, overflow: "hidden" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.4fr 100px 70px 1.8fr 1fr",
              background: "var(--surface-2)",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--ink-700)",
              letterSpacing: "0.04em",
              padding: "8px 12px",
              borderBottom: "1px solid var(--ink-200)",
            }}
          >
            <span>成本要素</span>
            <span style={{ textAlign: "right" }}>金额 (元)</span>
            <span style={{ textAlign: "right" }}>占比</span>
            <span>数据来源</span>
            <span>环比</span>
          </div>
          {costBreakdown.byType.map((t) => (
            <div
              key={t.key}
              style={{
                display: "grid",
                gridTemplateColumns: "1.4fr 100px 70px 1.8fr 1fr",
                padding: "10px 12px",
                borderTop: "1px solid var(--ink-100)",
                fontSize: 11.5,
                color: "var(--ink-800)",
                alignItems: "center",
              }}
            >
              <span style={{ fontWeight: 700 }}>{t.label}</span>
              <span
                style={{
                  textAlign: "right",
                  fontFamily: "ui-monospace, monospace",
                  fontWeight: 700,
                  color: "var(--ink-900)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {t.amount.toLocaleString()}
              </span>
              <span
                style={{
                  textAlign: "right",
                  fontFamily: "ui-monospace, monospace",
                  color: "var(--ink-600)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {t.pct.toFixed(1)}%
              </span>
              <span style={{ color: "var(--ai-700)", fontSize: 11 }}>
                <span style={{ marginRight: 4 }}>✨</span>
                {t.source}
              </span>
              <span style={{ fontSize: 11, color: "var(--ink-500)" }}>{t.trend}</span>
            </div>
          ))}
          {/* 合计行 */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.4fr 100px 70px 2.8fr",
              padding: "10px 12px",
              borderTop: "2px solid var(--ink-200)",
              background: "var(--brand-100)",
              fontSize: 12.5,
              fontWeight: 800,
              color: "var(--brand-700)",
              alignItems: "center",
            }}
          >
            <span>合计 = 损益表 行 2 主营业务成本</span>
            <span
              style={{
                textAlign: "right",
                fontFamily: "ui-monospace, monospace",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {costBreakdown.totalCost.toLocaleString()}
            </span>
            <span style={{ textAlign: "right", fontFamily: "ui-monospace, monospace" }}>100.0%</span>
            <span style={{ fontSize: 11, color: "var(--ok-700)", fontWeight: 600 }}>✓ 与损益表自洽</span>
          </div>
        </div>
      </div>

      {/* 第二块：按产品/客户拆分 — iter 21: 毛利率改成进度条 */}
      <div>
        <SectionLabel>② 按产品 / 客户 (真实毛利率,金蝶通用件给不出)</SectionLabel>
        <div style={{ border: "1px solid var(--ink-200)", borderRadius: 8, overflow: "hidden" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isDesktop ? "1.6fr 1fr 130px 130px 1.4fr 60px" : "1fr 60px",
              background: "var(--surface-2)",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--ink-700)",
              letterSpacing: "0.04em",
              padding: "8px 12px",
              borderBottom: "1px solid var(--ink-200)",
              gap: 8,
            }}
          >
            <span>产品</span>
            {isDesktop && <span>客户</span>}
            {isDesktop && <span style={{ textAlign: "right" }}>本月成本</span>}
            {isDesktop && <span style={{ textAlign: "right" }}>本月收入</span>}
            {isDesktop && <span>毛利率 (0 — 45%)</span>}
            <span style={{ textAlign: "right" }}>%</span>
          </div>
          {costBreakdown.byProduct.map((p) => {
            const pct = parseFloat(p.margin);
            const isLow = pct < 32;
            return (
              <div
                key={p.product}
                style={{
                  display: "grid",
                  gridTemplateColumns: isDesktop ? "1.6fr 1fr 130px 130px 1.4fr 60px" : "1fr 60px",
                  padding: "10px 12px",
                  borderTop: "1px solid var(--ink-100)",
                  fontSize: 11.5,
                  color: "var(--ink-800)",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span style={{ fontWeight: 600 }}>{p.product}</span>
                {isDesktop && <span style={{ color: "var(--ink-600)" }}>{p.customer}</span>}
                {isDesktop && (
                  <span
                    style={{
                      textAlign: "right",
                      fontFamily: "ui-monospace, monospace",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {p.cost.toLocaleString()}
                  </span>
                )}
                {isDesktop && (
                  <span
                    style={{
                      textAlign: "right",
                      fontFamily: "ui-monospace, monospace",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {p.revenue.toLocaleString()}
                  </span>
                )}
                {isDesktop && (
                  <div
                    style={{
                      height: 10,
                      borderRadius: 5,
                      background: "var(--surface-2)",
                      border: "1px solid var(--ink-100)",
                      overflow: "hidden",
                      position: "relative",
                    }}
                    title={`${p.margin} (条满刻度 = 45%)`}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(100, (pct / 45) * 100)}%`,
                        background: isLow ? "var(--warn-500)" : "var(--ok-500)",
                      }}
                    />
                  </div>
                )}
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    fontWeight: 800,
                    color: isLow ? "var(--warn-700)" : "var(--ok-700)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {p.margin}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <SignatureRow />
    </div>
  );
}

/* ============== 折旧台账视图 (iter 20 · 附件需求 6 "折旧") ============== */

function DepreciationLedgerView() {
  const isDesktop = useIsDesktop();
  return (
    <div className="card" style={{ padding: 20 }}>
      <AIDraftBanner draft={depreciationLedger.aiDraft} confirmedBy={depreciationLedger.confirmedBy} />

      <div style={{ marginTop: 14, marginBottom: 14, textAlign: "center" }}>
        <div style={{ fontSize: 17, fontWeight: 800, color: "var(--ink-900)", letterSpacing: "0.12em" }}>
          固定资产折旧台账
        </div>
        <div
          style={{
            fontSize: 10.5,
            color: "var(--ink-500)",
            marginTop: 4,
            fontWeight: 600,
            letterSpacing: "0.05em",
          }}
        >
          (打通资产负债表 行 39/40/41 + 成本拆分 折旧子项)
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginTop: 10,
            fontSize: 11.5,
            color: "var(--ink-700)",
            borderBottom: "1px solid var(--ink-200)",
            paddingBottom: 6,
          }}
        >
          <span>
            <strong style={{ color: "var(--ink-800)" }}>编制单位：</strong>
            {COMPANY_NAME}　　{depreciationLedger.period}
          </span>
          <span style={{ color: "var(--ink-500)" }}>单位：元 (¥)</span>
        </div>
      </div>

      {/* iter 21: 5 类资产 原值/累计折旧/净值 堆叠条 — 一眼看资产新旧 */}
      <div style={{ marginBottom: 16 }}>
        <SectionLabel>资产折旧覆盖率 (累计折旧 ÷ 原值)</SectionLabel>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {depreciationLedger.items.map((it) => {
            const depPct = (it.accumDepEnd / it.originalValue) * 100;
            return (
              <div
                key={it.name}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.4fr 1fr 60px",
                  alignItems: "center",
                  gap: 10,
                  fontSize: 11.5,
                }}
              >
                <span style={{ color: "var(--ink-800)", fontWeight: 600 }}>{it.name}</span>
                <div
                  style={{
                    height: 14,
                    borderRadius: 4,
                    background: "rgba(27,127,58,0.15)",
                    border: "1px solid var(--ink-100)",
                    overflow: "hidden",
                    position: "relative",
                  }}
                  title={`原值 ${it.originalValue.toLocaleString()} · 累计折旧 ${it.accumDepEnd.toLocaleString()} (${depPct.toFixed(0)}%) · 净值 ${it.netValue.toLocaleString()}`}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${depPct}%`,
                      background:
                        depPct > 60 ? "var(--warn-500)" : depPct > 30 ? "var(--brand-500)" : "var(--ok-500)",
                    }}
                  />
                </div>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    fontWeight: 700,
                    color: "var(--ink-700)",
                  }}
                >
                  {depPct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 11.5,
            fontFamily: "var(--font)",
            border: "1px solid var(--ink-200)",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <thead>
            <tr style={{ background: "var(--surface-2)" }}>
              <DepTh>资产名称</DepTh>
              <DepTh>类别</DepTh>
              <DepTh align="right">原值</DepTh>
              <DepTh align="right">年限</DepTh>
              {isDesktop && <DepTh align="right">残值率</DepTh>}
              {isDesktop && <DepTh align="right">期初累计</DepTh>}
              <DepTh align="right">本月折旧</DepTh>
              <DepTh align="right">期末累计</DepTh>
              <DepTh align="right">净值</DepTh>
            </tr>
          </thead>
          <tbody>
            {depreciationLedger.items.map((it) => (
              <tr key={it.name} style={{ borderTop: "1px solid var(--ink-100)" }}>
                <DepTd bold>{it.name}</DepTd>
                <DepTd>
                  <span
                    className="pill"
                    style={{
                      background: "var(--surface-2)",
                      color: "var(--ink-700)",
                      fontSize: 10.5,
                      fontWeight: 600,
                    }}
                  >
                    {it.category}
                  </span>
                </DepTd>
                <DepTd align="right" mono>
                  {it.originalValue.toLocaleString()}
                </DepTd>
                <DepTd align="right" mono>
                  {it.usefulLife} 年
                </DepTd>
                {isDesktop && (
                  <DepTd align="right" mono>
                    {it.salvageRate}%
                  </DepTd>
                )}
                {isDesktop && (
                  <DepTd align="right" mono>
                    {it.accumDepBegin.toLocaleString()}
                  </DepTd>
                )}
                <DepTd align="right" mono bold style={{ color: "var(--warn-700)" }}>
                  {it.monthlyDep.toLocaleString()}
                </DepTd>
                <DepTd align="right" mono>
                  {it.accumDepEnd.toLocaleString()}
                </DepTd>
                <DepTd align="right" mono bold>
                  {it.netValue.toLocaleString()}
                </DepTd>
              </tr>
            ))}
            {/* 合计行 */}
            <tr
              style={{
                background: "var(--brand-100)",
                borderTop: "2px solid var(--ink-200)",
                fontWeight: 800,
              }}
            >
              <DepTd bold>合计 = 资产负债表对账</DepTd>
              <DepTd>—</DepTd>
              <DepTd align="right" mono bold style={{ color: "var(--brand-700)" }}>
                {depreciationLedger.totalOriginal.toLocaleString()}
              </DepTd>
              <DepTd>—</DepTd>
              {isDesktop && <DepTd>—</DepTd>}
              {isDesktop && (
                <DepTd align="right" mono bold style={{ color: "var(--brand-700)" }}>
                  8,540,000
                </DepTd>
              )}
              <DepTd align="right" mono bold style={{ color: "var(--brand-700)" }}>
                {depreciationLedger.totalMonthlyDep.toLocaleString()}
              </DepTd>
              <DepTd align="right" mono bold style={{ color: "var(--brand-700)" }}>
                {depreciationLedger.totalAccumDepEnd.toLocaleString()}
              </DepTd>
              <DepTd align="right" mono bold style={{ color: "var(--brand-700)" }}>
                {depreciationLedger.totalNetValue.toLocaleString()}
              </DepTd>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 对账提示条 */}
      <div
        style={{
          marginTop: 14,
          padding: "10px 14px",
          borderRadius: 10,
          background: "var(--ok-100)",
          border: "1px solid #c7e4d2",
          fontSize: 11.5,
          color: "var(--ok-700)",
          lineHeight: 1.6,
        }}
      >
        <strong>✓ 与资产负债表自洽：</strong>
        原值合计 <strong>26,800,000 元</strong> = 行 39 固定资产原价 ·
        期末累计折旧 <strong>8,800,000 元</strong> = 行 40 累计折旧 期末 ·
        净值合计 <strong>18,000,000 元</strong> = 行 41 固定资产净值 期末 ·
        本月折旧 <strong>260,000 元</strong> = 已结转至 损益表 营业成本 (折旧子项)。
      </div>

      <SignatureRow />
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11.5,
        fontWeight: 700,
        color: "var(--jintai-green-dark)",
        marginBottom: 6,
        letterSpacing: "0.04em",
      }}
    >
      {children}
    </div>
  );
}

function DepTh({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right" | "center";
}) {
  return (
    <th
      style={{
        padding: "8px 10px",
        textAlign: align ?? "left",
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-500)",
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

function DepTd({
  children,
  align,
  mono,
  bold,
  style,
}: {
  children: React.ReactNode;
  align?: "right";
  mono?: boolean;
  bold?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <td
      style={{
        padding: "8px 10px",
        textAlign: align ?? "left",
        color: bold ? "var(--ink-900)" : "var(--ink-800)",
        fontFamily: mono ? "ui-monospace, monospace" : "var(--font)",
        fontWeight: bold ? 700 : 500,
        fontVariantNumeric: "tabular-nums",
        ...style,
      }}
    >
      {children}
    </td>
  );
}
