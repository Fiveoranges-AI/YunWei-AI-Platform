import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

const RESOURCE_CARDS = (c: Copy) => [
  {
    title: "FAQ",
    eyebrow: c.frequentlyAskedQuestions2,
    body: c.understandOurDiscoveryProcessApproach,
    href: "/#faq",
  },
  {
    title: c.dataSecurityAndAiBoundaries,
    eyebrow: "DATA SECURITY",
    body: c.readOurPrinciplesForAuthorized,
    href: "/data-security",
  },
  {
    title: c.anIllustrative90DayRoadmap,
    eyebrow: "ROADMAP",
    body: c.aReferencePathFromBusiness,
    href: "#roadmap",
  },
  {
    title: c.aiArticles,
    eyebrow: "ARTICLES",
    body: c.articlesOnManufacturingAiCrm,
    href: "#articles",
  },
  {
    title: c.manufacturingAiInsights,
    eyebrow: "INSIGHTS",
    body: c.practicalObservationsForManufacturingOwners,
    href: "#insights",
  },
];

export default function Resources() {
  const { copy: c, href: localize } = useLocale();

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="resources-page">
        <section className="company-hero-section">
          <div className="container">
            <div className="company-hero-inner">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.resources3}
              </span>
              <h1>{c.aClearerStartingPointFor}</h1>
              <p>
                {c.exploreFrequentlyAskedQuestionsData}
              </p>
            </div>
          </div>
        </section>

        <section className="resources-section">
          <div className="container">
            <div className="resources-grid">
              {RESOURCE_CARDS(c).map((card) => (
                <a key={card.title} href={localize(card.href)} className="resource-card">
                  <span>{card.eyebrow}</span>
                  <h2>{card.title}</h2>
                  <p>{card.body}</p>
                </a>
              ))}
            </div>
          </div>
        </section>

        <section id="roadmap" className="resources-detail-section">
          <div className="container">
            <article className="resources-detail-panel">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.anIllustrative90DayRoadmap}
              </span>
              <h2>{c.validateAUseCaseStructure}</h2>
              <p>
                {c.anIllustrativeSequenceUseThe}
              </p>
            </article>
          </div>
        </section>

        <section id="articles" className="resources-detail-section resources-detail-muted">
          <div className="container">
            <article className="resources-detail-panel">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.aiArticles}
              </span>
              <h2>{c.articlesAreBeingPrepared}</h2>
              <p>{c.futureArticlesWillExploreInventory}</p>
            </article>
          </div>
        </section>

        <section id="insights" className="resources-detail-section">
          <div className="container">
            <article className="resources-detail-panel">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.manufacturingAiInsights}
              </span>
              <h2>{c.practicalAiPerspectivesForManufacturing}</h2>
              <p>{c.ourFocusIsOnUse}</p>
            </article>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
