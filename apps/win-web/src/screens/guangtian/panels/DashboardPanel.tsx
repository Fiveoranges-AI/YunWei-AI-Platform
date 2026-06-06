import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { useGT } from "../state";
import {
  dashboardAlerts,
  dashboardQuickAsks,
  dashboardAiSample,
  skuRows,
} from "../data";
import { DashboardChartsGrid } from "./DashboardCharts";

type TabKey = "sku" | "inbound" | "outbound" | "ledger" | "shortage" | "replenish" | "ask" | "report" | "dashboard";

type Props = { onGoTab: (key: TabKey) => void };

const LEVEL_STYLES: Record<
  "high" | "medium" | "low",
  { bg: string; border: string; dot: string; tag: string; tagBg: string }
> = {
  high: {
    bg: "rgba(195,38,41,0.04)",
    border: "rgba(195,38,41,0.18)",
    dot: "var(--guangtian-red)",
    tag: "高风险",
    tagBg: "var(--guangtian-red)",
  },
  medium: {
    bg: "rgba(245,158,11,0.05)",
    border: "rgba(245,158,11,0.20)",
    dot: "var(--stock-low)",
    tag: "中风险",
    tagBg: "var(--stock-low)",
  },
  low: {
    bg: "rgba(107,114,128,0.04)",
    border: "var(--ink-100)",
    dot: "var(--ink-300)",
    tag: "提醒",
    tagBg: "var(--ink-400)",
  },
};

