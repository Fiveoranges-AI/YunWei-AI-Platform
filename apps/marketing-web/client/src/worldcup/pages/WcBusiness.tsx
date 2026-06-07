/* =============================================================
   /worldcup/business — 商家推广工具 · For Businesses
   How local merchants can reach Chinese fans during the World Cup.
   ============================================================= */

import { WC, CONTACT_EMAIL, POWERED_BY } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

const OFFERS = [
  { emoji: "📍", cn: "登上「商家推荐」", desc: "把你的观赛活动收录进华人球迷常看的推荐页面与片区清单。" },
  { emoji: "💬", cn: "进入球迷微信群", desc: "在多伦多华人球迷社群中曝光优惠与转播场次，直达目标客流。" },
  { emoji: "📣", cn: "活动信息分发", desc: "世界杯期间的看球之夜、套餐与活动，帮你触达更多本地球迷。" },
];

const STEPS = [
  { n: "01", cn: "提交信息", desc: "通过微信或邮件，把店铺与活动信息发给我们。" },
  { n: "02", cn: "简单核对", desc: "我们确认基本信息（地址、转播、联系方式）无误。" },
  { n: "03", cn: "上线 / 进群", desc: "信息进入推荐清单与球迷社群，开始触达华人球迷。" },
];

const PREPARE = ["店名 & 地址", "转播哪些场次 / 是否外放声音", "世界杯期间的优惠或套餐", "可容纳人数 / 是否需订位", "联系方式（微信 / 电话）"];

export default function WcBusiness() {
  const subject = encodeURIComponent("世界杯商家推广报名");
  const body = encodeURIComponent(
    ["店名：", "地址：", "转播场次：", "世界杯优惠 / 套餐：", "可容纳人数：", "联系方式（微信 / 电话）："].join("\n"),
  );
  const mailto = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;

  return (
    <>
      <PageHero
        kicker="商家推广工具 · For Businesses"
        titleCn="让华人球迷找到你"
        titleEn="Reach Chinese fans this World Cup"
        intro="世界杯期间，餐厅、酒吧、奶茶店与本地服务都迎来一波看球客流。把你的观赛活动加入这份华人球迷指南，让更多人看到你。"
      />

      {/* Offers */}
      <Section pad="3rem">
        <Heading cn="我们能帮你做什么" en="What we offer" />
        <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: "1.25rem" }}>
          {OFFERS.map((o) => (
            <Card key={o.cn} className="card-lift" style={{ height: "100%" }}>
              <div style={{ fontSize: "1.6rem" }}>{o.emoji}</div>
              <div style={{ marginTop: "0.6rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{o.cn}</div>
              <p style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{o.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Steps */}
      <Section bg={WC.paper} pad="3rem">
        <Heading cn="三步登上指南" en="Get listed in 3 steps" />
        <div className="grid grid-cols-1 sm:grid-cols-3" style={{ gap: "1.25rem" }}>
          {STEPS.map((s) => (
            <Card key={s.n} style={{ height: "100%" }}>
              <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "1.5rem", color: WC.green }}>{s.n}</div>
              <div style={{ marginTop: "0.4rem", fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{s.cn}</div>
              <p style={{ marginTop: "0.35rem", fontSize: "0.9rem", color: WC.muted, lineHeight: 1.6 }}>{s.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      {/* Prepare + CTA */}
      <Section pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.5rem", alignItems: "start" }}>
          <div>
            <Heading cn="提交前请准备" en="What to prepare" />
            <ul style={{ margin: 0, paddingLeft: "1.1rem", color: WC.inkSoft, lineHeight: 1.95, fontSize: "0.97rem" }}>
              {PREPARE.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
            <div style={{ marginTop: "1.25rem" }}>
              <InfoNote tone="neutral">
                收录与排序由社区维护，旨在帮助华人球迷找到合适的观赛点，不构成商业背书或排他合作。
              </InfoNote>
            </div>
          </div>

          <Card style={{ background: WC.greenTint, border: "1px solid rgba(11,122,75,0.25)" }}>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.2rem", color: WC.ink }}>现在就报名</div>
            <p style={{ marginTop: "0.5rem", color: WC.inkSoft, lineHeight: 1.7, fontSize: "0.95rem" }}>
              选择任一方式联系我们，附上上面准备好的信息即可。
            </p>
            <div style={{ marginTop: "1.1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <LinkButton href={mailto} variant="primary" external>
                邮件报名（自动填好模板）→
              </LinkButton>
              <LinkButton href="/worldcup/join" variant="gold">
                加入微信群 · 联系管理员 →
              </LinkButton>
            </div>
            <p style={{ marginTop: "0.85rem", fontSize: "0.8rem", color: WC.muted }}>
              邮箱：{CONTACT_EMAIL}
            </p>
          </Card>
        </div>

        <p style={{ marginTop: "2rem", textAlign: "center", fontSize: "0.78rem", color: WC.muted }}>
          本指南的技术与运营支持 · {POWERED_BY}
        </p>
      </Section>
    </>
  );
}
