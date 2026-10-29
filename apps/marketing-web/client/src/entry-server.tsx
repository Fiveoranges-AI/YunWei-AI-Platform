import { renderToString } from "react-dom/server";
import App from "./App";
export { pageSeo, indexableRoutes } from "./i18n/seo";
export { localizedHref } from "./i18n/routing";
export function render(path: string) {
  return renderToString(<App path={path} />);
}

export { en, zh } from "./i18n/catalog";
export { localeFromPath, unlocalizedPath } from "./i18n/routing";
export { buildMailtoUrl } from "./i18n/contact";
