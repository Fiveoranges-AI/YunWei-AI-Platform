/* =============================================================
   How to start — 不从大ERP开始，从一个可验证的小场景开始 (v1.3)
   Start small. Validate quickly. Scale with confidence.
   A 3-step, low-risk entry path that reduces the perceived cost of
   adopting AI vs. committing to a large ERP project up front.
   ============================================================= */

const STEPS = [
  {
    cn: "业务诊断",
    en: "Diagnose",
    desc: "梳理库存、订单、客户、流程和数据问题，找到最值得优先解决的场景。",
  },
  {
    cn: "可验证 Demo",
    en: "Validate",
    desc: "先做一个小范围 Demo，让老板和核心员工看到实际效果。",
  },
  {
    cn: "分阶段上线",
    en: "Scale",
    desc: "从一个部门、一个流程、一个数据看板开始，再逐步扩展。",
  },
];

export default function HowToStartSection() {
  return (
    <section id="how-to-start" className="bg-section-alt" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ marginBottom: "3.5rem", maxWidth: "820px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            如何开始 · HOW TO START
          </span>
          <h2
            style={{
              marginTop: "1rem",
              fontSize: "clamp(1.9rem, 3.6vw, 2.75rem)",
              lineHeight: 1.18,
              fontWeight: 700,
              color: "#0F2340",
              letterSpacing: "-0.01em",
              fontFamily: "Sora, sans-serif",
            }}
          >
            不从大 ERP 开始，从一个可验证的小场景开始
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
            Start small. Validate quickly. Scale with confidence.
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {STEPS.map((s, i) => (
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
              <div style={{ display: "flex", alignItems: "center", gap: "0.875rem" }}>
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
                    flexShrink: 0,
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

        {/* Risk-reduction supporting message */}
        <div
          style={{
            marginTop: "2.5rem",
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            padding: "1.5rem 1.75rem",
            borderRadius: "0.875rem",
            background: "var(--brand-blue-pale)",
            border: "1px solid rgba(45,110,168,0.22)",
          }}
        >
          <span
            className="slash-accent"
            style={{ width: "28px", height: "3px", flexShrink: 0 }}
          />
          <p
            style={{
              color: "#263B57",
              fontFamily: "Sora, sans-serif",
              fontSize: "1.0625rem",
              fontWeight: 600,
              lineHeight: 1.6,
            }}
          >
            降低试错成本，避免一开始就投入复杂、昂贵、难推动的大型系统。
          </p>
        </div>
      </div>
    </section>
  );
}
