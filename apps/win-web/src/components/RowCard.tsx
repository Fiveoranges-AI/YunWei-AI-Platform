import type { ReactNode } from "react";

type Props = {
  icon: ReactNode;
  iconBg: string;
  iconColor: string;
  children: ReactNode;
};

export function RowCard({ icon, iconBg, iconColor, children }: Props) {
  return (
    <div
      className="card"
      style={{ padding: 12, marginBottom: 8, display: "flex", gap: 12, alignItems: "flex-start" }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 10,
          background: iconBg,
          color: iconColor,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  );
}
