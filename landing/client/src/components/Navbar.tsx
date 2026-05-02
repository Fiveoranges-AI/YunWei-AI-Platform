/* =============================================================
   Navbar — Five Oranges AI · 运帷AI (v1.3)
   Editorial bilingual nav with EN-primary labels and CN tooltips,
   icon-utility right cluster (Demo · Portal) + Contact CTA pill.
   ============================================================= */

import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { cn: "解决方案", en: "Solutions", href: "#solutions" },
  { cn: "方法论", en: "Approach", href: "#approach" },
  { cn: "应用场景", en: "Use Cases", href: "#use-cases" },
  { cn: "关于我们", en: "About", href: "#about" },
];

const PORTAL_URL = "https://app.fiveoranges.ai/";
const DEMO_URL = "https://app.fiveoranges.ai/";
const CONTACT_HREF = "mailto:contact@fiveoranges.ai";

type CnTooltipProps = { text: string; show: boolean };
function CnTooltip({ text, show }: CnTooltipProps) {
  return (
    <span
      role="tooltip"
      aria-hidden={!show}
      style={{
        position: "absolute",
        top: "calc(100% + 10px)",
        left: "50%",
        transform: `translateX(-50%) translateY(${show ? "0" : "-4px"})`,
        background: "#0A2540",
        color: "#fff",
        fontFamily: "Sora, sans-serif",
        fontWeight: 500,
        fontSize: "12px",
        letterSpacing: "0.05em",
        padding: "7px 12px",
        borderRadius: "6px",
        whiteSpace: "nowrap",
        opacity: show ? 1 : 0,
        transition: "opacity 180ms ease-out 100ms, transform 180ms ease-out 100ms",
        pointerEvents: "none",
        boxShadow: "0 6px 20px rgba(10,37,64,0.22)",
        zIndex: 60,
      }}
    >
      <span
        aria-hidden
        style={{
          position: "absolute",
          top: "-5px",
          left: "50%",
          transform: "translateX(-50%) rotate(45deg)",
          width: "10px",
          height: "10px",
          background: "#0A2540",
          borderRadius: "2px 0 0 0",
        }}
      />
      <span style={{ position: "relative" }}>{text}</span>
    </span>
  );
}

type NavCapsuleProps = { item: { cn: string; en: string; href: string }; onNav?: () => void };
function NavCapsule({ item, onNav }: NavCapsuleProps) {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={item.href}
      onClick={onNav}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      aria-label={`${item.en} · ${item.cn}`}
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        padding: "8px 4px",
        color: hover ? "var(--brand-blue)" : "#0F2340",
        textDecoration: "none",
        fontFamily: "Sora, sans-serif",
        fontWeight: 500,
        fontSize: "14.5px",
        letterSpacing: "0.01em",
        transition: "color 200ms ease-out",
        outline: "none",
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ position: "relative" }}>
        {item.en}
        <span
          aria-hidden
          style={{
            position: "absolute",
            left: 0,
            bottom: "-5px",
            height: "2px",
            width: hover ? "100%" : "0%",
            background: "var(--brand-blue)",
            borderRadius: "2px",
            transition: "width 240ms cubic-bezier(0.32, 0.72, 0.24, 1.0)",
          }}
        />
      </span>
      <CnTooltip text={item.cn} show={hover} />
    </a>
  );
}

function LiveDot() {
  return (
    <span
      aria-hidden
      style={{ position: "relative", width: "8px", height: "8px", display: "inline-block", flexShrink: 0 }}
    >
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "999px",
          background: "#34D399",
          animation: "navLivePulse 1.8s ease-out infinite",
          opacity: 0.6,
        }}
      />
      <span
        style={{
          position: "absolute",
          inset: "1.5px",
          borderRadius: "999px",
          background: "#10B981",
        }}
      />
    </span>
  );
}

