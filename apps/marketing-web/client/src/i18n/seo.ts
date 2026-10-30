import { en, zh } from "./catalog";
import {
  localizedHref,
  localeFromPath,
  unlocalizedPath,
  routes,
} from "./routing";

const origin = "https://fiveoranges.ai";
export function pageSeo(path: string) {
  const locale = localeFromPath(path);
  const c = locale === "en" ? en : zh;
  const route = unlocalizedPath(path).replace(/\/$/, "") || "/";
  const content: Record<string, [string, string]> = {
    "/": [
      locale === "en"
        ? "Five Oranges AI — Operational Intelligence for Manufacturers"
        : "Five Oranges AI · 运帷AI — 制造业 AI 经营助手",
      locale === "en"
        ? "Connect fragmented ERP, Excel, and operational data. Explore practical AI-powered operational intelligence for small and mid-sized manufacturers."
        : "帮助制造业企业梳理库存、订单、客户、流程和经营数据，从可验证的小场景开始推进 AI 数字化升级。",
    ],
    "/about": [
      c.aboutFiveOrangesAi,
      locale === "en"
        ? c.fiveOrangesAiIsA
        : "了解运帷AI的使命、创始人背景与面向制造业中小企业的轻量化 AI 系统方法。",
    ],
    "/resources": [
      c.resourcesFiveOrangesAi,
      locale === "en"
        ? c.resourcesForManufacturersExploringOperational
        : "了解常见问题、数据安全原则、90天参考路线图和制造业 AI 落地观察。",
    ],
    "/kobeli": [
      c.kobeLiFounderOfFive,
      locale === "en"
        ? c.meetKobeLiFounderOf
        : "了解 Five Oranges AI / 运帷AI 创始人 Kobe Li 的企业架构、数据集成与数字化转型经验。",
    ],
    "/strategy-call": [
      c.bookADiscoveryCallFive,
      locale === "en"
        ? c.bookA30MinuteDiscovery3
        : "预约30分钟AI数字化诊断，判断库存、订单、客户、流程和经营数据中值得优先解决的场景。",
    ],
    "/privacy": [
      c.privacyPolicyFiveOrangesAi,
      locale === "en"
        ? c.howFiveOrangesAiHandles
        : "了解运帷AI如何收集、使用和处理网站咨询、演示和沟通中的信息。",
    ],
    "/terms": [
      c.termsOfUseFiveOranges,
      locale === "en"
        ? c.termsForUsingFiveOranges
        : "了解运帷AI网站内容、演示、知识产权和使用边界。",
    ],
    "/data-security": [
      c.dataSecurityFiveOrangesAi,
      locale === "en"
        ? c.fiveOrangesAiPrinciplesFor
        : "了解运帷AI的数据授权、权限设计、最小必要原则与 AI 使用边界。",
    ],
    "/demo.html": [
      locale === "en"
        ? "Interactive Sample Demo | Five Oranges AI"
        : "交互演示 · 示例数据 | 运帷AI",
      locale === "en"
        ? "Explore an illustrative order-management assistant using fictional sample data. No live ERP connection or customer endorsement is implied."
        : "使用虚构示例数据体验订单经营助手，不代表真实客户关系或实时系统接入。",
    ],
  };
  const [title, description] = content[route] || [
    c.pageNotFound,
    c.sorryThePageYouAre,
  ];
  const canonical = origin + localizedHref(route, locale);
  return {
    title,
    description,
    canonical,
    locale,
    route,
    found: route in content,
    alternates: {
      en: origin + route,
      "zh-CN": origin + localizedHref(route, "zh-CN"),
      "x-default": origin + route,
    },
  };
}
export const indexableRoutes = [...routes, "/demo.html"];
