/* =============================================================
   /worldcup/join — 加入微信群 · Join the WeChat group
   ============================================================= */

import { WC, CONTACT_EMAIL } from "../config";
import { PageHero, Section, Card, InfoNote, LinkButton, Heading } from "../ui";

const PERKS = [
  { emoji: "⏰", t: "赛程提醒", d: "开赛、变动与重点场次第一时间提醒。" },
  { emoji: "🚗", t: "约球 · 拼车", d: "一起去现场、拼车出行、组队观赛。" },
  { emoji: "📍", t: "观赛点情报", d: "群友分享华人友好的看球餐厅与活动。" },
  { emoji: "🎁", t: "本地优惠", d: "世界杯期间的商家活动与福利信息。" },
];

const RULES = [
  "文明交流，互相尊重，欢迎各队球迷。",
  "请勿发布广告 / 刷屏 / 无关链接（商家合作见「商家推广工具」）。",
  "禁止赌博、博彩、盘口及任何下注相关内容。",
  "请勿分享盗版、非法直播或 IPTV 链接，合法观赛见「网络观赛」。",
];

export default function WcJoin() {
  return (
    <>
      <PageHero
        kicker="加入微信群 · Join WeChat"
        titleCn="加入多伦多华人球迷群"
        titleEn="Join the Toronto Chinese fans group"
        intro="和大多地区的华人球迷一起看世界杯——约球、拼车、找观赛点，赛程与本地活动更新都在群里。"
      />

      <Section pad="3rem">
        <div className="grid grid-cols-1 lg:grid-cols-2" style={{ gap: "1.75rem", alignItems: "start" }}>
          {/* QR + join */}
          <Card style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "1.15rem", color: WC.ink }}>微信扫码入群</div>
            <p style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: WC.muted }}>扫码后请备注「世界杯」</p>

            {/* QR placeholder — replace with the real group QR image at
                client/public/worldcup-assets/wechat-group-qr.png and swap
                this block for an <img src="/worldcup-assets/wechat-group-qr.png" /> */}
            <div
              style={{
                margin: "1.25rem auto 0",
                width: "200px",
                height: "200px",
                borderRadius: "16px",
                border: `2px dashed ${WC.lineStrong}`,
                background: WC.greenTint,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.6rem",
                color: WC.muted,
              }}
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={WC.green} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <path d="M14 14h3v3M21 14v.01M21 21v-4M17 21h4M14 21h.01" />
              </svg>
              <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>群二维码更新中</span>
            </div>

            <p style={{ marginTop: "1.1rem", fontSize: "0.9rem", color: WC.inkSoft, lineHeight: 1.6 }}>
              二维码会定期更新。如已失效或无法扫码，请用下方邮件联系管理员，我们会拉你进群。
            </p>
            <div style={{ marginTop: "1rem" }}>
              <LinkButton href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("世界杯入群")}`} variant="primary" external>
                邮件联系管理员入群 →
              </LinkButton>
            </div>
          </Card>

          {/* Perks + rules */}
          <div>
            <Heading cn="群里有什么" en="What's inside" />
            <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: "1rem" }}>
              {PERKS.map((p) => (
                <Card key={p.t} style={{ display: "flex", gap: "0.8rem", alignItems: "flex-start" }}>
                  <span style={{ fontSize: "1.4rem", lineHeight: 1 }}>{p.emoji}</span>
                  <div>
                    <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: WC.ink }}>{p.t}</div>
                    <p style={{ marginTop: "0.25rem", fontSize: "0.88rem", color: WC.muted, lineHeight: 1.55 }}>{p.d}</p>
                  </div>
                </Card>
              ))}
            </div>

            <div style={{ marginTop: "1.25rem" }}>
              <InfoNote tone="info" title="群规 · House rules">
                <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.1rem", lineHeight: 1.8 }}>
                  {RULES.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </InfoNote>
            </div>
          </div>
        </div>
      </Section>
    </>
  );
}
