import { I } from "../icons";
import type { TabName } from "../App";

const ITEMS: { id: TabName; sub: string; icon: (s?: number, c?: string) => JSX.Element }[] = [
  { id: "customers", sub: "客户", icon: I.customers },
  { id: "upload", sub: "添加", icon: I.upload },
  { id: "ask", sub: "问 AI", icon: I.ask },
  { id: "profile", sub: "我的", icon: I.profile },
];

type Props = {
  active: TabName;
  onChange: (t: TabName) => void;
};

export function TabBar({ active, onChange }: Props) {
  return (
    <div
      className="tabbar"
      style={{
        flexShrink: 0,
        paddingBottom: "calc(24px + env(safe-area-inset-bottom))",
      }}
    >
      {ITEMS.map((it) => {
        const isActive = active === it.id;
        return (
          <button
            key={it.id}
            className={`tab ${isActive ? "active" : ""}`}
            onClick={() => onChange(it.id)}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "4px 10px",
                borderRadius: 10,
                background: isActive ? "var(--brand-50)" : "transparent",
                color: isActive ? "var(--brand-500)" : "var(--ink-500)",
              }}
            >
              {it.icon(20)}
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, marginTop: 1 }}>{it.sub}</div>
          </button>
        );
      })}
    </div>
  );
}
