import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { ANALYTICS_EVENTS, trackEvent } from "@/utils/analytics";
import { usePageSeo } from "@/utils/usePageSeo";
import { useState } from "react";

const EMAIL = "contact@fiveoranges.ai";

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

const OUTCOMES = [
  "我们会先判断你的问题是否适合用 AI 或轻量化系统解决。",
  "如果适合，会建议一个最小可验证场景。",
  "如果不适合，我们会直接说明，不建议你盲目投入。",
];

function buildMailtoUrl(form: { name: string; company: string; contact: string; challenge: string }) {
  const body = [
    "你好 Five Oranges AI，我想预约一次30分钟AI数字化诊断。",
    "",
    `姓名：${form.name || "（未填写）"}`,
    `公司：${form.company || "（未填写）"}`,
    `联系方式：${form.contact || "（未填写）"}`,
    "",
    "当前主要想解决的问题：",
    form.challenge || "（未填写）",
  ].join("\n");

  return `mailto:${EMAIL}?subject=${encodeURIComponent("预约30分钟AI数字化诊断")}&body=${encodeURIComponent(body)}`;
}

export default function StrategyCall() {
  const [form, setForm] = useState({ name: "", company: "", contact: "", challenge: "" });
  const [formStarted, setFormStarted] = useState(false);

  usePageSeo({
    title: "预约30分钟AI数字化诊断 | Five Oranges AI / 运帷AI",
    description:
      "Book a 30-minute AI digital transformation strategy call with Five Oranges AI / 运帷AI for manufacturing SMEs exploring AI, CRM, ERP, inventory, order and workflow modernization.",
    canonical: "https://fiveoranges.ai/strategy-call",
    keywords:
      "AI数字化诊断, Five Oranges AI, 运帷AI, 制造业AI转型, CRM ERP modernization, AI strategy call",
  });

  const handleFormStart = () => {
    if (formStarted) return;
    setFormStarted(true);
    trackEvent(ANALYTICS_EVENTS.strategyFormStart, { location: "strategy_call_form" });
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    trackEvent(ANALYTICS_EVENTS.strategyFormSubmit, { location: "strategy_call_form" });
    window.location.href = buildMailtoUrl(form);
  };

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
                  <a
                    href="#strategy-form"
                    className="strategy-primary-button"
                    onClick={() => trackEvent(ANALYTICS_EVENTS.strategyFormStart, { location: "strategy_hero" })}
                  >
                    填写预约信息
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                  </a>
                  <a
                    href="/demo.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="strategy-secondary-button"
                    onClick={() => trackEvent(ANALYTICS_EVENTS.demoEntryClick, { location: "strategy_hero" })}
                  >
                    查看 AI 经营助手演示
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

        <section className="strategy-submit-section">
          <div className="container">
            <div className="strategy-submit-grid">
              <article className="strategy-outcome-card">
                <span className="section-label">
                  <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
                  提交后 · NEXT STEPS
                </span>
                <h2>提交后你会得到什么？</h2>
                <ol>
                  {OUTCOMES.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ol>
              </article>

              <form id="strategy-form" className="strategy-form-card" onFocus={handleFormStart} onSubmit={handleSubmit}>
                <h2>预约信息</h2>
                <div className="strategy-form-row">
                  <label>
                    姓名
                    <input
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                      placeholder="你的姓名"
                    />
                  </label>
                  <label>
                    公司
                    <input
                      value={form.company}
                      onChange={(event) => setForm((current) => ({ ...current, company: event.target.value }))}
                      placeholder="公司名称"
                    />
                  </label>
                </div>
                <label>
                  联系方式
                  <input
                    value={form.contact}
                    onChange={(event) => setForm((current) => ({ ...current, contact: event.target.value }))}
                    placeholder="邮箱、电话或微信号"
                    required
                  />
                </label>
                <label>
                  当前最想解决的问题
                  <textarea
                    value={form.challenge}
                    onChange={(event) => setForm((current) => ({ ...current, challenge: event.target.value }))}
                    placeholder="例如：库存不准、订单进度不透明、客户资料分散、AI不知道从哪里开始"
                    rows={4}
                    required
                  />
                </label>
                <p className="strategy-wechat-note">
                  也可以通过微信沟通。为保护隐私，请先通过表单预约，我们会发送联系方式。
                </p>
                <button type="submit" className="strategy-primary-button">
                  提交预约信息
                </button>
              </form>
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
