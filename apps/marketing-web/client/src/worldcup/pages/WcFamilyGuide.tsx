/* =============================================================
   /worldcup/family-guide — 亲子看球 · Family Guide
   ============================================================= */

import { Link } from "wouter";
import { WC, TORONTO_MATCHES } from "../config";
import { PageHero, Section, Card, InfoNote, Heading, LinkButton } from "../ui";

const CHECKLIST = [
  { emoji: "🎧", t: "儿童耳塞 / 降噪耳罩", d: "现场声浪很大，给小朋友护好耳朵。" },
  { emoji: "🧴", t: "防晒 & 帽子 & 水", d: "下午场日晒强，注意补水防晒。" },
  { emoji: "🍪", t: "小零食 & 湿巾", d: "排队和中场时段顶饿、清洁两不误。" },
  { emoji: "👟", t: "舒适的鞋", d: "步行与站立时间长，全家都穿好走的鞋。" },
  { emoji: "🪪", t: "联系卡片", d: "在小朋友口袋放写有家长电话的卡片，万一走散。" },
  { emoji: "📍", t: "约定集合点", d: "进场前先和家人约好走散后的集合地点。" },
];

export default function WcFamilyGuide() {
  // Afternoon kickoffs are easier for younger kids
  const afternoon = TORONTO_MATCHES.filter((m) => {
    const hour = parseInt(m.timeEt.split(":")[0], 10);
    return hour < 18;
  });

  return (
    <>
      <PageHero
        kicker="亲子看球 · Family Guide"
        titleCn="带着孩子看世界杯"
        titleEn="Enjoying the World Cup with kids"
        intro="世界杯是和孩子一起感受体育与多元文化的好机会。无论是去球迷节、还是在家或社区一起看球，这份清单帮你把亲子观赛安排得轻松又安心。"
      />

      {/* Which matches */}
      <Section pad="3rem">
        <Heading cn="适合家庭的场次" en="Family-friendly kickoff times" />
        <p style={{ marginTop: "-1rem", marginBottom: "1.5rem", color: WC.inkSoft, lineHeight: 1.7, maxWidth: "60ch" }}>
          对低龄小朋友来说，下午开球的比赛更友好——结束时间早、不影响作息。多伦多的这些场次开球较早：
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: "1rem" }}>
          {afternoon.map((m) => (
            <Card key={m.no} style={{ borderColor: "rgba(11,122,75,0.3)" }}>
              <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "1.2rem", color: WC.green }}>
                {m.dateCn} · {m.timeEt} ET
              </div>
              <div style={{ marginTop: "0.4rem", fontSize: "0.95rem", color: WC.ink, fontWeight: 600 }}>
                {m.home} vs {m.away}
              </div>
            </Card>
          ))}
        </div>
        <p style={{ marginTop: "1rem", fontSize: "0.85rem", color: WC.muted }}>
          想看完整 6 场赛程？前往
          <Link href="/worldcup/schedule" className="wc-link" style={{ color: WC.green, fontWeight: 600 }}> 比赛日程 </Link>
          。
        </p>
      </Section>

      {/* Checklist */}
      <Section bg={WC.paper} pad="3rem">
        <Heading cn="亲子出行清单" en="What to pack" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" style={{ gap: "1.25rem" }}>
          {CHECKLIST.map((c) => (
            <Card key={c.t} className="card-lift" style={{ display: "flex", gap: "0.9rem", alignItems: "flex-start" }}>
              <span style={{ fontSize: "1.5rem", lineHeight: 1 }}>{c.emoji}</span>
              <div>
                <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{c.t}</div>
                <p style={{ marginTop: "0.3rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{c.d}</p>
              </div>
            </Card>
          ))}
        </div>
      </Section>

      {/* On-site tips */}
      <Section pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.5rem" }}>
          <div>
            <Heading cn="现场注意事项" en="At the venue" />
            <ul style={{ margin: 0, paddingLeft: "1.1rem", color: WC.inkSoft, lineHeight: 1.9, fontSize: "0.97rem" }}>
              <li>提前到场，避开入场与散场的人流高峰。</li>
              <li>留意无障碍通道与婴儿车政策（大型活动常有限制）。</li>
              <li>记下最近的洗手间与医疗 / 服务点位置。</li>
              <li>给孩子穿亮色衣服，方便人群中辨认。</li>
              <li>天气多变，备一件轻外套或雨具。</li>
            </ul>
          </div>
          <div>
            <Heading cn="在家 / 社区看球" en="Watching at home" />
            <p style={{ color: WC.inkSoft, lineHeight: 1.8, fontSize: "0.97rem" }}>
              不想带小朋友去人多的现场，也完全可以在家或社区一起看。通过
              <Link href="/worldcup/online-viewing" className="wc-link" style={{ color: WC.green, fontWeight: 600 }}> 合法转播渠道 </Link>
              收看，准备点小吃、和孩子聊聊参赛球队来自哪些国家，就是一堂生动的地理与文化课。
            </p>
            <div style={{ marginTop: "1rem" }}>
              <InfoNote tone="info" title="小小启蒙">
                可以让孩子各自“认领”一支球队加油、画国旗、数进球——把看球变成全家参与的小游戏。
              </InfoNote>
            </div>
          </div>
        </div>

        <div style={{ marginTop: "1.5rem", display: "flex", flexWrap: "wrap", gap: "0.85rem" }}>
          <LinkButton href="/worldcup/fan-festival" variant="primary">
            了解球迷节 →
          </LinkButton>
          <LinkButton href="/worldcup/transportation" variant="ghost">
            出行攻略 →
          </LinkButton>
        </div>
      </Section>
    </>
  );
}
