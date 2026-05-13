import { I } from "../icons";

type Props = {
  type: string;
  label: string;
  onClick?: () => void;
};

export function EvidenceChip({ type, label, onClick }: Props) {
  const icon = type === "微信" ? I.wechat(13) : type === "语音" ? I.voice(13) : I.doc(13);
  return (
    <button
      onClick={onClick}
      className="pill pill-ink"
      style={{
        background: "var(--surface-3)",
        color: "var(--ink-700)",
        cursor: onClick ? "pointer" : "default",
        border: "1px solid var(--ink-100)",
        padding: "5px 10px",
        fontWeight: 500,
        fontSize: 12,
        lineHeight: 1.2,
        gap: 6,
      }}
    >
      <span style={{ color: "var(--ink-500)" }}>{icon}</span>
      {label}
    </button>
  );
}
