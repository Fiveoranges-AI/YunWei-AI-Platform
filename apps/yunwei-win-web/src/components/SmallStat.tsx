import type { ReactNode } from "react";

type Props = {
  icon: ReactNode;
  label: string;
  value: string | number;
  tone?: "ai" | undefined;
};

export function SmallStat({ icon, label, value, tone }: Props) {
  const fg = tone === "ai" ? "var(--ai-500)" : "var(--ink-700)";
  return (
    <div className="card" style={{ padding: 12, display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ color: fg }}>{icon}</div>
      <div>
        <div className="num" style={{ fontSize: 16, fontWeight: 700, color: "var(--ink-900)", lineHeight: 1.1 }}>
          {value}
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-500)" }}>{label}</div>
      </div>
    </div>
  );
}
