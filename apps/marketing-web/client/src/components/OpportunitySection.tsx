import { useState } from "react";

const OPPORTUNITIES = [
  {
    cn: "库存可视化",
    en: "Inventory Visibility",
    desc: "把库存数量、库位、缺料和呆滞风险从表格里拉出来，让老板随时看清真实库存。",
  },
  {
    cn: "订单进度追踪",
    en: "Order Tracking",
    desc: "把销售订单、生产进度、采购状态和交付风险串起来，减少靠人追问的管理成本。",
  },
  {
    cn: "客户资产沉淀",
    en: "Customer Memory",
    desc: "把客户资料、报价、跟进记录和历史订单沉淀为可查询、可分析、可复用的客户资产。",
  },
  {
    cn: "流程自动化",
    en: "Workflow Automation",
    desc: "让审批、提醒、报表、异常通知和跨部门协作自动流转，减少人工重复盯流程。",
  },
  {
    cn: "轻量化系统替代",
    en: "Lightweight Systems",
    desc: "先用更轻的 CRM、库存、订单和运营系统替代零散表格，再逐步扩展到核心流程。",
  },
  {
    cn: "AI落地场景识别",
    en: "AI Use Case Mapping",
    desc: "判断哪些业务问题值得先用 AI 解决，避免一开始就投入到不清晰、不好验证的场景。",
  },
];

export default function OpportunitySection() {
  const [expanded, setExpanded] = useState(false);

  return (
    <section id="opportunities" className="opportunity-section">
      <div className="container">
        <div className="opportunity-header">
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            企业运营中的 AI 改造机会
          </span>
          <h2>帮制造业老板先看清，AI 应该从哪里开始。</h2>
          <p>不从概念开始，从库存、订单、客户、流程和经营数据里最痛的地方开始。</p>
        </div>

        <div className="opportunity-grid">
          {OPPORTUNITIES.map((item, index) => (
            <article
              key={item.en}
              className={`opportunity-card card-lift ${
                index > 2 && !expanded ? "opportunity-card-mobile-hidden" : ""
              }`}
            >
              <div className="opportunity-card-index">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <h3>{item.cn}</h3>
                <div>{item.en}</div>
              </div>
              <p>{item.desc}</p>
            </article>
          ))}
        </div>

        <button
          type="button"
          className="opportunity-expand-btn"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "收起部分场景" : "查看更多 AI 改造机会"}
        </button>
      </div>
    </section>
  );
}
