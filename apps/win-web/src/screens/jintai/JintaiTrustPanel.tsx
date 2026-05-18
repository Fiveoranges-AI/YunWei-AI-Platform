import { I } from "../../icons";
import { useIsMobile } from "../../lib/breakpoints";
import { trustItems, traceExamples } from "./data";
import { JintaiSourceCitation } from "./components";

export function JintaiTrustPanel() {
  const isMobile = useIsMobile();
  // Iter 8/9：在 4 张原有 + 2 张新增财务安全后扩到 6 张展示（其余在其他 tab 自然展示）
  // Iter 10/11：trace 示例 1 → 3（生产 + 财务三表 + 经营日报），演示 AI 不偷换账 + 不替老板瞎签
  const visibleTrust = trustItems.slice(0, 6);
  const visibleTrace = [traceExamples[0], traceExamples[3], traceExamples[4]];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 14,
        }}
      >
        {visibleTrust.map((t) => (
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

      <div className="card" style={{ padding: 22 }}>
        <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
          来源追溯示例
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-500)", marginBottom: 14 }}>
          点击任意 AI 给出的事实，可以一键跳回原始资料
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {visibleTrace.map((t, i) => (
            <div
              key={i}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 8,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ fontSize: 12.5, color: "var(--ink-900)", flex: 1, minWidth: 200, fontWeight: 500 }}>
                  <span style={{ color: "var(--ai-700)", fontWeight: 700 }}>AI 给出：</span>{" "}
                  {t.aiFact}
                </div>
                <span style={{ color: "var(--ink-400)" }}>{I.chev(11)}</span>
                <JintaiSourceCitation source={t.source} />
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
                  gap: 8,
                  fontSize: 11,
                  color: "var(--ink-600)",
                  paddingTop: 8,
                  borderTop: "1px dashed var(--ink-100)",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 700, color: "var(--ink-500)", letterSpacing: "0.04em" }}>抽取过程</span>
                  <span style={{ color: "var(--ink-800)" }}>{t.extractedBy}</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 700, color: "var(--ink-500)", letterSpacing: "0.04em" }}>人工确认</span>
                  <span style={{ color: "var(--ink-800)" }}>{t.confirmedBy}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
