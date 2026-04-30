/* =============================================================
   Footer — Five Oranges AI
   Style: White bg, minimal, with logo and nav links
   ============================================================= */

export default function Footer() {
  const handleScroll = (href: string) => {
    const el = document.querySelector(href);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <footer className="bg-white border-t border-slate-100">
      <div className="container py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-10">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-3 mb-4">
              <img
                src="/manus-storage/logo_clean_934597e8.png"
                alt="Five Oranges AI"
                className="h-10 w-10 object-contain"
              />
              <div>
                <div
                  className="font-bold text-sm"
                  style={{ fontFamily: "Sora, sans-serif", color: "#0F2340" }}
                >
                  Five Oranges AI
                </div>
                <div
                  className="text-xs font-medium"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
                >
                  运帷AI
                </div>
              </div>
            </div>
            <p
              className="text-sm leading-relaxed mb-2"
              style={{ fontFamily: "Manrope, sans-serif", color: "#64748B" }}
            >
              AI Transformation for Real-World Enterprises
            </p>
            <p
              className="text-xs"
              style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
            >
              让企业从经验驱动，走向数据驱动与智能执行。
            </p>
          </div>

          {/* Navigation */}
          <div>
            <h4
              className="font-semibold text-xs uppercase tracking-widest mb-4"
              style={{ fontFamily: "Sora, sans-serif", color: "#94A3B8" }}
            >
              Navigation
            </h4>
            <div className="flex flex-col gap-2">
              {[
                { label: "Solutions · 解决方案", href: "#solutions" },
                { label: "Approach · 实施方法", href: "#approach" },
                { label: "Use Cases · 应用场景", href: "#usecases" },
                { label: "About · 关于我们", href: "#about" },
                { label: "Contact · 联系我们", href: "#contact" },
              ].map((link) => (
                <button
                  key={link.href}
                  onClick={() => handleScroll(link.href)}
                  className="text-left text-sm hover:text-blue-600 transition-colors"
                  style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
                >
                  {link.label}
                </button>
              ))}
            </div>
          </div>

          {/* Contact */}
          <div>
            <h4
              className="font-semibold text-xs uppercase tracking-widest mb-4"
              style={{ fontFamily: "Sora, sans-serif", color: "#94A3B8" }}
            >
              Contact · 联系方式
            </h4>
            <div className="flex flex-col gap-3">
              <a
                href="mailto:contact@fiveoranges.ai"
                className="flex items-center gap-2.5 text-sm hover:text-blue-600 transition-colors"
                style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
              >
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <path d="M1.5 3.5h12v8a1 1 0 01-1 1h-10a1 1 0 01-1-1v-8z" stroke="#2D6EA8" strokeWidth="1.3"/>
                  <path d="M1.5 3.5l6 5 6-5" stroke="#2D6EA8" strokeWidth="1.3" strokeLinecap="round"/>
                </svg>
                contact@fiveoranges.ai
              </a>
              <div
                className="flex items-center gap-2.5 text-sm"
                style={{ fontFamily: "Manrope, sans-serif", color: "#475569" }}
              >
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <circle cx="7.5" cy="7.5" r="5.5" stroke="#2D6EA8" strokeWidth="1.3"/>
                  <path d="M7.5 2c-1.8 1.8-2.8 3.6-2.8 5.5s1 3.7 2.8 5.5M7.5 2c1.8 1.8 2.8 3.6 2.8 5.5s-1 3.7-2.8 5.5M2 7.5h11" stroke="#2D6EA8" strokeWidth="1.1"/>
                </svg>
                fiveoranges.ai
              </div>
            </div>

            {/* Five pillars mini */}
            <div className="mt-6 pt-6 border-t border-slate-100">
              <p
                className="text-xs font-semibold uppercase tracking-widest mb-2"
                style={{ fontFamily: "Sora, sans-serif", color: "#94A3B8" }}
              >
                Five Capabilities
              </p>
              <div className="flex flex-wrap gap-1.5">
                {["Strategy", "Process", "Data", "AI", "Execution"].map((cap) => (
                  <span
                    key={cap}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: "#EEF4FB", color: "#2D6EA8", fontFamily: "Sora, sans-serif" }}
                  >
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="rule-line mb-6" />
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
          <p
            className="text-xs"
            style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
          >
            © {new Date().getFullYear()} Five Oranges AI (运帷AI). All rights reserved.
          </p>
          <p
            className="text-xs"
            style={{ fontFamily: "Manrope, sans-serif", color: "#94A3B8" }}
          >
            fiveoranges.ai · From fragmented operations to intelligent execution.
          </p>
        </div>
      </div>
    </footer>
  );
}
