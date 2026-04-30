/* =============================================================
   WhySection — 5 differentiators
   Style: Alternating layout with large numbers, off-white bg
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const advantages = [
  {
    num: "01",
    en: "Business-First, Not Model-First",
    cn: "业务优先，而非技术优先",
    desc: "We start by understanding your business processes, workflows, and pain points — then select the right AI technology. Not the other way around.",
    cn_desc: "我们先深入理解业务流程与痛点，再选择合适的 AI 技术，而非用技术寻找问题。",
  },
  {
    num: "02",
    en: "Enterprise Architecture Mindset",
    cn: "企业级架构思维",
    desc: "Deep experience with CRM, ERP, Power Platform, Dataverse, Azure, API integration, and enterprise system architecture — we speak the language of your existing systems.",
    cn_desc: "具备 CRM、ERP、Power Platform、Dataverse、Azure、API 集成和企业系统架构丰富经验。",
  },
  {
    num: "03",
    en: "Practical AI Agent Implementation",
    cn: "可落地的 AI Agent 实施",
    desc: "Not concept demonstrations. Every AI Agent we build is designed around real business processes, with measurable outcomes and operational integration.",
    cn_desc: "不是概念演示，而是围绕真实业务流程设计可用的 Agent，具备可衡量的业务成果。",
  },
  {
    num: "04",
    en: "China + North America Perspective",
    cn: "中国与北美双视角",
    desc: "We understand Chinese manufacturing realities and North American enterprise software standards — bridging operational context with global best practices.",
    cn_desc: "理解中国制造业场景，也熟悉北美企业级软件、合规和数字化转型方法论。",
  },
  {
    num: "05",
    en: "Founder-Led Delivery",
    cn: "创始人亲自交付",
    desc: "Led by a senior Dynamics 365 Solution Architect with hands-on digital transformation experience. You work directly with the person who designs and builds your solution.",
    cn_desc: "由资深数字化转型与 Dynamics 365 Solution Architect 亲自参与方案设计与交付。",
  },
];

function useInView(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

export default function WhySection() {
  const { ref, inView } = useInView();

  return (
    <section id="about" className="py-24 lg:py-32 bg-section-alt relative overflow-hidden">
      {/* V watermark */}
      <span className="watermark-v" style={{ right: "-2%", top: "50%", transform: "translateY(-50%)" }}>V</span>

      <div className="container relative z-10" ref={ref}>
        {/* Header */}
        <div className="mb-16">
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Why Five Oranges AI · 为什么选择我们
          </span>
          <h2
            className="font-bold leading-tight"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
          >
            Consulting Depth.{" "}
            <span style={{ color: "#2D6EA8" }}>AI Speed.</span>
            <br />
            Execution Discipline.
          </h2>
          <p className="mt-2 text-base font-medium" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
            咨询深度、AI速度、交付纪律。
          </p>
        </div>

        {/* Advantages list */}
        <div className="flex flex-col gap-0">
          {advantages.map((a, i) => (
            <div
              key={i}
              className="flex flex-col md:flex-row gap-6 md:gap-10 py-8 border-b border-slate-200 last:border-0"
              style={{
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(20px)",
                transition: `opacity 0.5s ease ${i * 0.1}s, transform 0.5s ease ${i * 0.1}s`,
              }}
            >
              {/* Number */}
              <div className="flex-shrink-0 w-16">
                <span
                  className="font-bold"
                  style={{
                    fontFamily: "Sora, sans-serif",
                    fontSize: "2.5rem",
                    color: "rgba(45,110,168,0.15)",
                    lineHeight: 1,
                  }}
                >
                  {a.num}
                </span>
              </div>

              {/* Content */}
              <div className="flex-1 grid md:grid-cols-2 gap-4">
                <div>
                  <h3
                    className="font-bold mb-1"
                    style={{ fontFamily: "Sora, sans-serif", fontSize: "1.05rem", color: "#0F2340" }}
                  >
                    {a.en}
                  </h3>
                  <p
                    className="text-sm font-semibold"
                    style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
                  >
                    {a.cn}
                  </p>
                </div>
                <div>
                  <p
                    className="text-sm leading-relaxed mb-1"
                    style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
                  >
                    {a.desc}
                  </p>
                  <p
                    className="text-xs leading-relaxed"
                    style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
                  >
                    {a.cn_desc}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
