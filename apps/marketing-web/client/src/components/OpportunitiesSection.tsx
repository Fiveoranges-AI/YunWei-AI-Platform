/* =============================================================
   Opportunities — 企业运营中的 AI 改造机会 (v1.3)
   AI Opportunities Hidden in Daily Operations.
   Six premium cards surfacing where AI can be applied across a
   manufacturing SME's daily operations. Matches Solutions card style.
   ============================================================= */

const OPPORTUNITIES = [
  {
    cn: "库存可视化",
    en: "Inventory Visibility",
    desc: "Excel 每天更新，但账实不一致，管理层无法实时掌握库存状态。",
  },
  {
    cn: "订单进度追踪",
    en: "Order Tracking",
    desc: "订单、生产、发货和回款分散在不同人员和表格中，缺少统一视图。",
  },
  {
    cn: "客户资产沉淀",
    en: "Customer Data Assets",
    desc: "客户信息分散在微信、Excel 和个人电脑中，难以沉淀为企业资产。",
  },
  {
    cn: "流程自动化",
    en: "Process Automation",
    desc: "审批、采购、出入库、交付和跟进依赖人工提醒，容易遗漏。",
  },
  {
    cn: "轻量化系统替代",
    en: "Lightweight Systems",
    desc: "传统 ERP 功能复杂、成本高、推动难，中小企业需要更轻量的系统切入点。",
  },
  {
    cn: "AI 落地场景识别",
    en: "AI Use-Case Discovery",
    desc: "企业知道 AI 重要，但需要先判断哪些场景最适合优先验证和落地。",
  },
];

export default function OpportunitiesSection() {
  return (
    <section id="opportunities" className="bg-section-blue" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ marginBottom: "3.5rem", maxWidth: "820px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            AI 改造机会 · OPPORTUNITIES
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
            企业运营中的 AI 改造机会
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
            AI Opportunities Hidden in Daily Operations
          </div>
          <p
            style={{
              marginTop: "1.5rem",
              color: "#334155",
              fontSize: "1.0625rem",
              lineHeight: 1.75,
            }}
          >
            很多企业不是缺软件，而是库存、订单、客户、流程和数据之间没有被系统化连接。Five
            Oranges AI 帮助企业识别最值得优先落地的 AI 场景，从小范围验证开始，逐步完成数字化升级。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {OPPORTUNITIES.map((o, i) => (
            <article
              key={o.en}
              className="solution-card card-lift"
              style={{
                padding: "2rem 1.875rem",
                borderRadius: "0.875rem",
                background: "#FFFFFF",
                border: "1.5px solid rgba(15,35,64,0.18)",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <div
                style={{
                  width: "54px",
                  height: "54px",
                  borderRadius: "0.625rem",
                  background: "var(--brand-blue-pale)",
                  border: "1px solid rgba(45,110,168,0.22)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--brand-blue)",
                  fontFamily: "Sora, sans-serif",
                  fontWeight: 700,
                  fontSize: "1.0625rem",
                  letterSpacing: "0.04em",
                }}
              >
                0{i + 1}
              </div>
              <div>
                <div
                  style={{
                    fontSize: "1.375rem",
                    fontWeight: 700,
                    color: "#0F2340",
                    fontFamily: "Sora, sans-serif",
                    lineHeight: 1.2,
                    letterSpacing: "0.005em",
                  }}
                >
                  {o.cn}
                </div>
                <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--brand-blue)",
                    letterSpacing: "0.08em",
                    marginTop: "4px",
                    fontFamily: "Sora, sans-serif",
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >
                  {o.en}
                </div>
              </div>
              <p
                style={{
                  color: "#334155",
                  fontSize: "1rem",
                  lineHeight: 1.65,
                  marginTop: "0.25rem",
                }}
              >
                {o.desc}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
