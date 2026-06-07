/* =============================================================
   Shared UI primitives for the /worldcup microsite.
   Reuses the main site's typography (Sora/Manrope), `.container`,
   and responsive system, but with a distinct green/gold identity
   so the guide reads as a standalone community site.
   ============================================================= */

import type { CSSProperties, ReactNode } from "react";
import { Link } from "wouter";
import { WC } from "./config";

/* ---------- Section wrapper ---------- */
export function Section({
  children,
  bg,
  pad = "6rem",
  id,
  style,
}: {
  children: ReactNode;
  bg?: string;
  pad?: string;
  id?: string;
  style?: CSSProperties;
}) {
  return (
    <section id={id} style={{ padding: `${pad} 0`, background: bg ?? WC.white, ...style }}>
      <div className="container">{children}</div>
    </section>
  );
}

/* ---------- Eyebrow label (green pill) ---------- */
export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.5rem",
        fontFamily: "Sora, sans-serif",
        fontSize: "0.7rem",
        fontWeight: 600,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color: WC.green,
        background: WC.greenPale,
        border: `1px solid rgba(11,122,75,0.22)`,
        padding: "0.35rem 0.9rem",
        borderRadius: "2rem",
      }}
    >
      <span
        aria-hidden
        style={{ width: "16px", height: "2px", background: WC.green, transform: "skewX(-20deg)", borderRadius: "2px" }}
      />
      {children}
    </span>
  );
}

/* ---------- Standard sub-page header ---------- */
export function PageHero({
  kicker,
  titleCn,
  titleEn,
  intro,
  children,
}: {
  kicker: string;
  titleCn: string;
  titleEn: string;
  intro?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section
      style={{
        background: `linear-gradient(180deg, ${WC.greenTint} 0%, ${WC.white} 100%)`,
        borderBottom: `1px solid ${WC.line}`,
        padding: "3.25rem 0 3rem",
      }}
    >
      <div className="container">
        <SectionLabel>{kicker}</SectionLabel>
        <h1
          style={{
            margin: "1rem 0 0",
            fontFamily: "Sora, sans-serif",
            fontWeight: 800,
            fontSize: "clamp(2rem, 4.4vw, 3rem)",
            lineHeight: 1.12,
            letterSpacing: "-0.01em",
            color: WC.ink,
            maxWidth: "20ch",
          }}
        >
          {titleCn}
        </h1>
        <div
          style={{
            marginTop: "0.5rem",
            fontFamily: "Sora, sans-serif",
            fontWeight: 600,
            fontSize: "1rem",
            letterSpacing: "0.04em",
            color: WC.green,
          }}
        >
          {titleEn}
        </div>
        {intro && (
          <p style={{ marginTop: "1.25rem", maxWidth: "62ch", fontSize: "1.0625rem", lineHeight: 1.7, color: WC.inkSoft }}>
            {intro}
          </p>
        )}
        {children}
      </div>
    </section>
  );
}

