import { useLocale } from "@/i18n/LocaleContext";
/* =============================================================
   Footer — Five Oranges AI · 运帷AI (v1.3)
   Dark navy 3-column: brand+slogan / navigate / contact.
   ============================================================= */

const PORTAL_URL = "https://app.fiveoranges.ai/";
const DEMO_URL = "/demo.html";
const STRATEGY_CALL_URL = "/strategy-call";

export default function Footer() {
  const { copy: c, href: localize } = useLocale();
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
                  {c.fiveOranges}
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
                  {c.ai}
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
                {c.beyondTheScope2}
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
                {c.operationalIntelligenceForSmeManufacturing}
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
              {c.navigate}
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
                <a href={localize("/#solutions")} className="footer-link" style={{ color: "#94A3B8" }}>
                  {c.solutions}
                </a>
              </li>
              <li>
                <a href={localize("/#use-cases")} className="footer-link" style={{ color: "#94A3B8" }}>
                  {c.useCases}
                </a>
              </li>
              <li>
                <a href={localize("/#approach")} className="footer-link" style={{ color: "#94A3B8" }}>
                  {c.approach}
                </a>
              </li>
              <li>
                <a href={localize("/resources")} className="footer-link" style={{ color: "#94A3B8" }}>
                  {c.resources}
                </a>
              </li>
              <li>
                <a href={localize("/about")} className="footer-link" style={{ color: "#94A3B8" }}>
                  {c.about}
                </a>
              </li>
              <li>
                <a
                  href={localize(DEMO_URL)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-link"
                  style={{ color: "#94A3B8" }}
                >
                  {c.demo2}
                </a>
              </li>
              <li>
                <a
                  href={localize(PORTAL_URL)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-link"
                  style={{ color: "#60A5FA", display: "inline-flex", alignItems: "center", gap: "6px" }}
                >
                  {c.clientPortal3}<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
              {c.contact}
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
                <a href={localize(STRATEGY_CALL_URL)} className="footer-link" style={{ color: "#60A5FA" }}>
                  {c.talkToUs}
                </a>
              </li>
              <li>
                <a
                  href={localize("mailto:contact@fiveoranges.ai")}
                  className="footer-link"
                  style={{ color: "#94A3B8" }}
                >
                  {c.contactFiveorangesAi}
                </a>
              </li>
              <li>{c.canadianAiStartupServingManufacturers}</li>
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
          <span>© {new Date().getFullYear()} {c.fiveOrangesAiAllRights}</span>
          <span className="footer-legal-links">
            <a href={localize("/privacy")} className="footer-link" style={{ color: "#94A3B8" }}>
              {c.privacy}
            </a>
            <a href={localize("/terms")} className="footer-link" style={{ color: "#94A3B8" }}>
              {c.terms}
            </a>
            <a href={localize("/data-security")} className="footer-link" style={{ color: "#94A3B8" }}>
              {c.dataSecurity}
            </a>
            <a href={localize(STRATEGY_CALL_URL)} className="footer-link" style={{ color: "#94A3B8" }}>
              {c.contact}
            </a>
          </span>
        </div>
      </div>
    </footer>
  );
}
