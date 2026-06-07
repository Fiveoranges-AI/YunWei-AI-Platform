/* =============================================================
   FAQ — 常见问题 / Frequently Asked Questions (homepage)
   Objection-handling for manufacturing SME buyers. Native <details>
   disclosure — accessible, no JS state needed.
   ============================================================= */

const FAQS = [
  {
    q: "你们是做 ERP 替换吗？",
    a: "不是一开始就替换 ERP。我们通常先从最痛的小场景开始，例如库存、订单、客户或经营看板，验证有效后再逐步扩展。",
  },
  {
    q: "多久能看到 Demo？",
    a: "通常可以先做一个小范围、可验证的 Demo，让你和核心员工看到实际效果，再决定是否进入正式系统建设。",
  },
  {
    q: "适合多大规模的企业？",
    a: "适合仍在依赖 Excel、人工流程和分散数据管理的中小制造、贸易、仓储和工程类企业。",
  },
  {
    q: "需要企业已经有 ERP 吗？",
    a: "不需要。已有 ERP 的可以做集成；没有 ERP 的，也可以先从轻量化系统开始。",
  },
  {
    q: "AI 会不会泄露企业数据？",
    a: "正式项目中会根据客户要求设计权限、脱敏、审计和数据边界，客户数据不会用于训练公共模型。详见「数据安全与 AI 使用边界」。",
  },
  {
    q: "和金蝶、用友、传统 ERP 有什么区别？",
    a: "传统 ERP 偏大而全、推动周期长。Five Oranges AI 更关注从具体业务痛点出发，用轻量化系统和 AI 先解决最关键的问题，再逐步扩展。",
  },
];

export default function FaqSection() {
  return (
    <section id="faq" className="bg-section-alt" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ maxWidth: "760px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            常见问题 · FAQ
          </span>
          <h2
            style={{
              marginTop: "1rem",
              fontSize: "clamp(2.1rem, 4vw, 3rem)",
              lineHeight: 1.15,
              fontWeight: 700,
              color: "#0F2340",
              letterSpacing: "-0.01em",
              fontFamily: "Sora, sans-serif",
            }}
          >
            常见问题
          </h2>
          <div
            style={{
              marginTop: "0.75rem",
              fontFamily: "Sora, sans-serif",
              fontWeight: 500,
              fontSize: "1.0625rem",
              color: "#475569",
            }}
          >
            Frequently Asked Questions
          </div>
        </div>

        <div className="faq-list">
          {FAQS.map(({ q, a }) => (
            <details key={q} className="faq-item">
              <summary>
                <span>{q}</span>
                <svg
                  className="faq-chevron"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </summary>
              <p className="faq-answer">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
