import { useEffect, useState, type ReactNode } from "react";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";
import { getMe } from "../api/client";
import type { ScreenName, TabName } from "../App";
import { URail } from "./URail";
import { UHeader } from "./UHeader";
import { TabBar } from "./TabBar";

type Props = {
  activeTab: TabName;
  onTabChange: (t: TabName) => void;
  currentScreen: ScreenName;
  onAdd: () => void;
  children: ReactNode;
};

type ViewMeta = { title: string; sub: string };

const VIEW_META: Record<TabName, ViewMeta> = {
  customers: { title: "客户经营档案", sub: "AI 客户摘要 · 风险 · 规格记忆" },
  inbox: { title: "上传记录", sub: "AI 抽取队列 · 待确认 · 历史" },
  upload: { title: "添加资料", sub: "AI 自动归类匹配" },
  ask: { title: "AI 助手", sub: "基于客户档案问答 · 来源可追溯" },
  profile: { title: "我的", sub: "账号 · 团队 · 设置" },
};

export function AppShell({ activeTab, onTabChange, currentScreen, onAdd, children }: Props) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;
  const [avatarInitial, setAvatarInitial] = useState<string>("?");

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((u) => {
        if (cancelled) return;
        const name = (u.display_name || u.username || "").trim();
        if (name) setAvatarInitial(name.slice(0, 1).toUpperCase());
      })
      .catch(() => {
        /* keep fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Detail / review are sub-screens of a tab; header still reads from the tab.
  const meta = VIEW_META[activeTab];

  if (isWide) {
    return (
      <div
        style={{
          display: "flex",
          height: "100dvh",
          background: "#fff",
          fontFamily: "var(--font)",
        }}
      >
        <URail
          active={activeTab}
          onChange={onTabChange}
          onAdd={onAdd}
          avatarInitial={avatarInitial}
          compact={isTablet}
        />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <UHeader
            title={meta.title}
            sub={meta.sub}
            view={activeTab}
            compact={isTablet}
          />
          <main
            style={{
              flex: 1,
              minWidth: 0,
              minHeight: 0,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
              position: "relative",
              background: detailLikeBackground(currentScreen),
            }}
          >
            {children}
          </main>
        </div>
      </div>
    );
  }

  // Mobile: no rail/header — each screen renders its own top bar; bottom tab bar.
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
      <TabBar active={activeTab} onChange={onTabChange} onAdd={onAdd} />
    </div>
  );
}

function detailLikeBackground(screen: ScreenName): string {
  // Upload + profile + ask use a softer surface; list/detail/inbox are white.
  if (screen === "upload" || screen === "profile") return "var(--surface-2)";
  if (screen === "ask") return "var(--surface-2)";
  return "#fff";
}
