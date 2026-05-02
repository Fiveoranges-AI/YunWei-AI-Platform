/* =============================================================
   Solutions — Four building blocks for an AI-native operation (v1.3)
   ============================================================= */

const SOLUTIONS = [
  {
    cn: "AI 智能体",
    en: "AI Agents",
    desc: "面向业务领域训练的 AI 智能体，读取你的真实数据、自动撰写报告、并在现有系统中触发动作。",
  },
  {
    cn: "企业知识库",
    en: "Knowledge Bases",
    desc: "将 SOP、合同、历史记录统一为可被检索调用的知识层，让团队真正信任并依赖。",
  },
  {
    cn: "流程自动化",
    en: "Process Automation",
    desc: "替代 ERP / CRM / 表格之间的人工流转，构建可靠、可追溯的 AI 驱动流程。",
  },
  {
    cn: "智能驾驶舱",
    en: "Intelligent Dashboards",
    desc: "决策级仪表盘，把原始运营数据翻译成高管真正会问的那些问题。",
  },
];

export default function SolutionsSection() {
  return (
    <section id="solutions" style={{ padding: "7rem 0", background: "#FFFFFF" }}>
      <div className="container">
        <div
          className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6"
          style={{ marginBottom: "3.5rem" }}
        >
          <div>
            <span className="section-label">
              <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
              解决方案 · SOLUTIONS
            </span>
            <h2
              style={{
                marginTop: "1rem",
                fontSize: "clamp(2.1rem, 4vw, 3rem)",
                lineHeight: 1.15,
                fontWeight: 700,
                color: "#0F2340",
                maxWidth: "760px",
                letterSpacing: "-0.01em",
                fontFamily: "Sora, sans-serif",
              }}
            >
              Four building blocks for an AI-native operation.
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
              为 AI 原生运营打造的四大基石。
            </div>
          </div>
          <p
            style={{
              color: "#64748B",
              maxWidth: "360px",
              fontSize: "0.95rem",
              lineHeight: 1.65,
            }}
          >
            按需组合，从你真实的业务流程出发，而不是套用通用 AI 演示。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {SOLUTIONS.map((s, i) => (
            <article
              key={s.en}
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
                  {s.cn}
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
                  {s.en}
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
                {s.desc}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
