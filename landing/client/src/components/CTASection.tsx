/* =============================================================
   CTASection — Final call to action + contact
   Style: Light blue-gray bg with subtle pattern, centered
   ============================================================= */

import { useEffect, useRef, useState } from "react";

function useInView(threshold = 0.2) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, inView };
}

export default function CTASection() {
  const { ref, inView } = useInView();

  return (
    <section id="contact" className="py-24 lg:py-32 relative overflow-hidden">
      {/* Background */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `url(https://d2xsxph8kpxj0f.cloudfront.net/310519663273870289/64xTVtv7XqMZ3588Nzt2Xd/cta_bg-88CTvGGdCovCm6p83giqi7.webp)`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />
      {/* Overlay */}
      <div className="absolute inset-0" style={{ background: "rgba(238,244,251,0.92)" }} />

      {/* V watermark */}
      <span
        className="watermark-v"
        style={{ left: "50%", top: "50%", transform: "translate(-50%, -50%)" }}
      >
        V
      </span>

      <div className="container relative z-10" ref={ref}>
        <div
          className="max-w-2xl mx-auto text-center"
          style={{
            opacity: inView ? 1 : 0,
            transform: inView ? "translateY(0)" : "translateY(24px)",
            transition: "opacity 0.6s ease, transform 0.6s ease",
          }}
        >
          <span className="section-label mb-6 inline-flex">
            <span className="slash-accent" style={{ width: "1rem" }} />
            Get Started · 开始合作
          </span>

          <h2
            className="font-bold leading-tight mb-4"
            style={{ fontFamily: "Sora, sans-serif", fontSize: "clamp(2rem, 4vw, 3rem)", color: "#0F2340" }}
          >
            Ready to Build Your
            <br />
            <span style={{ color: "#2D6EA8" }}>AI Operating Layer?</span>
          </h2>

          <p
            className="text-base font-medium mb-3"
            style={{ color: "#2D6EA8", fontFamily: "Manrope, sans-serif" }}
          >
            准备好构建你的企业 AI 运营层了吗？
          </p>

          <p
            className="text-sm leading-relaxed mb-10"
            style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
          >
            Start with a focused strategy call. We'll identify the highest-value AI opportunity
            in your operations and outline a practical path to implementation — no hype, no demos,
            just actionable next steps.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <a
              href="mailto:contact@fiveoranges.ai"
              className="inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-lg text-white font-semibold text-sm transition-all duration-200 hover:opacity-90 hover:shadow-lg hover:-translate-y-0.5"
              style={{ background: "#2D6EA8", fontFamily: "Sora, sans-serif" }}
            >
              Book a Strategy Call
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </a>
            <a
              href="mailto:contact@fiveoranges.ai"
              className="inline-flex items-center justify-center gap-2.5 px-8 py-4 rounded-lg font-semibold text-sm border transition-all duration-200 hover:bg-white hover:-translate-y-0.5"
              style={{
                fontFamily: "Sora, sans-serif",
                color: "#0F2340",
                borderColor: "rgba(15,35,64,0.25)",
                background: "rgba(255,255,255,0.7)",
              }}
            >
              Contact Five Oranges AI
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12v8a1 1 0 01-1 1H3a1 1 0 01-1-1V4z" stroke="currentColor" strokeWidth="1.4"/>
                <path d="M2 4l6 5 6-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
            </a>
          </div>

          {/* Contact info */}
          <div
            className="inline-flex flex-col sm:flex-row gap-6 items-center px-8 py-5 rounded-xl border border-slate-200 bg-white/80"
          >
            <div className="flex items-center gap-2.5">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12v8a1 1 0 01-1 1H3a1 1 0 01-1-1V4z" stroke="#2D6EA8" strokeWidth="1.4"/>
                <path d="M2 4l6 5 6-5" stroke="#2D6EA8" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <a
                href="mailto:contact@fiveoranges.ai"
                className="text-sm font-medium hover:underline"
                style={{ fontFamily: "Manrope, sans-serif", color: "#0F2340" }}
              >
                contact@fiveoranges.ai
              </a>
            </div>
            <div className="hidden sm:block w-px h-4 bg-slate-200" />
            <div className="flex items-center gap-2.5">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6" stroke="#2D6EA8" strokeWidth="1.4"/>
                <path d="M8 2c-2 2-3 4-3 6s1 4 3 6M8 2c2 2 3 4 3 6s-1 4-3 6M2 8h12" stroke="#2D6EA8" strokeWidth="1.2"/>
              </svg>
              <span
                className="text-sm font-medium"
                style={{ fontFamily: "Manrope, sans-serif", color: "#0F2340" }}
              >
                fiveoranges.ai
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
