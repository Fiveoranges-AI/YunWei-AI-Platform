/* =============================================================
   Philosophy — AI doesn't replace operators, it frees them to think (v1.3)
   Dark navy section with executive silhouette + data wall scene.
   ============================================================= */

function PhilosophyScene() {
  return (
    <svg
      viewBox="0 0 800 500"
      preserveAspectRatio="xMidYMid slice"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      aria-hidden
    >
      <defs>
        <linearGradient id="philScene" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="#0F2340" />
          <stop offset="100%" stopColor="#0A1A33" />
        </linearGradient>
        <linearGradient id="philWall" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(96,165,250,0.10)" />
          <stop offset="100%" stopColor="rgba(96,165,250,0.02)" />
        </linearGradient>
        <radialGradient id="philVignette" cx="0.3" cy="0.5" r="0.9">
          <stop offset="0%" stopColor="rgba(15,35,64,0)" />
          <stop offset="100%" stopColor="rgba(10,26,51,0.55)" />
        </radialGradient>
      </defs>
      <rect width="800" height="500" fill="url(#philScene)" />

      {/* Floor line */}
      <line x1="0" y1="380" x2="800" y2="380" stroke="rgba(96,165,250,0.20)" strokeWidth="1" />

      {/* Data wall */}
      <rect
        x="440"
        y="80"
        width="320"
        height="280"
        rx="6"
        fill="url(#philWall)"
        stroke="rgba(96,165,250,0.30)"
        strokeWidth="1"
      />

      {/* Wall: chart 1 — yield */}
      <g opacity="0.55">
        <rect x="460" y="100" width="130" height="80" rx="4" fill="none" stroke="rgba(96,165,250,0.45)" />
        <polyline
          points="465,165 490,150 515,158 540,135 565,142 585,120"
          fill="none"
          stroke="#60A5FA"
          strokeWidth="1.6"
        />
        <text x="465" y="115" fill="rgba(255,255,255,0.45)" fontSize="9" fontFamily="Sora,sans-serif" letterSpacing="0.14em">
          YIELD · 良率
        </text>
      </g>

      {/* Wall: chart 2 — throughput */}
      <g opacity="0.55">
        <rect x="610" y="100" width="130" height="80" rx="4" fill="none" stroke="rgba(96,165,250,0.45)" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <rect
            key={i}
            x={620 + i * 18}
            y={170 - (i % 3) * 14 - 8}
            width="12"
            height={(i % 3) * 14 + 12}
            fill="rgba(96,165,250,0.55)"
          />
        ))}
        <text x="615" y="115" fill="rgba(255,255,255,0.45)" fontSize="9" fontFamily="Sora,sans-serif" letterSpacing="0.14em">
          THROUGHPUT · 节拍
        </text>
      </g>

      {/* Wall: heat grid */}
      <g opacity="0.55">
        <rect x="460" y="200" width="130" height="80" rx="4" fill="none" stroke="rgba(96,165,250,0.45)" />
        {Array.from({ length: 6 }).flatMap((_, r) =>
          Array.from({ length: 10 }).map((_, c) => {
            const v = (r * 10 + c * 7) % 100;
            return (
              <rect
                key={`${r}-${c}`}
                x={465 + c * 12}
                y={210 + r * 10}
                width="10"
                height="8"
                fill={`rgba(96,165,250,${0.15 + (v / 100) * 0.55})`}
              />
            );
          })
        )}
        <text x="465" y="296" fill="rgba(255,255,255,0.45)" fontSize="9" fontFamily="Sora,sans-serif" letterSpacing="0.14em">
          ANOMALY MAP · 异常
        </text>
      </g>

      {/* Wall: KPI tile */}
      <g opacity="0.7">
        <rect x="610" y="200" width="130" height="80" rx="4" fill="rgba(45,110,168,0.18)" stroke="rgba(96,165,250,0.45)" />
        <text x="625" y="232" fill="#fff" fontSize="22" fontWeight="700" fontFamily="Sora,sans-serif">
          +32%
        </text>
        <text x="625" y="252" fill="rgba(255,255,255,0.55)" fontSize="9" fontFamily="Sora,sans-serif" letterSpacing="0.14em">
          PRODUCTIVITY
        </text>
        <text x="625" y="266" fill="rgba(96,165,250,0.85)" fontSize="9" fontFamily="Sora,sans-serif">
          产能 · 同比
        </text>
      </g>

      {/* Wall: ticker */}
      <g opacity="0.5">
        <rect x="460" y="300" width="280" height="50" rx="4" fill="none" stroke="rgba(96,165,250,0.30)" />
        <polyline
          points="470,330 500,322 530,328 560,315 590,320 620,308 650,314 680,302 710,310 730,300"
          fill="none"
          stroke="#60A5FA"
          strokeWidth="1.6"
        />
        <circle cx="730" cy="300" r="3" fill="#60A5FA" />
      </g>

      {/* Executive silhouette */}
      <g>
        <path
          d="M 130 380 Q 130 280 175 250 L 200 245 Q 215 240 230 245 L 255 250 Q 300 280 300 380 Z"
          fill="#13294E"
        />
        <path
          d="M 175 250 Q 215 230 255 250 L 245 270 Q 215 252 185 270 Z"
          fill="rgba(96,165,250,0.18)"
        />
        <ellipse cx="215" cy="210" rx="32" ry="36" fill="#1B2F50" />
        <ellipse cx="215" cy="210" rx="32" ry="36" fill="rgba(96,165,250,0.10)" />
        <g>
          <rect
            x="262"
            y="300"
            width="100"
            height="68"
            rx="6"
            transform="rotate(-12 312 334)"
            fill="#1F3964"
            stroke="rgba(96,165,250,0.55)"
            strokeWidth="1.5"
          />
          <rect
            x="270"
            y="308"
            width="84"
            height="52"
            rx="3"
            transform="rotate(-12 312 334)"
            fill="rgba(96,165,250,0.18)"
          />
          <g transform="rotate(-12 312 334)" opacity="0.85">
            <line x1="276" y1="318" x2="346" y2="318" stroke="#60A5FA" strokeWidth="1.4" />
            <line x1="276" y1="328" x2="334" y2="328" stroke="rgba(96,165,250,0.6)" strokeWidth="1.2" />
            <polyline
              points="276,352 290,344 304,350 318,338 332,346 346,334"
              fill="none"
              stroke="#60A5FA"
              strokeWidth="1.4"
            />
            <circle cx="346" cy="334" r="2.5" fill="#60A5FA" />
          </g>
        </g>
        <path
          d="M 255 280 Q 285 295 305 320"
          stroke="#1B2F50"
          strokeWidth="14"
          fill="none"
          strokeLinecap="round"
        />
      </g>

      {/* Connection lines — agent ↔ wall */}
      <g opacity="0.35">
        <line x1="320" y1="320" x2="460" y2="240" stroke="#60A5FA" strokeWidth="1" strokeDasharray="3 5" />
        <line x1="320" y1="330" x2="460" y2="280" stroke="#60A5FA" strokeWidth="1" strokeDasharray="3 5" />
        <line x1="320" y1="340" x2="460" y2="320" stroke="#60A5FA" strokeWidth="1" strokeDasharray="3 5" />
      </g>

      {/* Vignette */}
      <rect width="800" height="500" fill="url(#philVignette)" pointerEvents="none" />
    </svg>
  );
}

