/* =============================================================
   ApproachSection — 4-step implementation process
   Style: Horizontal step cards with connecting line, white bg
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const steps = [
  {
    num: "01",
    en: "Diagnose",
    cn: "诊断",
    desc: "Business process analysis, pain point identification, system and data inventory.",
    cn_desc: "业务流程诊断、痛点梳理、系统与数据盘点",
    color: "#2D6EA8",
  },
  {
    num: "02",
    en: "Prioritize",
    cn: "优先排序",
    desc: "Select high-ROI, low-resistance AI scenarios that can be deployed quickly.",
    cn_desc: "选择高 ROI、低阻力、可快速落地的 AI 场景",
    color: "#3B7EC8",
  },
  {
    num: "03",
    en: "Build",
    cn: "构建",
    desc: "Develop AI Agents, knowledge bases, data interfaces, automation workflows, and dashboards.",
    cn_desc: "构建 AI Agent、知识库、数据接口、自动化流程和看板",
    color: "#4A8BC4",
  },
  {
    num: "04",
    en: "Scale",
    cn: "扩展",
    desc: "Expand from one scenario to sales, production, finance, HR, and executive decision layers.",
    cn_desc: "从一个场景扩展到销售、生产、财务、人事和管理决策层",
    color: "#5B9BD5",
  },
];

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

export default function ApproachSection() {
  const { ref, inView } = useInView();

  return (
    <section id="approach" className="py-24 lg:py-32 bg-white">
      <div className="container" ref={ref}>
        {/* Header */}
        <div className="mb-16">
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Implementation · 实施方法
          </span>
          <h2
            className="font-bold leading-tight"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
          >
            From Use Case to{" "}
            <span style={{ color: "#2D6EA8" }}>Operating System</span>
          </h2>
          <p className="mt-2 text-base font-medium" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
            从单一场景切入，逐步构建企业智能运营系统。
          </p>
        </div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
          {/* Connecting line (desktop) */}
          <div
            className="hidden lg:block absolute top-10 left-[12.5%] right-[12.5%] h-px"
            style={{ background: "linear-gradient(90deg, #2D6EA8, #5B9BD5)" }}
          />

          {steps.map((s, i) => (
            <div
              key={i}
              className="relative flex flex-col"
              style={{
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(24px)",
                transition: `opacity 0.5s ease ${i * 0.12}s, transform 0.5s ease ${i * 0.12}s`,
              }}
            >
              {/* Step circle */}
              <div className="flex items-center gap-4 mb-6">
                <div
                  className="relative z-10 w-20 h-20 rounded-full flex flex-col items-center justify-center border-2 bg-white"
                  style={{ borderColor: s.color }}
                >
                  <span
                    className="font-bold leading-none"
                    style={{ fontFamily: "Sora, sans-serif", fontSize: "0.65rem", color: s.color, letterSpacing: "0.1em" }}
                  >
                    STEP
                  </span>
                  <span
                    className="font-bold"
                    style={{ fontFamily: "Sora, sans-serif", fontSize: "1.4rem", color: s.color, lineHeight: 1.1 }}
                  >
                    {s.num}
                  </span>
                </div>
              </div>

              {/* Content */}
              <div
                className="flex-1 p-6 rounded-xl border border-slate-100"
                style={{ background: "#F8FAFC" }}
              >
                <h3
                  className="font-bold mb-0.5"
                  style={{ fontFamily: "Sora, sans-serif", fontSize: "1.1rem", color: "#0F2340" }}
                >
                  {s.en}
                </h3>
                <p
                  className="text-sm font-semibold mb-3"
                  style={{ fontFamily: "Manrope, sans-serif", color: s.color }}
                >
                  {s.cn}
                </p>
                <p
                  className="text-sm leading-relaxed mb-1"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
                >
                  {s.desc}
                </p>
                <p
                  className="text-xs leading-relaxed"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
                >
                  {s.cn_desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
