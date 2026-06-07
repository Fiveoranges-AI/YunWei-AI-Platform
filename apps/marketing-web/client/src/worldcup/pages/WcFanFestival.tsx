/* =============================================================
   /worldcup/fan-festival — Fan Festival 球迷节
   ============================================================= */

import { WC, OFFICIAL_LINKS, TOURNAMENT_WINDOW } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

const HIGHLIGHTS = [
  { emoji: "📺", cn: "免费看球大屏", desc: "巨型屏幕直播比赛，和成千上万球迷一起看球、一起欢呼。" },
  { emoji: "🌍", cn: "全部 104 场", desc: "不只是多伦多的比赛——全球每一场世界杯比赛都会在这里转播。" },
  { emoji: "🍔", cn: "美食与音乐", desc: "现场美食摊位、live 演出与文化活动，节日氛围拉满。" },
  { emoji: "🎮", cn: "互动体验", desc: "射门挑战、足球互动游戏与赞助商体验区，适合各年龄段。" },
];

export default function WcFanFestival() {
  return (
    <>
      <PageHero
        kicker="Fan Festival · 球迷节"
        titleCn="FIFA 官方球迷节（多伦多）"
        titleEn="FIFA Fan Festival™ Toronto"
        intro="没有球票？一样能融入世界杯。多伦多的官方球迷节设有免费看球大屏、美食、音乐与互动体验，全程转播全部 104 场比赛，是和华人朋友、带着家人一起看球的好去处。"
      />

      <Section pad="3rem">
        <Heading cn="现场有什么" en="What to expect" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" style={{ gap: "1.25rem" }}>
          {HIGHLIGHTS.map((h) => (
            <Card key={h.cn} className="card-lift" style={{ height: "100%" }}>
              <div style={{ fontSize: "1.6rem" }}>{h.emoji}</div>
              <div style={{ marginTop: "0.6rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{h.cn}</div>
              <p style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{h.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Location + admission */}
      <Section bg={WC.paper} pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.5rem" }}>
          <Card>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: WC.green, textTransform: "uppercase" }}>地点 · Location</div>
            <h3 style={{ margin: "0.6rem 0 0", fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.2rem", color: WC.ink }}>
              Fort York National Historic Site & The Bentway
            </h3>
            <p style={{ marginTop: "0.6rem", color: WC.inkSoft, lineHeight: 1.7 }}>
              球迷节设在相邻的 Fort York 国家历史遗址与 The Bentway，紧邻 Exhibition Place，距离多伦多体育场步行可达。看完球迷节，还能顺道逛逛湖滨与 Liberty Village。
            </p>
          </Card>
          <Card>
            <div style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: WC.green, textTransform: "uppercase" }}>开放 & 入场 · Dates & entry</div>
            <h3 style={{ margin: "0.6rem 0 0", fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.2rem", color: WC.ink }}>
              {TOURNAMENT_WINDOW.cn} · 普通入场免费
            </h3>
            <p style={{ marginTop: "0.6rem", color: WC.inkSoft, lineHeight: 1.7 }}>
              球迷节在赛事期间开放，普通入场（General Admission）免费；另有付费的高级体验区。免费名额可能需要提前在官方登记、且经常被抢空，出发前请务必查看官方最新信息。
            </p>
          </Card>
        </div>

        <div style={{ marginTop: "1.5rem" }}>
          <InfoNote tone="info" title="实用提示">
            热门场次（尤其加拿大队比赛）人流大，建议提前到场、轻装出行；现场通常有安检与物品限制，少带大包。具体每日开放时间、入场登记与活动安排以官方公布为准。
          </InfoNote>
        </div>

        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
          <LinkButton href={OFFICIAL_LINKS.fifaFanFestToronto} variant="primary" external>
            FIFA 官方球迷节信息 ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.cityOfToronto} variant="ghost" external>
            多伦多市政府活动页 ↗
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
