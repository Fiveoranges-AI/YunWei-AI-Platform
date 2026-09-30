import { useEffect, useState, type ReactNode } from "react";
import type { GoFn } from "../App";
import { getMe, type CurrentUser } from "../api/client";
import { I } from "../icons";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";
import {
  autoSyncLabel,
  loadPrefs,
  reminderSummary,
  type SettingsPrefs,
} from "../lib/settingsPrefs";
import {
  AccountSecurityPanel,
  AutoSyncPanel,
  ClearExtractionsPanel,
  DataExportPanel,
  EditProfilePanel,
  RemindersPanel,
  TeamPanel,
} from "../components/settings/SettingsPanels";

type PanelKey = "edit" | "account" | "team" | "reminders" | "autosync" | "export" | "clear";

export function ProfileScreen({ go: _go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [openPanel, setOpenPanel] = useState<PanelKey | null>(null);
  const [prefs, setPrefs] = useState<SettingsPrefs>(() => loadPrefs(""));

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((user) => {
        if (!cancelled) {
          setMe(user);
          setPrefs(loadPrefs(user.id));
        }
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "账号信息加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const userId = me?.id ?? "";
  const refreshPrefs = () => setPrefs(loadPrefs(userId));

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } catch {
      /* fall through */
    }
    window.location.href = "/";
  }

  const displayName = (me?.display_name || me?.username || "").trim();
  const profileName = displayName || (loadError ? "账号信息不可用" : "加载中");
  const initial = displayName.slice(0, 1).toUpperCase() || (loadError ? "!" : "?");
  const enterprise = me?.enterprises?.[0] ?? null;
  const enterpriseName = (
    enterprise?.display_name ||
    enterprise?.legal_name ||
    enterprise?.id ||
    ""
  ).trim();
  const role = roleLabel(enterprise?.role);
  const subtitle = loadError
    ? "无法读取登录用户"
    : enterpriseName
      ? `${role} · ${enterpriseName}`
      : me
        ? "未绑定企业"
        : "正在读取真实账号";

  const settings: {
    icon: ReactNode;
    label: string;
    sub?: string;
    onClick: () => void;
    disabled?: boolean;
  }[] = [
    {
      icon: I.shield(16),
      label: "账号与安全",
      sub: me?.username,
      onClick: () => me && setOpenPanel("account"),
      disabled: !me,
    },
    {
      icon: I.layers(16),
      label: "团队 · 权限",
      sub: enterpriseName || "未绑定企业",
      onClick: () => me && setOpenPanel("team"),
      disabled: !me,
    },
    {
      icon: I.bookmark(14),
      label: "提醒设置",
      sub: reminderSummary(prefs.reminders),
      onClick: () => setOpenPanel("reminders"),
    },
    {
      icon: I.cloud(16),
      label: "自动同步",
      sub: autoSyncLabel(prefs.autoSync),
      onClick: () => setOpenPanel("autosync"),
    },
    {
      icon: I.doc(16),
      label: "数据导出",
      sub: "导出 CSV · PDF · 备份",
      onClick: () => setOpenPanel("export"),
    },
    {
      icon: I.warn(16),
      label: "清理 AI 提取记录",
      onClick: () => setOpenPanel("clear"),
    },
  ];

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        background: "var(--surface-2)",
      }}
    >
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: isWide ? "40px 32px" : "16px 16px 100px",
        }}
      >
        {/* Profile header card */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "20px 22px",
            borderRadius: 14,
            background: "#fff",
            border: "1px solid var(--ink-100)",
            marginBottom: 24,
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              background: "linear-gradient(140deg, #5BB5E4, #2680CC)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {initial}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--ink-900)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {profileName}
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: "var(--ink-500)",
                marginTop: 3,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {subtitle}
            </div>
          </div>
          <button
            onClick={() => me && setOpenPanel("edit")}
            disabled={!me}
            style={{
              height: 36,
              padding: "0 14px",
              borderRadius: 8,
              background: "#fff",
              color: "var(--ink-800)",
              border: "1px solid var(--ink-200)",
              fontSize: 13,
              fontWeight: 600,
              cursor: me ? "pointer" : "not-allowed",
              opacity: me ? 1 : 0.5,
              fontFamily: "var(--font)",
            }}
          >
            编辑
          </button>
        </div>

        {/* External app: 超级小陈 */}
        <a
          href="https://agent-yinhu-super-xiaochen-production.up.railway.app"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "14px 18px",
            borderRadius: 14,
            background: "linear-gradient(135deg,#eaeefc,#d6deff)",
            border: "1px solid #dfe5fb",
            marginBottom: 16,
            textDecoration: "none",
            color: "inherit",
          }}
        >
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: "#fff",
              color: "#4a60c4",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {I.spark(18, "#4a60c4")}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#2c3a78" }}>超级小陈</div>
            <div style={{ fontSize: 11.5, color: "#4a60c4", marginTop: 2 }}>
              银湖 · Kingdee ERP 智能体 · 新窗口打开
            </div>
          </div>
          <span style={{ color: "#4a60c4" }}>{I.link(14, "#4a60c4")}</span>
        </a>

        {/* Settings list */}
        <div
          style={{
            background: "#fff",
            border: "1px solid var(--ink-100)",
            borderRadius: 14,
            overflow: "hidden",
          }}
        >
          {settings.map((it, i) => (
            <button
              key={it.label}
              onClick={it.onClick}
              disabled={it.disabled}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "14px 18px",
                background: "transparent",
                border: "none",
                borderBottom: i < settings.length - 1 ? "1px solid var(--ink-100)" : "none",
                cursor: it.disabled ? "not-allowed" : "pointer",
                opacity: it.disabled ? 0.5 : 1,
                textAlign: "left",
                fontFamily: "var(--font)",
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 9,
                  background: "var(--surface-3)",
                  color: "var(--ink-600)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {it.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{it.label}</div>
                {it.sub && (
                  <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>{it.sub}</div>
                )}
              </div>
              <span style={{ color: "var(--ink-300)" }}>{I.chev(15)}</span>
            </button>
          ))}
        </div>

        <button
          onClick={handleLogout}
          style={{
            width: "100%",
            marginTop: 16,
            height: 44,
            borderRadius: 10,
            border: "1px solid #f4cfcf",
            background: "var(--risk-100)",
            color: "var(--risk-700)",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          退出登录
        </button>

        <div
          style={{
            marginTop: 28,
            textAlign: "center",
            fontSize: 11.5,
            color: "var(--ink-400)",
          }}
        >
          v0.1.0 · Five Oranges AI · 智通客户
        </div>
      </div>

      {openPanel === "edit" && me && (
        <EditProfilePanel
          me={me}
          onSaved={(name) => setMe((prev) => (prev ? { ...prev, display_name: name } : prev))}
          onClose={() => setOpenPanel(null)}
        />
      )}
      {openPanel === "account" && me && (
        <AccountSecurityPanel me={me} onClose={() => setOpenPanel(null)} />
      )}
      {openPanel === "team" && me && (
        <TeamPanel
          enterpriseId={enterprise?.id ?? null}
          enterpriseName={enterpriseName}
          myUserId={me.id}
          onClose={() => setOpenPanel(null)}
        />
      )}
      {openPanel === "reminders" && (
        <RemindersPanel userId={userId} onChanged={refreshPrefs} onClose={() => setOpenPanel(null)} />
      )}
      {openPanel === "autosync" && (
        <AutoSyncPanel userId={userId} onChanged={refreshPrefs} onClose={() => setOpenPanel(null)} />
      )}
      {openPanel === "export" && <DataExportPanel onClose={() => setOpenPanel(null)} />}
      {openPanel === "clear" && <ClearExtractionsPanel onClose={() => setOpenPanel(null)} />}
    </div>
  );
}

function roleLabel(role: string | null | undefined): string {
  switch (role) {
    case "owner":
      return "所有者";
    case "admin":
      return "管理员";
    case "member":
      return "成员";
    default:
      return role || "成员";
  }
}