function DemoBtn() {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={DEMO_URL}
      target="_blank"
      rel="noopener noreferrer"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      aria-label="Demo · 演示"
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: "40px",
        height: "40px",
        borderRadius: "10px",
        background: hover ? "rgba(45,110,168,0.10)" : "transparent",
        color: hover ? "var(--brand-blue)" : "#0F2340",
        textDecoration: "none",
        transition: "background 180ms ease-out, color 180ms ease-out",
        outline: "none",
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="12" cy="12" r="9" />
        <path d="M10 9.5v5l4.5 -2.5z" fill="currentColor" stroke="none" />
      </svg>
      <span
        aria-hidden
        style={{ position: "absolute", top: "7px", right: "7px", width: "7px", height: "7px", pointerEvents: "none" }}
      >
        <span
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "999px",
            background: "#34D399",
            animation: "navLivePulse 1.8s ease-out infinite",
            opacity: 0.55,
          }}
        />
        <span
          style={{
            position: "absolute",
            inset: "1.5px",
            borderRadius: "999px",
            background: "#10B981",
            boxShadow: "0 0 0 1.5px #fff",
          }}
        />
      </span>
      <CnTooltip text="Demo · 演示" show={hover} />
    </a>
  );
}

function PortalBtn() {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={PORTAL_URL}
      target="_blank"
      rel="noopener noreferrer"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      aria-label="Client Portal · 客户登录"
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: "40px",
        height: "40px",
        borderRadius: "10px",
        background: hover ? "rgba(45,110,168,0.10)" : "transparent",
        color: hover ? "var(--brand-blue)" : "#0F2340",
        textDecoration: "none",
        transition: "background 180ms ease-out, color 180ms ease-out",
        outline: "none",
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
      <CnTooltip text="Client Portal · 客户登录" show={hover} />
    </a>
  );
}

