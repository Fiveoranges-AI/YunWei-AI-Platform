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
import { useEffect } from "react";
import type { ReactNode } from "react";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";

const CONTACT_HREF = "mailto:contact@fiveoranges.ai";

const seo = {
  title: "Kobe Li | Founder of Five Oranges AI / 运帷AI",
  description:
    "Kobe Li is the Founder and Chief AI Transformation Architect of Five Oranges AI / 运帷AI, helping manufacturing SMEs adopt practical AI, Dynamics 365, Power Platform and lightweight digital systems.",
  keywords:
    "Kobe Li, Five Oranges AI, 运帷AI, AI数字化转型, 制造业AI, Dynamics 365 architect, Power Platform consultant, AI transformation architect, CRM ERP modernization, manufacturing digital transformation",
};

const heroCredentials = [
  "Founder of Five Oranges AI / 运帷AI",
  "10+ years enterprise transformation",
  "Dynamics 365 / Power Platform / CRM / ERP",
  "AI-first systems for manufacturing SMEs",
  "Practical delivery, not theoretical consulting",
];

const philosophyCards = [
  {
    icon: Compass,
    en: "Business-first",
    cn: "先理解业务，再设计系统。",
  },
  {
    icon: Layers3,
    en: "Lightweight before heavy ERP",
    cn: "先做轻量化可落地方案，再考虑大型系统扩展。",
  },
  {
    icon: Sparkles,
    en: "AI embedded into workflow",
    cn: "AI必须进入真实流程，而不是停留在概念演示。",
  },
  {
    icon: ShieldCheck,
    en: "Adoption over complexity",
    cn: "系统价值取决于员工是否真的愿意用、老板是否真的看得懂。",
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

const bestFitClients = [
  "仍在用 Excel 管库存、订单、客户或项目",
  "老板知道企业需要数字化，但不知道第一步该做什么",
  "觉得传统ERP太重、太贵、太难推动",
  "想用AI提升管理效率，但缺少清晰落地场景",
  "厂二代正在推进企业管理升级",
  "有出海、外贸、北美客户或管理规范化需求",
  "希望先做一个可验证Demo，再决定是否扩大投入",
];

function useSeoMetadata() {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = seo.title;

    const upsertMeta = (attribute: "name" | "property", key: string, content: string) => {
      let tag = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
      if (!tag) {
        tag = document.createElement("meta");
        tag.setAttribute(attribute, key);
        document.head.appendChild(tag);
      }
      const previous = tag.getAttribute("content");
      tag.setAttribute("content", content);
      return () => {
        if (previous === null) tag?.remove();
        else tag?.setAttribute("content", previous);
      };
    };

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    const previousCanonical = canonical?.getAttribute("href");
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.setAttribute("rel", "canonical");
      document.head.appendChild(canonical);
    }
    canonical.setAttribute("href", "https://fiveoranges.ai/kobeli");

    const cleanup = [
      upsertMeta("name", "description", seo.description),
      upsertMeta("name", "keywords", seo.keywords),
      upsertMeta("property", "og:title", seo.title),
      upsertMeta("property", "og:description", seo.description),
      upsertMeta("property", "og:url", "https://fiveoranges.ai/kobeli"),
      upsertMeta("property", "og:type", "profile"),
      upsertMeta("name", "twitter:title", seo.title),
      upsertMeta("name", "twitter:description", seo.description),
    ];

    return () => {
      document.title = previousTitle;
      cleanup.forEach((fn) => fn());
      if (previousCanonical === undefined) canonical?.remove();
      else if (previousCanonical === null) canonical?.removeAttribute("href");
      else canonical?.setAttribute("href", previousCanonical);
    };
  }, []);
}

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
  return (
    <a href={CONTACT_HREF} className="founder-primary-button hover-lift">
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
  const Icon = icon === "home" ? Home : Mail;
  return (
    <a href={href} className="founder-secondary-button">
      <Icon size={15} strokeWidth={2.1} />
      {children}
    </a>
  );
}

function FounderCredibilityPanel() {
  return (
    <aside className="founder-profile-panel" aria-label="Kobe Li founder credibility panel">
      <div className="founder-profile-header">
        <div className="founder-avatar" aria-hidden>
          KL
        </div>
        <div>
          <div className="founder-profile-eyebrow">Founder Credibility</div>
          <h2 className="founder-profile-name">Kobe Li</h2>
          <div className="founder-profile-subtitle">North America-based AI & Digital Transformation Architect</div>
        </div>
      </div>

      <div className="founder-profile-proof-list founder-profile-proof-list-single">
        {heroCredentials.map((item) => (
          <div key={item} className="founder-profile-proof-item">
            <CheckCircle2 size={17} strokeWidth={2.1} />
            <span>{item}</span>
          </div>
        ))}
      </div>

      <div className="founder-executive-principle">
        <ShieldCheck size={18} strokeWidth={2} />
        <span>Practical AI transformation starts with business problems, not software features.</span>
      </div>

      <div className="founder-profile-metrics">
        <div>
          <span>Focus</span>
          <strong>Manufacturing SMEs</strong>
        </div>
        <div>
          <span>Method</span>
          <strong>Lightweight systems first</strong>
        </div>
      </div>
    </aside>
  );
}

