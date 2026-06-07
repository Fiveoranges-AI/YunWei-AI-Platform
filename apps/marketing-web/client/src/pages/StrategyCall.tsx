import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { usePageSeo } from "@/utils/usePageSeo";

const EMAIL = "contact@fiveoranges.ai";
const MAILTO = `mailto:${EMAIL}?subject=${encodeURIComponent("预约30分钟AI数字化诊断")}&body=${encodeURIComponent(
  "你好 Five Oranges AI，我想预约一次30分钟AI数字化诊断。我的企业目前主要想解决："
)}`;

const DIAGNOSIS_ITEMS = [
  "当前最影响管理效率的业务痛点",
  "库存、订单、客户、流程和经营数据的现状",
  "最适合先做 AI 或数字化 Demo 的小场景",
  "轻量化 CRM / ERP / 自动化系统的优先路径",
];

const BEST_FIT = [
  "仍在用 Excel 管库存、订单或客户",
  "想做数字化，但不确定从哪里开始",
  "觉得传统 ERP 太复杂、太贵、太难落地",
  "想用 AI 提高管理效率，但缺少清晰场景",
  "正在接班或推进企业管理升级的厂二代",
  "有北美客户、出海业务或希望提升管理规范性的制造企业",
];

export default function StrategyCall() {
  usePageSeo({
    title: "预约30分钟AI数字化诊断 | Five Oranges AI / 运帷AI",
    description:
      "Book a 30-minute AI digital transformation strategy call with Five Oranges AI / 运帷AI for manufacturing SMEs exploring AI, CRM, ERP, inventory, order and workflow modernization.",
    canonical: "https://fiveoranges.ai/strategy-call",
    keywords:
      "AI数字化诊断, Five Oranges AI, 运帷AI, 制造业AI转型, CRM ERP modernization, AI strategy call",
  });

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <main className="strategy-page">
        <section className="strategy-hero-section">
          <div className="container">
            <div className="strategy-hero-grid">
              <div>
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  预约沟通 · STRATEGY CALL
                </span>
                <h1>预约30分钟AI数字化诊断</h1>
                <p className="strategy-lead">
                  如果你的企业正在面临库存、订单、客户管理、流程、ERP、CRM 或 AI
                  落地问题，我们会一起判断最值得优先解决的业务场景。
                </p>
                <p className="strategy-support">
                  目标不是马上推一套大系统，而是帮你看清：哪个小场景最痛、最可验证、最值得先做。
                </p>

                <div className="strategy-actions">
                  <a href={MAILTO} className="strategy-primary-button">
                    发邮件预约诊断
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                  </a>
                  <a href="/demo.html" target="_blank" rel="noopener noreferrer" className="strategy-secondary-button">
                    先查看演示
                  </a>
                </div>
              </div>

              <aside className="strategy-card">
                <div className="strategy-card-kicker">30 MINUTES</div>
                <h2>这次沟通会聚焦什么？</h2>
                <ul>
                  {DIAGNOSIS_ITEMS.map((item) => (
                    <li key={item}>
                      <span aria-hidden>✓</span>
                      {item}
                    </li>
                  ))}
                </ul>
                <div className="strategy-card-footer">
                  <strong>{EMAIL}</strong>
                  <span>Five Oranges AI / 运帷AI</span>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="strategy-fit-section">
          <div className="container">
            <div className="strategy-section-header">
              <span className="section-label">
                <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                适合沟通的企业类型
              </span>
              <h2>这次诊断适合这些企业主。</h2>
            </div>

            <div className="strategy-fit-grid">
              {BEST_FIT.map((item) => (
                <article key={item} className="strategy-fit-card">
                  <span aria-hidden>✓</span>
                  <p>{item}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
