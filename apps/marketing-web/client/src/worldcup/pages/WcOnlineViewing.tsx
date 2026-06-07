/* =============================================================
   /worldcup/online-viewing — 网络观赛 · Watch Online (legally)
   Canada-legal options only: official broadcasters + licensed
   streaming. No piracy / illegal stream / IPTV references.
   ============================================================= */

import { Link } from "wouter";
import { WC, OFFICIAL_LINKS } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

const CHANNELS = [
  {
    emoji: "📡",
    cn: "TSN（英语）",
    tag: "全部 104 场",
    desc: "TSN1–TSN5 频道转播全部 104 场比赛（含有线 / 卫星套餐）。",
    free: false,
  },
  {
    emoji: "📺",
    cn: "CTV（英语）",
    tag: "免费 · 重点场次",
    desc: "免费无线电视转播精选场次，包括加拿大队比赛、揭幕战与决赛。",
    free: true,
  },
  {
    emoji: "🇫🇷",
    cn: "RDS / RDS2（法语）",
    tag: "法语转播",
    desc: "法语观众可通过 RDS 与 RDS2 收看世界杯转播。",
    free: false,
  },
  {
    emoji: "📱",
    cn: "正版流媒体 App",
    tag: "随时随地",
    desc: "TSN+、CTV App、RDS App、Crave 等官方应用可在手机 / 电视上收看。",
    free: false,
  },
];

export default function WcOnlineViewing() {
  return (
    <>
      <PageHero
        kicker="网络观赛 · Watch Online"
        titleCn="在加拿大合法收看世界杯"
        titleEn="Legal ways to watch in Canada"
        intro="2026 世界杯在加拿大由 Bell Media 旗下平台转播。下面整理了官方与正版的观看方式——既有免费选项，也有付费流媒体，总有一款适合你。"
      />

      {/* Channels */}
      <Section pad="3rem">
        <Heading cn="官方与正版渠道" en="Official broadcasters & licensed streaming" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" style={{ gap: "1.25rem" }}>
          {CHANNELS.map((c) => (
            <Card key={c.cn} className="card-lift" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: "1.6rem" }}>{c.emoji}</span>
                {c.free && (
                  <span style={{ fontSize: "0.7rem", fontWeight: 700, color: WC.green, background: WC.greenPale, border: "1px solid rgba(11,122,75,0.25)", borderRadius: "2rem", padding: "0.2rem 0.6rem" }}>
                    免费 FREE
                  </span>
                )}
              </div>
              <div style={{ marginTop: "0.7rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{c.cn}</div>
              <div style={{ fontSize: "0.72rem", color: WC.green, fontWeight: 600, marginTop: "2px" }}>{c.tag}</div>
              <p style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{c.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Pricing + free tips */}
      <Section bg={WC.paper} pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.5rem", alignItems: "start" }}>
          <Card>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.1rem", color: WC.ink }}>价格参考 · Pricing</div>
            <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.1rem", color: WC.inkSoft, lineHeight: 1.9, fontSize: "0.95rem" }}>
              <li>TSN+ 独立订阅：约 <strong>$29.99 / 月</strong> 或 <strong>$249.99 / 年</strong>。</li>
              <li>CTV GO / RDS GO：有线电视订户可<strong>免费</strong>使用。</li>
              <li>部分场次可在 <strong>Crave</strong> 收看（视套餐而定）。</li>
            </ul>
            <p style={{ marginTop: "0.6rem", fontSize: "0.8rem", color: WC.muted }}>价格与套餐以各平台官方公布为准。</p>
          </Card>
          <Card style={{ background: WC.greenTint, border: "1px solid rgba(11,122,75,0.25)" }}>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.1rem", color: WC.ink }}>想省钱？合法免费看</div>
            <ul style={{ margin: "0.75rem 0 0", paddingLeft: "1.1rem", color: WC.inkSoft, lineHeight: 1.9, fontSize: "0.95rem" }}>
              <li>加拿大队比赛、揭幕战与决赛可通过 <strong>CTV 免费无线信号</strong>收看（家用天线即可）。</li>
              <li>前往
                <Link className="wc-link" href="/worldcup/fan-festival" style={{ color: WC.green, fontWeight: 600 }}> 官方球迷节 </Link>
                ，大屏免费看全部比赛。</li>
              <li>关注官方 App 的免费试看与精彩集锦。</li>
            </ul>
          </Card>
        </div>
      </Section>

      {/* Safety warning */}
      <Section pad="3rem">
        <InfoNote tone="warn" title="重要 · 请远离非法直播">
          请只通过上述官方与正版渠道观看。非法免费直播、盗版网站与非法 IPTV / 破解工具不仅侵权违法，还极易导致<strong>账号被盗、银行卡信息泄露、设备中毒</strong>。本指南<strong>不会</strong>提供任何此类链接或工具。
        </InfoNote>
        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
          <LinkButton href={OFFICIAL_LINKS.tsn} variant="primary" external>
            TSN ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.ctv} variant="ghost" external>
            CTV ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.rds} variant="ghost" external>
            RDS ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.crave} variant="ghost" external>
            Crave ↗
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
