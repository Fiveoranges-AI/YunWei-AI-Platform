/* =============================================================
   SolutionsSection — Six AI solution cards
   Style: 3-col grid, left-border accent, card-lift hover
   Background: Warm off-white #F8F7F4
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const solutions = [
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="3" y="3" width="22" height="22" rx="4" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M8 10h12M8 14h8M8 18h10" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round"/>
      </svg>
    ),
    en: "AI Business Assistant",
    cn: "企业经营 AI 助理",
    desc: "Internal Q&A over company policies, procedures, documents, and business data. Helps employees find answers faster and reduce repetitive communication.",
    cn_desc: "基于企业内部文档与业务数据的智能问答，减少重复沟通，提升响应效率。",
    tag: "Knowledge · 知识管理",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <path d="M4 20L10 8l5 8 4-5 5 9" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="22" cy="6" r="2.5" stroke="#2D6EA8" strokeWidth="1.6"/>
      </svg>
    ),
    en: "Manufacturing Operations Intelligence",
    cn: "制造业运营智能",
    desc: "Production briefing, capacity visibility, machine status monitoring, and exception alerts. Connects shop-floor data with management decision-making.",
    cn_desc: "生产简报、产能可视化、设备状态监控与异常预警，打通车间数据与管理层决策。",
    tag: "Manufacturing · 制造业",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <path d="M6 22V14M11 22V10M16 22V6M21 22V12" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M4 8l5-3 5 4 5-5 5 3" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    en: "AI Pricing & Quotation Engine",
    cn: "智能报价与成本分析",
    desc: "Uses historical orders, material costs, production risks, and margin rules to support quotation decisions. Especially suitable for custom manufacturing.",
    cn_desc: "结合历史订单、原材料成本、生产风险与毛利规则，辅助报价决策，提升报价准确率。",
    tag: "Finance · 财务决策",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <circle cx="14" cy="10" r="5" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M6 24c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M18 14l2 2 4-4" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    en: "HR Attendance & Overtime Automation",
    cn: "考勤与加班智能分析",
    desc: "Converts raw punch-in/out records into standardized attendance, overtime, absence, and exception reports. Reduces manual HR reconciliation.",
    cn_desc: "将原始打卡数据转化为标准化考勤、加班、缺勤与异常报告，大幅减少人工核对工作量。",
    tag: "HR · 人力资源",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <path d="M8 4h12a2 2 0 012 2v16a2 2 0 01-2 2H8a2 2 0 01-2-2V6a2 2 0 012-2z" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M10 10h8M10 14h8M10 18h5" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round"/>
        <path d="M20 2v4M8 2v4" stroke="#2D6EA8" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
    en: "ISO & Compliance Document Assistant",
    cn: "ISO 与合规文件智能助手",
    desc: "Helps maintain audit documents, process checklists, version updates, and compliance evidence. Supports ISO9001-style management documentation.",
    cn_desc: "协助维护审核文件、流程清单、版本更新与合规证据，支持 ISO9001 等体系文件管理。",
    tag: "Compliance · 合规管理",
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="3" y="3" width="10" height="10" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
        <rect x="15" y="3" width="10" height="10" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
        <rect x="3" y="15" width="10" height="10" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
        <rect x="15" y="15" width="10" height="10" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
      </svg>
    ),
    en: "Executive Intelligence Dashboard",
    cn: "管理驾驶舱",
    desc: "Converts operational data into executive summaries, KPIs, risks, and recommended actions. Designed for owners, general managers, and business leaders.",
    cn_desc: "将运营数据转化为管理层摘要、KPI、风险提示与行动建议，专为老板、总经理和二代企业家设计。",
    tag: "Dashboard · 管理决策",
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

export default function SolutionsSection() {
  const { ref, inView } = useInView();

  return (
    <section id="solutions" className="py-24 lg:py-32 bg-section-alt relative overflow-hidden">
      {/* V watermark */}
      <span className="watermark-v" style={{ left: "-2%", top: "50%", transform: "translateY(-50%)" }}>V</span>

      <div className="container relative z-10" ref={ref}>
        {/* Section header */}
        <div className="mb-16">
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Solutions · 解决方案
          </span>
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
            <div>
              <h2
                className="font-bold leading-tight"
                style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
              >
                Purpose-Built AI for
                <br />
                <span style={{ color: "#2D6EA8" }}>Real Enterprise Operations</span>
              </h2>
              <p className="mt-2 text-base font-medium" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
                真正落地的 AI 解决方案
              </p>
            </div>
            <p
              className="max-w-md text-sm leading-relaxed"
              style={{ color: "#64748B", fontFamily: "Manrope, sans-serif" }}
            >
              Each solution is designed around measurable business outcomes — not technology demonstrations. We build what your operations actually need.
            </p>
          </div>
        </div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {solutions.map((s, i) => (
            <div
              key={i}
              className="card-lift bg-white rounded-xl p-7 border border-slate-100 relative overflow-hidden"
              style={{
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(28px)",
                transition: `opacity 0.55s ease ${i * 0.08}s, transform 0.55s ease ${i * 0.08}s`,
                borderLeft: "3px solid #2D6EA8",
              }}
            >
              {/* Icon */}
              <div
                className="w-12 h-12 rounded-lg flex items-center justify-center mb-5"
                style={{ background: "#EEF4FB" }}
              >
                {s.icon}
              </div>

              {/* Tag */}
              <span
                className="inline-block text-xs font-semibold uppercase tracking-wider mb-3 px-2 py-0.5 rounded"
                style={{ background: "#EEF4FB", color: "#2D6EA8", fontFamily: "Sora, sans-serif", letterSpacing: "0.08em" }}
              >
                {s.tag}
              </span>

              {/* Title */}
              <h3
                className="font-bold mb-1 leading-snug"
                style={{ fontFamily: "Sora, sans-serif", fontSize: "1rem", color: "#0F2340" }}
              >
                {s.en}
              </h3>
              <p
                className="text-sm font-medium mb-3"
                style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
              >
                {s.cn}
              </p>

              {/* Description */}
              <p
                className="text-sm leading-relaxed mb-2"
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
          ))}
        </div>
      </div>
    </section>
  );
}
