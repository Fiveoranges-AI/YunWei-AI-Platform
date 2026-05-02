/* =============================================================
   UseCases — Where AI agents are already earning their keep (v1.3)
   3 industry cards (manufacturing / trading / executive) with
   subtle SVG bg patterns and scene icons.
   ============================================================= */

const USE_CASES = [
  {
    tagCn: "制造业",
    tagEn: "Manufacturing",
    titleCn: "生产简报，自动撰写",
    body: "一个每日早班的 AI 简报智能体，自动汇总 MES、质量日志、班次反馈，把异常浮现在站会之前。",
    kind: "manufacturing" as const,
  },
  {
    tagCn: "贸易",
    tagEn: "Trading",
    titleCn: "守得住毛利的报价引擎",
    body: "一个根据实时成本、合同条款、历史中标率自动起草客户报价的定价智能体。",
    kind: "trading" as const,
  },
  {
    tagCn: "管理",
    tagEn: "Executive",
    titleCn: "CEO 驾驶舱，告别表格",
    body: "一个自然语言驾驶舱，CEO 真正会打开——每个数字都可以一键追溯到源记录。",
    kind: "executive" as const,
  },
];

type SceneKind = "manufacturing" | "trading" | "executive";

function SceneIcon({ kind }: { kind: SceneKind }) {
  const sw = 1.6;
  if (kind === "manufacturing") {
    return (
      <svg width="44" height="44" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="14" cy="14" r="3.5" />
        <path d="M11 17.2 L9 26 M17 17.2 L19 26" />
        <rect x="6" y="26" width="36" height="14" rx="1.5" />
        <path d="M22 22 L34 22 L36 26" />
        <circle cx="34" cy="22" r="2.2" />
        <path d="M11 33 h26 M11 36 h20" opacity="0.6" />
      </svg>
    );
  }
  if (kind === "trading") {
    return (
      <svg width="44" height="44" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <circle cx="24" cy="24" r="16" />
        <path d="M8 24 h32 M24 8 q8 8 8 16 t-8 16 M24 8 q-8 8 -8 16 t8 16" opacity="0.55" />
        <path d="M14 32 L20 28 L28 32 L34 24" />
        <path d="M28 24 L34 24 L34 18" />
      </svg>
    );
  }
  return (
    <svg width="44" height="44" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M6 30 a18 18 0 0 1 36 0" />
      <path d="M24 30 L30 18" />
      <circle cx="24" cy="30" r="2" fill="currentColor" />
      <path d="M14 36 h20" />
      <path d="M11 30 v3 M16 26 v7 M24 24 v9 M32 26 v7 M37 30 v3" opacity="0.4" />
    </svg>
  );
}

