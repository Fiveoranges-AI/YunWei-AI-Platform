import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

const WHY_CARDS = (c: Copy) => [
  {
    title: c.startWithTheBusiness,
    body: c.identifyTheMostValuableInventory,
  },
  {
    title: c.keepTheFirstStepManageable,
    body: c.aUsefulSystemForA,
  },
  {
    title: c.bringAiIntoRealWorkflows,
    body: c.exploreAiInReportingKnowledge,
  },
];

const WORKFLOW = (c: Copy) => [c.businessDiscovery, c.aTestablePrototype, c.phasedRollout, c.continuousImprovement];

export default function About() {
  const { copy: c, href: localize } = useLocale();

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="company-page">
        <section className="company-hero-section">
          <div className="container">
            <div className="company-hero-inner">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.aboutFiveOrangesAi2}
              </span>
              <h1>{c.practicalAiForTheWay}</h1>
              <p>
                {c.fiveOrangesAiIsA2}
              </p>
            </div>
          </div>
        </section>

        <section className="company-section">
          <div className="container">
            <div className="company-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.ourMission}
              </span>
              <h2>{c.makeCriticalOperationsEasierTo}</h2>
              <p>
                {c.digitalTransformationNeedsAClear}
              </p>
            </div>
          </div>
        </section>

        <section className="company-section company-section-blue">
          <div className="container">
            <div className="company-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.whyFiveOrangesAi2}
              </span>
              <h2>{c.enterpriseSystemsExperienceAppliedTo}</h2>
            </div>
            <div className="company-card-grid">
              {WHY_CARDS(c).map((card) => (
                <article key={card.title} className="company-card">
                  <h3>{card.title}</h3>
                  <p>{card.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="company-section">
          <div className="container">
            <div className="company-founder-mini">
              <div>
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  {c.founderAndArchitecture}
                </span>
                <h2>{c.experienceThatConnectsBusinessNeeds}</h2>
                <p>
                  {c.foundedByKobeLiFive}
                </p>
              </div>
              <a href={localize("/kobeli")} className="company-secondary-link">
                {c.meetTheFounder}<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </a>
            </div>
          </div>
        </section>

        <section className="company-section company-section-blue">
          <div className="container">
            <div className="company-workflow-panel">
              <div>
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  {c.howWeWork}
                </span>
                <h2>{c.startWithDiscoveryDecideWhat}</h2>
                <p>{c.weAssessWhetherAiOr}</p>
              </div>
              <div className="company-workflow">
                {WORKFLOW(c).map((step, index) => (
                  <div key={step}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{step}</strong>
                  </div>
                ))}
              </div>
              <a href={localize("/strategy-call")} className="company-primary-link">
                {c.bookA30MinuteDiscovery2}
              </a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
