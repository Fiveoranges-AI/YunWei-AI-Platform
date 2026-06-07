/* =============================================================
   WcNav — standalone navigation for the /worldcup microsite.
   This nav exists ONLY inside /worldcup. It does not touch, and is
   not part of, the main Five Oranges AI site header.
   Desktop: two-row sticky header (brand + sections). Mobile: drawer.
   ============================================================= */

import { useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { WC, WC_BRAND, WC_NAV } from "./config";
import { BallMark } from "./ui";

const JOIN = WC_NAV[WC_NAV.length - 1]; // 加入微信群
const SECTIONS = WC_NAV.slice(0, -1); // everything except Join (shown as CTA)

function isActive(loc: string, href: string) {
  return loc === href || loc === href + "/";
}

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link
      href="/worldcup"
      onClick={onClick}
      style={{ display: "inline-flex", alignItems: "center", gap: "12px", textDecoration: "none", minWidth: 0 }}
      aria-label={`${WC_BRAND.cn} · ${WC_BRAND.en}`}
    >
      <span
        style={{
          width: "44px",
          height: "44px",
          borderRadius: "12px",
          background: WC.greenPale,
          border: `1px solid rgba(11,122,75,0.25)`,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <BallMark size={26} />
      </span>
      <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.05, minWidth: 0 }}>
        <span
          style={{
            fontFamily: "Sora, sans-serif",
            fontWeight: 800,
            fontSize: "1.0625rem",
            color: WC.ink,
            letterSpacing: "0.01em",
            whiteSpace: "nowrap",
          }}
        >
          {WC_BRAND.cn}
        </span>
        <span
          style={{
            fontFamily: "Sora, sans-serif",
            fontWeight: 500,
            fontSize: "0.68rem",
            color: WC.green,
            letterSpacing: "0.06em",
            marginTop: "3px",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {WC_BRAND.en}
        </span>
      </span>
    </Link>
  );
}

function JoinPill({ onClick, block = false }: { onClick?: () => void; block?: boolean }) {
  return (
    <Link
      href={JOIN.href}
      onClick={onClick}
      className="wc-cta wc-cta-primary"
      style={{
        display: block ? "flex" : "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        background: WC.green,
        color: "#fff",
        fontFamily: "Sora, sans-serif",
        fontWeight: 600,
        fontSize: "0.9rem",
        padding: "0.6rem 1.1rem",
        borderRadius: "999px",
        textDecoration: "none",
        boxShadow: "0 4px 12px rgba(11,122,75,0.22)",
        whiteSpace: "nowrap",
      }}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M9.5 9.2a1 1 0 110-2 1 1 0 010 2zm5 0a1 1 0 110-2 1 1 0 010 2z" />
        <path d="M8.5 3C4.9 3 2 5.5 2 8.6c0 1.8 1 3.4 2.6 4.4L4 15.3l2.6-1.3c.6.1 1.2.2 1.9.2h.5a5.3 5.3 0 01-.2-1.4c0-3 2.9-5.3 6.4-5.3h.6C15.7 4.8 12.4 3 8.5 3z" />
        <path d="M22 13.6c0-2.6-2.5-4.7-5.6-4.7s-5.6 2.1-5.6 4.7 2.5 4.7 5.6 4.7c.6 0 1.2-.1 1.8-.2l2 1-.6-1.7c1.4-.9 2.4-2.3 2.4-3.8zm-7.4-.8a.8.8 0 110-1.6.8.8 0 010 1.6zm3.7 0a.8.8 0 110-1.6.8.8 0 010 1.6z" />
      </svg>
      {JOIN.cn}
    </Link>
  );
}

export default function WcNav() {
  const [loc] = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "#fff",
        borderBottom: `1px solid ${scrolled ? WC.line : "rgba(15,35,64,0.05)"}`,
        boxShadow: scrolled ? "0 1px 3px rgba(15,35,64,0.05)" : "none",
        transition: "border-color 200ms ease, box-shadow 200ms ease",
      }}
    >
      {/* Row 1: brand + primary CTA / hamburger */}
      <div className="container">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: "66px", gap: "1rem" }}>
          <Brand onClick={close} />
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span className="hidden lg:inline-flex">
              <JoinPill />
            </span>
            <button
              className="lg:hidden"
              aria-label="打开菜单 Open menu"
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                background: open ? WC.greenPale : "transparent",
                border: `1px solid ${WC.line}`,
              }}
            >
              {open ? (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={WC.ink} strokeWidth="2">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              ) : (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={WC.ink} strokeWidth="2">
                  <path d="M4 7h16M4 12h16M4 17h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Row 2: section links (desktop) */}
      <div className="hidden lg:block" style={{ borderTop: `1px solid ${WC.line}`, background: "#fff" }}>
        <div className="container">
          <nav style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.35rem 1.4rem", padding: "0.5rem 0" }}>
            {SECTIONS.map((item) => {
              const active = isActive(loc, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="wc-navlink"
                  data-active={active}
                  style={{
                    fontFamily: "Sora, sans-serif",
                    fontWeight: active ? 700 : 500,
                    fontSize: "0.92rem",
                    color: active ? WC.green : WC.inkSoft,
                    textDecoration: "none",
                    padding: "0.45rem 0",
                    borderBottom: `2px solid ${active ? WC.green : "transparent"}`,
                    whiteSpace: "nowrap",
                  }}
                >
                  {item.cn}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <>
          <div
            className="lg:hidden"
            onClick={close}
            aria-hidden
            style={{
              position: "fixed",
              inset: "66px 0 0 0",
              background: "rgba(15,35,64,0.45)",
              backdropFilter: "blur(2px)",
              WebkitBackdropFilter: "blur(2px)",
              zIndex: 40,
              animation: "drawerScrimFadeIn 200ms ease-out",
            }}
          />
          <div
            className="lg:hidden"
            style={{
              position: "fixed",
              top: "66px",
              right: 0,
              bottom: 0,
              width: "min(330px, 86vw)",
              background: "#fff",
              borderLeft: `1px solid ${WC.line}`,
              boxShadow: "-12px 0 30px rgba(15,35,64,0.12)",
              overflowY: "auto",
              zIndex: 41,
              animation: "drawerSlideInRight 260ms cubic-bezier(0.32,0.72,0.24,1.0)",
              padding: "0.75rem 0.75rem 2rem",
            }}
          >
            {WC_NAV.map((item) => {
              const active = isActive(loc, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={close}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "0.85rem 1rem",
                    borderRadius: "10px",
                    color: active ? WC.green : WC.ink,
                    background: active ? WC.greenPale : "transparent",
                    fontFamily: "Sora, sans-serif",
                    fontWeight: 600,
                    fontSize: "1rem",
                    textDecoration: "none",
                  }}
                >
                  <span>{item.cn}</span>
                  <span style={{ fontSize: "0.7rem", letterSpacing: "0.06em", color: WC.muted }}>{item.en}</span>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </header>
  );
}
