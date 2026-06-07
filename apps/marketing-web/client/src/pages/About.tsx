import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { usePageSeo } from "@/utils/usePageSeo";

const WHY_CARDS = [
  {
    title: "从业务场景开始",
    body: "先判断库存、订单、客户、流程和经营数据中最值得投入的场景，而不是先推软件清单。",
  },
  {
    title: "轻量化系统优先",
    body: "适合中小制造企业的系统，应该先可用、可接受、可扩展，再逐步进入更复杂的管理流程。",
  },
  {
    title: "AI 进入真实流程",
    body: "AI 不停留在聊天窗口，而是进入报表、知识问答、异常提醒、流程流转和经营决策。",
  },
];

const WORKFLOW = ["业务诊断", "可验证 Demo", "分阶段上线", "持续优化"];

export default function About() {
  usePageSeo({
    title: "About Five Oranges AI / 运帷AI",
    description:
      "Five Oranges AI / 运帷AI helps Chinese manufacturing SMEs and traditional businesses adopt practical AI, lightweight CRM/ERP, inventory, workflow and business system modernization.",
    canonical: "https://fiveoranges.ai/about",
    keywords: "Five Oranges AI, 运帷AI, AI数字化转型, 制造业数字化, 轻量化ERP, CRM ERP modernization",
  });

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="company-page">
        <section className="company-hero-section">
          <div className="container">
            <div className="company-hero-inner">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                关于运帷AI · ABOUT
              </span>
              <h1>让传统企业用更轻量的方式完成 AI 数字化升级。</h1>
              <p>
                Five Oranges AI / 运帷AI 服务中国制造业中小企业、贸易/出海企业和传统业务团队，帮助企业把分散数据、手工流程和管理经验转化为可追踪、可自动化、可 AI 增强的业务系统。
              </p>
            </div>
          </div>
        </section>

        <section className="company-section">
          <div className="container">
            <div className="company-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                公司使命
              </span>
              <h2>不是把企业带进更复杂的系统，而是先把关键业务看清楚。</h2>
              <p>
                很多企业不是不想数字化，而是不知道第一步该从哪里开始。我们的工作是帮助企业先找到最小、最痛、最可验证的场景，再逐步扩展到库存、订单、客户、流程和经营数据。
              </p>
            </div>
          </div>
        </section>

        <section className="company-section company-section-blue">
          <div className="container">
            <div className="company-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                为什么是 Five Oranges AI
              </span>
              <h2>我们把企业系统经验，转化成更容易落地的 AI 工作流。</h2>
            </div>
            <div className="company-card-grid">
              {WHY_CARDS.map((card) => (
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
                  创始人与架构能力
                </span>
                <h2>企业级架构经验，是方案落地的底层保障。</h2>
                <p>
                  Five Oranges AI / 运帷AI 由 Kobe Li 创立。Kobe 拥有10年以上 Microsoft Dynamics 365、Power Platform、CRM、ERP、流程自动化和企业级数字化转型经验，并将这些经验转化为更适合中小制造企业的轻量化 AI 系统方法。
                </p>
              </div>
              <a href="/kobeli" className="company-secondary-link">
                查看创始人背景
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
                  合作方式
                </span>
                <h2>从一次诊断开始，先判断是否值得投入。</h2>
                <p>我们会先判断问题是否适合用 AI 或轻量化系统解决。如果适合，再建议一个最小可验证场景。</p>
              </div>
              <div className="company-workflow">
                {WORKFLOW.map((step, index) => (
                  <div key={step}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{step}</strong>
                  </div>
                ))}
              </div>
              <a href="/strategy-call" className="company-primary-link">
                预约30分钟AI数字化诊断
              </a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
