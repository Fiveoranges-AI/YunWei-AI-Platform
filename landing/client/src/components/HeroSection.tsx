/* =============================================================
   Hero — Five Oranges AI · 运帷AI (v1.3)
   "Beyond the scope. 进无止境" — left copy, right layered visual
   stage representing the 5 themes (Accuracy / Efficiency /
   Productivity / Cost / Multi-agent).
   ============================================================= */

const DEMO_URL = "/demo.html";
const CONTACT_HREF = "mailto:contact@fiveoranges.ai";

function HeroVisual() {
  return (
    <div
      aria-hidden
      style={{
        position: "relative",
        width: "100%",
        aspectRatio: "5 / 4",
        borderRadius: "20px",
        overflow: "hidden",
        background:
          "linear-gradient(160deg, #EEF4FB 0%, #DCE9F6 60%, #C6DAEE 100%)",
        boxShadow:
          "0 1px 2px rgba(15,35,64,0.06), 0 24px 60px rgba(15,35,64,0.14), inset 0 0 0 1px rgba(45,110,168,0.10)",
      }}
    >
      {/* Soft grid pattern */}
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity: 0.55 }}>
        <defs>
          <pattern id="heroGrid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path
              d="M 32 0 L 0 0 0 32"
              fill="none"
              stroke="rgba(45,110,168,0.20)"
              strokeWidth="1"
              shapeRendering="crispEdges"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#heroGrid)" />
      </svg>

      {/* Watermark V */}
      <div
        style={{
          position: "absolute",
          right: "-30px",
          bottom: "-50px",
          fontFamily: "Sora, sans-serif",
          fontSize: "380px",
          fontWeight: 800,
          color: "rgba(45,110,168,0.08)",
          lineHeight: 1,
          letterSpacing: "-0.05em",
          userSelect: "none",
          pointerEvents: "none",
        }}
      >
        V
      </div>

      {/* Dashboard panel — top left */}
      <div
        style={{
          position: "absolute",
          top: "5%",
          left: "4%",
          width: "50%",
          padding: "20px",
          borderRadius: "14px",
          background: "#fff",
          boxShadow: "0 1px 0 rgba(15,35,64,0.04), 0 18px 38px rgba(15,35,64,0.14)",
          border: "1px solid rgba(15,35,64,0.08)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "999px",
                background: "#10B981",
                flexShrink: 0,
                boxShadow: "0 0 0 3px rgba(16,185,129,0.18)",
              }}
            />
            <span
              style={{
                fontFamily: "Sora, sans-serif",
                fontSize: "14px",
                fontWeight: 700,
                color: "#0F2340",
                letterSpacing: "0.01em",
              }}
            >
              智能驾驶舱
            </span>
          </div>
          <span
            style={{
              fontFamily: "Sora, sans-serif",
              fontSize: "11px",
              color: "#10B981",
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              fontWeight: 700,
            }}
          >
            Live
          </span>
        </div>
        <svg width="100%" height="96" viewBox="0 0 240 96" preserveAspectRatio="none" style={{ display: "block" }}>
          <defs>
            <linearGradient id="heroLineFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#2D6EA8" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#2D6EA8" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M 0 70 L 30 60 L 60 64 L 90 42 L 120 50 L 150 30 L 180 36 L 210 18 L 240 24 L 240 96 L 0 96 Z"
            fill="url(#heroLineFill)"
          />
          <path
            d="M 0 70 L 30 60 L 60 64 L 90 42 L 120 50 L 150 30 L 180 36 L 210 18 L 240 24"
            fill="none"
            stroke="#2D6EA8"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="210" cy="18" r="4.5" fill="#fff" stroke="#2D6EA8" strokeWidth="2.5" />
        </svg>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: "14px" }}>
          <div>
            <div style={{ fontFamily: "Sora, sans-serif", fontSize: "20px", fontWeight: 700, color: "#0F2340", letterSpacing: "-0.01em" }}>
              +32%
            </div>
            <div style={{ fontSize: "11px", color: "#64748B", letterSpacing: "0.06em", marginTop: "2px", fontFamily: "Sora, sans-serif" }}>
              产能
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "Sora, sans-serif", fontSize: "20px", fontWeight: 700, color: "#0F2340", letterSpacing: "-0.01em" }}>
              −18%
            </div>
            <div style={{ fontSize: "11px", color: "#64748B", letterSpacing: "0.06em", marginTop: "2px", fontFamily: "Sora, sans-serif" }}>
              成本
            </div>
          </div>
        </div>
      </div>

      {/* Accuracy card — top right */}
      <div
        style={{
          position: "absolute",
          top: "8%",
          right: "5%",
          width: "36%",
          padding: "20px",
          borderRadius: "14px",
          background: "#0F2340",
          color: "#fff",
          boxShadow: "0 4px 14px rgba(15,35,64,0.20), 0 22px 48px rgba(15,35,64,0.28)",
        }}
      >
        <div
          style={{
            fontFamily: "Sora, sans-serif",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "0.18em",
            color: "#60A5FA",
            textTransform: "uppercase",
            marginBottom: "12px",
          }}
        >
          精准 · ACCURACY
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <svg width="64" height="64" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="26" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="4" />
            <circle
              cx="32"
              cy="32"
              r="26"
              fill="none"
              stroke="#60A5FA"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${0.94 * 2 * Math.PI * 26} ${2 * Math.PI * 26}`}
              transform="rotate(-90 32 32)"
            />
            <text x="32" y="37" textAnchor="middle" fill="#fff" fontSize="15" fontFamily="Sora, sans-serif" fontWeight="700">
              94%
            </text>
          </svg>
          <div>
            <div style={{ fontFamily: "Sora, sans-serif", fontSize: "16px", fontWeight: 700, lineHeight: 1.2 }}>
              检测命中
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "#94A3B8",
                marginTop: "4px",
                fontFamily: "Sora, sans-serif",
                letterSpacing: "0.06em",
              }}
            >
              缺陷识别准确率
            </div>
          </div>
        </div>
      </div>

      {/* Efficiency strip — mid right */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          right: "5%",
          width: "42%",
          padding: "18px 20px",
          borderRadius: "14px",
          background: "#fff",
          boxShadow: "0 1px 0 rgba(15,35,64,0.04), 0 18px 38px rgba(15,35,64,0.14)",
          border: "1px solid rgba(15,35,64,0.08)",
        }}
      >
        <div
          style={{
            fontFamily: "Sora, sans-serif",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "0.18em",
            color: "#2D6EA8",
            textTransform: "uppercase",
            marginBottom: "12px",
          }}
        >
          效率 · EFFICIENCY
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={`pipe-${i}`} style={{ display: "contents" }}>
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "6px",
                  background: i <= 4 ? "var(--brand-blue)" : "#E2E8F0",
                  flexShrink: 0,
                  boxShadow: i <= 4 ? "0 2px 6px rgba(45,110,168,0.25)" : "none",
                }}
              />
              {i < 5 && (
                <div
                  style={{
                    flex: 1,
                    height: "3px",
                    background: i < 4 ? "var(--brand-blue)" : "#E2E8F0",
                    borderRadius: "2px",
                  }}
                />
              )}
            </div>
          ))}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: "12px",
            fontSize: "12px",
            color: "#64748B",
            fontFamily: "Sora, sans-serif",
          }}
        >
          <span style={{ fontWeight: 600 }}>节拍 4 / 5</span>
          <span style={{ color: "#10B981", fontWeight: 700 }}>● 实时同步</span>
        </div>
      </div>

      {/* Multi-agent chip — bottom left */}
      <div
        style={{
          position: "absolute",
          bottom: "5%",
          left: "4%",
          width: "42%",
          padding: "18px 20px",
          borderRadius: "14px",
          background: "#fff",
          boxShadow: "0 1px 0 rgba(15,35,64,0.04), 0 18px 38px rgba(15,35,64,0.14)",
          border: "1px solid rgba(15,35,64,0.08)",
        }}
      >
        <div
          style={{
            fontFamily: "Sora, sans-serif",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "0.18em",
            color: "#2D6EA8",
            textTransform: "uppercase",
            marginBottom: "14px",
          }}
        >
          协同 · MULTI-AGENT
        </div>
        <div style={{ display: "flex", alignItems: "center" }}>
          {[
            { l: "A", c: "#2D6EA8" },
            { l: "B", c: "#0F2340" },
            { l: "C", c: "#60A5FA" },
            { l: "+2", c: "#94A3B8" },
          ].map((a, i) => (
            <div
              key={a.l}
              style={{
                width: "34px",
                height: "34px",
                borderRadius: "999px",
                background: a.c,
                color: "#fff",
                fontFamily: "Sora, sans-serif",
                fontSize: "13px",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginLeft: i === 0 ? 0 : "-8px",
                border: "2.5px solid #fff",
                position: "relative",
                zIndex: 4 - i,
                boxShadow: "0 2px 8px rgba(15,35,64,0.15)",
              }}
            >
              {a.l}
            </div>
          ))}
          <div
            style={{
              marginLeft: "14px",
              fontFamily: "Sora, sans-serif",
              fontSize: "14px",
              color: "#0F2340",
              fontWeight: 700,
            }}
          >
            5 Agents 协作
          </div>
        </div>
      </div>

      {/* CTA pair — bottom-right inset */}
      <div
        style={{
          position: "absolute",
          right: "24px",
          bottom: "24px",
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          justifyContent: "flex-end",
          alignItems: "center",
        }}
      >
        <a
          href={DEMO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="hover-lift"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "12px",
            padding: "14px 22px",
            background: "var(--brand-blue)",
            color: "#fff",
            fontFamily: "Sora, sans-serif",
            fontWeight: 700,
            fontSize: "15px",
            borderRadius: "10px",
            boxShadow: "0 8px 24px rgba(45,110,168,0.32)",
            transition: "transform 200ms ease-out, box-shadow 200ms ease-out",
            whiteSpace: "nowrap",
            textDecoration: "none",
          }}
        >
          <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.15 }}>
            <span>查看演示</span>
            <span style={{ fontSize: "10.5px", letterSpacing: "0.14em", opacity: 0.72, fontWeight: 500, textTransform: "uppercase" }}>
              Live Demo
            </span>
          </span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </a>

        <a
          href={CONTACT_HREF}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "14px 22px",
            color: "var(--brand-blue)",
            fontFamily: "Sora, sans-serif",
            fontWeight: 700,
            fontSize: "15px",
            borderRadius: "10px",
            border: "1px solid rgba(45,110,168,0.55)",
            background: "rgba(255,255,255,0.92)",
            backdropFilter: "blur(4px)",
            transition: "background 200ms ease-out, border-color 200ms ease-out",
            whiteSpace: "nowrap",
            textDecoration: "none",
          }}
        >
          <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-start", lineHeight: 1.15 }}>
            <span>预约咨询</span>
            <span style={{ fontSize: "10.5px", letterSpacing: "0.14em", opacity: 0.7, fontWeight: 500, textTransform: "uppercase" }}>
              Book a Call
            </span>
          </span>
        </a>
      </div>
    </div>
  );
}

export default function HeroSection() {
  return (
    <section
      id="top"
      className="relative overflow-hidden"
      style={{
        background: "linear-gradient(180deg, #FFFFFF 0%, #F8F7F4 100%)",
        paddingTop: "9rem",
        paddingBottom: "5rem",
        borderBottom: "1px solid rgba(15,35,64,0.06)",
      }}
    >
      <div className="container relative z-10">
        <div className="hero-grid">
          {/* Left — copy */}
          <div>
            <h1
              className="fade-up"
              style={{
                marginTop: 0,
                fontFamily: "Sora, sans-serif",
                fontWeight: 700,
                fontSize: "clamp(3rem, 6.4vw, 5.5rem)",
                lineHeight: 1.02,
                letterSpacing: "-0.025em",
                color: "#0F2340",
              }}
            >
              Beyond <span style={{ color: "var(--brand-blue)" }}>the scope.</span>
            </h1>

            <div
              className="fade-up fade-up-delay-1"
              style={{
                marginTop: "0.75rem",
                fontFamily: "Sora, sans-serif",
                fontWeight: 600,
                fontSize: "clamp(1.1rem, 1.6vw, 1.4rem)",
                lineHeight: 1.3,
                letterSpacing: "0.18em",
                color: "var(--brand-blue)",
              }}
            >
              进无止境
            </div>

            <p
              className="fade-up fade-up-delay-2"
              style={{
                marginTop: "1.75rem",
                fontSize: "1.0625rem",
                lineHeight: 1.65,
                color: "#334155",
                maxWidth: "560px",
              }}
            >
              我们帮助制造业、贸易与企业团队，将分散数据与手工流程，转化为
              <strong style={{ color: "#0F2340" }}>真正能跑业务的 AI 智能体</strong>。
            </p>
          </div>

          {/* Right — visual */}
          <div className="fade-up fade-up-delay-2">
            <HeroVisual />
          </div>
        </div>
      </div>
    </section>
  );
}
