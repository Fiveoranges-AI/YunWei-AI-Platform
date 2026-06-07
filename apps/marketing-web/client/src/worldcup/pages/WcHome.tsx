/* =============================================================
   /worldcup — microsite home / hub.
   ============================================================= */

import { Link } from "wouter";
import { WC, WC_BRAND, STADIUM, TORONTO_MATCHES } from "../config";
import { Section, SectionLabel, LinkButton, Card, Stat, Heading, InfoNote, UnofficialChip, BallMark } from "../ui";

const CARDS = [
  { emoji: "📅", cn: "比赛日程", en: "Schedule", href: "/worldcup/schedule", desc: "多伦多 6 场比赛的日期、时间与对阵，含加拿大主场揭幕战。" },
  { emoji: "🎉", cn: "Fan Festival", en: "Fan Festival", href: "/worldcup/fan-festival", desc: "官方球迷节地点、免费看球大屏、美食与现场氛围全攻略。" },
  { emoji: "🚇", cn: "出行攻略", en: "Getting There", href: "/worldcup/transportation", desc: "从大多地区到球场与球迷节，地铁、GO 火车、电车怎么坐。" },
  { emoji: "👨‍👩‍👧", cn: "亲子看球", en: "Family Guide", href: "/worldcup/family-guide", desc: "带娃看球清单、适合家庭的场次与现场注意事项。" },
  { emoji: "🍜", cn: "商家推荐", en: "Where to Watch", href: "/worldcup/where-to-watch", desc: "华人友好的餐厅、酒吧与社区观赛点，按片区整理。" },
  { emoji: "📺", cn: "网络观赛", en: "Watch Online", href: "/worldcup/online-viewing", desc: "加拿大合法转播与正版流媒体（TSN / CTV / RDS）一览。" },
  { emoji: "📣", cn: "商家推广工具", en: "For Businesses", href: "/worldcup/business", desc: "本地商家如何被华人球迷看到：登上推荐、进入社群。" },
  { emoji: "💬", cn: "加入微信群", en: "Join WeChat", href: "/worldcup/join", desc: "加入华人球迷微信群，第一时间获取更新与约球信息。" },
];

