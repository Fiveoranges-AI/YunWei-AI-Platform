import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
/* =============================================================
   Solutions — Four building blocks for an AI-native operation (v1.3)
   ============================================================= */

const SOLUTIONS = (c: Copy) => [
  {
    cn: c.aiAssistants,
    en: "AI Agents",
    desc: c.exploreAssistantsThatAnswerOperational,
  },
  {
    cn: c.businessKnowledge,
    en: "Knowledge Bases",
    desc: c.organizeProceduresDocumentsAndBusiness,
  },
  {
    cn: c.workflowAutomation,
    en: "Process Automation",
    desc: c.assessHowApprovedDataFlows,
  },
  {
    cn: c.operationsOverview,
    en: "Intelligent Dashboards",
    desc: c.bringOperationalInformationTogetherTo,
  },
];

export default function SolutionsSection() {
  const { copy: c, locale } = useLocale();
  return (
    <section id="solutions" style={{ padding: "7rem 0", background: "#FFFFFF" }}>
      <div className="container">
        <div
          className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6"
          style={{ marginBottom: "3.5rem" }}
        >
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              {c.solutions3}
            </span>
            <h2
              style={{
                marginTop: "1rem",
                fontSize: "clamp(2.1rem, 4vw, 3rem)",
                lineHeight: 1.15,
                fontWeight: 700,
                color: "#0F2340",
                maxWidth: "760px",
                letterSpacing: "-0.01em",
                fontFamily: "Sora, sans-serif",
              }}
            >
              {c.anIntelligenceLayerForYour}
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
              {c.designedAroundManufacturingWorkflows}
            </div>
          </div>
          <p
            style={{
              color: "#64748B",
              maxWidth: "360px",
              fontSize: "0.95rem",
              lineHeight: 1.65,
            }}
          >
            {c.weScopeEachEngagementAround}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {SOLUTIONS(c).map((s, i) => (
            <article
              key={s.en}
              className="solution-card card-lift"
              style={{
                padding: "2rem 1.875rem",
                borderRadius: "0.875rem",
                background: "#FFFFFF",
                border: "1.5px solid rgba(15,35,64,0.18)",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <div
                style={{
                  width: "54px",
                  height: "54px",
                  borderRadius: "0.625rem",
                  background: "var(--brand-blue-pale)",
                  border: "1px solid rgba(45,110,168,0.22)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--brand-blue)",
                  fontFamily: "Sora, sans-serif",
                  fontWeight: 700,
                  fontSize: "1.0625rem",
                  letterSpacing: "0.04em",
                }}
              >
                0{i + 1}
              </div>
              <div>
                <div
                  style={{
                    fontSize: "1.375rem",
                    fontWeight: 700,
                    color: "#0F2340",
                    fontFamily: "Sora, sans-serif",
                    lineHeight: 1.2,
                    letterSpacing: "0.005em",
                  }}
                >
                  {s.cn}
                </div>
                {locale === "zh-CN" && <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--brand-blue)",
                    letterSpacing: "0.08em",
                    marginTop: "4px",
                    fontFamily: "Sora, sans-serif",
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >{s.en}</div>}
              </div>
              <p
                style={{
                  color: "#334155",
                  fontSize: "1rem",
                  lineHeight: 1.65,
                  marginTop: "0.25rem",
                }}
              >
                {s.desc}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
