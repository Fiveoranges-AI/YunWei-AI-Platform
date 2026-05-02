/* =============================================================
   Why — Three commitments we don't break (v1.3)
   CN-primary blue title pills, top-border accent
   ============================================================= */

const WHY = [
  {
    cn: "流程先行",
    en: "Workflow-first",
    desc: "我们把每一个智能体都锚定在一个具体的业务流程上，而不是一个通用对话框。",
  },
  {
    cn: "可追溯",
    en: "Auditable",
    desc: "驾驶舱里的每一个数字都可以追溯到源记录——拒绝 AI 幻觉。",
  },
  {
    cn: "共创交付",
    en: "Co-built",
    desc: "我们和你的团队坐在一起做事。共同设计，而不是隔墙交付。",
  },
];

export default function WhySection() {
  return (
    <section style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ marginBottom: "3.5rem", maxWidth: "760px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            为什么选择我们 · WHY US
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
            Three commitments we don't break.
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
            我们绝不打破的三项承诺。
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {WHY.map((w, i) => (
            <div
              key={w.en}
              style={{
                padding: "2.25rem 2rem 2rem",
                background: "#FFFFFF",
                borderTop: "3px solid var(--brand-blue)",
                boxShadow:
                  "0 1px 2px rgba(15,35,64,0.04), 0 8px 24px rgba(15,35,64,0.06)",
                borderRadius: "0 0 0.625rem 0.625rem",
                display: "flex",
                flexDirection: "column",
                gap: "1.25rem",
              }}
            >
              <div
                style={{
                  fontSize: "0.95rem",
                  letterSpacing: "0.18em",
                  fontWeight: 700,
                  color: "var(--brand-blue)",
                  fontFamily: "Sora, sans-serif",
                }}
              >
                0{i + 1}
              </div>

              <div
                style={{
                  alignSelf: "flex-start",
                  display: "inline-flex",
                  flexDirection: "column",
                  gap: "2px",
                  padding: "12px 18px",
                  background: "var(--brand-blue)",
                  borderRadius: "8px",
                  color: "#fff",
                  fontFamily: "Sora, sans-serif",
                  boxShadow: "0 4px 12px rgba(45,110,168,0.20)",
                }}
              >
                <span
                  style={{
                    fontSize: "1.375rem",
                    fontWeight: 700,
                    letterSpacing: "0.01em",
                    lineHeight: 1.1,
                  }}
                >
                  {w.cn}
                </span>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    letterSpacing: "0.14em",
                    opacity: 0.85,
                    textTransform: "uppercase",
                  }}
                >
                  {w.en}
                </span>
              </div>

              <p style={{ color: "#334155", fontSize: "1rem", lineHeight: 1.7 }}>{w.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
