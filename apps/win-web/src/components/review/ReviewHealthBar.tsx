// Slice ② — review data-health bar.
//
// Compact header strip: 本次资料完整度 (a score + progress bar, kept
// separate from confidence) on the left, and a "需要你确认 · N 项" entry
// that opens the progressive 逐项补全 flow on the right. When nothing
// needs attention it reads as 全部就绪.

import { I } from "../../icons";
import type { ReviewProgress } from "../../lib/reviewProgress";

type Props = {
  progress: ReviewProgress;
  readOnly: boolean;
  onStartFocus: () => void;
};

function scoreColor(score: number): string {
  if (score >= 90) return "var(--ok-500)";
  if (score >= 60) return "var(--brand-500)";
  return "var(--warn-500)";
}

export function ReviewHealthBar({ progress, readOnly, onStartFocus }: Props) {
  const { score, filled, total, attention } = progress;
  const count = attention.length;
  const color = scoreColor(score);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        flexWrap: "wrap",
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        borderRadius: 12,
        padding: "10px 14px",
        flexShrink: 0,
      }}
    >
      {/* Completeness */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1, minWidth: 180 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--ink-500)", fontWeight: 600 }}>
            本次资料完整度
          </span>
          <span className="num" style={{ fontSize: 16, fontWeight: 700, color }}>
            {score}%
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
            已填 {filled} / {total} 项
          </span>
        </div>
        <div
          style={{
            height: 6,
            borderRadius: 99,
            background: "var(--ink-50)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${score}%`,
              background: color,
              borderRadius: 99,
              transition: "width 240ms ease",
            }}
          />
        </div>
      </div>

      {/* Attention / focus entry */}
      {count === 0 ? (
        <span
          className="pill pill-ok"
          style={{ gap: 5, flexShrink: 0 }}
        >
          {I.check(13)} 全部就绪
        </span>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <span style={{ fontSize: 12.5, color: "var(--warn-700)", fontWeight: 600 }}>
            需要你确认 · {count} 项
          </span>
          {!readOnly && (
            <button
              type="button"
              onClick={onStartFocus}
              className="btn btn-primary"
              style={{ height: 34, padding: "0 14px", fontSize: 13 }}
            >
              {I.spark(14, "#fff")}
              <span>逐项补全</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
