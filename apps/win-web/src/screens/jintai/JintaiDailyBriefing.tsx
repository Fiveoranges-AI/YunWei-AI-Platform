import { useEffect, useState } from "react";
import { getJintaiBriefing } from "../../api/jintai";
import { useIsDesktop } from "../../lib/breakpoints";
import { dailyBriefingMetrics, dailyRisks } from "./data";
import type { Risk, SourceRef } from "./data";

type BriefingMetric = { label: string; value: number | string; sub: string };
type BriefingRisk = {
  severity: Risk;
  title: string;
  detail: string;
  suggestion: string;
  sources: SourceRef[];
};

const SEV: Record<Risk, { label: string; bg: string; fg: string; border: string }> = {
  high: { label: "高", bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4" },
  medium: { label: "中", bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6" },
  low: { label: "低", bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2" },
};

export function JintaiDailyBriefing() {
  const isDesktop = useIsDesktop();
  const [briefingDate, setBriefingDate] = useState("2026-05-16");
  const [metrics, setMetrics] = useState<BriefingMetric[]>(dailyBriefingMetrics);
  const [risks, setRisks] = useState<BriefingRisk[]>(dailyRisks);

  useEffect(() => {
    let cancelled = false;
    getJintaiBriefing()
      .then((briefing) => {
        if (cancelled) return;
        setBriefingDate(briefing.briefingDate);
        setMetrics(briefing.metrics);
        setRisks(briefing.risks);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // 视觉减负：metrics 6 → 4；风险卡 detail/suggestion 截断 + 隐藏 sources 墙
  const shownMetrics = metrics.slice(0, 4);
  return (
    <div style={{ display: "grid", gridTemplateColumns: isDesktop ? "1fr 1fr" : "1fr", gap: 20 }}>
      <div className="card" style={{ padding: 22 }}>
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, color: "var(--ink-500)" }}>今日生产经营简报</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-900)", marginTop: 2 }}>{briefingDate}</div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isDesktop ? "repeat(2, 1fr)" : "repeat(2, 1fr)",
            gap: 10,
          }}
        >
          {shownMetrics.map((m) => (
            <div
              key={m.label}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
              }}
            >
              <div style={{ fontSize: 11.5, color: "var(--ink-500)" }}>{m.label}</div>
              <div
                className="num"
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  color: "var(--ink-900)",
                  marginTop: 4,
                  letterSpacing: "-0.01em",
                }}
              >
                {m.value}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 4, lineHeight: 1.4 }}>{m.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: 22 }}>
        <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 14 }}>
          风险提醒 · 按优先级
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {risks.map((r) => {
            const sev = SEV[r.severity];
            const detail = r.detail.length > 90 ? r.detail.slice(0, 88) + "…" : r.detail;
            return (
              <article
                key={r.title}
                style={{
                  padding: 14,
                  borderRadius: 10,
                  background: "var(--surface)",
                  border: `1px solid ${sev.border}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
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
                <div style={{ fontSize: 12, color: "var(--ink-600)", lineHeight: 1.55 }}>
                  {detail}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
