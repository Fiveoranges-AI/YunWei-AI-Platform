const FAQS = [
  {
    q: "一定要先上大型 ERP 吗？",
    a: "不一定。很多中小制造企业更适合先从一个可验证的小场景开始，例如库存、订单追踪或客户资料沉淀。",
  },
  {
    q: "我们现在只有 Excel，也可以做 AI 数字化吗？",
    a: "可以。关键是先梳理数据结构和流程规则，再决定用轻量系统、自动化还是 AI 智能体来承接。",
  },
  {
    q: "30分钟诊断会聊什么？",
    a: "主要聊当前业务痛点、现有工具、优先场景、可行的 Demo 范围，以及是否值得进入下一步方案设计。",
  },
  {
    q: "Five Oranges AI 会夸大 AI 效果吗？",
    a: "不会。我们更关注可落地、可验证、可维护的业务系统，AI 只应该放在真正能提高效率的位置。",
  },
];

export default function FAQSection() {
  return (
    <section id="faq" className="faq-section">
      <div className="container">
        <div className="faq-header">
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            常见问题 · FAQ
          </span>
          <h2>企业主最常问的几个问题。</h2>
        </div>

        <div className="faq-list">
          {FAQS.map((item) => (
            <details key={item.q} className="faq-item">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