function ContactBtn() {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={CONTACT_HREF}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      aria-label="Contact · 联系我们"
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: "8px",
        padding: "10px 18px",
        borderRadius: "999px",
        background: hover ? "var(--brand-blue)" : "#0F2340",
        color: "#fff",
        fontFamily: "Sora, sans-serif",
        fontWeight: 600,
        fontSize: "14px",
        letterSpacing: "0.01em",
        textDecoration: "none",
        boxShadow: "0 1px 2px rgba(15,35,64,0.08), 0 6px 16px rgba(15,35,64,0.10)",
        transition: "background 200ms ease-out",
        outline: "none",
        whiteSpace: "nowrap",
      }}
    >
      <span>Contact</span>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </svg>
      <CnTooltip text="联系我们" show={hover} />
    </a>
  );
}

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const closeDrawer = () => setOpen(false);

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 w-full"
      style={{
        background: "#FFFFFF",
        borderBottom: scrolled ? "1px solid rgba(15,35,64,0.08)" : "1px solid rgba(15,35,64,0.04)",
        boxShadow: scrolled ? "0 1px 3px rgba(15,35,64,0.04)" : "none",
        transition: "border-color 200ms ease-out, box-shadow 200ms ease-out",
      }}
    >
      <div className="container flex items-center justify-between" style={{ height: "76px" }}>
        {/* Brand */}
        <a
          href="#top"
          className="flex items-center"
          style={{ minWidth: 0, gap: "12px", textDecoration: "none" }}
        >
          <img
            src="/manus-storage/logo_clean_934597e8.png"
            alt=""
            width={40}
            height={40}
            style={{
              borderRadius: "10px",
              boxShadow: "0 0 0 1px rgba(15,35,64,0.08), 0 2px 6px rgba(15,35,64,0.06)",
            }}
          />
          <div
            style={{
              fontFamily: "Sora, sans-serif",
              display: "inline-flex",
              alignItems: "baseline",
              gap: "8px",
            }}
          >
            <span
              style={{
                fontWeight: 700,
                color: "#0F2340",
                letterSpacing: "0.04em",
                whiteSpace: "nowrap",
                fontSize: "20px",
              }}
            >
              FIVE ORANGES
            </span>
            <span
              aria-hidden
              style={{
                width: "1px",
                height: "14px",
                background: "rgba(15,35,64,0.18)",
                display: "inline-block",
                alignSelf: "center",
              }}
            />
            <span
              style={{
                color: "var(--brand-blue)",
                letterSpacing: "0.14em",
                whiteSpace: "nowrap",
                fontWeight: 600,
                fontSize: "20px",
              }}
            >
              运帷 AI
            </span>
          </div>
        </a>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center" style={{ gap: "24px" }}>
          {NAV_ITEMS.map((item) => (
            <NavCapsule key={item.en} item={item} />
          ))}
        </nav>

        {/* Right cluster */}
        <div className="flex items-center" style={{ gap: "4px" }}>
          <span className="hidden lg:inline-flex">
            <DemoBtn />
          </span>
          <span className="hidden lg:inline-flex">
            <PortalBtn />
          </span>
          <span
            aria-hidden
            className="hidden lg:inline-block"
            style={{
              width: "1px",
              height: "20px",
              background: "rgba(15,35,64,0.10)",
              margin: "0 4px",
            }}
          />
          <span className="hidden lg:inline-flex" style={{ marginLeft: "6px" }}>
            <ContactBtn />
          </span>

          <button
            className="lg:hidden"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            style={{
              width: "44px",
              height: "44px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "10px",
              transition: "background 150ms ease-out, transform 100ms ease-out",
            }}
          >
            {open ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0F2340" strokeWidth="2">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0F2340" strokeWidth="2">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div
          className="drawer-panel lg:hidden"
          style={{
            background: "#fff",
            borderTop: "1px solid #E2E8F0",
            boxShadow: "0 12px 30px rgba(15,35,64,0.08)",
          }}
        >
          <div
            className="container"
            style={{
              paddingTop: "20px",
              paddingBottom: "28px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}
          >
            {NAV_ITEMS.map((item) => (
              <a
                key={item.en}
                href={item.href}
                onClick={closeDrawer}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 20px",
                  borderRadius: "10px",
                  color: "#0F2340",
                  fontFamily: "Sora, sans-serif",
                  fontWeight: 600,
                  fontSize: "17px",
                  textDecoration: "none",
                  transition: "background 150ms ease-out",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#F1F5F9")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span>{item.cn}</span>
                <span style={{ fontSize: "12px", letterSpacing: "0.1em", color: "#94A3B8" }}>
                  {item.en}
                </span>
              </a>
            ))}

            <div style={{ height: "1px", background: "#E2E8F0", margin: "12px 4px" }} />

            <a
              href={DEMO_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={closeDrawer}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 20px",
                borderRadius: "10px",
                border: "1px solid rgba(15,35,64,0.14)",
                color: "#0F2340",
                fontFamily: "Sora, sans-serif",
                fontWeight: 500,
                fontSize: "15px",
                textDecoration: "none",
                marginTop: "4px",
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
                <LiveDot />
                Demo · 演示
              </span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>

            <a
              href={PORTAL_URL}
              target="_blank"
              rel="noopener noreferrer"
              onClick={closeDrawer}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "14px 20px",
                borderRadius: "10px",
                border: "1px solid rgba(45,110,168,0.45)",
                color: "var(--brand-blue)",
                fontFamily: "Sora, sans-serif",
                fontWeight: 600,
                fontSize: "15px",
                textDecoration: "none",
                marginTop: "4px",
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                Client Portal · 客户登录
              </span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M7 17L17 7M7 7h10v10" />
              </svg>
            </a>

            <a
              href={CONTACT_HREF}
              onClick={closeDrawer}
              style={{
                marginTop: "4px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "14px 20px",
                borderRadius: "10px",
                background: "#0F2340",
                color: "#fff",
                fontFamily: "Sora, sans-serif",
                fontWeight: 600,
                fontSize: "15px",
                textDecoration: "none",
              }}
            >
              Contact · 联系我们
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
