/* =============================================================
   CTA — Ready to see it run on your data? (v1.3)
   2-column layout: copy + 3-button cluster (Demo / Book / Portal).
   ============================================================= */

const DEMO_URL = "/demo.html";
const PORTAL_URL = "https://app.fiveoranges.ai/";
const CONTACT_HREF = "mailto:contact@fiveoranges.ai";

export default function CTASection() {
  return (
    <section
      id="contact"
      style={{
        padding: "6rem 0",
        background: "#FFFFFF",
        borderTop: "1px solid #E2E8F0",
      }}
    >
      <div className="container">
        <div className="cta-grid">
          <div style={{ maxWidth: "620px" }}>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              进无止境 · BEYOND THE SCOPE
            </span>
            <h2
              style={{
                marginTop: "1rem",
                fontSize: "clamp(1.85rem, 3.2vw, 2.625rem)",
                lineHeight: 1.2,
                fontWeight: 700,
                color: "#0F2340",
                letterSpacing: "-0.01em",
                fontFamily: "Sora, sans-serif",
              }}
            >
              Ready to see it run on your data?
            </h2>
            <div
              style={{
                marginTop: "0.75rem",
                fontFamily: "Sora, sans-serif",
                fontWeight: 500,
                fontSize: "1.0625rem",
                color: "#475569",
              }}
            >
              想看 AI 在你自己的数据上跑起来吗？
            </div>
            <p
              style={{
                marginTop: "1.25rem",
                color: "#475569",
                fontSize: "1rem",
                lineHeight: 1.7,
              }}
            >
              预约 30 分钟战略通话。我们将和你一起诊断你最痛的那条流程，并诚实地告诉你——AI 是否是合适的解法。
            </p>
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.875rem",
              justifyContent: "flex-start",
            }}
          >
            <a
              href={DEMO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hover-lift"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "12px",
                padding: "14px 22px",
                background: "var(--brand-blue)",
                color: "#fff",
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                fontSize: "15px",
                borderRadius: "10px",
                boxShadow: "0 8px 24px rgba(45,110,168,0.32)",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.15 }}>
                <span>查看演示</span>
                <span
                  style={{
                    fontSize: "10.5px",
                    letterSpacing: "0.14em",
                    opacity: 0.78,
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >
                  Try Live Demo
                </span>
              </span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>

            <a
              href={CONTACT_HREF}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 22px",
                color: "#0F2340",
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                fontSize: "15px",
                borderRadius: "10px",
                border: "1.5px solid rgba(15,35,64,0.18)",
                background: "#fff",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.15 }}>
                <span>预约咨询</span>
                <span
                  style={{
                    fontSize: "10.5px",
                    letterSpacing: "0.14em",
                    opacity: 0.6,
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >
                  Book a Call
                </span>
              </span>
            </a>

            <a
              href={PORTAL_URL}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "14px 22px",
                color: "var(--brand-blue)",
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                fontSize: "15px",
                borderRadius: "10px",
                border: "1.5px solid rgba(45,110,168,0.5)",
                background: "#fff",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.15 }}>
                <span>客户登录</span>
                <span
                  style={{
                    fontSize: "10.5px",
                    letterSpacing: "0.14em",
                    opacity: 0.7,
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >
                  Client Portal
                </span>
              </span>
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