export function DashboardPanel({ onGoTab }: Props) {
  const isDesktop = useIsDesktop();
  const { skuStocks, showToast, todayInboundCount, todayOutboundCount } = useGT();

  // iter G18: KPI 数字与 Donut + 日报对齐
  // 低库存 46 = filter(2 条演示) + 44 模拟（与 DIST 中 46 / dailyReport "46 个 SKU" 一致）
  // 订单缺货 = shortageOrders.length 实际值，避免点 KPI 跳过去发现卡数不符
  const lowStockCount = skuRows.filter((r) => {
    const s = skuStocks[r.code] ?? r.stock;
    return s > 0 && s < r.safety;
  }).length + 44;
  const outOfStockOrders = 3;
  const totalSku = 1286;

  type Kpi = {
    label: string;
    value: string;
    trend: string;
    trendLabel: string;
    color: string;
    target: TabKey;
    skuFilter?: string;
  };
  // iter G17 第一性原理：4 张卡直接对应出入库 4 核心需求
  // 知道有多少 → SKU 总数 / 低库存 / 今日出入库
  // 缺货提前知道 → 订单缺货风险
  const kpis: Kpi[] = [
    { label: "SKU 总数",     value: totalSku.toLocaleString(), trend: "+12", trendLabel: "本月新增", color: "var(--brand-500)", target: "sku" },
    { label: "低库存预警",   value: String(lowStockCount),     trend: "SKU", trendLabel: "点击查看 →", color: "var(--stock-low)", target: "sku" },
    { label: "订单缺货风险", value: String(outOfStockOrders),  trend: "单",  trendLabel: "含紧急 1 · 点击 →", color: "var(--guangtian-red)", target: "shortage" },
    { label: "今日出入库",   value: `${todayInboundCount}/${todayOutboundCount}`, trend: "笔", trendLabel: "入 / 出 · 点击 →", color: "var(--guangtian-blue)", target: "ledger" },
  ];

  // iter G9: 风险提醒 5 → 3（最严重的）
  const topAlerts = dashboardAlerts.slice(0, 3);
  // iter G9: 快捷问题 6 → 4
  const topQuickAsks = dashboardQuickAsks.slice(0, 4);

  // R2: 老板助手 tab 已砍 —— 这些速查问题改为直接跳「缺货预警」(真业务页)
  const onAskQuestion = (_q: string) => {
    onGoTab("shortage");
  };

  return (
    <div>
      {/* spec: 顶部「今日必须处理的三件事」—— 老板进来第一眼就知道今天要干嘛 */}
      <section
        className="card"
        style={{
          padding: "16px 20px 14px",
          marginBottom: 20,
          borderTop: "3px solid var(--guangtian-red)",
        }}
      >
        <header
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 12,
            gap: 8,
          }}
        >
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
            今日必须处理的三件事
          </h2>
          <span style={{ fontSize: 11.5, color: "var(--ink-400)" }}>
            AI 已从 {dashboardAlerts.length} 条风险里挑出最该先处理的 3 件
          </span>
        </header>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {topAlerts.map((a, i) => {
            const emoji = a.level === "high" ? "🔴" : a.level === "medium" ? "🟡" : "🟢";
            const target = "shortage"; // R2: 补产 tab 已砍,风险一律跳缺货预警
            return (
              <button
                key={i}
                onClick={() => { onGoTab(target); showToast(`已跳转 · ${a.title}`, "info"); }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  width: "100%",
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: 10,
                  border: "1px solid var(--ink-100)",
                  background: a.level === "high" ? "rgba(217,32,32,0.045)" : a.level === "medium" ? "rgba(245,158,11,0.05)" : "var(--surface-2)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                  transition: "transform 0.12s ease, box-shadow 0.12s ease",
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = "var(--shadow-card-hover)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.boxShadow = ""; }}
              >
                <span style={{ fontSize: 18, flexShrink: 0 }}>{emoji}</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: "block", fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)", lineHeight: 1.35 }}>
                    {a.title}
                  </span>
                  <span style={{ display: "block", fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.5, marginTop: 2 }}>
                    {a.body}
                  </span>
                </span>
                <span style={{ flexShrink: 0, fontSize: 12, fontWeight: 700, color: "var(--guangtian-red)" }}>
                  处理 →
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* KPI 卡片 - iter G10: 全卡可点跳对应 tab */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
          gap: 14,
          marginBottom: 24,
        }}
      >
        {kpis.map((k) => (
          <button
            key={k.label}
            onClick={() => {
              onGoTab(k.target);
              showToast(`已跳转至「${k.label}」明细`, "info");
            }}
            className="card"
            style={{
              padding: "18px 18px 16px",
              borderLeft: `3px solid ${k.color}`,
              minWidth: 0,
              textAlign: "left",
              cursor: "pointer",
              border: "1px solid var(--ink-100)",
              borderLeftWidth: 3,
              borderLeftColor: k.color,
              background: "#fff",
              fontFamily: "var(--font)",
              transition: "transform 0.15s ease, box-shadow 0.15s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-2px)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "var(--shadow-card-hover)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "";
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "var(--ink-500)",
                fontWeight: 600,
                marginBottom: 8,
                lineHeight: 1.2,
              }}
            >
              {k.label}
            </div>
            <div
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: "var(--ink-900)",
                lineHeight: 1.1,
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.015em",
              }}
            >
              {k.value}
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--ink-400)",
                  marginLeft: 5,
                }}
              >
                {k.trend}
              </span>
            </div>
            <div
              style={{
                fontSize: 11,
                color: k.target !== "sku" || k.label === "SKU 总数" ? "var(--ink-400)" : "var(--guangtian-red)",
                marginTop: 6,
                lineHeight: 1.3,
                fontWeight: 500,
              }}
            >
              {k.trendLabel}
            </div>
          </button>
        ))}
      </section>

      {/* iter G12-A: 3 SVG 图表 */}
      <DashboardChartsGrid />

      {/* 风险提醒 + AI 助手 — 双栏 */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "1.65fr 1fr" : "1fr",
          gap: 20,
        }}
      >
        {/* 风险提醒列表 */}
        <div className="card" style={{ padding: "20px 22px" }}>
          <header
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 14,
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: 7,
                  background: "rgba(195,38,41,0.10)",
                  color: "var(--guangtian-red)",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {I.warn(14, "var(--guangtian-red)")}
              </span>
              <h3
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 700,
                  color: "var(--ink-900)",
                }}
              >
                全部库存风险
              </h3>
            </div>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
              共 {dashboardAlerts.length} 条
            </span>
          </header>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            {dashboardAlerts.map((a, i) => {
              const s = LEVEL_STYLES[a.level];
              return (
                <li
                  key={i}
                  style={{
                    padding: "10px 12px",
                    background: s.bg,
                    border: `1px solid ${s.border}`,
                    borderRadius: 9,
                    display: "flex",
                    gap: 10,
                  }}
                >
                  <span
                    aria-hidden
                    style={{
                      flexShrink: 0,
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: s.dot,
                      marginTop: 7,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        flexWrap: "wrap",
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 9.5,
                          fontWeight: 700,
                          padding: "2px 7px",
                          borderRadius: 4,
                          background: s.tagBg,
                          color: "#fff",
                          letterSpacing: "0.02em",
                        }}
                      >
                        {s.tag}
                      </span>
                      <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)" }}>
                        {a.title}
                      </span>
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.55 }}>
                      {a.body}
                    </div>
                    {a.cta && (
                      <button
                        onClick={() => {
                          const target = "shortage";
                          onGoTab(target);
                          showToast(`已跳转 · ${a.cta}`, "info");
                        }}
                        style={{
                          marginTop: 7,
                          padding: "4px 10px",
                          fontSize: 11,
                          fontWeight: 600,
                          borderRadius: 6,
                          border: "1px solid var(--ink-200)",
                          background: "#fff",
                          color: "var(--ink-700)",
                          cursor: "pointer",
                          fontFamily: "var(--font)",
                        }}
                      >
                        → {a.cta}
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {/* AI 助手 sidecard */}
        <div
          className="card"
          style={{
            padding: "20px 22px",
            background: "linear-gradient(180deg, #FAF8FF 0%, #FFFFFF 60%)",
            borderLeft: "3px solid var(--ai-purple)",
          }}
        >
          <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <span
              style={{
                width: 26,
                height: 26,
                borderRadius: 7,
                background: "rgba(123,92,250,0.12)",
                color: "var(--ai-purple-deep)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {I.chat(14, "var(--ai-purple-deep)")}
            </span>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
              缺货速查
            </h3>
          </header>
          <p
            style={{
              margin: "0 0 10px",
              fontSize: 11.5,
              color: "var(--ink-500)",
              lineHeight: 1.5,
            }}
          >
            老板关心的问题，点一下直接看「缺货预警」答案。
          </p>

          {/* iter G9: quick asks 6 → 4; iter G10: 点击自动填入问问 AI tab */}
          <div style={{ display: "flex", flexDirection: "column", gap: 7, marginBottom: 14 }}>
            {topQuickAsks.map((q) => (
              <button
                key={q}
                onClick={() => onAskQuestion(q)}
                style={{
                  padding: "9px 12px",
                  fontSize: 12,
                  fontWeight: 500,
                  textAlign: "left",
                  borderRadius: 7,
                  border: "1px solid var(--ink-100)",
                  background: "#fff",
                  color: "var(--ink-700)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                  transition: "background 0.15s ease, border-color 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "var(--ai-50)";
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--ai-200)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "#fff";
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--ink-100)";
                }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* AI 示例回答 */}
          <div
            style={{
              padding: "10px 12px",
              borderRadius: 9,
              background: "var(--ai-50)",
              border: "1px solid var(--ai-100)",
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: "var(--ai-700)",
                fontWeight: 700,
                marginBottom: 5,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {I.spark(12, "var(--ai-700)")} AI 示例
            </div>
            <div
              style={{
                fontSize: 11.5,
                color: "var(--ink-600)",
                lineHeight: 1.55,
                marginBottom: 6,
                fontStyle: "italic",
              }}
            >
              "{dashboardAiSample.q}"
            </div>
            <div
              style={{
                fontSize: 11.5,
                color: "var(--ink-800)",
                lineHeight: 1.65,
                whiteSpace: "pre-line",
              }}
            >
              {dashboardAiSample.a}
            </div>
            <div
              style={{
                marginTop: 8,
                paddingTop: 8,
                borderTop: "1px dashed var(--ai-200)",
                fontSize: 10,
                color: "var(--ai-700)",
                lineHeight: 1.5,
              }}
            >
              <strong style={{ fontWeight: 700 }}>数据来源：</strong>
              <br />
              {dashboardAiSample.sources.join(" · ")}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
