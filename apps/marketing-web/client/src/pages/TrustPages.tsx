import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

type TrustPageContent = {
  title: string;
  label: string;
  description: string;
  canonical: string;
  sections: Array<{ heading: string; body: string }>;
};

const UPDATED = "June 7, 2026";

const pages = (c: Copy) => ({
  privacy: {
    title: c.privacyPolicyFiveOrangesAi,
    label: c.privacyPolicy,
    description:
      c.howFiveOrangesAiHandles,
    canonical: "https://fiveoranges.ai/privacy",
    sections: [
      {
        heading: c.informationWeCollect,
        body: c.whenYouContactFiveOranges,
      },
      {
        heading: c.howWeUseInformation,
        body: c.weUseThisInformationTo,
      },
      {
        heading: c.informationSharing,
        body: c.weDoNotSellOr,
      },
      {
        heading: c.contactUs,
        body: c.toRequestAccessCorrectionOr,
      },
    ],
  },
  terms: {
    title: c.termsOfUseFiveOranges,
    label: c.termsOfUse,
    description:
      c.termsForUsingFiveOranges,
    canonical: "https://fiveoranges.ai/terms",
    sections: [
      {
        heading: c.websiteInformation,
        body: c.thisWebsiteDescribesFiveOranges,
      },
      {
        heading: c.demosAndUseCases,
        body: c.demosIllustratePotentialSystemExperiences,
      },
      {
        heading: c.intellectualProperty,
        body: c.websiteTextVisualDesignBrand,
      },
      {
        heading: c.limitations,
        body: c.weAimToKeepInformation,
      },
    ],
  },
  security: {
    title: c.dataSecurityFiveOrangesAi,
    label: c.dataSecurity2,
    description:
      c.fiveOrangesAiPrinciplesFor,
    canonical: "https://fiveoranges.ai/data-security",
    sections: [
      {
        heading: c.minimumNecessaryInformation,
        body: c.duringDiscoveryAndScopingWe,
      },
      {
        heading: c.authorizedDataUse,
        body: c.businessDataConnectionsDemosAnd,
      },
      {
        heading: c.systemAndAccessDesign,
        body: c.ourDesignPrioritiesForCrm,
      },
      {
        heading: c.boundariesForAi,
        body: c.aiShouldServeAClear,
      },
    ],
  },
} satisfies Record<string, TrustPageContent>);

function TrustPage({ content }: { content: TrustPageContent }) {
  const { copy: c, href: localize, locale } = useLocale();

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="trust-page">
        <section className="trust-hero-section">
          <div className="container">
            <div className="trust-page-inner">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {content.label}
              </span>
              <h1>{content.title.replace(c.fiveOrangesAi2, "")}</h1>
              <p>{locale === "en" ? c.lastUpdated : "最后更新："} {locale === "en" ? UPDATED : "2026年6月7日"}</p>
            </div>
          </div>
        </section>

        <section className="trust-content-section">
          <div className="container">
            <div className="trust-content-card">
              {content.sections.map((section) => (
                <article key={section.heading}>
                  <h2>{section.heading}</h2>
                  <p>{section.body}</p>
                </article>
              ))}
              <a href={localize("/strategy-call")} className="trust-page-link">
                {c.contactFiveOrangesAi2}<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function PrivacyPage() {
  const { copy: c } = useLocale();
  return <TrustPage content={pages(c).privacy} />;
}

export function TermsPage() {
  const { copy: c } = useLocale();
  return <TrustPage content={pages(c).terms} />;
}

export function DataSecurityPage() {
  const { copy: c } = useLocale();
  return <TrustPage content={pages(c).security} />;
}
