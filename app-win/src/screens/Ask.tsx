import type { GoFn } from "../App";
import { I } from "../icons";

export function AskScreen({ go: _go, params }: { go: GoFn; params: Record<string, string> }) {
  return (
    <div
      className="screen"
      style={{
        background: "var(--bg)",
        alignItems: "center",
        justifyContent: "center",
        display: "flex",
      }}
    >
      <div style={{ textAlign: "center", padding: 24 }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 14,
            margin: "0 auto 16px",
            background: "var(--ai-50)",
            color: "var(--ai-500)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {I.spark(28)}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-900)" }}>问 AI</div>
        <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>
          {params.id ? `针对 ${params.id} ` : ""}WP3-6 即将构建
        </div>
      </div>
    </div>
  );
}
