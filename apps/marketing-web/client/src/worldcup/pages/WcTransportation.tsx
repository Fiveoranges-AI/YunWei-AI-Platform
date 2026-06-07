/* =============================================================
   /worldcup/transportation — 出行攻略 · Getting There
   ============================================================= */

import { WC, OFFICIAL_LINKS, STADIUM } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

const OPTIONS = [
  {
    emoji: "🚆",
    cn: "GO 火车",
    en: "GO Transit",
    desc: "Lakeshore West 线在 Exhibition GO 站下车，步行即到球场与球迷节，是从西边及湖滨沿线最直接的方式。",
  },
  {
    emoji: "🚋",
    cn: "TTC 电车",
    en: "Streetcar",
    desc: "509 Harbourfront 与 511 Bathurst 电车直达 Exhibition Loop；可从 Union 站（509）或 Bathurst 站（511）换乘。",
  },
  {
    emoji: "🚇",
    cn: "地铁 + 换乘",
    en: "Subway + transfer",
    desc: "乘 TTC 1 号线到 Union 站换 509 电车，或到 Bathurst 站换 511 电车。Presto 卡 / 手机刷卡最方便。",
  },
  {
    emoji: "🚶",
    cn: "步行 / 单车",
    en: "Walk / bike",
    desc: "从 Liberty Village、湖滨一带步行可达；沿途有 Bike Share 站点，骑行也很方便。",
  },
];

export default function WcTransportation() {
  return (
    <>
      <PageHero
        kicker="出行攻略 · Getting There"
        titleCn="怎么去球场和球迷节"
        titleEn="Getting to the stadium & Fan Festival"
        intro={`多伦多体育场与官方球迷节都位于 Exhibition Place / Fort York 一带（${STADIUM.address}）。比赛日人多、周边会有道路与停车限制，强烈建议优先公共交通。`}
      />

      <Section pad="3rem">
        <Heading cn="四种到达方式" en="Four ways to get there" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" style={{ gap: "1.25rem" }}>
          {OPTIONS.map((o) => (
            <Card key={o.cn} className="card-lift" style={{ height: "100%" }}>
              <div style={{ fontSize: "1.6rem" }}>{o.emoji}</div>
              <div style={{ marginTop: "0.6rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{o.cn}</div>
              <div style={{ fontSize: "0.72rem", color: WC.green, fontWeight: 600, letterSpacing: "0.04em", marginTop: "2px" }}>{o.en}</div>
              <p style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{o.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* From the suburbs */}
      <Section bg={WC.paper} pad="3rem">
        <Heading cn="从大多地区出发" en="From across the GTA" />
        <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: "1.25rem" }}>
          <Card>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink, fontSize: "1.05rem" }}>
              士嘉堡 / 北约克 / 万锦 / 列治文山
            </div>
            <p style={{ marginTop: "0.5rem", color: WC.inkSoft, lineHeight: 1.7, fontSize: "0.95rem" }}>
              先乘 TTC 或 York Region / GO 巴士接驳到地铁，再坐 1 号线到 Union 站换 509 电车直达 Exhibition。也可在沿线 GO 站搭乘 GO 火车到 Union 后换乘。
            </p>
          </Card>
          <Card>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink, fontSize: "1.05rem" }}>
              密西沙加 / 奥克维尔 / 西区沿湖
            </div>
            <p style={{ marginTop: "0.5rem", color: WC.inkSoft, lineHeight: 1.7, fontSize: "0.95rem" }}>
              GO Transit Lakeshore West 线最方便，可直接在 Exhibition GO 站下车，省去市区换乘。出发前查好当日班次与回程末班时间。
            </p>
          </Card>
        </div>

        <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
          <InfoNote tone="info" title="比赛日小贴士">
            ① 提前 1–2 小时出发，散场时人流集中；② 备好 Presto 或手机感应支付，避免排队买票；③ 现场有安检，少带大包、遵守物品规定；④ 留意官方公布的临时道路封闭与改线信息。
          </InfoNote>
          <InfoNote tone="warn" title="自驾提醒">
            比赛日周边停车非常紧张、价格高且容易拥堵，并可能有道路封闭。如确需自驾，建议停在地铁沿线再换乘公共交通。
          </InfoNote>
        </div>

        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
          <LinkButton href={OFFICIAL_LINKS.ttc} variant="primary" external>
            TTC 线路与票价 ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.goTransit} variant="ghost" external>
            GO Transit 班次 ↗
          </LinkButton>
          <LinkButton href={OFFICIAL_LINKS.cityOfToronto} variant="ghost" external>
            多伦多市·赛事出行 ↗
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
