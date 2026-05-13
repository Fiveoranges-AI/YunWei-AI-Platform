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
    <div className="tabbar" style={{ flexShrink: 0 }}>
      {LEFT.map((it) => (
        <TabItem key={it.id} item={it} active={active === it.id} onClick={() => onChange(it.id)} />
      ))}

      {/* Center FAB-style plus → opens upload */}
      <button
        className="tab"
        aria-label="添加资料"
        onClick={() => (onAdd ? onAdd() : onChange("upload"))}
      >
        <div className="tab-plus">{I.plus(20, "#fff")}</div>
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
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: active ? "var(--brand-500)" : "var(--ink-500)",
        }}
      >
        {item.icon(20)}
      </span>
      <span style={{ fontSize: 12, fontWeight: 600, lineHeight: 1 }}>{item.sub}</span>
    </button>
  );
}
