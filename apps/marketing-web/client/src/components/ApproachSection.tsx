import { useLocale } from "@/i18n/LocaleContext";
import type { Copy } from "@/i18n/catalog";
/* =============================================================
   Approach — Start with one validated business scene.
   ============================================================= */

import type { CSSProperties } from "react";

const STEPS = (c: Copy) => [
  {
    cn: c.businessDiscovery,
    en: "Diagnose",
    desc: c.reviewInventoryOrdersCustomersWorkflows,
  },
  {
    cn: c.aTestablePrototype,
    en: "Validate",
    desc: c.buildAFocusedPrototypeYour,
  },
  {
    cn: c.phasedRollout,
    en: "Scale",
    desc: c.expandIntoCoreWorkflowsOnce,
  },
];

export default function ApproachSection() {
  const { copy: c, locale } = useLocale();
  return (
    <section id="approach" className="bg-section-blue" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ marginBottom: "4.5rem", maxWidth: "760px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            {c.ourApproach}
          </span>
          <h2
            style={{
              marginTop: "1rem",
              fontSize: "clamp(2.1rem, 4vw, 3rem)",
              lineHeight: 1.15,
              fontWeight: 700,
              color: "#0F2340",
              letterSpacing: "-0.01em",
              fontFamily: "Sora, sans-serif",
            }}
          >
              {c.startWithOneWorkflowProve}
            </h2>
          <div
            style={{
              marginTop: "0.75rem",
              fontFamily: "Sora, sans-serif",
              fontWeight: 500,
              fontSize: "1.0625rem",
              color: "#475569",
            }}
          >
            {c.startSmallValidateFastThen}
          </div>
        </div>

        <div className="approach-rail">
          {/* Diagonal connector — desktop only */}
          <svg
            className="approach-line"
            viewBox="0 0 1000 220"
            preserveAspectRatio="none"
            aria-hidden
          >
            <defs>
              <linearGradient id="approachLineGrad" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="#2D6EA8" stopOpacity="0.15" />
                <stop offset="50%" stopColor="#2D6EA8" stopOpacity="0.55" />
                <stop offset="100%" stopColor="#2D6EA8" stopOpacity="0.15" />
              </linearGradient>
            </defs>
            <path
              d="M 60 180 L 960 40"
              stroke="url(#approachLineGrad)"
              strokeWidth="2"
              strokeDasharray="6 8"
              fill="none"
            />
            <polygon points="960,40 950,32 950,48" fill="#2D6EA8" opacity="0.7" />
          </svg>

          <div className="approach-steps">
            {STEPS(c).map((s, i) => (
              <div
                key={s.en}
                className="approach-step"
                style={{ ["--step-i" as string]: i } as CSSProperties}
              >
                <div
                  style={{
                    width: "5.5rem",
                    height: "5.5rem",
                    background: "#fff",
                    border: "2px solid var(--brand-blue)",
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "Sora, sans-serif",
                    fontWeight: 700,
                    fontSize: "1.625rem",
                    color: "var(--brand-blue)",
                    position: "relative",
                    zIndex: 2,
                    marginBottom: "1.25rem",
                    boxShadow:
                      "0 8px 22px rgba(45,110,168,0.18), inset 0 0 0 4px #fff, inset 0 0 0 5px rgba(45,110,168,0.10)",
                  }}
                >
                  0{i + 1}
                </div>

                <div
                  style={{
                    fontSize: "1.375rem",
                    fontWeight: 700,
                    color: "#0F2340",
                    fontFamily: "Sora, sans-serif",
                    lineHeight: 1.2,
                  }}
                >
                  {s.cn}
                </div>
                {locale === "zh-CN" && <div
                  style={{
                    fontSize: "0.8125rem",
                    color: "var(--brand-blue)",
                    letterSpacing: "0.14em",
                    marginTop: "4px",
                    fontFamily: "Sora, sans-serif",
                    fontWeight: 500,
                    textTransform: "uppercase",
                  }}
                >{s.en}</div>}
                <p
                  style={{
                    marginTop: "0.875rem",
                    color: "#475569",
                    fontSize: "0.9375rem",
                    lineHeight: 1.65,
                  }}
                >
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
