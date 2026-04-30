/* =============================================================
   PhilosophySection — Five Capabilities brand module
   Style: Roman V motif, 5 pillars, off-white bg
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const pillars = [
  {
    roman: "I",
    en: "Strategy",
    cn: "战略判断",
    desc: "Align AI initiatives with business goals. Identify where intelligence creates the most measurable value.",
    cn_desc: "将 AI 举措与业务目标对齐，识别智能化创造最大可量化价值的关键节点。",
  },
  {
    roman: "II",
    en: "Process",
    cn: "流程重塑",
    desc: "Redesign workflows before automating them. Eliminate inefficiencies, then apply AI where it multiplies impact.",
    cn_desc: "先重塑流程再自动化。消除低效环节，再在能放大效果的节点引入 AI。",
  },
  {
    roman: "III",
    en: "Data",
    cn: "数据治理",
    desc: "Build the data foundation that AI requires. Structure, clean, and connect your operational data assets.",
    cn_desc: "构建 AI 所需的数据基础。结构化、清洗并连接企业运营数据资产。",
  },
  {
    roman: "IV",
    en: "AI",
    cn: "智能代理",
    desc: "Deploy AI Agents that act, not just answer. Automate decisions, surface insights, and trigger actions.",
    cn_desc: "部署能行动而非仅回答的 AI Agent。自动化决策、呈现洞察、触发行动。",
  },
  {
    roman: "V",
    en: "Execution",
    cn: "执行闭环",
    desc: "Close the loop between intelligence and action. Measure outcomes, iterate, and scale what works.",
    cn_desc: "打通智能与行动之间的闭环。衡量成果、持续迭代、扩展有效方案。",
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

export default function PhilosophySection() {
  const { ref, inView } = useInView();

  return (
    <section className="py-24 lg:py-32 bg-section-alt relative overflow-hidden">
      {/* Brand philosophy image background */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: `url(https://d2xsxph8kpxj0f.cloudfront.net/310519663273870289/64xTVtv7XqMZ3588Nzt2Xd/brand_philosophy-EZxaHYZ9zCSQHTPtGoY5rv.webp)`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />

      <div className="container relative z-10" ref={ref}>
        {/* Header */}
        <div className="text-center mb-16">
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Brand Philosophy · 品牌理念
          </span>
          <h2
            className="font-bold leading-tight mb-3"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
          >
            Five Capabilities.{" "}
            <span style={{ color: "#2D6EA8" }}>One Intelligent Enterprise.</span>
          </h2>
          <p className="text-base font-medium mb-4" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
            五种能力，构建一个智能企业。
          </p>
          <p
            className="max-w-2xl mx-auto text-sm leading-relaxed"
            style={{ fontFamily: "Manrope, sans-serif", color: "#64748B" }}
          >
            The name "Five Oranges" represents five essential capabilities for enterprise transformation.
            The Roman numeral <strong style={{ color: "#2D6EA8" }}>V</strong> — and the Chinese "运帷AI" (运筹帷幄之中，决胜千里之外) — 
            embody strategic mastery: winning from a position of intelligence, not reaction.
          </p>
          <p
            className="max-w-2xl mx-auto text-xs leading-relaxed mt-2"
            style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
          >
            "运帷AI"取自"运筹帷幄之中，决胜千里之外"——强调企业经营中的战略判断、流程优化、数据智能和执行落地。
          </p>
        </div>

        {/* Five pillars */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {pillars.map((p, i) => (
            <div
              key={i}
              className="card-lift flex flex-col p-6 rounded-xl bg-white border border-slate-100 text-center relative overflow-hidden"
              style={{
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(28px)",
                transition: `opacity 0.5s ease ${i * 0.1}s, transform 0.5s ease ${i * 0.1}s`,
              }}
            >
              {/* Roman numeral watermark */}
              <span
                className="absolute top-2 right-3 font-bold"
                style={{
                  fontFamily: "Sora, sans-serif",
                  fontSize: "3rem",
                  color: "rgba(45,110,168,0.07)",
                  lineHeight: 1,
                  userSelect: "none",
                }}
              >
                {p.roman}
              </span>

              {/* Number badge */}
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-4"
                style={{ background: "#EEF4FB" }}
              >
                <span
                  className="font-bold text-sm"
                  style={{ fontFamily: "Sora, sans-serif", color: "#2D6EA8" }}
                >
                  {p.roman}
                </span>
              </div>

              <h3
                className="font-bold mb-0.5"
                style={{ fontFamily: "Sora, sans-serif", fontSize: "1rem", color: "#0F2340" }}
              >
                {p.en}
              </h3>
              <p
                className="text-sm font-semibold mb-3"
                style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
              >
                {p.cn}
              </p>
              <p
                className="text-xs leading-relaxed mb-1"
                style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
              >
                {p.desc}
              </p>
              <p
                className="text-xs leading-relaxed"
                style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
              >
                {p.cn_desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
