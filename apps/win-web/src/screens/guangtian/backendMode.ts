/**
 * 光天 backend-mode 开关. 默认 mock (客户 demo 安全);URL `?mode=backend` 切真后端.
 * 与锦泰一致: 默认永远 mock, backend 必须显式开启.
 */
export type BackendMode = "mock" | "backend";

export function readInitialMode(): BackendMode {
  if (typeof window === "undefined") return "mock";
  const qp = new URLSearchParams(window.location.search);
  return qp.get("mode") === "backend" ? "backend" : "mock";
}

/** 切换 mode 时同步 URL query, 不动 hash (tab 路由用 hash). */
export function writeModeToUrl(mode: BackendMode): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  if (mode === "backend") url.searchParams.set("mode", "backend");
  else url.searchParams.delete("mode");
  history.replaceState(null, "", url.toString());
}
