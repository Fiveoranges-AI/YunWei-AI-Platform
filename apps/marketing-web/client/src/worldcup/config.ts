/* =============================================================
   2026 多伦多世界杯华人指南 · Toronto World Cup 2026 Chinese Fan Guide
   ----------------------------------------------------------------
   Standalone community microsite under /worldcup. Shared config:
   palette, brand strings, navigation, official links, disclaimer.
   This file is intentionally self-contained so the microsite does
   not depend on (or alter) the main Five Oranges AI site.
   ============================================================= */

/** Brand / identity strings shown to fans (user-facing brand). */
export const WC_BRAND = {
  cn: "2026 多伦多世界杯华人指南",
  en: "Toronto World Cup 2026 Chinese Fan Guide",
  short: "多伦多世界杯华人指南",
};

/** Light-touch maker credit line (do NOT over-brand as a corporate page). */
export const POWERED_BY = "Powered by Five Oranges AI";
export const FOOTER_LINE = "2026 多伦多世界杯华人指南 · Powered by Five Oranges AI";

/** Required legal disclaimer — independent, unaffiliated guide. */
export const DISCLAIMER_EN =
  "This is an independent Chinese fan guide. It is not affiliated with FIFA, FIFA World Cup, City of Toronto, official broadcasters, official ticketing providers, or any event organizer.";
export const DISCLAIMER_CN =
  "本站为独立的华人球迷信息指南，与 FIFA、国际足联世界杯、多伦多市政府、官方转播机构、官方票务机构及任何赛事主办方均无隶属或合作关系。";

/** Contact for community / business submissions (receives mail). */
export const CONTACT_EMAIL = "contact@fiveoranges.ai";

/* -------------------------------------------------------------
   Microsite palette — a fresh, sporty "pitch green + warm gold"
   identity, deliberately distinct from the corporate blue/navy
   site so /worldcup reads as a standalone community guide.
   ------------------------------------------------------------- */
export const WC = {
  green: "#0B7A4B",
  greenDark: "#075235",
  greenDeep: "#063C28",
  greenPale: "#E8F4EC",
  greenTint: "#F2F9F4",
  gold: "#D98A1F",
  goldSoft: "#E8A33D",
  goldPale: "#FBF1DD",
  ink: "#0F2340",
  inkSoft: "#33445A",
  muted: "#5B6B7B",
  paper: "#FAF8F3",
  line: "rgba(15,35,64,0.10)",
  lineStrong: "rgba(15,35,64,0.16)",
  white: "#FFFFFF",
} as const;

/* -------------------------------------------------------------
   Microsite navigation — lives ONLY inside /worldcup.
   Order per spec. `home` is rendered as the brand link; the rest
   appear in the nav bar; `join` is highlighted as the key CTA.
   ------------------------------------------------------------- */
export type WcNavItem = { cn: string; en: string; href: string };

export const WC_NAV: WcNavItem[] = [
  { cn: "首页", en: "Home", href: "/worldcup" },
  { cn: "比赛日程", en: "Schedule", href: "/worldcup/schedule" },
  { cn: "Fan Festival", en: "Fan Festival", href: "/worldcup/fan-festival" },
  { cn: "出行攻略", en: "Getting There", href: "/worldcup/transportation" },
  { cn: "亲子看球", en: "Family Guide", href: "/worldcup/family-guide" },
  { cn: "商家推荐", en: "Where to Watch", href: "/worldcup/where-to-watch" },
  { cn: "网络观赛", en: "Watch Online", href: "/worldcup/online-viewing" },
  { cn: "商家推广工具", en: "For Businesses", href: "/worldcup/business" },
  { cn: "加入微信群", en: "Join WeChat", href: "/worldcup/join" },
];

/** Official / authoritative external links (open in new tab). */
export const OFFICIAL_LINKS = {
  fifaToronto:
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/canada/toronto",
  fifaFanFestToronto:
    "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/fifa-fan-festival/toronto",
  torontoHostCommittee: "https://torontofwc26.ca/",
  torontoHostSchedule: "https://torontofwc26.ca/game",
  cityOfToronto: "https://www.toronto.ca/explore-enjoy/festivals-events/fifa-world-cup-2026/",
  ttc: "https://www.ttc.ca/",
  goTransit: "https://www.gotransit.com/",
  tsn: "https://www.tsn.ca/soccer/fifa-world-cup",
  ctv: "https://www.ctv.ca/",
  rds: "https://www.rds.ca/",
  crave: "https://www.crave.ca/",
} as const;

/** Tournament window (across USA / Canada / Mexico). */
export const TOURNAMENT_WINDOW = { cn: "2026年6月11日 – 7月19日", en: "June 11 – July 19, 2026" };

/* -------------------------------------------------------------
   Toronto match schedule — 6 matches at Toronto Stadium.
   Source: Toronto host committee (torontofwc26.ca/game) + FIFA.
   Always shown with a "subject to official confirmation" note.
   ------------------------------------------------------------- */
export type WcMatch = {
  no: number;
  dateCn: string;
  dateEn: string;
  weekday: string;
  timeEt: string;
  home: string;
  away: string;
  stageCn: string;
  stageEn: string;
  highlight?: boolean;
  note?: string;
};

export const TORONTO_MATCHES: WcMatch[] = [
  {
    no: 3,
    dateCn: "6月12日",
    dateEn: "Jun 12",
    weekday: "周五 Fri",
    timeEt: "15:00",
    home: "加拿大 Canada",
    away: "波黑 Bosnia & Herzegovina",
    stageCn: "小组赛",
    stageEn: "Group Stage",
    highlight: true,
    note: "加拿大队主场揭幕战 · 全程第 3 场比赛",
  },
  {
    no: 21,
    dateCn: "6月17日",
    dateEn: "Jun 17",
    weekday: "周三 Wed",
    timeEt: "19:00",
    home: "加纳 Ghana",
    away: "巴拿马 Panama",
    stageCn: "小组赛",
    stageEn: "Group Stage",
  },
  {
    no: 33,
    dateCn: "6月20日",
    dateEn: "Jun 20",
    weekday: "周六 Sat",
    timeEt: "16:00",
    home: "德国 Germany",
    away: "科特迪瓦 Côte d'Ivoire",
    stageCn: "小组赛",
    stageEn: "Group Stage",
  },
  {
    no: 46,
    dateCn: "6月23日",
    dateEn: "Jun 23",
    weekday: "周二 Tue",
    timeEt: "19:00",
    home: "克罗地亚 Croatia",
    away: "巴拿马 Panama",
    stageCn: "小组赛",
    stageEn: "Group Stage",
  },
  {
    no: 62,
    dateCn: "6月26日",
    dateEn: "Jun 26",
    weekday: "周五 Fri",
    timeEt: "15:00",
    home: "塞内加尔 Senegal",
    away: "伊拉克 Iraq",
    stageCn: "小组赛",
    stageEn: "Group Stage",
  },
  {
    no: 83,
    dateCn: "7月2日",
    dateEn: "Jul 2",
    weekday: "周四 Thu",
    timeEt: "19:00",
    home: "待定 TBD",
    away: "待定 TBD",
    stageCn: "32强淘汰赛",
    stageEn: "Round of 32",
    note: "对阵球队由小组赛排名决定（K 组 vs L 组）",
  },
];

export const STADIUM = {
  nameCn: "多伦多体育场（BMO Field）",
  nameEn: "Toronto Stadium (BMO Field)",
  address: "170 Princes' Blvd, Exhibition Place, Toronto, ON M6K 3C3",
  capacity: "约 45,736",
};
