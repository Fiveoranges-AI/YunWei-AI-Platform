/* =============================================================
   Footer — Five Oranges AI · 运帷AI (v1.3)
   Dark navy 3-column: brand+slogan / navigate / contact.
   ============================================================= */

const PORTAL_URL = "https://app.fiveoranges.ai/";
const DEMO_URL = "https://app.fiveoranges.ai/";

export default function Footer() {
  return (
    <footer style={{ padding: "4rem 0 2.5rem", background: "#0F2340", color: "#94A3B8" }}>
      <div className="container">
        <div className="footer-grid">
          {/* Brand + slogan */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "1.5rem" }}>
              <div
                style={{
                  width: "52px",
                  height: "52px",
                  borderRadius: "12px",
                  background: "#fff",
                  padding: "6px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <img
                  src="/manus-storage/logo_clean_934597e8.png"
                  alt=""
                  width={40}
                  height={40}
                  style={{ borderRadius: "8px" }}
                />
              </div>
              <div style={{ fontFamily: "Sora, sans-serif" }}>
                <div
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    color: "#fff",
                    letterSpacing: "0.02em",
                    lineHeight: 1.1,
                  }}
                >
                  FIVE ORANGES
                </div>
                <div
                  style={{
                    fontSize: "18px",
                    color: "#60A5FA",
                    fontWeight: 600,
                    letterSpacing: "0.18em",
                    marginTop: "3px",
                  }}
                >
                  运帷 AI
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "baseline", gap: "14px", flexWrap: "wrap" }}>
              <span
                style={{
                  fontFamily: "Sora, sans-serif",
                  fontWeight: 700,
                  fontSize: "1.5rem",
                  color: "#fff",
                  letterSpacing: "-0.01em",
                  lineHeight: 1.1,
                }}
              >
                Beyond the scope.
              </span>
              <span
                style={{
                  fontFamily: "Sora, sans-serif",
                  fontWeight: 600,
                  fontSize: "1rem",
                  color: "#60A5FA",
                  letterSpacing: "0.06em",
                }}
              >
                进无止境
              </span>
            </div>
          </div>

          {/* Navigate */}
          <div>
            <div
              style={{
                fontSize: "0.825rem",
                letterSpacing: "0.18em",
                color: "#fff",
                textTransform: "uppercase",
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                marginBottom: "1rem",
              }}
            >
              Navigate
            </div>
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: "0.625rem",
                fontSize: "0.9375rem",
              }}
            >
              <li>
                <a href="#solutions" className="footer-link" style={{ color: "#94A3B8" }}>
                  解决方案 · Solutions
                </a>
              </li>
              <li>
                <a href="#approach" className="footer-link" style={{ color: "#94A3B8" }}>
                  方法论 · Approach
                </a>
              </li>
              <li>
                <a href="#use-cases" className="footer-link" style={{ color: "#94A3B8" }}>
                  案例 · Use Cases
                </a>
              </li>
              <li>
                <a
                  href={DEMO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-link"
                  style={{ color: "#94A3B8" }}
                >
                  演示 · Demo
                </a>
              </li>
              <li>
                <a
                  href={PORTAL_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-link"
                  style={{ color: "#60A5FA", display: "inline-flex", alignItems: "center", gap: "6px" }}
                >
                  客户登录 · Client Portal
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M7 17L17 7M7 7h10v10" />
                  </svg>
                </a>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <div
              style={{
                fontSize: "0.825rem",
                letterSpacing: "0.18em",
                color: "#fff",
                textTransform: "uppercase",
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                marginBottom: "1rem",
              }}
            >
              Contact
            </div>
            <ul
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                display: "flex",
                flexDirection: "column",
                gap: "0.625rem",
                fontSize: "0.9375rem",
              }}
            >
              <li>
                <a
                  href="mailto:contact@fiveoranges.ai"
                  className="footer-link"
                  style={{ color: "#94A3B8" }}
                >
                  contact@fiveoranges.ai
                </a>
              </li>
              <li>Shanghai · 上海</li>
            </ul>
          </div>
        </div>

        <div
          style={{
            marginTop: "3rem",
            paddingTop: "1.5rem",
            borderTop: "1px solid rgba(255,255,255,0.08)",
            fontSize: "0.78rem",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            gap: "0.5rem",
          }}
        >
          <span>© {new Date().getFullYear()} Five Oranges AI · 运帷 AI. All rights reserved.</span>
        </div>
      </div>
    </footer>
  );
}
