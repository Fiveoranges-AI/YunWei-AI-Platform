import { I } from "../icons";
import type { TabName } from "../App";

type SideItem = {
  id: TabName;
  sub: string;
  icon: (s?: number, c?: string) => JSX.Element;
};

const LEFT: SideItem[] = [
  { id: "customers", sub: "客户", icon: I.customers },
  { id: "inbox", sub: "上传记录", icon: I.layers },
];

const RIGHT: SideItem[] = [
  { id: "ask", sub: "AI 助手", icon: I.ask },
  { id: "profile", sub: "我的", icon: I.profile },
];

type Props = {
  active: TabName;
  onChange: (t: TabName) => void;
  onAdd?: () => void;
};

export function TabBar({ active, onChange, onAdd }: Props) {
  return (
    <div
      className="tabbar"
      style={{
        flexShrink: 0,
        paddingBottom: "calc(24px + env(safe-area-inset-bottom))",
      }}
    >
      {LEFT.map((it) => (
        <TabItem key={it.id} item={it} active={active === it.id} onClick={() => onChange(it.id)} />
      ))}

      {/* Center FAB-style plus → opens upload */}
      <button
        className="tab"
        aria-label="添加资料"
        onClick={() => (onAdd ? onAdd() : onChange("upload"))}
        style={{ paddingTop: 0 }}
      >
        <div className="tab-plus">{I.plus(22, "#fff")}</div>
      </button>

      {RIGHT.map((it) => (
        <TabItem key={it.id} item={it} active={active === it.id} onClick={() => onChange(it.id)} />
      ))}
    </div>
  );
}

function TabItem({
  item,
  active,
  onClick,
}: {
  item: SideItem;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`tab ${active ? "active" : ""}`} onClick={onClick}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "4px 10px",
          borderRadius: 10,
          background: active ? "var(--brand-50)" : "transparent",
          color: active ? "var(--brand-500)" : "var(--ink-500)",
        }}
      >
        {item.icon(20)}
      </div>
      <div style={{ fontSize: 10, fontWeight: 600, marginTop: 1 }}>{item.sub}</div>
    </button>
  );
}