export default function PhilosophySection() {
  return (
    <section
      id="about"
      style={{
        padding: "8rem 0",
        background: "#0F2340",
        color: "#fff",
        position: "relative",
        overflow: "hidden",
        minHeight: "560px",
      }}
    >
      <div style={{ position: "absolute", inset: 0, opacity: 0.85 }}>
        <PhilosophyScene />
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(15,35,64,0.92) 0%, rgba(15,35,64,0.78) 36%, rgba(15,35,64,0.35) 60%, rgba(15,35,64,0.10) 100%)",
        }}
      />

      <div className="container relative z-10">
        <div style={{ maxWidth: "640px" }}>
          <span className="section-label">
            <span className="slash-accent" style={{ width: "20px", height: "2px", background: "#60A5FA" }} />
            <span style={{ color: "#60A5FA" }}>我们的理念 · OUR PHILOSOPHY</span>
          </span>
          <h2
            style={{
              marginTop: "1.25rem",
              fontSize: "clamp(2.1rem, 4vw, 3rem)",
              lineHeight: 1.2,
              fontWeight: 700,
              color: "#fff",
              letterSpacing: "-0.01em",
              fontFamily: "Sora, sans-serif",
            }}
          >
            AI doesn't replace operators.
            <br />
            <span style={{ color: "#60A5FA" }}>It frees them to think.</span>
          </h2>

          <div style={{ marginTop: "1.5rem", maxWidth: "560px" }}>
            <p style={{ color: "#CBD5E1", fontSize: "1rem", lineHeight: 1.75 }}>
              我们不相信花哨的演示，也不相信一上线就崩的「Demo 级」AI。
              我们相信能在工厂周一早晨活下来的智能体——靠每天省下真实的工时，赢得自己的位置。
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
