/* =============================================================
   UseCasesSection — Sample use cases
   Style: Compact list with icon bullets, blue section bg
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const useCases = [
  {
    en: "Daily production briefing generated automatically from operational data",
    cn: "基于运营数据自动生成每日生产简报",
    category: "Manufacturing",
  },
  {
    en: "AI assistant answering employee questions from internal policies and SOPs",
    cn: "基于内部政策与 SOP 的员工智能问答助手",
    category: "Knowledge",
  },
  {
    en: "Quotation risk scoring based on historical manufacturing data",
    cn: "基于历史制造数据的报价风险评分",
    category: "Finance",
  },
  {
    en: "HR attendance exception report from raw clock-in data",
    cn: "基于原始打卡数据的考勤异常报告",
    category: "HR",
  },
  {
    en: "Executive dashboard summarizing orders, revenue, cost, capacity, and risks",
    cn: "汇总订单、营收、成本、产能与风险的管理层看板",
    category: "Dashboard",
  },
  {
    en: "ISO audit checklist and evidence management assistant",
    cn: "ISO 审核清单与证据管理智能助手",
    category: "Compliance",
  },
  {
    en: "Enterprise WeChat / DingTalk notification agent for task reminders and management alerts",
    cn: "企业微信 / 钉钉任务提醒与管理预警通知 Agent",
    category: "Automation",
  },
];

const categoryColors: Record<string, string> = {
  Manufacturing: "#2D6EA8",
  Knowledge: "#3B7EC8",
  Finance: "#4A8BC4",
  HR: "#5B9BD5",
  Dashboard: "#2D6EA8",
  Compliance: "#3B7EC8",
  Automation: "#4A8BC4",
};

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

export default function UseCasesSection() {
  const { ref, inView } = useInView();

  return (
    <section id="usecases" className="py-24 lg:py-32 bg-section-blue relative overflow-hidden">
      {/* Decorative image */}
      <div
        className="absolute right-0 top-0 bottom-0 w-1/3 opacity-20 hidden lg:block"
        style={{
          backgroundImage: `url(https://d2xsxph8kpxj0f.cloudfront.net/310519663273870289/64xTVtv7XqMZ3588Nzt2Xd/solutions_visual-LgsvoGzE6sdzcV5wh8irET.webp)`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />

      <div className="container relative z-10" ref={ref}>
        <div className="max-w-3xl">
          {/* Header */}
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Use Cases · 应用场景
          </span>
          <h2
            className="font-bold leading-tight mb-3"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
          >
            Example Use Cases{" "}
            <span style={{ color: "#2D6EA8" }}>We Can Deliver</span>
          </h2>
          <p className="text-base font-medium mb-12" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
            典型可落地场景
          </p>

          {/* Use case list */}
          <div className="flex flex-col gap-3">
            {useCases.map((uc, i) => (
              <div
                key={i}
                className="flex items-start gap-4 p-5 rounded-xl bg-white border border-slate-100 card-lift"
                style={{
                  opacity: inView ? 1 : 0,
                  transform: inView ? "translateX(0)" : "translateX(-20px)",
                  transition: `opacity 0.45s ease ${i * 0.07}s, transform 0.45s ease ${i * 0.07}s`,
                }}
              >
                {/* Category badge */}
                <div className="flex-shrink-0 mt-0.5">
                  <span
                    className="inline-block w-2 h-2 rounded-full mt-1.5"
                    style={{ background: categoryColors[uc.category] || "#2D6EA8" }}
                  />
                </div>
                <div className="flex-1">
                  <p
                    className="text-sm font-semibold mb-0.5 leading-snug"
                    style={{ fontFamily: "Manrope, sans-serif", color: "#0F2340" }}
                  >
                    {uc.en}
                  </p>
                  <p
                    className="text-xs"
                    style={{ fontFamily: "Manrope, sans-serif", color: "#64748B" }}
                  >
                    {uc.cn}
                  </p>
                </div>
                <span
                  className="flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full"
                  style={{
                    background: "#EEF4FB",
                    color: categoryColors[uc.category] || "#2D6EA8",
                    fontFamily: "Sora, sans-serif",
                    letterSpacing: "0.05em",
                  }}
                >
                  {uc.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
