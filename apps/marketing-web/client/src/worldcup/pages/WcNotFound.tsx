/* =============================================================
   /worldcup/* fallback — keeps lost visitors inside the microsite.
   ============================================================= */

import { WC } from "../config";
import { Section, LinkButton } from "../ui";

export default function WcNotFound() {
  return (
    <Section pad="5rem">
      <div style={{ textAlign: "center", maxWidth: "44ch", margin: "0 auto" }}>
        <div style={{ fontSize: "3rem" }}>⚽</div>
        <h1 style={{ marginTop: "1rem", fontFamily: "Sora, sans-serif", fontWeight: 800, fontSize: "clamp(1.6rem, 4vw, 2.2rem)", color: WC.ink }}>
          这个页面找不到了
        </h1>
        <p style={{ marginTop: "0.75rem", color: WC.muted, lineHeight: 1.7 }}>
          该页面可能已移动或不存在。回到首页继续浏览多伦多世界杯华人指南吧。
        </p>
        <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "center", gap: "0.85rem", flexWrap: "wrap" }}>
          <LinkButton href="/worldcup" variant="primary">
            返回指南首页 →
          </LinkButton>
          <LinkButton href="/worldcup/schedule" variant="ghost">
            查看比赛日程
          </LinkButton>
        </div>
      </div>
    </Section>
  );
}
