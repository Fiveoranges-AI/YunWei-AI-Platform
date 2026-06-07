/* =============================================================
   /worldcup/schedule — 比赛日程 · Toronto Match Schedule
   ============================================================= */

import { WC, TORONTO_MATCHES, STADIUM, TOURNAMENT_WINDOW, OFFICIAL_LINKS } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

export default function WcSchedule() {
  return (
    <>
      <PageHero
        kicker="比赛日程 · Schedule"
        titleCn="多伦多比赛日程"
        titleEn="Toronto Match Schedule"
        intro="2026 世界杯，多伦多将举办 6 场比赛：5 场小组赛 + 1 场 32 强淘汰赛，全部在多伦多体育场（BMO Field）进行。所有时间为多伦多当地时间（ET）。"
      />

      {/* Venue facts */}
      <Section pad="3rem">
        <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: "1.25rem" }}>
          <Card>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: WC.green, textTransform: "uppercase" }}>球场 · Stadium</div>
            <div style={{ marginTop: "0.5rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{STADIUM.nameCn}</div>
            <div style={{ marginTop: "0.35rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{STADIUM.address}</div>
          </Card>
          <Card>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: WC.green, textTransform: "uppercase" }}>容量 · Capacity</div>
            <div style={{ marginTop: "0.5rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{STADIUM.capacity} 人</div>
            <div style={{ marginTop: "0.35rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>为世界杯新增 1.7 万+ 座位</div>
          </Card>
          <Card>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: WC.green, textTransform: "uppercase" }}>赛事周期 · Window</div>
            <div style={{ marginTop: "0.5rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{TOURNAMENT_WINDOW.cn}</div>
            <div style={{ marginTop: "0.35rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>全球 · 美 / 加 / 墨三国合办</div>
          </Card>
        </div>
      </Section>

      {/* Match list */}
      <Section pad="1rem">
        <Heading cn="多伦多 6 场比赛" en="Six matches at Toronto Stadium" />
        <div style={{ display: "flex", flexDirection: "column", gap: "0.9rem" }}>
          {TORONTO_MATCHES.map((m) => (
            <div
              key={m.no}
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "1rem 1.5rem",
                background: m.highlight ? WC.greenPale : "#fff",
                border: `1px solid ${m.highlight ? "rgba(11,122,75,0.35)" : WC.lineStrong}`,
                borderRadius: "0.9rem",
                padding: "1.15rem 1.35rem",
              }}
            >
              {/* Date */}
              <div style={{ minWidth: "92px" }}>
                <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "1.35rem", color: m.highlight ? WC.green : WC.ink, lineHeight: 1 }}>
                  {m.dateCn}
                </div>
                <div style={{ fontSize: "0.78rem", color: WC.muted, marginTop: "0.3rem" }}>
                  {m.weekday} · {m.timeEt} ET
                </div>
              </div>

              {/* Teams */}
              <div style={{ flex: 1, minWidth: "180px" }}>
                <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.05rem", color: WC.ink }}>
                  {m.home} <span style={{ color: WC.muted, fontWeight: 500, padding: "0 0.35rem" }}>vs</span> {m.away}
                </div>
                {m.note && <div style={{ fontSize: "0.82rem", color: WC.muted, marginTop: "0.3rem", lineHeight: 1.5 }}>{m.note}</div>}
              </div>

              {/* Stage */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span
                  style={{
                    fontSize: "0.78rem",
                    fontWeight: 600,
                    color: m.stageEn === "Round of 32" ? WC.gold : WC.green,
                    background: m.stageEn === "Round of 32" ? WC.goldPale : WC.greenTint,
                    border: `1px solid ${m.stageEn === "Round of 32" ? "rgba(217,138,31,0.3)" : "rgba(11,122,75,0.2)"}`,
                    borderRadius: "2rem",
                    padding: "0.3rem 0.8rem",
                    whiteSpace: "nowrap",
                  }}
                >
                  {m.stageCn}
                </span>
                <span style={{ fontSize: "0.78rem", color: WC.muted }}>第 {m.no} 场</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Notes */}
      <Section pad="2.5rem">
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <InfoNote tone="neutral" title="数据校对说明">
            赛程与对阵以 FIFA 官方及多伦多主办委员会公布为准；32 强对阵球队将在小组赛结束后确定。出现变动时本页会同步更新。
          </InfoNote>
          <InfoNote tone="warn" title="购票提醒 · Tickets">
            门票请仅通过 FIFA 官方票务渠道购买，谨防二手 / 黄牛与钓鱼网站。本指南不出售门票，也不提供任何转售链接。
          </InfoNote>
        </div>
        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
          <LinkButton href={OFFICIAL_LINKS.torontoHostSchedule} variant="primary" external>
            官方赛程（多伦多）↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.fifaToronto} variant="ghost" external>
            FIFA 多伦多主办城市 ↗
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
