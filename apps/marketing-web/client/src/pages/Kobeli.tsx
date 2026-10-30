import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
import {
  ArrowRight,
  BarChart3,
  Boxes,
  CheckCircle2,
  ClipboardCheck,
  Compass,
  Database,
  Factory,
  Home,
  Layers3,
  Mail,
  Network,
  Quote,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { ReactNode } from "react";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

const CONTACT_HREF = "/strategy-call";


const heroCredentials = (c: Copy) => [
  c.founderOfFiveOrangesAi,
  c.founderArchitectureExperience,
  "Dynamics 365 / Power Platform / CRM / ERP",
  "AI-first systems for manufacturing SMEs",
  "Practical delivery, not theoretical consulting",
];

const philosophyCards = (c: Copy) => [
  {
    icon: Compass,
    en: "Business-first",
    cn: c.understandTheBusinessBeforeDesigning,
  },
  {
    icon: Layers3,
    en: "Lightweight before heavy ERP",
    cn: c.startWithAFocusedSolution,
  },
  {
    icon: Sparkles,
    en: "AI embedded into workflow",
    cn: c.embedAiInAUseful,
  },
  {
    icon: ShieldCheck,
    en: "Adoption over complexity",
    cn: c.systemValueDependsOnWhether,
  },
];

const expertiseCards = [
  { icon: Compass, title: "AI Transformation Roadmap" },
  { icon: Factory, title: "Manufacturing Process Modernization" },
  { icon: Network, title: "Dynamics 365 Architecture" },
  { icon: Layers3, title: "Power Platform Solution Design" },
  { icon: Boxes, title: "CRM / ERP Modernization" },
  { icon: ClipboardCheck, title: "Inventory & Operations Systems" },
  { icon: Workflow, title: "Workflow Automation" },
  { icon: BarChart3, title: "Data Model & Reporting Design" },
  { icon: Database, title: "Requirements Discovery & Solution Blueprinting" },
];

const experiencePillars = [
  "Enterprise consulting",
  "Public sector transformation",
  "CRM/ERP solution architecture",
  "Workflow automation",
  "Stakeholder workshops",
  "Data integration",
  "UAT and training",
  "Production delivery",
];

const associatedOrganizations = [
  "CGI",
  "KPMG",
  "Grant Thornton",
  "Canadian public sector",
  "Municipal transformation programs",
];

const bestFitClients = (c: Copy) => [
  c.inventoryOrdersCustomersOrProjects,
  c.youNeedAClearFirst,
  c.traditionalErpProjectsFeelToo,
  c.youWantPracticalAiWith,
  c.youAreLeadingASuccession,
  c.youAreExpandingIntoNew,
  c.youWantToEvaluateA,
];


function SectionHeader({
  label,
  title,
  subtitle,
}: {
  label: string;
  title: string;
  subtitle?: string;
}) {

  return (
    <div className="founder-section-header">
      <span className="section-label">
        <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
        {label}
      </span>
      <h2 className="founder-section-title">{title}</h2>
      {subtitle && <p className="founder-section-subtitle">{subtitle}</p>}
    </div>
  );
}

function PrimaryButton({ children }: { children: ReactNode }) {
  const { href: localize } = useLocale();
  return (
    <a href={localize(CONTACT_HREF)} className="founder-primary-button hover-lift">
      {children}
      <ArrowRight size={16} strokeWidth={2.2} />
    </a>
  );
}

function SecondaryButton({
  href,
  children,
  icon = "mail",
}: {
  href: string;
  children: ReactNode;
  icon?: "mail" | "home";
}) {
  const { href: localize } = useLocale();
  const Icon = icon === "home" ? Home : Mail;
  return (
    <a href={localize(href)} className="founder-secondary-button">
      <Icon size={15} strokeWidth={2.1} />
      {children}
    </a>
  );
}

function FounderCredibilityPanel() {
  const { copy: c } = useLocale();
  return (
    <aside className="founder-profile-panel" aria-label="Kobe Li founder credibility panel">
      <div className="founder-profile-header">
        <div className="founder-avatar" aria-hidden>
          {c.kl}
        </div>
        <div>
          <div className="founder-profile-eyebrow">{c.founderBackground}</div>
          <h2 className="founder-profile-name">{c.kobeLi}</h2>
          <div className="founder-profile-subtitle">{c.enterpriseSolutionArchitecturePracticalAi}</div>
        </div>
      </div>

      <div className="founder-profile-proof-list founder-profile-proof-list-single">
        {heroCredentials(c).map((item) => (
          <div key={item} className="founder-profile-proof-item">
            <CheckCircle2 size={17} strokeWidth={2.1} />
            <span>{item}</span>
          </div>
        ))}
      </div>

      <div className="founder-executive-principle">
        <ShieldCheck size={18} strokeWidth={2} />
        <span>{c.practicalAiTransformationStartsWith}</span>
      </div>

      <div className="founder-profile-metrics">
        <div>
          <span>{c.focus}</span>
          <strong>{c.smallAndMidSizedManufacturers}</strong>
        </div>
        <div>
          <span>{c.method}</span>
          <strong>{c.lightweightSystemsFirst}</strong>
        </div>
      </div>
    </aside>
  );
}

export default function Kobeli() {
  const { copy: c, href: localize, locale } = useLocale();

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main>
        <section id="kobeli-top" className="founder-hero-section">
          <div className="container">
            <div className="founder-hero-grid">
              <div>
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  {c.kobeLiFounder}
                </span>
                <h1 className="founder-hero-title">{c.kobeLi}</h1>
                <div className="founder-hero-role">
                  <strong>{c.founderSolutionArchitect}</strong>
                  <span>{c.fiveOrangesAi}</span>
                </div>
                <p className="founder-hero-support founder-hero-support-strong">
                  {c.helpingManufacturersConnectOperationalInformation}
                </p>
                <p className="founder-hero-copy">
                  {c.kobeLiBringsExperienceIn}
                </p>
                <div className="founder-button-row">
                  <PrimaryButton>{c.bookADiscoveryCall}</PrimaryButton>
                  <SecondaryButton href={localize(CONTACT_HREF)}>{c.contactFiveOrangesAi}</SecondaryButton>
                </div>
              </div>

              <div>
                <FounderCredibilityPanel />
              </div>
            </div>
          </div>
        </section>

        <section className="founder-story-section">
          <div className="container">
            <div className="founder-story-grid">
              <SectionHeader
                label="FOUNDER MISSION"
                title={c.helpManufacturersTakeAClear}
                subtitle={c.practicalAiTransformationStartsWith}
              />
              <div className="founder-story-card">
                <p>
                  {c.forManySmallerManufacturersLarge}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="founder-work-section bg-section-blue">
          <div className="container">
            <div className="founder-work-heading">
              <SectionHeader
                label={c.operatingPhilosophy}
                title={c.reduceUncertaintyBeforeExpandingThe}
                subtitle={c.designSystemsYourTeamCan}
              />
            </div>
            <div className="founder-work-grid">
              {philosophyCards(c).map((card, index) => {
                const Icon = card.icon;
                return (
                  <article key={card.en} className="founder-work-card card-lift">
                    <div className="founder-work-card-top">
                      <div className="founder-work-icon">
                        <Icon size={24} strokeWidth={1.9} />
                      </div>
                      <span>0{index + 1}</span>
                    </div>
                    <h3>{card.en}</h3>
                    <p>{card.cn}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="founder-expertise-section">
          <div className="container">
            <div className="founder-work-heading">
              <SectionHeader
                label={c.selectedExpertise}
                title={c.architectureForPracticalOperationalImprovement}
                subtitle={c.businessDiscoverySystemDesignWorkflows}
              />
            </div>
            <div className="founder-expertise-grid">
              {expertiseCards.map((item) => {
                const Icon = item.icon;
                return (
                  <article key={item.title} className="founder-expertise-card">
                    <Icon size={21} strokeWidth={1.9} />
                    <span>{item.title}</span>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="founder-experience-section">
          <div className="container">
            <div className="founder-experience-grid">
              <SectionHeader
                label={c.founderExperience}
                title={c.fromEnterpriseSystemsToManufacturing}
                subtitle={c.applyEnterpriseArchitectureExperienceTo}
              />
              <div className="founder-experience-card">
                <p>
                  {c.founderExperienceIncludesEnterpriseConsulting}
                </p>
                <div className="founder-experience-pill-grid">
                  {experiencePillars.map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
                {locale === "zh-CN" && <div className="founder-experience-associated">
                  <strong>{c.professionalExperienceIncludesWorkAssociated}</strong>
                  <div>
                    {associatedOrganizations.map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                  <p>{c.theseReferencesDescribeFounderProfessional}</p>
                </div>}
              </div>
            </div>
          </div>
        </section>

        <section className="founder-client-section">
          <div className="container">
            <div className="founder-client-grid-wrap">
              <SectionHeader
                label={c.bestFitEngagements}
                title={c.whoWeWorkWith}
                subtitle={c.commonReasonsManufacturingLeadersStart}
              />
              <div className="founder-client-grid">
                {bestFitClients(c).map((item) => (
                  <div key={item} className="founder-client-item">
                    <CheckCircle2 size={18} strokeWidth={2.1} />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="founder-quote-section">
          <div className="container">
            <div className="founder-quote-card">
              <Quote size={44} color="#2D6EA8" strokeWidth={1.6} />
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                {c.ourFocus}
              </span>
              <blockquote>
                {c.iHelpBusinessOwnersTurn}
              </blockquote>
              <p>{c.iHelpTraditionalBusinessOwners}</p>
            </div>
          </div>
        </section>

        <section id="contact" className="founder-final-cta">
          <div className="container">
            <div className="founder-cta-grid">
              <div>
                <SectionHeader
                  label={c.getStarted}
                  title={c.whatShouldYourFirstAi}
                  subtitle={c.ifYouAreAssessingInventory}
                />
              </div>
              <div className="founder-button-row">
                <PrimaryButton>{c.bookADiscoveryCall}</PrimaryButton>
                <SecondaryButton href={localize("/")} icon="home">
                  {c.backToHome}</SecondaryButton>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
