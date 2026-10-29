import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Script } from "node:vm";
import {
  indexableRoutes,
  pageSeo,
  localizedHref,
  localeFromPath,
  unlocalizedPath,
  en,
  zh,
  render,
  buildMailtoUrl,
} from "../dist/server/entry-server.js";
const output = new URL("../dist/public/", import.meta.url);
const htmlFor = async route =>
  readFile(
    new URL(
      route === "/demo.html" || route === "/zh/demo.html"
        ? route.slice(1)
        : (route === "/" ? "" : route.slice(1) + "/") + "index.html",
      output
    ),
    "utf8"
  );

test("locale URLs are explicit, idempotent, and preserve deep-link context", () => {
  assert.equal(localeFromPath("/"), "en");
  assert.equal(localeFromPath("/zh/strategy-call"), "zh-CN");
  assert.equal(localeFromPath("/zhang"), "en");
  assert.equal(
    localizedHref("/about?utm=test#founder", "zh-CN"),
    "/zh/about?utm=test#founder"
  );
  assert.equal(
    localizedHref("/zh/about?utm=test#founder", "en"),
    "/about?utm=test#founder"
  );
  assert.equal(localizedHref("/zh/", "zh-CN"), "/zh/");
  assert.equal(unlocalizedPath("/zh"), "/");
  for (const url of [
    "mailto:contact@fiveoranges.ai",
    "https://app.fiveoranges.ai/",
    "//example.com",
    "#faq",
  ])
    assert.equal(localizedHref(url, "zh-CN"), url);
});

test("catalogs contain every message in both languages", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort());
  assert.ok(Object.keys(en).length > 300);
  for (const value of Object.values(en)) assert.ok(value.trim());
});

for (const locale of ["en", "zh-CN"])
  for (const route of indexableRoutes) {
    const url = localizedHref(route, locale);
    test(`${url} has crawlable localized content and reciprocal SEO`, async () => {
      const html = await htmlFor(url);
      const seo = pageSeo(url);
      assert.ok(html.includes(`<html lang="${locale}"`));
      assert.equal((html.match(/<title>/g) || []).length, 1);
      assert.ok(html.includes(`href="${seo.canonical}"`));
      for (const [language, alternate] of Object.entries(seo.alternates))
        assert.ok(html.includes(`hreflang="${language}" href="${alternate}"`));
      assert.ok(html.includes('property="og:locale"'));
      assert.ok(html.includes('name="description"'));
      assert.ok(html.includes("<h1"));
      assert.ok(!html.includes("{{demo"));
      const text = html
        .replace(/<script[\s\S]*?<\/script>/g, "")
        .replace(/<style[\s\S]*?<\/style>/g, "")
        .replace(/<[^>]+>/g, "")
        .replace("简体中文", "");
      if (locale === "en")
        assert.ok(
          !/[\u3400-\u9fff。]/.test(text),
          `Unlocalized content in ${url}`
        );
      else assert.ok(/[\u3400-\u9fff]/.test(text));
      if (route !== "/demo.html") {
        assert.ok(
          html.includes(
            'aria-label="' +
              (locale === "en" ? "Choose language" : "选择语言") +
              '"'
          )
        );
        for (const [, href] of html.matchAll(/href="([^\"]+)"/g)) {
          if (
            href.startsWith("/") &&
            !href.startsWith("//") &&
            !href.startsWith("/assets/") &&
            !href.startsWith("/manus-storage/")
          ) {
            const target = new URL(href, "https://fiveoranges.ai").pathname;
            assert.equal(
              localeFromPath(target),
              locale,
              `Locale lost in ${url}: ${href}`
            );
            await htmlFor(target);
          }
        }
      }
    });
  }

test("contact drafts are localized, encoded, and preserve user input", () => {
  const form = {
    name: "Alex & 李",
    company: "A+B Manufacturing",
    contact: "alex@example.com",
    challenge: "Order delays?\nInventory & ERP",
  };
  for (const locale of ["en", "zh-CN"]) {
    const url = new URL(buildMailtoUrl(form, locale));
    assert.equal(url.pathname, "contact@fiveoranges.ai");
    const body = url.searchParams.get("body");
    for (const value of Object.values(form)) assert.ok(body.includes(value));
    assert.equal(
      url.searchParams.get("subject"),
      (locale === "en" ? en : zh).bookA30MinuteDiscovery2
    );
  }
});

test("Chinese page structure, anchors, and full content remain available", () => {
  const html = render("/zh/");
  for (const id of [
    "top",
    "opportunities",
    "approach",
    "solutions",
    "use-cases",
    "about",
    "faq",
    "contact",
  ])
    assert.ok(html.includes(`id="${id}"`));
  for (const text of [
    zh.aClearerViewOfInventory,
    zh.bringInventoryCountsLocationsShortages,
    zh.exploreAssistantsThatAnswerOperational,
    zh.aPotentialWorkflowBringProduction,
    zh.ourDesignPriorityIsTo,
    zh.usefulAiHasToEarn,
  ])
    assert.ok(html.includes(text));
});

test("unknown pages remain localized and are excluded from indexing", () => {
  assert.equal(pageSeo("/zh/missing").found, false);
  assert.ok(render("/zh/missing").includes(zh.pageNotFound));
  assert.ok(render("/missing").includes(en.pageNotFound));
});

test("demo scripts compile in both languages and show sample-data boundaries", async () => {
  for (const url of ["/demo.html", "/zh/demo.html"]) {
    const html = await htmlFor(url);
    for (const [, js] of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g))
      new Script(js);
    assert.ok(html.includes('id="demo-language"'));
    assert.ok(html.includes('role="note"'));
    assert.ok(!html.includes("{{"));
  }
});

test("sitemap lists all 18 localized pages with reciprocal alternates", async () => {
  const sitemap = await readFile(new URL("sitemap.xml", output), "utf8");
  assert.equal((sitemap.match(/<url>/g) || []).length, 18);
  assert.equal((sitemap.match(/hreflang=/g) || []).length, 54);
  assert.ok(!sitemap.includes("/404"));
});

test("extensionless production routes resolve to their own static localized HTML", async () => {
  const config = JSON.parse(
    await readFile(new URL("../../../vercel.json", import.meta.url), "utf8")
  );
  for (const locale of ["en", "zh-CN"])
    for (const route of indexableRoutes.filter(
      route => route !== "/" && route !== "/demo.html"
    )) {
      const url = localizedHref(route, locale);
      const rewrite = config.rewrites.find(rule => rule.source === url);
      assert.equal(rewrite?.destination, url + ".html");
      const flat = await readFile(
        new URL(url.slice(1) + ".html", output),
        "utf8"
      );
      assert.equal(flat, await htmlFor(url));
      assert.ok(
        flat.includes(render(url)),
        `Static body must match route ${url}`
      );
    }
});
