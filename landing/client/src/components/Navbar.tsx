/* =============================================================
   Navbar — Five Oranges AI
   Style: Transparent → frosted glass on scroll
   Fixed top, bilingual nav links
   ============================================================= */

import { useState, useEffect } from "react";

const navLinks = [
  { label: "Solutions", cn: "解决方案", href: "#solutions" },
  { label: "Approach", cn: "实施方法", href: "#approach" },
  { label: "Use Cases", cn: "应用场景", href: "#usecases" },
  { label: "About", cn: "关于我们", href: "#about" },
  { label: "Contact", cn: "联系我们", href: "#contact" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const handleNavClick = (href: string) => {
    setMobileOpen(false);
    const el = document.querySelector(href);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-white/90 backdrop-blur-md shadow-sm border-b border-slate-100"
          : "bg-transparent"
      }`}
    >
      <div className="container">
        <div className="flex items-center justify-between h-16 lg:h-18">
          {/* Logo */}
          <a
            href="#"
            onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            className="flex items-center gap-3 group"
          >
            <img
              src="/manus-storage/logo_clean_934597e8.png"
              alt="Five Oranges AI Logo"
              className="h-10 w-10 object-contain"
            />
            <div className="flex flex-col leading-none">
              <span
                className="font-bold text-sm tracking-tight"
                style={{ fontFamily: "Sora, sans-serif", color: "#0F2340" }}
              >
                Five Oranges AI
              </span>
              <span
                className="text-xs font-medium"
                style={{ fontFamily: "Manrope, sans-serif", color: "#2D6EA8" }}
              >
                运帷AI
              </span>
            </div>
          </a>

          {/* Desktop nav */}
          <nav className="hidden lg:flex items-center gap-1">
            {navLinks.map((link) => (
              <button
                key={link.href}
                onClick={() => handleNavClick(link.href)}
                className="group px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 hover:bg-blue-50"
                style={{ fontFamily: "Manrope, sans-serif", color: "#374151" }}
              >
                <span className="group-hover:text-[#2D6EA8] transition-colors">{link.label}</span>
                <span className="block text-xs text-slate-400 group-hover:text-blue-400 transition-colors leading-none mt-0.5">{link.cn}</span>
              </button>
            ))}
          </nav>

          {/* CTA + mobile toggle */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => handleNavClick("#contact")}
              className="hidden lg:inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-200 hover:opacity-90 hover:shadow-md"
              style={{ fontFamily: "Sora, sans-serif", background: "#2D6EA8" }}
            >
              Book a Call
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 7h10M8 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {/* Mobile hamburger */}
            <button
              className="lg:hidden p-2 rounded-lg hover:bg-slate-100 transition-colors"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              <div className="w-5 flex flex-col gap-1.5">
                <span className={`block h-0.5 bg-slate-700 transition-all duration-200 ${mobileOpen ? "rotate-45 translate-y-2" : ""}`} />
                <span className={`block h-0.5 bg-slate-700 transition-all duration-200 ${mobileOpen ? "opacity-0" : ""}`} />
                <span className={`block h-0.5 bg-slate-700 transition-all duration-200 ${mobileOpen ? "-rotate-45 -translate-y-2" : ""}`} />
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="lg:hidden bg-white border-t border-slate-100 shadow-lg">
          <div className="container py-4 flex flex-col gap-1">
            {navLinks.map((link) => (
              <button
                key={link.href}
                onClick={() => handleNavClick(link.href)}
                className="flex items-center justify-between px-4 py-3 rounded-lg hover:bg-blue-50 transition-colors text-left"
              >
                <span className="font-medium text-slate-800" style={{ fontFamily: "Manrope, sans-serif" }}>{link.label}</span>
                <span className="text-sm text-slate-400" style={{ fontFamily: "Manrope, sans-serif" }}>{link.cn}</span>
              </button>
            ))}
            <button
              onClick={() => handleNavClick("#contact")}
              className="mt-2 w-full px-4 py-3 rounded-lg text-sm font-semibold text-white text-center"
              style={{ background: "#2D6EA8", fontFamily: "Sora, sans-serif" }}
            >
              Book a Strategy Call
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
