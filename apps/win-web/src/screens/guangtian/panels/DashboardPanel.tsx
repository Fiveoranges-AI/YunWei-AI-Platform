// G3 占位 — 将在下一轮填充
type Props = { onGoTab: (key: string) => void };
export function DashboardPanel(_props: Props) {
  return <div style={{ padding: 24, color: "var(--ink-400)" }}>工作台 · 待 iter G3 填充</div>;
}
