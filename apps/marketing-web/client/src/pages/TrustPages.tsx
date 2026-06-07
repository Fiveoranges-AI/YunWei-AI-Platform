import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { usePageSeo } from "@/utils/usePageSeo";

type TrustPageContent = {
  title: string;
  label: string;
  description: string;
  canonical: string;
  sections: Array<{ heading: string; body: string }>;
};

const UPDATED = "June 7, 2026";

const pages = {
  privacy: {
    title: "Privacy Policy | Five Oranges AI / 运帷AI",
    label: "隐私政策 · PRIVACY",
    description:
      "Five Oranges AI / 运帷AI privacy policy for business inquiry, website, demo and consulting communications.",
    canonical: "https://fiveoranges.ai/privacy",
    sections: [
      {
        heading: "我们收集的信息",
        body: "当你通过网站、邮件或预约沟通联系 Five Oranges AI / 运帷AI 时，我们可能会收集姓名、公司、联系方式、业务需求、项目背景和你主动提供的资料。",
      },
      {
        heading: "我们如何使用信息",
        body: "这些信息仅用于回应咨询、安排沟通、理解业务场景、准备方案建议、改进网站体验和提供与 AI 数字化转型相关的服务。",
      },
      {
        heading: "数据分享",
        body: "除非获得你的授权、法律要求或为了提供必要的技术服务，我们不会出售或出租你的个人信息或企业资料。",
      },
      {
        heading: "联系我们",
        body: "如需访问、更正或删除你提供的信息，请联系 contact@fiveoranges.ai。",
      },
    ],
  },
  terms: {
    title: "Terms of Use | Five Oranges AI / 运帷AI",
    label: "使用条款 · TERMS",
    description:
      "Five Oranges AI / 运帷AI website terms for informational content, demo pages and consulting communications.",
    canonical: "https://fiveoranges.ai/terms",
    sections: [
      {
        heading: "网站内容",
        body: "本网站内容用于介绍 Five Oranges AI / 运帷AI 的服务方向、方法论、演示和咨询能力，不构成固定报价、法律意见或保证性承诺。",
      },
      {
        heading: "演示与案例表达",
        body: "网站中的演示用于说明可能的系统体验和业务场景。任何正式项目范围、交付内容、时间和费用均以双方确认的书面文件为准。",
      },
      {
        heading: "知识产权",
        body: "网站文字、视觉设计、品牌资产和页面结构归 Five Oranges AI / 运帷AI 或相关权利方所有，未经授权不得复制、出售或作为第三方产品宣传使用。",
      },
      {
        heading: "责任限制",
        body: "我们会尽力保持信息准确和及时，但不保证网站内容在所有情况下完整、无误或适用于每一家企业的具体场景。",
      },
    ],
  },
  security: {
    title: "Data Security | Five Oranges AI / 运帷AI",
    label: "数据安全 · DATA SECURITY",
    description:
      "Five Oranges AI / 运帷AI data security principles for AI digital transformation, CRM, ERP, workflow automation and consulting projects.",
    canonical: "https://fiveoranges.ai/data-security",
    sections: [
      {
        heading: "最小必要原则",
        body: "在诊断和方案阶段，我们只要求了解完成业务判断所需的最小必要信息，避免在早期收集不必要的敏感数据。",
      },
      {
        heading: "授权数据使用",
        body: "任何企业数据接入、系统演示或原型验证，都应基于客户明确授权，并围绕已确认的业务目标进行。",
      },
      {
        heading: "系统与权限设计",
        body: "在 CRM、ERP、Power Platform、报表和 AI 系统方案中，我们优先考虑权限边界、角色访问、审计记录和数据可追溯性。",
      },
      {
        heading: "AI 落地边界",
        body: "AI 应该服务于清晰的业务流程和可验证的管理目标。涉及敏感数据、客户资料或经营数据时，需要在接入、存储、使用和输出环节设置边界。",
      },
    ],
  },
} satisfies Record<string, TrustPageContent>;

function TrustPage({ content }: { content: TrustPageContent }) {
  usePageSeo({
    title: content.title,
    description: content.description,
    canonical: content.canonical,
  });

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
              <h1>{content.title.replace(" | Five Oranges AI / 运帷AI", "")}</h1>
              <p>Last updated: {UPDATED}</p>
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
              <a href="/strategy-call" className="trust-page-link">
                联系 Five Oranges AI
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
  return <TrustPage content={pages.privacy} />;
}

export function TermsPage() {
  return <TrustPage content={pages.terms} />;
}

export function DataSecurityPage() {
  return <TrustPage content={pages.security} />;
}
