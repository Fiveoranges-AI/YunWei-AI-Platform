import type { GoFn } from "../App";
import { Mono } from "../components/Mono";
import { Section } from "../components/Section";
import { I } from "../icons";
import { useIsDesktop } from "../lib/breakpoints";

export function ProfileScreen({ go: _go }: { go: GoFn }) {
  const isDesktop = useIsDesktop();

  async function handleLogout() {
    try {
      await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
    } catch {
      /* ignore — clear the cookie locally regardless and let the platform
         re-prompt at "/" */
    }
    // Platform "/" serves login.html when there's no app_session cookie.
    window.location.href = "/";
  }

  return (
    <div className="screen" style={{ background: "var(--bg)" }}>
      {/* Top */}
      <div
        style={{
          padding: isDesktop ? "20px 32px 8px" : "8px 16px 8px",
          maxWidth: isDesktop ? 720 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        <div style={{ fontSize: 22, fontWeight: 700, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
          我的
        </div>
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "8px 32px 40px" : "4px 16px 100px",
          maxWidth: isDesktop ? 720 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {/* User card */}
        <div className="card" style={{ padding: 16, marginBottom: 16, display: "flex", alignItems: "center", gap: 14 }}>
          <Mono text="李" color="var(--brand-500)" size={56} radius={28} fontSize={22} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)" }}>李欣</div>
            <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 2 }}>
              销售助理 · 万华化学客户组
            </div>
          </div>
          <button
            style={{
              background: "var(--surface-3)",
              border: "1px solid var(--ink-100)",
              borderRadius: 10,
              padding: "8px 12px",
              fontSize: 12,
              color: "var(--ink-700)",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            编辑
          </button>
        </div>

        <Section title="账号设置">
          <div className="card" style={{ padding: "4px 0" }}>
            <ProfileRow icon={I.profile(16)} label="个人信息" />
            <Separator />
            <ProfileRow icon={I.bookmark(14)} label="收藏与标签" />
            <Separator />
            <ProfileRow icon={I.cash(16)} label="账单与计划" sub="基础版" />
          </div>
        </Section>

        <Section title="数据与同步">
          <div className="card" style={{ padding: "4px 0" }}>
            <ProfileRow icon={I.cloud(16)} label="自动同步" sub="每 4 小时" />
            <Separator />
            <ProfileRow icon={I.doc(16)} label="导出数据" />
            <Separator />
            <ProfileRow icon={I.warn(16)} label="清理 AI 提取记录" />
          </div>
        </Section>

        <Section title="通知">
          <div className="card" style={{ padding: "4px 0" }}>
            <ProfileRow icon={I.task(16)} label="待办提醒" sub="开启" />
            <Separator />
            <ProfileRow icon={I.warn(16)} label="风险线索预警" sub="开启" />
            <Separator />
            <ProfileRow icon={I.hand(16)} label="承诺到期提醒" sub="提前 3 天" />
          </div>
        </Section>

        <Section title="关于">
          <div className="card" style={{ padding: "4px 0" }}>
            <ProfileRow icon={I.spark(15)} label="智通客户" sub="v0.1.0 · Phase 1" />
            <Separator />
            <ProfileRow icon={I.link(14)} label="帮助文档" />
            <Separator />
            <ProfileRow icon={I.chat(16)} label="意见反馈" />
          </div>
        </Section>

        <button
          className="btn btn-secondary"
          onClick={handleLogout}
          style={{
            width: "100%",
            marginTop: 12,
            color: "var(--risk-500)",
            background: "var(--risk-100)",
            border: "1px solid #f4cfcf",
          }}
        >
          退出登录
        </button>
      </div>
    </div>
  );
}

function ProfileRow({
  icon,
  label,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  sub?: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 14px" }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 10,
          background: "var(--surface-3)",
          color: "var(--ink-700)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink-900)" }}>{label}</div>
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--ink-500)" }}>{sub}</div>}
      <span style={{ color: "var(--ink-400)" }}>{I.chev(14)}</span>
    </div>
  );
}

function Separator() {
  return <div style={{ height: 1, background: "var(--ink-100)", marginLeft: 58 }} />;
}
