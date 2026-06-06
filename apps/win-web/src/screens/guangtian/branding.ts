/**
 * 跨客户品牌 / 行业话术配置 —— "AI Inventory OS 可复制"的核心 stub。
 *
 * 同一套 demo,换 `?customer=<id>` 即换公司名 / 产品名 / 品牌色 / 行业术语:
 *   ?customer=guangtian (默认) · jintai · yinhu · haina
 *
 * 品牌色通过在 demo 根节点覆盖 CSS 变量 --guangtian-red / --guangtian-blue 生效,
 * 全站 30+ 处 var(--guangtian-*) 自动换肤 —— 不改组件即可复制到新客户。
 * 这是 stub:真正上线时由"客户配置 / 租户元数据"驱动,这里先证明架构成立。
 */

export type CustomerBrand = {
  id: string;
  company: string; // 中文公司名(hero 主标题)
  companyEn: string; // 英文行 / 副标
  product: string; // 产品名(hero 副标题)
  tagline: string; // 一句价值主张
  logo: string; // public/ 下文件名
  colors: { primary: string; secondary: string }; // → --guangtian-red / --guangtian-blue
  /** 行业话术:不同制造业换词,让 demo 不"出戏" */
  terms: { line: string; team: string };
};

const BRANDS: Record<string, CustomerBrand> = {
  guangtian: {
    id: "guangtian",
    company: "宜兴光天耐火材料",
    companyEn: "YIXING GUANGTIAN REFRACTORY",
    product: "AI 库存管家",
    tagline: "知道有多少 · 每笔可查 · 缺货提前知道 · 老板直接问 — AI 替您管 1,000+ SKU。",
    logo: "guangtian-logo.png",
    colors: { primary: "#D92020", secondary: "#1A3F8E" }, // 红 + 蓝
    terms: { line: "窑炉", team: "工艺组" },
  },
  jintai: {
    id: "jintai",
    company: "宜兴锦泰耐火材料",
    companyEn: "JINTAI REFRACTORY",
    product: "AI 库存管家",
    tagline: "知道有多少 · 每笔可查 · 缺货提前知道 · 老板直接问 — AI 替您管全厂 SKU。",
    logo: "jintai-logo.png",
    colors: { primary: "#C0392B", secondary: "#1E8449" }, // 红 + 绿
    terms: { line: "产线", team: "生产组" },
  },
  yinhu: {
    id: "yinhu",
    company: "银湖石墨",
    companyEn: "YINHU GRAPHITE",
    product: "AI 库存管家",
    tagline: "知道有多少 · 每笔可查 · 缺货提前知道 · 老板直接问 — AI 替您管全厂物料。",
    logo: "guangtian-logo.png", // stub: 用占位,上线换客户 logo
    colors: { primary: "#37474F", secondary: "#00897B" }, // 石墨灰 + 青
    terms: { line: "产线", team: "生产组" },
  },
  haina: {
    id: "haina",
    company: "海纳环保",
    companyEn: "HAINA ENVIRONMENTAL",
    product: "AI 库存管家",
    tagline: "知道有多少 · 每笔可查 · 缺货提前知道 · 老板直接问 — AI 替您管全厂物料。",
    logo: "guangtian-logo.png", // stub 占位
    colors: { primary: "#1E7A46", secondary: "#0E7490" }, // 环保绿 + 青蓝
    terms: { line: "产线", team: "生产组" },
  },
};

export function resolveBrand(): CustomerBrand {
  if (typeof window === "undefined") return BRANDS.guangtian;
  const id = new URLSearchParams(window.location.search).get("customer") ?? "guangtian";
  return BRANDS[id] ?? BRANDS.guangtian;
}

/** demo 根节点用:把品牌色注入 CSS 变量,全站 var(--guangtian-*) 自动换肤。 */
export function brandCssVars(brand: CustomerBrand): Record<string, string> {
  return {
    "--guangtian-red": brand.colors.primary,
    "--guangtian-blue": brand.colors.secondary,
  };
}
