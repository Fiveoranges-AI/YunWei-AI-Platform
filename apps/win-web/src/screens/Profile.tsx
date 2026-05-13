import { useEffect, useState, type ReactNode } from "react";
import type { GoFn } from "../App";
import { getMe, type CurrentUser } from "../api/client";
import { I } from "../icons";
import { useIsDesktop, useIsTablet } from "../lib/breakpoints";

export function ProfileScreen({ go: _go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();
  const isTablet = useIsTablet();
  const isWide = isDesktop || isTablet;
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "账号信息加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const settings: { icon: ReactNode; label: string; sub?: string }[] = [
    { icon: I.shield(16), label: "账号与安全", sub: me?.username },
    { icon: I.layers(16), label: "团队 · 权限", sub: enterpriseName ? `${enterpriseName}` : "未绑定企业" },
    { icon: I.bookmark(14), label: "提醒设置", sub: "回款 · 风险 · 续约 · 规格" },
    { icon: I.cloud(16), label: "自动同步", sub: "每 4 小时" },
    { icon: I.doc(16), label: "数据导出", sub: "导出 CSV · PDF · 备份" },
    { icon: I.warn(16), label: "清理 AI 提取记录" },
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
            style={{
              height: 36,
              padding: "0 14px",
              borderRadius: 8,
              background: "#fff",
              color: "var(--ink-800)",
              border: "1px solid var(--ink-200)",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            编辑
          </button>
        </div>

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
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "14px 18px",
                background: "transparent",
                border: "none",
                borderBottom: i < settings.length - 1 ? "1px solid var(--ink-100)" : "none",
                cursor: "pointer",
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
