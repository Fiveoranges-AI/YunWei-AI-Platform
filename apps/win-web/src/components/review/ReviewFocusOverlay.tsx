// Slice ② — progressive 逐项补全 overlay.
//
// "AI 每次只问一个最关键的问题" — instead of a long form, walk the
// attention queue (missing-required / low-confidence / invalid) one cell
// at a time. Each step shows why AI flagged it (the lightweight 让 AI 澄清),
// the source excerpt, and a single type-aware input (reused ReviewCellEditor).
// Edits autosave through the same onCellPatch path as the main wizard.

import { useMemo, useState } from "react";
import { I } from "../../icons";
import {
  REASON_LABEL,
  clarifyText,
  findCell,
  type AttentionItem,
} from "../../lib/reviewProgress";
import type { ReviewCellPatch, ReviewDraft } from "../../data/types";
import { ReviewCellEditor } from "./ReviewCellEditor";

type Props = {
  draft: ReviewDraft;
  attention: AttentionItem[];
  readOnly: boolean;
  onCellPatch: (patch: ReviewCellPatch) => void;
  onClose: () => void;
};

const REASON_PILL: Record<string, string> = {
  missing_required: "pill-risk",
  invalid: "pill-risk",
  low_confidence: "pill-warn",
};

export function ReviewFocusOverlay({
  draft,
  attention,
  readOnly,
  onCellPatch,
  onClose,
}: Props) {
  // Snapshot the queue once so resolving an item doesn't reshuffle under
  // the cursor; the cell itself is always read live from the draft.
  const [queue] = useState<AttentionItem[]>(() => attention);
  const [cursor, setCursor] = useState(0);

  const total = queue.length;
  const item = cursor < total ? queue[cursor] : null;
  const cell = useMemo(() => (item ? findCell(draft, item) : null), [draft, item]);

  function advance() {
    setCursor((c) => Math.min(c + 1, total));
  }
  function back() {
    setCursor((c) => Math.max(c - 1, 0));
  }

  // Accept the current value as human-reviewed: stamp `edited` so it leaves
  // the attention set even when the user didn't change the AI value.
  function acceptAndNext() {
    if (cell && !readOnly && item) {
      const filled = cell.display_value != null && String(cell.display_value).trim() !== "";
      if (filled && cell.status !== "edited") {
        onCellPatch({
          table_name: item.tableName,
          client_row_id: item.rowId,
          field_name: item.field,
          value: cell.value,
          status: "edited",
        });
      }
    }
    advance();
  }

  const excerpt =
    cell?.evidence?.excerpt ?? cell?.source_refs?.find((r) => r.excerpt)?.excerpt ?? null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(11,18,32,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 540,
          background: "var(--surface)",
          borderRadius: 16,
          boxShadow: "var(--shadow-pop)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "92%",
          overflow: "hidden",
        }}
      >
        {/* Header + progress */}
        <div style={{ padding: "16px 18px 12px", borderBottom: "1px solid var(--ink-100)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--ai-600)", display: "flex" }}>{I.spark(16)}</span>
            <span style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              智能补全
            </span>
            <span style={{ fontSize: 12, color: "var(--ink-400)" }}>
              AI 每次只问一个关键项
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭"
              style={{
                marginLeft: "auto",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--ink-400)",
                display: "flex",
                padding: 2,
              }}
            >
              {I.close(18)}
            </button>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
            <div style={{ flex: 1, height: 5, borderRadius: 99, background: "var(--ink-50)", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${total === 0 ? 100 : (Math.min(cursor, total) / total) * 100}%`,
                  background: "var(--ai-500)",
                  borderRadius: 99,
                  transition: "width 200ms ease",
                }}
              />
            </div>
            <span className="num" style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 600 }}>
              {Math.min(cursor + (item ? 1 : 0), total)} / {total}
            </span>
          </div>
        </div>

        {/* Body */}
        {item && cell ? (
          <div style={{ padding: 18, overflowY: "auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 12.5, color: "var(--ink-500)", fontWeight: 600 }}>
                {item.tableLabel}
                {item.isArray ? ` · 第 ${item.rowIndex + 1} 条` : ""}
              </span>
              <span className={`pill ${REASON_PILL[item.reason]}`} style={{ fontSize: 10.5, padding: "2px 7px" }}>
                {REASON_LABEL[item.reason]}
              </span>
            </div>

            {/* 让 AI 澄清 — why this is flagged + the source evidence */}
            <div
              style={{
                background: "var(--ai-50)",
                border: "1px solid var(--ai-100)",
                borderRadius: 10,
                padding: "10px 12px",
                marginBottom: 14,
              }}
            >
              <div style={{ fontSize: 13, color: "var(--ai-900)", lineHeight: 1.55 }}>
                {clarifyText(cell, item.reason)}
              </div>
              {excerpt ? (
                <div
                  style={{
                    marginTop: 8,
                    fontSize: 12,
                    color: "var(--ink-600)",
                    background: "var(--surface)",
                    border: "1px solid var(--ink-100)",
                    borderRadius: 8,
                    padding: "7px 9px",
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ color: "var(--ink-400)", marginRight: 6 }}>AI 依据</span>
                  “{excerpt}”
                </div>
              ) : null}
            </div>

            <ReviewCellEditor
              cell={cell}
              rowId={item.rowId}
              tableName={item.tableName}
              showLabel
              disabled={readOnly}
              readOnly={readOnly}
              onChange={({ value, status }) =>
                onCellPatch({
                  table_name: item.tableName,
                  client_row_id: item.rowId,
                  field_name: item.field,
                  value,
                  status,
                })
              }
            />
          </div>
        ) : (
          <div style={{ padding: "36px 24px", textAlign: "center" }}>
            <div style={{ color: "var(--ok-500)", display: "flex", justifyContent: "center", marginBottom: 10 }}>
              {I.check(30)}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)" }}>
              都确认完了
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-500)", marginTop: 6 }}>
              关键项已逐项过完一遍，可以回去确认入库了。
            </div>
          </div>
        )}

        {/* Footer nav */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--ink-100)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {item ? (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={back}
                disabled={cursor === 0}
                style={{ height: 38, opacity: cursor === 0 ? 0.5 : 1 }}
              >
                上一项
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={advance}
                style={{ height: 38 }}
              >
                跳过
              </button>
              <div style={{ flex: 1 }} />
              <button
                type="button"
                className="btn btn-primary"
                onClick={acceptAndNext}
                disabled={readOnly}
                style={{ height: 38 }}
              >
                {cursor + 1 >= total ? "确认并完成" : "确认并继续"}
              </button>
            </>
          ) : (
            <>
              <div style={{ flex: 1 }} />
              <button type="button" className="btn btn-primary" onClick={onClose} style={{ height: 38 }}>
                完成
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
