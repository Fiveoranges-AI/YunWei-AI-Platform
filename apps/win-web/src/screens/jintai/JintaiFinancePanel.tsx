import { useState } from "react";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { financeReports } from "./data";
import type {
  BalanceSheet,
  CashFlowStatement,
  FinanceReport,
  IncomeStatement,
  ReportLine,
} from "./data";
import { JintaiSourceCitation } from "./components";

type ReportId = FinanceReport["id"];

const COMPANY_NAME = "宜兴市锦泰耐火材料有限公司";

export function JintaiFinancePanel() {
  const [active, setActive] = useState<ReportId>("balance");
  const report = financeReports.find((r) => r.id === active) ?? financeReports[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* iter 19.1：AI-native 模式定位条 — "脱离金蝶也能跑" */}
      <AINativeBanner />

      {/* 子 tab — 三张表 */}
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
        background: "var(--surface-2)",
        borderBottom: "1px solid var(--ink-200)",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--ink-700)",
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
        borderTop: line.underline ? "1px solid var(--ink-200)" : "1px solid var(--ink-50)",
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
        borderTop: "1px solid var(--ink-50)",
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
        borderTop: line.underline ? "1px solid var(--ink-200)" : "1px solid var(--ink-50)",
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

/* AI-native 定位条：脱离金蝶也能跑 */
function AINativeBanner() {
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 10,
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
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "3px 9px",
          borderRadius: 5,
          background: "var(--jintai-red)",
          color: "#fff",
          fontSize: 10.5,
          fontWeight: 700,
          letterSpacing: "0.06em",
        }}
      >
        AI-NATIVE 模式
      </span>
      <span style={{ color: "var(--ink-700)", lineHeight: 1.55, flex: 1, minWidth: 280 }}>
        本套财务三表<strong style={{ color: "var(--jintai-green-dark)" }}>不依赖金蝶</strong>。
        AI 直接从 发票 / 销售合同 / 入库单 / 银行流水 / 工资表 / 抄表 自动归集 →
        生成会企小企业准则三表草稿 → 王会计 1 步确认入账。
        <span style={{ color: "var(--ink-500)" }}>
          (金蝶科目余额表可作为可选数据源导入 · 不强制 · 共生不替代)
        </span>
      </span>
    </div>
  );
}

const AI_INSIGHTS: Record<ReportId, { headline: string; body: string; suggestion: string }> = {
  balance: {
    headline: "资产期末 4,900 万元，三表对账平",
    body:
      "期末资产总计 49,000,000 元 = 负债 18,980,000 + 所有者权益 30,020,000，账期平。环比期初 +1,060,000 元，主要来自存货 +380,000 与货币资金 +170,000；应收帐款 12,500,000 仍偏高（容百锂电 5,200,000 + 横店 3,100,000）。",
    suggestion: "AI 建议：本月底前与容百对接 SO-2026-001 验收回款节奏（下月到期一笔 1,800,000 元），把应收占流动资产从 40.5% 降回 38% 以下。",
  },
  income: {
    headline: "本月净利润 1,189,000 元，毛利率 35.0%",
    body:
      "本月主营收入 6,800,000 元（环比 +8.6%），主营业务利润 2,344,000 元；期间费用 795,000 元控制平稳；本月净利润 1,189,000 元。利润分配段全月未提取盈余公积（5 月留存月份），可供分配利润 19,300,000 元 = 末未分配利润 19,300,000 元（与资产负债表行次 121 一致）。",
    suggestion: "AI 建议：横店东磁匣钵单价下行 −2.1%，本月毛利率被压低 0.4 个点，可在 Q3 谈判时提示电熔白刚玉 +6.7% 的原料成本压力。",
  },
  cashflow: {
    headline: "经营净流入 +870,000，期末余额 8,200,000",
    body:
      "经营活动净流入 870,000 元（容百首付 1,200,000 + 横店尾款 800,000 减原料/工资支出）；投资活动 −200,000 元（等静压辅机升级）；筹资活动 −500,000 元（偿还短期借款）。补充资料中净利润 1,189,000 经 折旧 260,000 + 经营性应收 −700,000 等调节后得 +870,000，与左半呼应。期末现金 8,200,000 = 资产负债表 货币资金 8,200,000。",
    suggestion: "AI 建议：下月初有 3 张原料采购付款（合计 327,000 元）到期，建议预留 400,000 元经营备用金，并提前催收容百到期 1,800,000 元。",
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
      <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.6 }}>{ins.body}</div>
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
      资产负债表 期末货币资金 <strong>8,200,000 元</strong> = 现金流量表 现金期末余额 <strong>8,200,000 元</strong> ·
      利润分配表 八、未分配利润 <strong>19,300,000 元</strong> = 资产负债表 行次 121 未分配利润 <strong>19,300,000 元</strong> ·
      利润分配表 净利润 <strong>1,189,000 元</strong> = 现金流量表 补充资料 净利润 <strong>1,189,000 元</strong> ·
      所有数字均由 AI 自三方账套数据 (Kingdee / 支付宝 / 银行流水) 自动归集，不修改任何原始凭证。
    </div>
  );
}
