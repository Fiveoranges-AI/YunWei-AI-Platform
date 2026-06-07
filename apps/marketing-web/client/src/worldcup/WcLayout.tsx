/* =============================================================
   WcLayout — shell for every /worldcup page: standalone nav +
   content + standalone footer. Resets scroll and sets the document
   title on route change. Self-contained; does not affect main site.
   ============================================================= */

import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "wouter";
import { WC, WC_BRAND, WC_NAV } from "./config";
import WcNav from "./WcNav";
import WcFooter from "./WcFooter";

const TITLES: Record<string, string> = Object.fromEntries(
  WC_NAV.map((n) => [n.href, n.href === "/worldcup" ? WC_BRAND.cn : `${n.cn} · ${WC_BRAND.cn}`]),
);

export default function WcLayout({ children }: { children: ReactNode }) {
  const [loc] = useLocation();
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    document.title = TITLES[loc] ?? WC_BRAND.cn;
  }, [loc]);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 600);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="wc-root" style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#fff", color: WC.ink }}>
      <WcNav />
      <main style={{ flex: 1 }}>{children}</main>
      <WcFooter />

      {showTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="回到顶部 Scroll to top"
          style={{
            position: "fixed",
            bottom: "1.5rem",
            right: "1.5rem",
            zIndex: 45,
            width: "44px",
            height: "44px",
            borderRadius: "999px",
            background: WC.green,
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 8px 20px rgba(11,122,75,0.3)",
            border: "none",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 14V4M5 8l4-4 4 4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </div>
  );
}
