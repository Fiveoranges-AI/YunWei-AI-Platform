import { I } from "../icons";
import type { TabName } from "../App";

const ITEMS: { id: TabName; label: string; sub: string; icon: (s?: number, c?: string) => JSX.Element }[] = [
  { id: "customers", label: "客户", sub: "Customers", icon: I.customers },
  { id: "upload", label: "添加", sub: "Upload", icon: I.upload },
  { id: "ask", label: "问 AI", sub: "Ask AI", icon: I.ask },
  { id: "profile", label: "我的", sub: "Profile", icon: I.profile },
];

type Props = {
  active: TabName;
  onChange: (t: TabName) => void;
};

export function Sidebar({ active, onChange }: Props) {
  return (
    <aside
      style={{
        width: 240,
        flexShrink: 0,
        background: "var(--surface)",
        borderRight: "1px solid var(--ink-100)",
        display: "flex",
        flexDirection: "column",
        padding: "20px 16px 16px",
      }}
    >
      {/* Brand */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 8px 24px" }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            background: "linear-gradient(135deg, var(--brand-500), var(--ai-500))",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: "-0.02em",
          }}
        >
          智
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
            智通客户
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)" }}>Super Customer Profile</div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {ITEMS.map((it) => {
          const isActive = it.id === active;
          return (
            <button
              key={it.id}
              onClick={() => onChange(it.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 10,
                background: isActive ? "var(--brand-50)" : "transparent",
                color: isActive ? "var(--brand-700)" : "var(--ink-700)",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "var(--font)",
                fontSize: 14,
                fontWeight: isActive ? 600 : 500,
                transition: "background 120ms ease",
              }}
            >
              <span style={{ color: isActive ? "var(--brand-500)" : "var(--ink-500)" }}>
                {it.icon(20)}
              </span>
              <span style={{ flex: 1 }}>{it.label}</span>
              <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{it.sub}</span>
            </button>
          );
        })}
      </nav>

      <div style={{ flex: 1 }} />

      {/* Footer */}
      <div
        style={{
          padding: "12px",
          borderRadius: 12,
          background: "var(--surface-3)",
          fontSize: 11,
          color: "var(--ink-500)",
          lineHeight: 1.5,
        }}
      >
        <div style={{ fontWeight: 600, color: "var(--ink-700)", marginBottom: 4 }}>运帷 AI · 智通客户</div>
        基于 yunwei-tools 的客户档案智能整理。Phase 1 (mock data)
      </div>
    </aside>
  );
}
