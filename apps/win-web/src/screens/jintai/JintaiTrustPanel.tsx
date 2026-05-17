import { I } from "../../icons";
import { trustItems, traceExamples } from "./data";
import { JintaiSourceCitation } from "./components";

export function JintaiTrustPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 12,
        }}
      >
        {trustItems.map((t) => (
          <div
            key={t.title}
            className="card-flat"
            style={{
              padding: 14,
              display: "flex",
              flexDirection: "column",
              gap: 6,
              borderRadius: 12,
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "var(--ai-100)",
                color: "var(--ai-700)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {I.shield(14)}
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>{t.title}</div>
            <div style={{ fontSize: 12, color: "var(--ink-600)", lineHeight: 1.55 }}>{t.body}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ padding: 18 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
          来源追溯示例
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-500)", marginBottom: 12 }}>
          点击任意 AI 给出的事实，可以一键跳回原始资料
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {traceExamples.map((t, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 10,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
                flexWrap: "wrap",
              }}
            >
              <div style={{ fontSize: 12, color: "var(--ink-800)", flex: 1, minWidth: 200 }}>
                <span style={{ color: "var(--ai-700)", fontWeight: 600 }}>AI 给出：</span>{" "}
                {t.aiFact}
              </div>
              <span style={{ color: "var(--ink-400)" }}>{I.chev(11)}</span>
              <JintaiSourceCitation source={t.source} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
