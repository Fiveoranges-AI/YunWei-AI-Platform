/* =============================================================
   WcFooter — standalone footer for the /worldcup microsite.
   Carries the required brand line, light-touch "Powered by
   Five Oranges AI" credit, and the independence disclaimer.
   ============================================================= */

import { Link } from "wouter";
import {
  WC,
  WC_BRAND,
  WC_NAV,
  FOOTER_LINE,
  DISCLAIMER_EN,
  DISCLAIMER_CN,
  CONTACT_EMAIL,
  OFFICIAL_LINKS,
} from "./config";
import { BallMark } from "./ui";

const linkStyle = { color: "rgba(255,255,255,0.72)", textDecoration: "none", fontSize: "0.9rem" } as const;

export default function WcFooter() {
  return (
    <footer style={{ background: WC.greenDeep, color: "rgba(255,255,255,0.72)", padding: "3.5rem 0 2rem" }}>
      <div className="container">
        <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: "2.5rem" }}>
          {/* Brand */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "1rem" }}>
              <span
                style={{
                  width: "46px",
                  height: "46px",
                  borderRadius: "12px",
                  background: "#fff",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <BallMark size={28} color={WC.green} />
              </span>
              <div style={{ fontFamily: "Sora, sans-serif", lineHeight: 1.2 }}>
                <div style={{ color: "#fff", fontWeight: 800, fontSize: "1.0625rem" }}>{WC_BRAND.cn}</div>
                <div style={{ color: WC.goldSoft, fontWeight: 500, fontSize: "0.72rem", letterSpacing: "0.05em", marginTop: "3px" }}>
                  {WC_BRAND.en}
                </div>
              </div>
            </div>
            <p style={{ fontSize: "0.9rem", lineHeight: 1.7, maxWidth: "34ch" }}>
              为多伦多及大多地区华人球迷整理的世界杯观赛、出行、亲子与本地商家信息，由社区维护、持续更新。
            </p>
          </div>

          {/* Navigate */}
          <div>
            <div style={{ color: "#fff", fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "0.8rem", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: "1rem" }}>
              指南导航 · Guide
            </div>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem 1rem" }}>
              {WC_NAV.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} className="wc-flink" style={linkStyle}>
                    {item.cn}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Official + contact */}
          <div>
            <div style={{ color: "#fff", fontFamily: "Sora, sans-serif", fontWeight: 700, fontSize: "0.8rem", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: "1rem" }}>
              官方信息 · Official
            </div>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              <li>
                <a href={OFFICIAL_LINKS.fifaToronto} target="_blank" rel="noopener noreferrer" className="wc-flink" style={linkStyle}>
                  FIFA 官方 · 多伦多主办城市 ↗
                </a>
              </li>
              <li>
                <a href={OFFICIAL_LINKS.torontoHostCommittee} target="_blank" rel="noopener noreferrer" className="wc-flink" style={linkStyle}>
                  多伦多主办委员会 ↗
                </a>
              </li>
              <li>
                <a href={`mailto:${CONTACT_EMAIL}?subject=世界杯指南`} className="wc-flink" style={linkStyle}>
                  {CONTACT_EMAIL}
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Disclaimer */}
        <div
          style={{
            marginTop: "2.75rem",
            padding: "1.25rem 1.25rem",
            background: "rgba(255,255,255,0.06)",
            borderRadius: "0.6rem",
            fontSize: "0.78rem",
            lineHeight: 1.6,
            color: "rgba(255,255,255,0.62)",
          }}
        >
          <div>{DISCLAIMER_EN}</div>
          <div style={{ marginTop: "0.4rem" }}>{DISCLAIMER_CN}</div>
        </div>

        {/* Bottom line — required footer + light-touch credit */}
        <div
          style={{
            marginTop: "1.75rem",
            paddingTop: "1.25rem",
            borderTop: "1px solid rgba(255,255,255,0.12)",
            display: "flex",
            flexWrap: "wrap",
            gap: "0.5rem 1rem",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.8rem",
          }}
        >
          <span>
            2026 多伦多世界杯华人指南 ·{" "}
            <a href="/" className="wc-flink" style={{ color: WC.goldSoft, textDecoration: "none", fontWeight: 600 }}>
              Powered by Five Oranges AI
            </a>
          </span>
          <span style={{ color: "rgba(255,255,255,0.45)" }}>© {new Date().getFullYear()} · {FOOTER_LINE}</span>
        </div>
      </div>
    </footer>
  );
}