function CaseBgPattern({ kind }: { kind: SceneKind }) {
  const baseStyle = {
    position: "absolute" as const,
    inset: 0,
    width: "100%",
    height: "100%",
    opacity: 0.1,
    pointerEvents: "none" as const,
  };

  if (kind === "manufacturing") {
    return (
      <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" style={baseStyle} aria-hidden>
        <defs>
          <linearGradient id="mfgGrad" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#2D6EA8" />
            <stop offset="100%" stopColor="#0F2340" />
          </linearGradient>
        </defs>
        <g stroke="url(#mfgGrad)" strokeWidth="1.2" fill="none">
          {Array.from({ length: 8 }).map((_, i) => (
            <line key={i} x1="0" y1={40 + i * 30} x2="400" y2={40 + i * 30} strokeDasharray="3 6" />
          ))}
          <circle cx="320" cy="60" r="36" />
          <circle cx="320" cy="60" r="22" />
          <rect x="40" y="200" width="240" height="40" rx="4" />
          <line x1="40" y1="220" x2="280" y2="220" />
        </g>
      </svg>
    );
  }
  if (kind === "trading") {
    return (
      <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" style={baseStyle} aria-hidden>
        <g stroke="#2D6EA8" strokeWidth="1.2" fill="none">
          <circle cx="320" cy="80" r="60" />
          <ellipse cx="320" cy="80" rx="60" ry="22" />
          <ellipse cx="320" cy="80" rx="60" ry="40" />
          <line x1="260" y1="80" x2="380" y2="80" />
          <line x1="320" y1="20" x2="320" y2="140" />
          <path d="M40 240 q60 -40 120 -10 t120 -20" strokeWidth="1.6" />
          <path d="M40 260 q60 -30 120 0 t120 -10" strokeWidth="1.2" opacity="0.6" />
        </g>
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" style={baseStyle} aria-hidden>
      <g stroke="#2D6EA8" strokeWidth="1.2" fill="none">
        <path d="M40 240 q40 -100 80 -60 t80 -80 t80 60 t80 -40" strokeWidth="1.6" />
        <line x1="40" y1="240" x2="360" y2="240" />
        {Array.from({ length: 9 }).map((_, i) => (
          <line key={i} x1={40 + i * 40} y1="240" x2={40 + i * 40} y2="246" />
        ))}
        <rect x="280" y="40" width="100" height="60" rx="4" />
        <line x1="290" y1="56" x2="370" y2="56" />
        <line x1="290" y1="68" x2="350" y2="68" />
        <line x1="290" y1="80" x2="360" y2="80" />
      </g>
    </svg>
  );
}

export default function UseCasesSection() {
  return (
    <section id="use-cases" style={{ padding: "7rem 0" }}>
      <div className="container">
        <div style={{ marginBottom: "3.5rem", maxWidth: "760px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px" }} />
            应用场景 · USE CASES
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
            Where AI agents are already earning their keep.
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
            AI 智能体已经在这些场景中创造价值。
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {USE_CASES.map((u) => (
            <article
              key={u.tagEn}
              className="card-lift"
              style={{
                position: "relative",
                padding: "2rem",
                background: "#FFFFFF",
                border: "1.5px solid rgba(15,35,64,0.14)",
                borderRadius: "0.875rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
                minHeight: "320px",
                overflow: "hidden",
              }}
            >
              <CaseBgPattern kind={u.kind} />

              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  position: "relative",
                  zIndex: 2,
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    gap: "2px",
                    padding: "8px 16px",
                    background: "var(--brand-blue-pale)",
                    border: "1px solid rgba(45,110,168,0.25)",
                    borderRadius: "999px",
                    fontFamily: "Sora, sans-serif",
                  }}
                >
                  <span
                    style={{
                      fontSize: "1rem",
                      fontWeight: 700,
                      color: "var(--brand-blue)",
                      letterSpacing: "0.01em",
                      lineHeight: 1.1,
                    }}
                  >
                    {u.tagCn}
                  </span>
                  <span
                    style={{
                      fontSize: "9.5px",
                      fontWeight: 500,
                      letterSpacing: "0.16em",
                      color: "var(--brand-blue)",
                      opacity: 0.7,
                      textTransform: "uppercase",
                    }}
                  >
                    {u.tagEn}
                  </span>
                </span>

                <div
                  style={{
                    width: "60px",
                    height: "60px",
                    borderRadius: "12px",
                    background: "linear-gradient(135deg, #EEF4FB 0%, #DCE9F6 100%)",
                    border: "1px solid rgba(45,110,168,0.18)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--brand-blue)",
                    flexShrink: 0,
                  }}
                >
                  <SceneIcon kind={u.kind} />
                </div>
              </div>

              <h3
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  color: "#0F2340",
                  lineHeight: 1.3,
                  fontFamily: "Sora, sans-serif",
                  position: "relative",
                  zIndex: 2,
                  marginTop: "0.5rem",
                }}
              >
                {u.titleCn}
              </h3>
              <p
                style={{
                  color: "#334155",
                  fontSize: "0.9375rem",
                  lineHeight: 1.7,
                  position: "relative",
                  zIndex: 2,
                  marginTop: "0.25rem",
                }}
              >
                {u.body}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
