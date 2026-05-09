import type { GoFn } from "../App";
import { I } from "../icons";

export function UploadScreen({ go: _go }: { go: GoFn }) {
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
            background: "var(--brand-50)",
            color: "var(--brand-500)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {I.cloud(28)}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-900)" }}>添加客户资料</div>
        <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>WP3-6 即将构建</div>
      </div>
    </div>
  );
}
