import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import {
  kpiCards,
  dashboardAlerts,
  dashboardQuickAsks,
  dashboardAiSample,
} from "../data";

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

  return (
    <div>
      {/* 价值主张 */}
      <div
        style={{
          padding: "14px 18px",
          background: "linear-gradient(120deg, var(--ai-50) 0%, #F6F0FF 100%)",
          border: "1px solid var(--ai-100)",
          borderRadius: 12,
          marginBottom: 18,
          fontSize: 13,
          lineHeight: 1.6,
          color: "var(--ink-700)",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <span
          style={{
            flexShrink: 0,
            display: "inline-flex",
            width: 28,
            height: 28,
            borderRadius: 8,
            background: "rgba(123,92,250,0.12)",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--ai-purple-deep)",
          }}
        >
          {I.spark(14, "var(--ai-purple-deep)")}
        </span>
        <span>
          <strong style={{ color: "var(--ink-900)" }}>用 AI 把 1,000+ SKU 管清楚</strong>：
          实时记录出入库，提前 3 天发现缺货风险，让老板不用再靠 Excel 和人工记忆管库存。
        </span>
      </div>

      {/* KPI 卡片 - 7 张 */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "repeat(7, 1fr)" : "repeat(2, 1fr)",
          gap: 10,
          marginBottom: 22,
        }}
      >
        {kpiCards.map((k) => (
          <div
            key={k.label}
            className="card"
            style={{
              padding: "14px 14px 13px",
              borderLeft: `3px solid ${k.color}`,
              minWidth: 0,
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: "var(--ink-500)",
                fontWeight: 600,
                marginBottom: 6,
                lineHeight: 1.2,
              }}
            >
              {k.label}
            </div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 800,
                color: "var(--ink-900)",
                lineHeight: 1.1,
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.01em",
              }}
            >
              {k.value}
              <span
                style={{
                  fontSize: 11.5,
                  fontWeight: 600,
                  color: "var(--ink-400)",
                  marginLeft: 4,
                }}
              >
                {k.trend}
              </span>
            </div>
            <div
              style={{
                fontSize: 10.5,
                color: "var(--ink-400)",
                marginTop: 5,
                lineHeight: 1.3,
              }}
            >
              {k.trendLabel}
            </div>
          </div>
        ))}
      </section>

      {/* 风险提醒 + AI 助手 — 双栏 */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "1.65fr 1fr" : "1fr",
          gap: 16,
        }}
      >
        {/* 风险提醒列表 */}
        <div className="card" style={{ padding: "16px 18px" }}>
          <header
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
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
                今日库存风险提醒
              </h3>
            </div>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
              共 {dashboardAlerts.length} 条 · 2 红 / 2 黄 / 1 灰
            </span>
          </header>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
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
                        onClick={() =>
                          onGoTab(a.cta === "查看缺货预警" ? "shortage" : "replenish")
                        }
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
            padding: "16px 18px",
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
              问问 AI 库存管家
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
            老板手机一句话，AI 拿实时库存秒答。
          </p>

          {/* 6 quick asks */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 14 }}>
            {dashboardQuickAsks.map((q) => (
              <button
                key={q}
                onClick={() => onGoTab("ask")}
                style={{
                  padding: "8px 11px",
                  fontSize: 12,
                  fontWeight: 500,
                  textAlign: "left",
                  borderRadius: 7,
                  border: "1px solid var(--ink-100)",
                  background: "#fff",
                  color: "var(--ink-700)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
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
