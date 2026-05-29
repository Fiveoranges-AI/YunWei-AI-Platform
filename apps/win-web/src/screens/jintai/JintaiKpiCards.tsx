import { kpis } from "./data";

export function JintaiKpiCards() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        gap: 10,
        marginBottom: 24,
      }}
    >
      {kpis.map((k) => (
        <div
          key={k.label}
          className="card-flat"
          style={{
            padding: "12px 14px",
            borderRadius: 12,
          }}
        >
          <div style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>
            {k.label}
          </div>
          <div
            className="num"
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: "var(--ink-900)",
              marginTop: 4,
              letterSpacing: "-0.01em",
            }}
          >
            {k.value}
            {k.suffix ? (
              <span style={{ fontSize: 14, color: "var(--ink-500)", marginLeft: 2 }}>
                {k.suffix}
              </span>
            ) : null}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "var(--ink-400)",
              marginTop: 4,
              lineHeight: 1.4,
            }}
          >
            {k.hint}
          </div>
        </div>
      ))}
    </div>
  );
}
