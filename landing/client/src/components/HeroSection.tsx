/* =============================================================
   HeroSection — Five Oranges AI
   Style: Left-anchored display type, right geometric visual
   Background: White with subtle geometric overlay
   ============================================================= */

export default function HeroSection() {
  const handleScroll = (href: string) => {
    const el = document.querySelector(href);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section
      className="relative min-h-screen flex items-center overflow-hidden"
      style={{ background: "#FFFFFF" }}
    >
      {/* Background image — subtle geometric */}
      <div
        className="absolute inset-0 opacity-60"
        style={{
          backgroundImage: `url(https://d2xsxph8kpxj0f.cloudfront.net/310519663273870289/64xTVtv7XqMZ3588Nzt2Xd/hero_bg-m8WYmQq5sZjYVmfR2cjCBf.webp)`,
          backgroundSize: "cover",
          backgroundPosition: "center right",
        }}
      />

      {/* Gradient overlay to ensure text readability */}
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(105deg, rgba(255,255,255,0.97) 45%, rgba(255,255,255,0.7) 70%, rgba(255,255,255,0.3) 100%)",
        }}
      />

      {/* V watermark */}
      <span
        className="watermark-v"
        style={{ right: "8%", top: "50%", transform: "translateY(-50%)" }}
      >
        V
      </span>

      <div className="container relative z-10 pt-24 pb-20">
        <div className="max-w-3xl">
          {/* Label */}
          <div className="fade-up fade-up-delay-1 mb-6">
            <span className="section-label">
              <span className="slash-accent" style={{ width: "1.2rem" }} />
              AI Transformation · 企业智能转型
            </span>
          </div>

          {/* Main headline */}
          <h1
            className="fade-up fade-up-delay-2 font-bold leading-[1.08] tracking-tight mb-6"
            style={{
              fontFamily: "Sora, sans-serif",
              fontSize: "clamp(2.6rem, 5.5vw, 4.5rem)",
              color: "#0F2340",
            }}
          >
            From Fragmented
            <br />
            <span style={{ color: "#2D6EA8" }}>Operations</span> to
            <br />
            Intelligent Execution.
          </h1>

          {/* Chinese sub-headline */}
          <p
            className="fade-up fade-up-delay-3 font-medium mb-4"
            style={{
              fontFamily: "Manrope, sans-serif",
              fontSize: "clamp(1rem, 1.8vw, 1.2rem)",
              color: "#2D6EA8",
              letterSpacing: "0.02em",
            }}
          >
            让企业从经验驱动，走向数据驱动与智能执行。
          </p>

          {/* Description */}
          <p
            className="fade-up fade-up-delay-3 mb-10 max-w-xl leading-relaxed"
            style={{
              fontFamily: "Manrope, sans-serif",
              fontSize: "clamp(0.95rem, 1.4vw, 1.05rem)",
              color: "#475569",
            }}
          >
            We help manufacturing, trading, and enterprise organizations build
            AI Agents, knowledge bases, process automation, and intelligent
            dashboards — grounded in real business workflows, not demos.
          </p>

          {/* CTA buttons */}
          <div className="fade-up fade-up-delay-4 flex flex-wrap gap-4">
            <button
              onClick={() => handleScroll("#contact")}
              className="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-lg text-white font-semibold text-sm transition-all duration-200 hover:opacity-90 hover:shadow-lg hover:-translate-y-0.5"
              style={{ background: "#2D6EA8", fontFamily: "Sora, sans-serif" }}
            >
              Book a Strategy Call
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button
              onClick={() => handleScroll("#solutions")}
              className="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-lg font-semibold text-sm border transition-all duration-200 hover:bg-blue-50 hover:-translate-y-0.5"
              style={{
                fontFamily: "Sora, sans-serif",
                color: "#0F2340",
                borderColor: "rgba(15,35,64,0.2)",
              }}
            >
              Explore Solutions
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 3v10M4 9l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          {/* Five pillars strip */}
          <div className="fade-up fade-up-delay-5 mt-14 pt-8 border-t border-slate-100">
            <p
              className="text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "#94A3B8", fontFamily: "Sora, sans-serif" }}
            >
              Five Capabilities · 五种核心能力
            </p>
            <div className="flex flex-wrap gap-x-8 gap-y-2">
              {[
                { en: "Strategy", cn: "战略判断" },
                { en: "Process", cn: "流程重塑" },
                { en: "Data", cn: "数据治理" },
                { en: "AI", cn: "智能代理" },
                { en: "Execution", cn: "执行闭环" },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: "#2D6EA8" }}
                  />
                  <span
                    className="text-sm font-semibold"
                    style={{ color: "#0F2340", fontFamily: "Sora, sans-serif" }}
                  >
                    {item.en}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "#94A3B8", fontFamily: "Manrope, sans-serif" }}
                  >
                    {item.cn}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-24"
        style={{ background: "linear-gradient(to bottom, transparent, #ffffff)" }}
      />
    </section>
  );
}
