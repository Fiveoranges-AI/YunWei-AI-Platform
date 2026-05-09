type Tone = "warn" | "ai" | undefined;

export function MiniStat({ label, value, tone }: { label: string; value: string | number; tone?: Tone }) {
  const fg = tone === "warn" ? "var(--warn-700)" : tone === "ai" ? "var(--ai-700)" : "var(--ink-900)";
  return (
    <div style={{ flex: 1, textAlign: "left" }}>
      <div className="num" style={{ fontSize: 15, fontWeight: 700, color: fg, lineHeight: 1.2 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>{label}</div>
    </div>
  );
}
