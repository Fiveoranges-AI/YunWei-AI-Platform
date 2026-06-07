import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { usePageSeo } from "@/utils/usePageSeo";

const RESOURCE_CARDS = [
  {
    title: "FAQ",
    eyebrow: "常见问题",
    body: "快速了解 AI 数字化诊断、轻量化系统和落地方式。",
    href: "/#faq",
  },
  {
    title: "数据安全与AI使用边界",
    eyebrow: "DATA SECURITY",
    body: "了解客户数据、权限、脱敏、审计和 AI 使用边界的基本原则。",
    href: "/data-security",
  },
  {
    title: "90天AI数字化落地路线图",
    eyebrow: "ROADMAP",
    body: "从业务诊断、Demo 验证到分阶段上线的 90 天参考路径。",
    href: "#roadmap",
  },
  {
    title: "AI数字化文章",
    eyebrow: "ARTICLES",
    body: "后续将沉淀制造业 AI、CRM、ERP 和流程自动化相关文章。",
    href: "#articles",
  },
  {
    title: "Manufacturing AI insights",
    eyebrow: "INSIGHTS",
    body: "面向制造业老板和管理团队的 AI 落地观察与方法论。",
    href: "#insights",
  },
];

export default function Resources() {
  usePageSeo({
    title: "Resources | Five Oranges AI / 运帷AI",
    description:
      "Resources from Five Oranges AI / 运帷AI for AI digital transformation, data security, manufacturing AI, lightweight ERP/CRM and workflow modernization.",
    canonical: "https://fiveoranges.ai/resources",
    keywords: "Five Oranges AI resources, 运帷AI资源, AI数字化, 数据安全, 制造业AI, 90天AI数字化路线图",
  });

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="resources-page">
        <section className="company-hero-section">
          <div className="container">
            <div className="company-hero-inner">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                资源中心 · RESOURCES
              </span>
              <h1>面向传统企业的 AI 数字化资源。</h1>
              <p>
                这里汇总 Five Oranges AI / 运帷AI 的常见问题、数据安全说明、落地路线图和制造业 AI 观察，帮助企业主在投入前先建立清晰判断。
              </p>
            </div>
          </div>
        </section>

        <section className="resources-section">
          <div className="container">
            <div className="resources-grid">
              {RESOURCE_CARDS.map((card) => (
                <a key={card.title} href={card.href} className="resource-card">
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
                90天AI数字化落地路线图
              </span>
              <h2>小场景验证 → 数据结构化 → AI工作流 → 分阶段扩展</h2>
              <p>
                前 30 天聚焦业务诊断与最小场景；中间 30 天完成 Demo 与数据结构梳理；后 30 天评估上线边界、权限、流程和扩展计划。
              </p>
            </article>
          </div>
        </section>

        <section id="articles" className="resources-detail-section resources-detail-muted">
          <div className="container">
            <article className="resources-detail-panel">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                AI数字化文章
              </span>
              <h2>文章内容正在整理中。</h2>
              <p>后续会围绕制造业库存、订单、客户、ERP/CRM、AI 工作流和企业数据治理持续更新。</p>
            </article>
          </div>
        </section>

        <section id="insights" className="resources-detail-section">
          <div className="container">
            <article className="resources-detail-panel">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                Manufacturing AI insights
              </span>
              <h2>为制造业老板准备的 AI 落地观察。</h2>
              <p>重点关注可落地、可验证、可维护的 AI 场景，而不是泛泛的工具清单或概念演示。</p>
            </article>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
