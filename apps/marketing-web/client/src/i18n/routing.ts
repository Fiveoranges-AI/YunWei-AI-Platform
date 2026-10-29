export type Locale = "en" | "zh-CN";
export const routes = [
  "/",
  "/about",
  "/resources",
  "/kobeli",
  "/strategy-call",
  "/privacy",
  "/terms",
  "/data-security",
] as const;

export function localeFromPath(path: string): Locale {
  return /^\/zh(?:\/|$)/.test(path) ? "zh-CN" : "en";
}

export function unlocalizedPath(path: string): string {
  return path.replace(/^\/zh(?=\/|$)/, "") || "/";
}

export function localizedHref(href: string, locale: Locale): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  const path = unlocalizedPath(href);
  return locale === "zh-CN" ? `/zh${path === "/" ? "/" : path}` : path;
}
