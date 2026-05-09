import type { GoFn } from "../App";
import { I } from "../icons";

export function CustomerDetailScreen({
  go,
  params,
}: {
  go: GoFn;
  params: Record<string, string>;
}) {
  return (
    <ComingSoonScreen
      title="客户档案"
      sub={`即将构建 — id: ${params.id ?? "(未知)"}`}
      onBack={() => go("list")}
    />
  );
}

function ComingSoonScreen({
  title,
  sub,
  onBack,
}: {
  title: string;
  sub: string;
  onBack?: () => void;
}) {
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
          {I.spark(24)}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--ink-900)" }}>{title}</div>
        <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>{sub}</div>
        {onBack && (
          <button
            className="btn btn-secondary"
            style={{ marginTop: 20 }}
            onClick={onBack}
          >
            返回
          </button>
        )}
      </div>
    </div>
  );
}
