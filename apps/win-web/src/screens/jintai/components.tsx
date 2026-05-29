import type { ReactNode } from "react";
import type { Risk, SourceRef } from "./data";

const RISK_META: Record<Risk, { label: string; bg: string; fg: string; border: string }> = {
  high: { label: "高风险", bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4" },
  medium: { label: "中风险", bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6" },
  low: { label: "低风险", bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2" },
};

export function JintaiRiskBadge({ risk }: { risk: Risk }) {
  const m = RISK_META[risk];
  return (
    <span
      className="pill pill-dot"
      style={{ background: m.bg, color: m.fg, border: `1px solid ${m.border}` }}
    >
      {m.label}
    </span>
  );
}

const STATUS_META: Record<
  string,
  { fg: string; bg: string }
> = {
  待确认: { fg: "var(--ai-700)", bg: "var(--ai-100)" },
  订单已生成: { fg: "var(--ok-700)", bg: "var(--ok-100)" },
  流转单已生成: { fg: "var(--ok-700)", bg: "var(--ok-100)" },
  出货已记录: { fg: "var(--ok-700)", bg: "var(--ok-100)" },
  进行中: { fg: "var(--brand-700)", bg: "var(--brand-100)" },
  已完成: { fg: "var(--ok-700)", bg: "var(--ok-100)" },
  未开始: { fg: "var(--ink-600)", bg: "var(--ink-100)" },
  完成: { fg: "var(--ok-700)", bg: "var(--ok-100)" },
  待开始: { fg: "var(--ink-600)", bg: "var(--ink-100)" },
};

export function JintaiStatusBadge({ status }: { status: string }) {
  const m = STATUS_META[status] ?? { fg: "var(--ink-700)", bg: "var(--ink-100)" };
  return (
    <span className="pill" style={{ background: m.bg, color: m.fg }}>
      {status}
    </span>
  );
}

const SOURCE_ICON: Record<SourceRef["kind"], string> = {
  合同: "📄",
  生产流转单: "🗂",
  Excel: "🟢",
  微信: "💬",
  出货单: "📦",
  工艺单: "⚙️",
  入库单: "📥",
};

export function JintaiSourceCitation({ source }: { source: SourceRef }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 9px",
        borderRadius: 8,
        background: "var(--surface-3)",
        border: "1px solid var(--ink-100)",
        color: "var(--ink-700)",
        fontSize: 11.5,
        fontWeight: 500,
        lineHeight: 1.2,
      }}
      title={source.label}
    >
      <span style={{ fontSize: 11 }}>{SOURCE_ICON[source.kind] ?? "📎"}</span>
      <span style={{ color: "var(--ink-400)" }}>{source.kind}</span>
      <span
        style={{
          maxWidth: 220,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          color: "var(--ink-800)",
        }}
      >
        {source.label}
      </span>
    </span>
  );
}

export function JintaiSection({
  title,
  trailing,
  children,
  id,
}: {
  title: string;
  trailing?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section id={id} style={{ marginBottom: 28, scrollMarginTop: 80 }}>
      <div className="sec-h" style={{ paddingLeft: 2, marginBottom: 12 }}>
        <h3>{title}</h3>
        {trailing}
      </div>
      {children}
    </section>
  );
}

export function JintaiCard({
  children,
  style,
  flat,
  className,
}: {
  children: ReactNode;
  style?: React.CSSProperties;
  flat?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`${flat ? "card-flat" : "card"}${className ? " " + className : ""}`}
      style={{ padding: 16, ...style }}
    >
      {children}
    </div>
  );
}
