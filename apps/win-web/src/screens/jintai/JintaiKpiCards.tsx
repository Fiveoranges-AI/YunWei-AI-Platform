import { useEffect, useState } from "react";
import { getJintaiKpis } from "../../api/jintai";
import { kpis } from "./data";

export function JintaiKpiCards() {
  const [items, setItems] = useState(kpis);

  useEffect(() => {
    let cancelled = false;
    getJintaiKpis()
      .then((backendKpis) => {
        if (!cancelled) setItems(backendKpis);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Tab 1 视觉减负：6 → 4 张关键 KPI（已识别 / 待确认 / 进行中 / 延期风险）
  const shown = items.slice(0, 4);
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 14,
        marginBottom: 24,
      }}
    >
      {shown.map((k) => (
        <div
          key={k.label}
          className="card-flat"
          style={{
            padding: "16px 18px",
            borderRadius: 12,
          }}
        >
          <div style={{ fontSize: 12, color: "var(--ink-500)", fontWeight: 600 }}>
            {k.label}
          </div>
          <div
            className="num"
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: "var(--ink-900)",
              marginTop: 6,
              letterSpacing: "-0.01em",
            }}
          >
            {k.value}
            {k.suffix ? (
              <span style={{ fontSize: 14, color: "var(--ink-500)", marginLeft: 2 }}>
                {k.suffix}
              </span>
            ) : null}
          </div>
          <div
            style={{
              fontSize: 11.5,
              color: "var(--ink-400)",
              marginTop: 6,
              lineHeight: 1.45,
            }}
          >
            {k.hint}
          </div>
        </div>
      ))}
    </div>
  );
}
