import type { ReactNode } from "react";
import { useIsDesktop } from "../lib/breakpoints";
import type { TabName } from "../App";
import { Sidebar } from "./Sidebar";
import { TabBar } from "./TabBar";

type Props = {
  activeTab: TabName;
  onTabChange: (t: TabName) => void;
  children: ReactNode;
};

export function AppShell({ activeTab, onTabChange, children }: Props) {
  const isDesktop = useIsDesktop();

  if (isDesktop) {
    return (
      <div
        style={{
          display: "flex",
          height: "100dvh",
          background: "var(--bg-2)",
        }}
      >
        <Sidebar active={activeTab} onChange={onTabChange} />
        <main
          style={{
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            position: "relative",
          }}
        >
          {children}
        </main>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100dvh",
        background: "var(--bg)",
      }}
    >
      <main
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}
      >
        {children}
      </main>
      <TabBar active={activeTab} onChange={onTabChange} />
    </div>
  );
}
