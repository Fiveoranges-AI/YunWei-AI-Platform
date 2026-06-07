/* =============================================================
   /worldcup/where-to-watch — 商家推荐 · Where to Watch (in person)
   Recommended ways & places to watch with others. We list venue
   TYPES and neighbourhoods rather than unverified business names;
   businesses can get listed via /worldcup/business.
   ============================================================= */

import { Link } from "wouter";
import { WC } from "../config";
import { PageHero, Section, Card, InfoNote, Heading, LinkButton } from "../ui";

const WAYS = [
  {
    emoji: "🎉",
    cn: "官方球迷节",
    desc: "最大、最热闹的免费看球点，全部 104 场都转播。",
    to: "/worldcup/fan-festival",
    cta: "球迷节攻略",
  },
  {
    emoji: "🍜",
    cn: "华人餐厅 & 酒吧",
    desc: "在熟悉的中餐 / 烧烤 / 火锅店里，边吃边和朋友看球。",
  },
  {
    emoji: "🏘️",
    cn: "社区 / 球迷聚会",
    desc: "社团、同乡会、球迷组织常组织集体观赛，氛围最对味。",
  },
];

const AREAS = [
  { cn: "士嘉堡 Scarborough", d: "华人餐饮密集，中餐厅与茶餐厅多，适合家庭与朋友聚看。" },
  { cn: "万锦 Markham", d: "大统华周边及各大商场餐饮集中，停车方便、选择多。" },
  { cn: "列治文山 Richmond Hill", d: "Yonge 沿线中餐与小吃聚集，约上三五好友很方便。" },
  { cn: "北约克 North York", d: "地铁沿线，市区与北边通勤都方便，餐厅营业到较晚。" },
  { cn: "市中心唐人街 Downtown", d: "靠近球场与球迷节，看完现场可顺道觅食。" },
];

const TIPS = [
  "提前打电话或在社媒确认：当天是否转播你想看的那场？",
  "热门场次（如加拿大队）建议提前订位 / 占座。",
  "问清楚有几块屏幕、声音是否外放、最低消费。",
  "人多时结伴前往，注意财物与回程交通安排。",
];

export default function WcWhereToWatch() {
  return (
    <>
      <PageHero
        kicker="商家推荐 · Where to Watch"
        titleCn="推荐观赛好去处"
        titleEn="Where to watch with fellow fans"
        intro="想和大家一起看球、感受气氛？这里整理了几种适合华人球迷的线下观赛方式，并按片区给出寻找华人友好餐厅与酒吧的方向。"
      />

      {/* Ways */}
      <Section pad="3rem">
        <Heading cn="三种看球方式" en="Three ways to watch together" />
        <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: "1.25rem" }}>
          {WAYS.map((w) => (
            <Card key={w.cn} className="card-lift" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: "1.6rem" }}>{w.emoji}</div>
              <div style={{ marginTop: "0.6rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{w.cn}</div>
              <p style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6, flex: 1 }}>{w.desc}</p>
              {w.to && (
                <Link href={w.to} className="wc-link" style={{ marginTop: "0.75rem", color: WC.green, fontWeight: 600, fontSize: "0.9rem" }}>
                  {w.cta} →
                </Link>
              )}
            </Card>
          ))}
        </div>
      </Section>

      {/* Neighbourhoods */}
      <Section bg={WC.paper} pad="3rem">
        <Heading cn="按片区找华人友好场所" en="Chinese-friendly areas across the GTA" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" style={{ gap: "1.25rem" }}>
          {AREAS.map((a) => (
            <Card key={a.cn}>
              <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{a.cn}</div>
              <p style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{a.d}</p>
            </Card>
          ))}
        </div>
        <div style={{ marginTop: "1.5rem" }}>
          <InfoNote tone="neutral" title="说明">
            以上为片区方向参考，并非对具体商家的背书。各店是否转播、营业时间与最低消费以商家当日信息为准。具体推荐名单由社区共建，欢迎在
            <Link href="/worldcup/join" className="wc-link" style={{ color: WC.green, fontWeight: 600 }}> 微信群 </Link>
            里分享与补充。
          </InfoNote>
        </div>
      </Section>

      {/* Choosing tips */}
      <Section pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.5rem", alignItems: "start" }}>
          <div>
            <Heading cn="挑选观赛点小贴士" en="How to pick a spot" />
            <ul style={{ margin: 0, paddingLeft: "1.1rem", color: WC.inkSoft, lineHeight: 1.9, fontSize: "0.97rem" }}>
              {TIPS.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
          <Card style={{ background: WC.greenTint, border: `1px solid rgba(11,122,75,0.25)` }}>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.1rem", color: WC.ink }}>你是商家？</div>
            <p style={{ marginTop: "0.5rem", color: WC.inkSoft, lineHeight: 1.7, fontSize: "0.95rem" }}>
              餐厅、酒吧、奶茶店想在世界杯期间被华人球迷看到？把你的观赛活动加入推荐名单与球迷社群。
            </p>
            <div style={{ marginTop: "1rem" }}>
              <LinkButton href="/worldcup/business" variant="primary">
                查看商家推广工具 →
              </LinkButton>
            </div>
          </Card>
        </div>
      </Section>
    </>
  );
}
