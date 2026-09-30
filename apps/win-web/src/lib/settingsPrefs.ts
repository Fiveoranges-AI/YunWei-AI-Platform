// Per-user UI preferences for the 设置 page (提醒设置 + 自动同步).
//
// There's no backend settings endpoint, so these are device-local
// preferences persisted to localStorage, keyed by user id. They drive the
// row subtitles on the Profile screen and the toggle/selector panels.

export type ReminderKey = "payment" | "risk" | "renewal" | "spec";
export type ReminderPrefs = Record<ReminderKey, boolean>;
export type AutoSyncFreq = "off" | "1h" | "4h" | "12h" | "24h";

export type SettingsPrefs = {
  reminders: ReminderPrefs;
  autoSync: AutoSyncFreq;
};

export const REMINDER_LABELS: { key: ReminderKey; label: string; hint: string }[] = [
  { key: "payment", label: "回款提醒", hint: "应收账款到期前提醒" },
  { key: "risk", label: "风险预警", hint: "客户风险升级时提醒" },
  { key: "renewal", label: "续约提醒", hint: "合同到期前提醒" },
  { key: "spec", label: "规格变更", hint: "产品规格 / 要求变化时提醒" },
];

export const AUTO_SYNC_OPTIONS: { value: AutoSyncFreq; label: string }[] = [
  { value: "off", label: "关闭" },
  { value: "1h", label: "每 1 小时" },
  { value: "4h", label: "每 4 小时" },
  { value: "12h", label: "每 12 小时" },
  { value: "24h", label: "每天" },
];

const DEFAULTS: SettingsPrefs = {
  reminders: { payment: true, risk: true, renewal: true, spec: true },
  autoSync: "4h",
};

function keyFor(userId: string): string {
  return `win:settings:${userId || "anon"}`;
}

export function loadPrefs(userId: string): SettingsPrefs {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<SettingsPrefs>;
    return {
      reminders: { ...DEFAULTS.reminders, ...(parsed.reminders ?? {}) },
      autoSync: parsed.autoSync ?? DEFAULTS.autoSync,
    };
  } catch {
    return DEFAULTS;
  }
}

export function savePrefs(userId: string, prefs: SettingsPrefs): void {
  try {
    localStorage.setItem(keyFor(userId), JSON.stringify(prefs));
  } catch {
    /* storage full / disabled — preferences just won't persist */
  }
}

/** Short subtitle for the 提醒设置 row, e.g. "回款 · 风险 · 续约" or "全部关闭". */
export function reminderSummary(r: ReminderPrefs): string {
  const on = [
    r.payment && "回款",
    r.risk && "风险",
    r.renewal && "续约",
    r.spec && "规格",
  ].filter(Boolean);
  if (on.length === 0) return "全部关闭";
  if (on.length === 4) return "回款 · 风险 · 续约 · 规格";
  return on.join(" · ");
}

export function autoSyncLabel(freq: AutoSyncFreq): string {
  return AUTO_SYNC_OPTIONS.find((o) => o.value === freq)?.label ?? "每 4 小时";
}