/* ---------- Generic card ---------- */
export function Card({
  children,
  style,
  className = "",
}: {
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <div
      className={`wc-card ${className}`.trim()}
      style={{
        background: WC.white,
        border: `1px solid ${WC.lineStrong}`,
        borderRadius: "0.9rem",
        padding: "1.75rem",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/* ---------- Buttons (links) ---------- */
type BtnVariant = "primary" | "gold" | "ghost";
const btnBase: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.5rem",
  fontFamily: "Sora, sans-serif",
  fontWeight: 600,
  fontSize: "0.95rem",
  letterSpacing: "0.01em",
  padding: "0.8rem 1.4rem",
  borderRadius: "0.7rem",
  textDecoration: "none",
  cursor: "pointer",
  border: "1px solid transparent",
  whiteSpace: "nowrap",
};
function variantStyle(v: BtnVariant): CSSProperties {
  if (v === "primary") return { background: WC.green, color: "#fff", boxShadow: "0 6px 16px rgba(11,122,75,0.22)" };
  if (v === "gold") return { background: WC.gold, color: "#fff", boxShadow: "0 6px 16px rgba(217,138,31,0.22)" };
  return { background: "#fff", color: WC.ink, border: `1.5px solid ${WC.lineStrong}` };
}

export function LinkButton({
  href,
  children,
  variant = "primary",
  external = false,
  style,
}: {
  href: string;
  children: ReactNode;
  variant?: BtnVariant;
  external?: boolean;
  style?: CSSProperties;
}) {
  const cls = `wc-cta wc-cta-${variant}`;
  const merged = { ...btnBase, ...variantStyle(variant), ...style };
  if (external) {
    return (
      <a className={cls} href={href} target="_blank" rel="noopener noreferrer" style={merged}>
        {children}
      </a>
    );
  }
  return (
    <Link className={cls} href={href} style={merged}>
      {children}
    </Link>
  );
}

/* ---------- Callout / note ---------- */
export function InfoNote({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "neutral";
  title?: ReactNode;
  children: ReactNode;
}) {
  const map = {
    info: { bg: WC.greenPale, bar: WC.green, text: WC.greenDark },
    warn: { bg: WC.goldPale, bar: WC.gold, text: "#8A5A12" },
    neutral: { bg: "#F4F6F8", bar: WC.muted, text: WC.inkSoft },
  } as const;
  const c = map[tone];
  return (
    <div
      style={{
        background: c.bg,
        borderLeft: `4px solid ${c.bar}`,
        borderRadius: "0.5rem",
        padding: "1rem 1.15rem",
        fontSize: "0.95rem",
        lineHeight: 1.65,
        color: WC.inkSoft,
      }}
    >
      {title && (
        <div style={{ fontFamily: "Sora, sans-serif", fontWeight: 700, color: c.text, marginBottom: "0.35rem" }}>
          {title}
        </div>
      )}
      {children}
    </div>
  );
}

/* ---------- Stat block ---------- */
export function Stat({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div>
      <div
        style={{
          fontFamily: "Sora, sans-serif",
          fontWeight: 800,
          fontSize: "clamp(1.8rem, 3.5vw, 2.4rem)",
          color: WC.green,
          lineHeight: 1,
          letterSpacing: "-0.01em",
        }}
      >
        {value}
      </div>
      <div style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: WC.muted, fontWeight: 500 }}>{label}</div>
    </div>
  );
}

/* ---------- Section heading (CN + EN) ---------- */
export function Heading({ cn, en }: { cn: string; en?: string }) {
  return (
    <div style={{ marginBottom: "2rem" }}>
      <h2
        style={{
          fontFamily: "Sora, sans-serif",
          fontWeight: 700,
          fontSize: "clamp(1.6rem, 3vw, 2.1rem)",
          lineHeight: 1.2,
          letterSpacing: "-0.01em",
          color: WC.ink,
        }}
      >
        {cn}
      </h2>
      {en && (
        <div style={{ marginTop: "0.35rem", fontFamily: "Sora, sans-serif", fontWeight: 500, color: WC.green, letterSpacing: "0.03em" }}>
          {en}
        </div>
      )}
    </div>
  );
}

/* ---------- Inline "unofficial guide" disclaimer chip ---------- */
export function UnofficialChip() {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        fontSize: "0.78rem",
        fontWeight: 600,
        color: WC.muted,
        background: "#fff",
        border: `1px solid ${WC.lineStrong}`,
        borderRadius: "2rem",
        padding: "0.3rem 0.8rem",
      }}
    >
      <span aria-hidden style={{ width: "6px", height: "6px", borderRadius: "999px", background: WC.gold }} />
      非官方独立指南 · Independent guide
    </span>
  );
}

/* ---------- Soccer-ball mark (microsite logo glyph) ---------- */
export function BallMark({ size = 30, color = WC.green }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <circle cx="16" cy="16" r="14" fill={color} />
      <path
        d="M16 7.5l4.2 3.05-1.6 4.95h-5.2l-1.6-4.95L16 7.5z"
        fill="#fff"
      />
      <path
        d="M16 7.5V4.2M20.2 10.55l3.0-1.0M18.6 15.5l3.1 2.2M13.4 15.5l-3.1 2.2M11.8 10.55l-3.0-1.0"
        stroke="#fff"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}
