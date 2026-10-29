import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import {
  render,
  pageSeo,
  indexableRoutes,
  localizedHref,
} from "../dist/server/entry-server.js";
import { renderDemo } from "./demo.mjs";
const output = new URL("../dist/public/", import.meta.url);
const template = await readFile(new URL("index.html", output), "utf8");
const escape = value =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;");
export function seoHead(seo) {
  return `<title>${escape(seo.title)}</title><meta name="description" content="${escape(seo.description)}"><meta name="robots" content="${seo.found ? "index,follow" : "noindex,follow"}"><link rel="canonical" href="${seo.canonical}">${Object.entries(
    seo.alternates
  )
    .map(
      ([language, href]) =>
        `<link rel="alternate" hreflang="${language}" href="${href}">`
    )
    .join("")}${Object.entries({
    title: seo.title,
    description: seo.description,
    url: seo.canonical,
    type: "website",
    locale: seo.locale === "en" ? "en_CA" : "zh_CN",
    "locale:alternate": seo.locale === "en" ? "zh_CN" : "en_CA",
    image: "https://fiveoranges.ai/manus-storage/logo_clean_934597e8.png",
  })
    .map(
      ([key, value]) => `<meta property="og:${key}" content="${escape(value)}">`
    )
    .join("")}`;
}
const urls = [];
for (const locale of ["en", "zh-CN"]) {
  for (const route of [...indexableRoutes, "/404"]) {
    const url = localizedHref(route, locale);
    const seo = pageSeo(url);
    let html =
      route === "/demo.html"
        ? await renderDemo(locale)
        : template.replace(
            '<div id="root"></div>',
            `<div id="root">${render(url)}</div>`
          );
    html = html
      .replace(/<title>[\s\S]*?<\/title>/, "")
      .replace(/<meta name="description"[^>]*\/?\s*>/, "")
      .replace(/<html lang="[^"]+"/, `<html lang="${locale}"`)
      .replace("</head>", seoHead(seo) + "</head>");
    const relative =
      route === "/demo.html"
        ? url.slice(1)
        : path.join(url.slice(1), "index.html");
    const file = new URL(relative, output);
    await mkdir(new URL(".", file), { recursive: true });
    await writeFile(file, html);
    if (route !== "/" && route !== "/demo.html")
      await writeFile(new URL(url.slice(1) + ".html", output), html);
    if (seo.found)
      urls.push(
        `<url><loc>${seo.canonical}</loc>${Object.entries(seo.alternates)
          .map(
            ([lang, href]) =>
              `<xhtml:link rel="alternate" hreflang="${lang}" href="${href}"/>`
          )
          .join("")}</url>`
      );
  }
}
await writeFile(
  new URL("sitemap.xml", output),
  `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">${urls.join("")}</urlset>`
);
await writeFile(
  new URL("robots.txt", output),
  "User-agent: *\nAllow: /\nSitemap: https://fiveoranges.ai/sitemap.xml\n"
);
console.log(
  `Prerendered ${urls.length} indexable localized pages and localized 404s.`
);
