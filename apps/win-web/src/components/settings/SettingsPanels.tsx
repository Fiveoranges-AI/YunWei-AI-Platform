// The seven 设置 panels, each opened from a row on the Profile screen.
// Backend-backed where an endpoint exists (编辑 / 账号与安全 / 团队·权限 /
// 清理 AI 提取记录), device-local where there's no endpoint (提醒设置 /
// 自动同步), and fully client-side for 数据导出.

import { useEffect, useState } from "react";
import {
  changePassword,
  listCustomers,
  listEnterpriseMembers,
  updateMe,
  type CurrentUser,
  type EnterpriseMember,
} from "../../api/client";
import { deleteIngestJob, listIngestJobs } from "../../api/ingest";
import type { CustomerDetail, IngestJob } from "../../data/types";
import { exportCustomersBackup, exportCustomersCsv, printCustomers } from "../../lib/exportData";
import {
  AUTO_SYNC_OPTIONS,
  REMINDER_LABELS,
  loadPrefs,
  savePrefs,
  type AutoSyncFreq,
  type ReminderPrefs,
} from "../../lib/settingsPrefs";
import { I } from "../../icons";
import { Banner, Btn, Field, SettingsSheet, TextInput, Toggle } from "./SettingsSheet";

function roleLabel(role: string | null | undefined): string {
  switch (role) {
    case "owner":
      return "所有者";
    case "admin":
      return "管理员";
    case "member":
      return "成员";
    case "platform_admin":
      return "平台管理员";
    default:
      return role || "成员";
  }
}

const errMsg = (e: unknown) => (e instanceof Error ? e.message : "操作失败，请稍后再试");

// ─── 1. 编辑资料 ─────────────────────────────────────────────────

export function EditProfilePanel({
  me,
  onSaved,
  onClose,
}: {
  me: CurrentUser;
  onSaved: (displayName: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState((me.display_name || me.username || "").trim());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = name.trim();
  const dirty = trimmed !== (me.display_name || me.username || "").trim();
  const valid = trimmed.length >= 1 && trimmed.length <= 64;

  async function save() {
    if (!valid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const res = await updateMe(trimmed);
      onSaved(res.display_name);
      onClose();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <SettingsSheet
      title="编辑资料"
      subtitle="修改你的显示名称"
      onClose={onClose}
      footer={
        <>
          <Btn onClick={onClose} style={{ flex: 1 }}>
            取消
          </Btn>
          <Btn variant="primary" onClick={save} disabled={!valid || !dirty || saving} style={{ flex: 1 }}>
            {saving ? "保存中…" : "保存"}
          </Btn>
        </>
      }
    >
      {error && <Banner kind="error" text={error} />}
      <Field label="显示名称" hint="1–64 个字符，用于团队与提醒中的署名">
        <TextInput
          value={name}
          maxLength={64}
          autoFocus
          placeholder="输入显示名称"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
          }}
        />
      </Field>
      <Field label="用户名">
        <TextInput value={me.username} disabled style={{ background: "var(--surface-3)", color: "var(--ink-500)" }} />
      </Field>
    </SettingsSheet>
  );
}

// ─── 2. 账号与安全 ───────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, padding: "9px 0", borderBottom: "1px solid var(--ink-100)" }}>
      <span style={{ fontSize: 13, color: "var(--ink-500)", flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, color: "var(--ink-900)", fontWeight: 500, textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {value}
      </span>
    </div>
  );
}

export function AccountSecurityPanel({ me, onClose }: { me: CurrentUser; onClose: () => void }) {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const enterprise = me.enterprises?.[0];
  const canSubmit = cur.length > 0 && next.length >= 8 && next === confirm && !saving;

  async function submit() {
    setError(null);
    if (next.length < 8) return setError("新密码至少 8 位");
    if (next !== confirm) return setError("两次输入的新密码不一致");
    setSaving(true);
    try {
      await changePassword(cur, next);
      setDone(true);
      setCur("");
      setNext("");
      setConfirm("");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <SettingsSheet
      title="账号与安全"
      subtitle="账号信息与密码"
      onClose={onClose}
      footer={
        <Btn onClick={onClose} style={{ flex: 1 }}>
          关闭
        </Btn>
      }
    >
      <div style={{ marginBottom: 18 }}>
        <InfoRow label="用户名" value={me.username} />
        <InfoRow label="显示名称" value={me.display_name || me.username} />
        {enterprise && <InfoRow label="所属企业" value={enterprise.display_name || enterprise.legal_name || enterprise.id} />}
        {enterprise && <InfoRow label="角色" value={roleLabel(enterprise.role)} />}
        {me.is_platform_admin && <InfoRow label="平台权限" value="平台管理员" />}
      </div>

      <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)", margin: "4px 0 12px" }}>修改密码</div>
      {done && <Banner kind="success" text="密码已更新，其他设备已退出登录。" />}
      {error && <Banner kind="error" text={error} />}
      <Field label="当前密码">
        <TextInput type="password" value={cur} autoComplete="current-password" placeholder="输入当前密码" onChange={(e) => setCur(e.target.value)} />
      </Field>
      <Field label="新密码" hint="至少 8 位">
        <TextInput type="password" value={next} autoComplete="new-password" placeholder="输入新密码" onChange={(e) => setNext(e.target.value)} />
      </Field>
      <Field label="确认新密码">
        <TextInput type="password" value={confirm} autoComplete="new-password" placeholder="再次输入新密码" onChange={(e) => setConfirm(e.target.value)} onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()} />
      </Field>
      <Btn variant="primary" onClick={submit} disabled={!canSubmit} style={{ width: "100%" }}>
        {saving ? "更新中…" : "更新密码"}
      </Btn>
    </SettingsSheet>
  );
}