export default function WcHome() {
  const opener = TORONTO_MATCHES[0];
  return (
    <>
      {/* Hero */}
      <section
        style={{
          position: "relative",
          overflow: "hidden",
          background: `linear-gradient(160deg, ${WC.greenDeep} 0%, ${WC.greenDark} 55%, ${WC.green} 130%)`,
          color: "#fff",
        }}
      >
        <div
          aria-hidden
          style={{
            position: "absolute",
            top: "-40%",
            right: "-10%",
            width: "560px",
            height: "560px",
            borderRadius: "999px",
            background: "radial-gradient(circle, rgba(217,138,31,0.22) 0%, rgba(217,138,31,0) 70%)",
            pointerEvents: "none",
          }}
        />
        <div className="container" style={{ position: "relative", padding: "3.75rem 0 4rem" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.25rem" }}>
            <span style={{ width: "40px", height: "40px", borderRadius: "11px", background: "rgba(255,255,255,0.12)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
              <BallMark size={24} color="#fff" />
            </span>
            <span style={{ fontFamily: "Sora, sans-serif", fontWeight: 600, letterSpacing: "0.08em", fontSize: "0.82rem", color: WC.goldSoft }}>
              TORONTO · CANADA · 2026
            </span>
          </div>

          <h1
            style={{
              fontFamily: "Sora, sans-serif",
              fontWeight: 800,
              fontSize: "clamp(2.3rem, 6vw, 4rem)",
              lineHeight: 1.08,
              letterSpacing: "-0.02em",
              maxWidth: "18ch",
              margin: 0,
            }}
          >
            {WC_BRAND.cn}
          </h1>
          <div style={{ marginTop: "0.85rem", fontFamily: "Sora, sans-serif", fontWeight: 500, fontSize: "clamp(1rem, 2.2vw, 1.25rem)", color: "rgba(255,255,255,0.82)", letterSpacing: "0.02em" }}>
            {WC_BRAND.en}
          </div>

          <p style={{ marginTop: "1.5rem", maxWidth: "54ch", fontSize: "1.075rem", lineHeight: 1.75, color: "rgba(255,255,255,0.86)" }}>
            为多伦多及大多地区华人球迷打造的一站式世界杯指南——比赛日程、球迷节、出行、亲子看球、合法观赛与本地商家，中文整理，持续更新。
          </p>

          <div style={{ marginTop: "2rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
            <LinkButton href="/worldcup/schedule" variant="gold">
              查看比赛日程 →
            </LinkButton>
            <LinkButton
              href="/worldcup/join"
              variant="ghost"
              style={{ background: "rgba(255,255,255,0.1)", color: "#fff", border: "1.5px solid rgba(255,255,255,0.35)" }}
            >
              加入微信群
            </LinkButton>
          </div>

          <div style={{ marginTop: "2rem" }}>
            <UnofficialChip />
          </div>
        </div>
      </section>

      {/* Stats */}
      <Section pad="3rem" bg={WC.paper}>
        <div className="grid grid-cols-2 lg:grid-cols-4" style={{ gap: "2rem" }}>
          <Stat value="6 场" label="多伦多举办的比赛 · Matches in Toronto" />
          <Stat value="6.12" label="加拿大主场揭幕战 · Canada's opener" />
          <Stat value={STADIUM.capacity} label="多伦多体育场容量 · Stadium capacity" />
          <Stat value="104 场" label="世界杯总场次 · Total matches worldwide" />
        </div>
      </Section>

      {/* Directory */}
      <Section>
        <Heading cn="指南目录" en="Everything you need · 选一个开始" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" style={{ gap: "1.25rem" }}>
          {CARDS.map((c) => (
            <Link key={c.href} href={c.href} style={{ textDecoration: "none" }}>
              <Card className="card-lift" style={{ height: "100%", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <span
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "12px",
                    background: WC.greenPale,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "1.45rem",
                  }}
                >
                  {c.emoji}
                </span>
                <div>
                  <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.075rem", color: WC.ink }}>{c.cn}</div>
                  <div style={{ fontSize: "0.72rem", color: WC.green, letterSpacing: "0.05em", marginTop: "2px", fontWeight: 600 }}>{c.en}</div>
                </div>
                <p style={{ fontSize: "0.9rem", lineHeight: 1.6, color: WC.muted, margin: 0 }}>{c.desc}</p>
              </Card>
            </Link>
          ))}
        </div>
      </Section>

      {/* Canada opener highlight */}
      <Section bg={WC.greenTint} pad="3.5rem">
        <div
          style={{
            background: "#fff",
            border: `1px solid ${WC.lineStrong}`,
            borderRadius: "1rem",
            padding: "clamp(1.5rem, 4vw, 2.5rem)",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1.5rem",
          }}
        >
          <div style={{ maxWidth: "44ch" }}>
            <SectionLabel>不容错过 · Don't miss</SectionLabel>
            <h3 style={{ margin: "0.9rem 0 0", fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "clamp(1.5rem, 3.5vw, 2rem)", color: WC.ink, lineHeight: 1.2 }}>
              {opener.dateCn} · {opener.home} <span style={{ color: WC.muted, fontWeight: 600 }}>vs</span> {opener.away}
            </h3>
            <p style={{ marginTop: "0.75rem", color: WC.inkSoft, lineHeight: 1.7 }}>
              加拿大队史上首次在本土世界杯的主场揭幕战，也是整届赛事的第 3 场比赛，在多伦多体育场（{opener.timeEt} ET）打响。
            </p>
          </div>
          <LinkButton href="/worldcup/schedule" variant="primary">
            全部 6 场赛程 →
          </LinkButton>
        </div>
      </Section>

      {/* Legal viewing reminder */}
      <Section pad="3rem">
        <InfoNote tone="warn" title="安全 · 合法观赛提醒">
          请通过官方与正版渠道观看比赛（详见
          <Link href="/worldcup/online-viewing" className="wc-link" style={{ color: WC.green, fontWeight: 600 }}>
            {" "}网络观赛{" "}
          </Link>
          ）。本指南不提供任何盗版、非法直播、非法 IPTV 或破解工具的链接——它们存在法律风险，也容易导致账号被盗、设备中毒。
        </InfoNote>
      </Section>

      {/* Join CTA */}
      <Section bg={WC.greenDeep} pad="3.5rem" style={{ color: "#fff" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1.5rem" }}>
          <div style={{ maxWidth: "48ch" }}>
            <h3 style={{ margin: 0, fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "clamp(1.5rem, 3.5vw, 2rem)", color: "#fff" }}>
              加入多伦多华人球迷微信群
            </h3>
            <p style={{ marginTop: "0.75rem", color: "rgba(255,255,255,0.82)", lineHeight: 1.7 }}>
              一起约球、拼车、找观赛点，第一时间获取赛程与本地活动更新。
            </p>
          </div>
          <LinkButton href="/worldcup/join" variant="gold">
            立即加入 →
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
