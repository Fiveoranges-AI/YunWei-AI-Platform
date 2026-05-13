export function fmtCNY(n: number): string {
  if (n >= 10000) {
    const wan = n / 10000;
    return "¥ " + (Math.abs(wan) >= 100 ? wan.toFixed(0) : wan.toFixed(1)) + " 万";
  }
  return "¥ " + n.toLocaleString("zh-CN");
}

export function fmtCNYRaw(n: number): string {
  return "¥" + n.toLocaleString("zh-CN");
}

/**
 * Compact monetary formatting for tight columns — converts to 万 when ≥10k
 * but without the leading currency prefix, so the caller can pair with a
 * separate "¥" glyph for visual alignment. Below 10k returns the comma-grouped
 * digit string.
 */
export function fmtCNYBig(n: number): string {
  if (n >= 10000) {
    const wan = n / 10000;
    return (Math.abs(wan) >= 100 ? wan.toFixed(0) : wan.toFixed(1)) + " 万";
  }
  return n.toLocaleString("zh-CN");
}

export function fmtRelative(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const diff = Date.now() - d.getTime();
  const min = 60_000;
  const hour = 60 * min;
  const day = 24 * hour;
  if (diff < hour) return Math.max(1, Math.floor(diff / min)) + " 分钟前";
  if (diff < day) return Math.floor(diff / hour) + " 小时前";
  if (diff < 7 * day) return Math.floor(diff / day) + " 天前";
  return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}