// ─── 3. 团队 · 权限 ──────────────────────────────────────────────

export function TeamPanel({
  enterpriseId,
  enterpriseName,
  myUserId,
  onClose,
}: {
  enterpriseId: string | null;
  enterpriseName: string;
  myUserId: string;
  onClose: () => void;
}) {
  const [members, setMembers] = useState<EnterpriseMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enterpriseId) {
      setError("当前账号未绑定企业。");
      return;
    }
    let cancelled = false;
    listEnterpriseMembers(enterpriseId)
      .then((m) => !cancelled && setMembers(m))
      .catch((e) => !cancelled && setError(errMsg(e)));
    return () => {
      cancelled = true;
    };
  }, [enterpriseId]);

  return (
    <SettingsSheet
      title="团队 · 权限"
      subtitle={enterpriseName || "企业成员"}
      onClose={onClose}
      footer={
        <Btn onClick={onClose} style={{ flex: 1 }}>
          关闭
        </Btn>
      }
    >
      {error && <Banner kind="info" text={error} />}
      {!error && members === null && (
        <div style={{ fontSize: 13, color: "var(--ink-500)", padding: "12px 0" }}>正在加载成员…</div>
      )}
      {members && members.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--ink-500)", padding: "12px 0" }}>暂无成员。</div>
      )}
      {members?.map((m) => {
        const display = (m.display_name || m.username || "").trim();
        return (
          <div key={m.user_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid var(--ink-100)" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 18,
                background: "linear-gradient(140deg,#5BB5E4,#2680CC)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {display.slice(0, 1).toUpperCase() || "?"}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--ink-900)" }}>
                {display || m.username}
                {m.user_id === myUserId && (
                  <span style={{ fontSize: 11, color: "var(--ink-400)", fontWeight: 500, marginLeft: 6 }}>（我）</span>
                )}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 1 }}>{m.username}</div>
            </div>
            <span
              style={{
                fontSize: 11.5,
                fontWeight: 600,
                color: m.role === "owner" ? "#a9690c" : "var(--ink-600)",
                background: m.role === "owner" ? "#fcf1dd" : "var(--surface-3)",
                padding: "3px 9px",
                borderRadius: 20,
                flexShrink: 0,
              }}
            >
              {roleLabel(m.role)}
            </span>
          </div>
        );
      })}
    </SettingsSheet>
  );
}

// ─── 4. 提醒设置 ─────────────────────────────────────────────────

