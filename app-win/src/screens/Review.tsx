import type { GoFn } from "../App";
import { I } from "../icons";

export function ReviewScreen({ go }: { go: GoFn }) {
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
          {I.check(28)}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-900)" }}>AI 审核</div>
        <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>WP3-6 即将构建</div>
        <button className="btn btn-secondary" style={{ marginTop: 20 }} onClick={() => go("upload")}>
          返回上传
        </button>
      </div>
    </div>
  );
}
