import type { CSSProperties, ReactNode } from "react";
import { I } from "../icons";

type Props = {
  children: ReactNode;
  style?: CSSProperties;
};

export function AISummary({ children, style = {} }: Props) {
  return (
    <div className="ai-surface" style={{ padding: 14, ...style }}>
      <svg
        className="sparkle"
        style={{ position: "absolute", top: 8, right: 12, opacity: 0.5, pointerEvents: "none" }}
        width="44"
        height="44"
        viewBox="0 0 44 44"
        fill="none"
      >
        <path d="M22 4l3 8 8 3-8 3-3 8-3-8-8-3 8-3 3-8z" fill="#c8d2f1" opacity="0.7" />
        <path d="M34 22l1.5 4 4 1.5-4 1.5L34 33l-1.5-4-4-1.5 4-1.5L34 22z" fill="#c8d2f1" opacity="0.5" />
      </svg>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 8,
          color: "var(--ai-700)",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          position: "relative",
        }}
      >
        {I.spark(14)} AI 摘要
      </div>
      <div className="body" style={{ color: "var(--ink-800)", position: "relative" }}>
        {children}
      </div>
    </div>
  );
}