export function RemindersPanel({
  userId,
  onChanged,
  onClose,
}: {
  userId: string;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [reminders, setReminders] = useState<ReminderPrefs>(() => loadPrefs(userId).reminders);

  function toggle(key: keyof ReminderPrefs, value: boolean) {
    // Derive from the freshly-persisted prefs (not the closure) so rapid
    // toggles don't clobber each other with stale state.
    const prefs = loadPrefs(userId);
    const nextReminders = { ...prefs.reminders, [key]: value };
    savePrefs(userId, { ...prefs, reminders: nextReminders });
    setReminders(nextReminders);
    onChanged();
  }

  return (
    <SettingsSheet
      title="提醒设置"
      subtitle="选择需要主动提醒的事项"
      onClose={onClose}
      footer={
        <Btn variant="primary" onClick={onClose} style={{ flex: 1 }}>
          完成
        </Btn>
      }
    >
      {REMINDER_LABELS.map((r, i) => (
        <div
          key={r.key}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "13px 0",
            borderBottom: i < REMINDER_LABELS.length - 1 ? "1px solid var(--ink-100)" : "none",
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{r.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>{r.hint}</div>
          </div>
          <Toggle on={reminders[r.key]} onChange={(v) => toggle(r.key, v)} />
        </div>
      ))}
    </SettingsSheet>
  );
}

// ─── 5. 自动同步 ─────────────────────────────────────────────────

export function AutoSyncPanel({
  userId,
  onChanged,
  onClose,
}: {
  userId: string;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [freq, setFreq] = useState<AutoSyncFreq>(() => loadPrefs(userId).autoSync);

  function pick(value: AutoSyncFreq) {
    setFreq(value);
    const prefs = loadPrefs(userId);
    savePrefs(userId, { ...prefs, autoSync: value });
    onChanged();
  }

  return (
    <SettingsSheet
      title="自动同步"
      subtitle="自动刷新与提醒的频率"
      onClose={onClose}
      footer={
        <Btn variant="primary" onClick={onClose} style={{ flex: 1 }}>
          完成
        </Btn>
      }
    >
      <Banner kind="info" text="此为本机偏好，控制客户数据自动刷新与提醒的检查频率。" />
      {AUTO_SYNC_OPTIONS.map((opt, i) => (
        <button
          key={opt.value}
          onClick={() => pick(opt.value)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "13px 2px",
            background: "transparent",
            border: "none",
            borderBottom: i < AUTO_SYNC_OPTIONS.length - 1 ? "1px solid var(--ink-100)" : "none",
            cursor: "pointer",
            fontFamily: "var(--font)",
            textAlign: "left",
          }}
        >
          <span style={{ flex: 1, fontSize: 14, fontWeight: freq === opt.value ? 700 : 500, color: "var(--ink-900)" }}>
            {opt.label}
          </span>
          {freq === opt.value && <span style={{ color: "var(--brand-500, #2680CC)" }}>{I.check(18)}</span>}
        </button>
      ))}
    </SettingsSheet>
  );
}

// ─── 6. 数据导出 ─────────────────────────────────────────────────

export function DataExportPanel({ onClose }: { onClose: () => void }) {
  const [customers, setCustomers] = useState<CustomerDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCustomers()
      .then((c) => !cancelled && setCustomers(c))
      .catch((e) => !cancelled && setError(errMsg(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = customers !== null;
  const count = customers?.length ?? 0;

  const actions: { label: string; sub: string; icon: React.ReactNode; run: () => void }[] = [
    { label: "导出 CSV", sub: "客户名单表格，可用 Excel 打开", icon: I.doc(16), run: () => customers && exportCustomersCsv(customers) },
    { label: "导出备份", sub: "完整客户数据 JSON 备份", icon: I.cloud(16), run: () => customers && exportCustomersBackup(customers) },
    {
      label: "导出 PDF",
      sub: "打印友好的名单，可存为 PDF",
      icon: I.doc(16),
      run: () => {
        if (customers && !printCustomers(customers)) setHint("浏览器拦截了弹出窗口，请允许后重试。");
      },
    },
  ];

  return (
    <SettingsSheet
      title="数据导出"
      subtitle={ready ? `共 ${count} 家客户` : "正在准备数据…"}
      onClose={onClose}
      footer={
        <Btn onClick={onClose} style={{ flex: 1 }}>
          关闭
        </Btn>
      }
    >
      {error && <Banner kind="error" text={error} />}
      {hint && <Banner kind="info" text={hint} />}
      {actions.map((a, i) => (
        <button
          key={a.label}
          onClick={a.run}
          disabled={!ready || count === 0}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "13px 0",
            background: "transparent",
            border: "none",
            borderBottom: i < actions.length - 1 ? "1px solid var(--ink-100)" : "none",
            cursor: !ready || count === 0 ? "not-allowed" : "pointer",
            opacity: !ready || count === 0 ? 0.5 : 1,
            fontFamily: "var(--font)",
            textAlign: "left",
          }}
        >
          <div style={{ width: 34, height: 34, borderRadius: 9, background: "var(--surface-3)", color: "var(--ink-600)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            {a.icon}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-900)" }}>{a.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>{a.sub}</div>
          </div>
          <span style={{ color: "var(--ink-300)" }}>{I.chev(15)}</span>
        </button>
      ))}
      {ready && count === 0 && <div style={{ fontSize: 12.5, color: "var(--ink-400)", marginTop: 12 }}>暂无客户数据可导出。</div>}
    </SettingsSheet>
  );
}

// ─── 7. 清理 AI 提取记录 ─────────────────────────────────────────

const JOB_STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  extracted: "待确认",
  confirmed: "已确认",
  failed: "失败",
  canceled: "已取消",
};

export function ClearExtractionsPanel({ onClose }: { onClose: () => void }) {
  const [jobs, setJobs] = useState<IngestJob[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"list" | "confirm" | "deleting" | "done">("list");
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ deleted: number; skipped: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    listIngestJobs("history", 200)
      .then((j) => !cancelled && setJobs(j))
      .catch((e) => !cancelled && setError(errMsg(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  async function runClear() {
    if (!jobs) return;
    setPhase("deleting");
    let deleted = 0;
    let skipped = 0;
    for (const job of jobs) {
      try {
        await deleteIngestJob(job.id);
        deleted += 1;
      } catch {
        skipped += 1;
      }
      setProgress(deleted + skipped);
    }
    setResult({ deleted, skipped });
    setPhase("done");
  }

  const count = jobs?.length ?? 0;

  return (
    <SettingsSheet
      title="清理 AI 提取记录"
      subtitle="删除历史识别 / 提取任务记录"
      onClose={onClose}
      footer={
        phase === "done" ? (
          <Btn variant="primary" onClick={onClose} style={{ flex: 1 }}>
            完成
          </Btn>
        ) : phase === "confirm" ? (
          <>
            <Btn onClick={() => setPhase("list")} style={{ flex: 1 }}>
              取消
            </Btn>
            <Btn variant="danger" onClick={runClear} style={{ flex: 1 }}>
              确认清理 {count} 条
            </Btn>
          </>
        ) : (
          <Btn
            variant="danger"
            onClick={() => setPhase("confirm")}
            disabled={!jobs || count === 0 || phase === "deleting"}
            style={{ flex: 1 }}
          >
            清理 {count > 0 ? `${count} 条记录` : "记录"}
          </Btn>
        )
      }
    >
      {error && <Banner kind="info" text={`无法读取提取记录：${error}`} />}
      {!error && jobs === null && <div style={{ fontSize: 13, color: "var(--ink-500)", padding: "12px 0" }}>正在统计…</div>}

      {phase === "confirm" && (
        <Banner kind="error" text={`将永久删除 ${count} 条历史提取记录，此操作不可撤销。已确认归档的客户数据不受影响。`} />
      )}
      {phase === "deleting" && (
        <Banner kind="info" text={`正在清理… ${progress}/${count}`} />
      )}
      {phase === "done" && result && (
        <Banner kind="success" text={`已清理 ${result.deleted} 条${result.skipped ? `，跳过 ${result.skipped} 条（不可删除）` : ""}。`} />
      )}

      {jobs && count === 0 && phase !== "done" && (
        <div style={{ fontSize: 13, color: "var(--ink-500)", padding: "12px 0" }}>没有可清理的历史提取记录。</div>
      )}

      {jobs && count > 0 && phase !== "done" && (
        <div style={{ marginTop: 4 }}>
          {jobs.slice(0, 12).map((j) => (
            <div key={j.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderBottom: "1px solid var(--ink-100)" }}>
              <span style={{ color: "var(--ink-400)" }}>{I.doc(15)}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, color: "var(--ink-900)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {j.original_filename || j.source_hint || j.id.slice(0, 8)}
                </div>
              </div>
              <span style={{ fontSize: 11, color: "var(--ink-400)", flexShrink: 0 }}>{JOB_STATUS_LABEL[j.status] || j.status}</span>
            </div>
          ))}
          {count > 12 && <div style={{ fontSize: 11.5, color: "var(--ink-400)", marginTop: 8 }}>…等共 {count} 条</div>}
        </div>
      )}
    </SettingsSheet>
  );
}
