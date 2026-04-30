/* =============================================================
   CustomersSection — Target customer profiles
   Style: 2x2 grid with icon cards, white background
   ============================================================= */

import { useEffect, useRef, useState } from "react";

const customers = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <rect x="4" y="12" width="24" height="16" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M10 12V8a6 6 0 0112 0v4" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M16 18v4" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <circle cx="16" cy="17" r="2" fill="#2D6EA8"/>
      </svg>
    ),
    en: "Manufacturing SMEs",
    cn: "制造业中小企业",
    desc: "Chinese and North American manufacturers seeking to digitize operations, improve production visibility, and reduce cost variability.",
    cn_desc: "中国及北美制造业中小企业，推进运营数字化、提升生产可视化、降低成本波动。",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <circle cx="16" cy="10" r="5" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M8 28c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M22 6l2 2-6 6" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    en: "Second-Generation Business Leaders",
    cn: "厂二代 / 二代企业家",
    desc: "Next-generation operators driving management upgrades, digital transformation, and internationalization of family businesses.",
    cn_desc: "希望推动管理升级、数字化转型和国际化的厂二代与二代企业家。",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <path d="M4 16h24" stroke="#2D6EA8" strokeWidth="1.8" strokeLinecap="round"/>
        <path d="M16 4l12 12-12 12L4 16l12-12z" stroke="#2D6EA8" strokeWidth="1.8" strokeLinejoin="round"/>
      </svg>
    ),
    en: "Trading & Export Companies",
    cn: "贸易与外贸企业",
    desc: "Export-oriented businesses needing to improve sales efficiency, customer follow-up, quotation accuracy, and compliance management.",
    cn_desc: "需要提升销售、客户跟进、报价和合规效率的外贸与贸易型企业。",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <rect x="4" y="6" width="24" height="20" rx="2" stroke="#2D6EA8" strokeWidth="1.8"/>
        <path d="M10 12h12M10 16h8M10 20h10" stroke="#2D6EA8" strokeWidth="1.6" strokeLinecap="round"/>
        <path d="M20 2v4M12 2v4" stroke="#2D6EA8" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
    ),
    en: "Public Sector & Regulated Organizations",
    cn: "政府与公共部门",
    desc: "Government agencies and regulated organizations requiring compliant, secure, and auditable digital transformation solutions.",
    cn_desc: "需要合规、安全、可审计数字化方案的政府机构和公共部门组织。",
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

export default function CustomersSection() {
  const { ref, inView } = useInView();

  return (
    <section className="py-24 lg:py-32 bg-white">
      <div className="container" ref={ref}>
        {/* Header */}
        <div className="mb-14">
          <span className="section-label mb-5 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Who We Serve · 服务对象
          </span>
          <h2
            className="font-bold leading-tight"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(1.9rem, 3.5vw, 2.8rem)", color: "#0F2340" }}
          >
            Built for Ambitious Operators
            <br />
            and <span style={{ color: "#2D6EA8" }}>Transformation Leaders</span>
          </h2>
          <p className="mt-2 text-base font-medium" style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}>
            服务有升级意识的企业经营者与转型负责人
          </p>
        </div>

        {/* Customer grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {customers.map((c, i) => (
            <div
              key={i}
              className="card-lift flex gap-6 p-7 rounded-xl border border-slate-100 bg-white"
              style={{
                opacity: inView ? 1 : 0,
                transform: inView ? "translateY(0)" : "translateY(24px)",
                transition: `opacity 0.5s ease ${i * 0.1}s, transform 0.5s ease ${i * 0.1}s`,
              }}
            >
              <div
                className="flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center"
                style={{ background: "#EEF4FB" }}
              >
                {c.icon}
              </div>
              <div>
                <h3
                  className="font-bold mb-0.5"
                  style={{ fontFamily: "Sora, sans-serif", fontSize: "1.05rem", color: "#0F2340" }}
                >
                  {c.en}
                </h3>
                <p
                  className="text-sm font-semibold mb-3"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
                >
                  {c.cn}
                </p>
                <p
                  className="text-sm leading-relaxed mb-1"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
                >
                  {c.desc}
                </p>
                <p
                  className="text-xs leading-relaxed"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
                >
                  {c.cn_desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