export default function Kobeli() {
  useSeoMetadata();

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
                  Kobe Li / Founder
                </span>
                <h1 className="founder-hero-title">Kobe Li</h1>
                <div className="founder-hero-role">
                  <strong>Founder & Chief AI Transformation Architect</strong>
                  <span>Five Oranges AI / 运帷AI</span>
                </div>
                <p className="founder-hero-support founder-hero-support-strong">
                  North America-based AI & Digital Transformation Architect helping traditional businesses turn operational complexity into structured, AI-enabled systems.
                </p>
                <p className="founder-hero-copy">
                  Kobe Li 拥有10年以上企业级数字化转型、Microsoft Dynamics 365、Power Platform、CRM、ERP、流程自动化和系统架构经验。他创立 Five Oranges AI / 运帷AI，专注于帮助传统制造业企业用更轻量、更务实、更容易落地的方式完成 AI 与数字化升级。
                </p>
                <div className="founder-button-row">
                  <PrimaryButton>预约战略沟通</PrimaryButton>
                  <SecondaryButton href={CONTACT_HREF}>Contact Five Oranges AI</SecondaryButton>
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
                title="让传统企业用更低风险、更高确定性的方式完成AI数字化升级。"
                subtitle="Practical AI transformation starts with business problems, not software features."
              />
              <div className="founder-story-card">
                <p>
                  很多中小制造企业并不是不愿意数字化，而是过去接触到的系统太复杂、太贵、太难落地。Five Oranges AI / 运帷AI 的使命，是帮助企业从最真实的经营问题出发，先解决库存、流程、客户、订单和数据管理中的关键痛点，再逐步构建可扩展的AI增强型业务系统。
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="founder-work-section bg-section-blue">
          <div className="container">
            <div className="founder-work-heading">
              <SectionHeader
                label="落地原则 · OPERATING PHILOSOPHY"
                title="Kobe 如何降低 AI 数字化落地风险"
                subtitle="Operating Philosophy: 用企业真正能接受、能执行、能持续使用的方式推进AI数字化。"
              />
            </div>
            <div className="founder-work-grid">
              {philosophyCards.map((card, index) => {
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
                label="能力 · SELECTED EXPERTISE"
                title="面向制造业升级的核心能力"
                subtitle="Selected Expertise: 围绕制造业AI数字化升级需要的路线图、系统架构、流程和数据能力。"
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
                label="经验 · FOUNDER EXPERIENCE"
                title="从企业级数字化到制造业AI落地"
                subtitle="Founder Experience: 用创始人的企业级交付经验，服务制造业中小企业的AI落地。"
              />
              <div className="founder-experience-card">
                <p>
                  Founder experience includes enterprise consulting, public sector transformation, CRM/ERP solution architecture, workflow automation, stakeholder workshops, data integration, UAT, training, and production delivery.
                </p>
                <div className="founder-experience-pill-grid">
                  {experiencePillars.map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
                <div className="founder-experience-associated">
                  <strong>Professional experience includes work associated with organizations such as:</strong>
                  <div>
                    {associatedOrganizations.map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                  <p>These references describe founder professional experience only and do not imply Five Oranges AI client relationships.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="founder-client-section">
          <div className="container">
            <div className="founder-client-grid-wrap">
              <SectionHeader
                label="适合沟通 · BEST-FIT ENGAGEMENTS"
                title="适合沟通的企业类型"
                subtitle="Best Fit Engagements: 适合与 Kobe / Five Oranges AI 沟通的企业。"
              />
              <div className="founder-client-grid">
                {bestFitClients.map((item) => (
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
                定位语 · POSITIONING STATEMENT
              </span>
              <blockquote>
                我帮助传统企业老板，把混乱的业务流程转化为清晰、可追踪、可自动化、可AI增强的管理系统。
              </blockquote>
              <p>I help traditional business owners turn operational complexity into structured, AI-enabled systems.</p>
            </div>
          </div>
        </section>

        <section id="contact" className="founder-final-cta">
          <div className="container">
            <div className="founder-cta-grid">
              <div>
                <SectionHeader
                  label="开始合作 · GET STARTED"
                  title="准备判断你的企业第一个AI落地场景？"
                  subtitle="如果你的企业正在面对库存、流程、客户管理、ERP、CRM或AI落地问题，可以预约一次战略沟通，先判断最值得优先解决的业务场景。"
                />
              </div>
              <div className="founder-button-row">
                <PrimaryButton>预约战略沟通</PrimaryButton>
                <SecondaryButton href="/" icon="home">
                  返回首页
                </SecondaryButton>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
