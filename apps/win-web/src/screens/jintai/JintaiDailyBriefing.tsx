import { I } from "../../icons";
import { dailyBriefingMetrics, dailyRisks } from "./data";
import type { Risk } from "./data";
import { JintaiSourceCitation } from "./components";

const SEV: Record<Risk, { label: string; bg: string; fg: string; border: string }> = {
  high: { label: "高", bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4" },
  medium: { label: "中", bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6" },
  low: { label: "低", bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2" },
};

export function JintaiDailyBriefing() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <div className="card" style={{ padding: 18 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div>
            <div style={{ fontSize: 11, color: "var(--ink-500)" }}>今日生产经营简报</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)" }}>2026-05-16</div>
          </div>
          <span className="pill pill-ai" style={{ fontSize: 11 }}>
            {I.spark(10)} AI 整理
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 8,
          }}
        >
          {dailyBriefingMetrics.map((m) => (
            <div
              key={m.label}
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--ink-500)" }}>{m.label}</div>
              <div
                className="num"
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "var(--ink-900)",
                  marginTop: 2,
                  letterSpacing: "-0.01em",
                }}
              >
                {m.value}
              </div>
              <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 2 }}>{m.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: 18 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 12 }}>
          风险提醒 · 按优先级
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {dailyRisks.map((r) => {
            const sev = SEV[r.severity];
            return (
              <article
                key={r.title}
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: "var(--surface)",
                  border: `1px solid ${sev.border}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    marginBottom: 6,
                  }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      background: sev.bg,
                      color: sev.fg,
                      fontSize: 11,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {sev.label}
                  </span>
                  <div style={{ flex: 1, fontSize: 13, fontWeight: 700, color: "var(--ink-900)", lineHeight: 1.45 }}>
                    {r.title}
                  </div>
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55, marginBottom: 8 }}>
                  {r.detail}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--ai-700)",
                    background: "var(--ai-50)",
                    border: "1px solid #d8e8f4",
                    borderRadius: 8,
                    padding: "8px 10px",
                    lineHeight: 1.55,
                    marginBottom: 8,
                  }}
                >
                  <strong style={{ marginRight: 6 }}>建议：</strong>
                  {r.suggestion}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {r.sources.map((s, i) => (
                    <JintaiSourceCitation key={i} source={s} />
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
