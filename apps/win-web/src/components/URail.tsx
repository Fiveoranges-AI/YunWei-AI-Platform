import { I } from "../icons";
import type { TabName } from "../App";

type Item = {
  id: TabName;
  label: string;
  icon: (s?: number, c?: string) => JSX.Element;
};

const ITEMS: Item[] = [
  { id: "customers", label: "客户", icon: I.customers },
  { id: "inbox", label: "上传记录", icon: I.layers },
  { id: "ask", label: "AI 助手", icon: I.ask },
  { id: "jintai", label: "锦泰试点", icon: I.bulb },
  { id: "profile", label: "我的", icon: I.profile },
];

type Props = {
  active: TabName;
  onChange: (t: TabName) => void;
  onAdd: () => void;
  avatarInitial?: string;
  compact?: boolean;
};

export function URail({ active, onChange, onAdd, avatarInitial = "?", compact: _compact = false }: Props) {
  return (
    <aside
      style={{
        width: 64,
        height: "100%",
        flexShrink: 0,
        background: "var(--navy-900)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: 18,
        paddingBottom: 16,
      }}
    >
      {/* Primary CTA — 添加资料 */}
      <button
        onClick={onAdd}
        title="添加资料"
        aria-label="添加资料"
        style={{
          width: 40,
          height: 40,
          borderRadius: 11,
          background: "linear-gradient(140deg, #5BB5E4 0%, #2680CC 100%)",
          color: "#fff",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow:
            "0 4px 14px rgba(45,155,216,0.40), 0 0 0 1px rgba(91,181,228,0.35) inset",
          marginBottom: 8,
        }}
      >
        {I.plus(22, "#fff")}
      </button>

      {/* Separator */}
      <div
        style={{
          width: 24,
          height: 1,
          background: "rgba(255,255,255,0.08)",
          margin: "8px 0 14px",
        }}
      />

      {/* Nav */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
        {ITEMS.map((it) => {
          const isActive = it.id === active;
          return (
            <button
              key={it.id}
              onClick={() => onChange(it.id)}
              title={it.label}
              aria-label={it.label}
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: isActive ? "rgba(91,181,228,0.18)" : "transparent",
                color: isActive ? "#DCEDF8" : "#6B7C99",
                border: isActive ? "1px solid rgba(91,181,228,0.28)" : "1px solid transparent",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                transition: "background 120ms ease, color 120ms ease",
              }}
            >
              {it.icon(20)}
            </button>
          );
        })}
      </div>

      {/* Bottom: avatar */}
      <button
        onClick={() => onChange("profile")}
        aria-label="个人"
        style={{
          width: 32,
          height: 32,
          borderRadius: 16,
          border: "none",
          cursor: "pointer",
          background: "#1F5FA3",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 700,
        }}
      >
        {avatarInitial}
      </button>
    </aside>
  );
}
