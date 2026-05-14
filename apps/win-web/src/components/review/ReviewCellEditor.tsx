// V2 review cell editor — a controlled input for a single ReviewCell.
//
// The parent (ReviewTableWorkspace) owns the patch buffer. This component
// is presentational: render the right control for the cell's data_type,
// surface status (missing/edited/low_confidence/rejected/invalid) via
// border + chips, and pipe edits back through `onChange`.

import { useMemo } from "react";
import { EvidenceChip } from "../EvidenceChip";
import type { ReviewCell, ReviewCellStatus } from "../../data/types";

type Props = {
  cell: ReviewCell;
  rowId: string;
  tableName: string;
  onChange: (patch: { value: unknown; status?: ReviewCellStatus }) => void;
  onReject?: () => void;
  invalidReason?: string | null;
  disabled?: boolean;
};

function borderColor(status: ReviewCellStatus, hasInvalid: boolean): string {
  if (hasInvalid || status === "invalid") return "var(--risk-500)";
  if (status === "low_confidence") return "var(--warn-500)";
  if (status === "edited") return "var(--brand-500)";
  if (status === "missing") return "var(--ink-200)";
  if (status === "rejected") return "var(--ink-100)";
  return "var(--ink-100)";
}

function backgroundColor(status: ReviewCellStatus): string {
  if (status === "missing") return "var(--surface-2)";
  if (status === "rejected") return "var(--surface-3)";
  return "var(--surface)";
}

function toDateInputValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") {
    // Accept ISO datetime, slice to YYYY-MM-DD for <input type="date">.
    return value.slice(0, 10);
  }
  return "";
}

function toDateTimeInputValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") {
    // datetime-local wants "YYYY-MM-DDTHH:MM".
    return value.slice(0, 16);
  }
  return "";
}

function toNumberInputValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  if (typeof value === "string") return value;
  return "";
}

function toTextInputValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function ReviewCellEditor({
  cell,
  onChange,
  onReject,
  invalidReason,
  disabled,
}: Props) {
  const isRejected = cell.status === "rejected";
  const isMissing = cell.status === "missing";
  const isEdited = cell.status === "edited";
  const isLow = cell.status === "low_confidence";
  const isInvalid = cell.status === "invalid" || Boolean(invalidReason);

  const inputStyle = useMemo<React.CSSProperties>(() => {
    return {
      width: "100%",
      padding: "7px 10px",
      fontSize: 13.5,
      border: `1px solid ${borderColor(cell.status, Boolean(invalidReason))}`,
      borderRadius: 8,
      background: backgroundColor(cell.status),
      color: isRejected ? "var(--ink-400)" : "var(--ink-900)",
      textDecoration: isRejected ? "line-through" : "none",
      fontFamily: "var(--font)",
      boxSizing: "border-box",
      outline: "none",
    };
  }, [cell.status, invalidReason, isRejected]);

  // Emit `edited` whenever the user changes a non-rejected cell. Empty
  // input maps to null so backend validation sees missing required cells.
  function emit(rawValue: unknown): void {
    onChange({
      value: rawValue,
      status: isRejected ? "rejected" : "edited",
    });
  }

  let control: React.ReactNode;
  if (cell.data_type === "boolean") {
    const v = cell.value === true || cell.value === "true";
    control = (
      <label
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
          color: isRejected ? "var(--ink-400)" : "var(--ink-900)",
          textDecoration: isRejected ? "line-through" : "none",
        }}
      >
        <input
          type="checkbox"
          checked={v}
          disabled={disabled || isRejected}
          onChange={(e) => emit(e.target.checked)}
        />
        <span>{v ? "是" : "否"}</span>
      </label>
    );
  } else if (cell.data_type === "date") {
    control = (
      <input
        type="date"
        value={toDateInputValue(cell.value)}
        disabled={disabled || isRejected}
        onChange={(e) => emit(e.target.value || null)}
        style={inputStyle}
      />
    );
  } else if (cell.data_type === "datetime") {
    control = (
      <input
        type="datetime-local"
        value={toDateTimeInputValue(cell.value)}
        disabled={disabled || isRejected}
        onChange={(e) => emit(e.target.value || null)}
        style={inputStyle}
      />
    );
  } else if (cell.data_type === "decimal" || cell.data_type === "integer") {
    control = (
      <input
        type="number"
        inputMode="decimal"
        step={cell.data_type === "integer" ? 1 : "any"}
        value={toNumberInputValue(cell.value)}
        disabled={disabled || isRejected}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            emit(null);
            return;
          }
          const n = Number(raw);
          emit(Number.isFinite(n) ? n : raw);
        }}
        style={inputStyle}
      />
    );
  } else {
    control = (
      <input
        type="text"
        value={toTextInputValue(cell.value)}
        disabled={disabled || isRejected}
        onChange={(e) => emit(e.target.value === "" ? null : e.target.value)}
        style={inputStyle}
      />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 18 }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--ink-500)",
            letterSpacing: "0.01em",
          }}
        >
          {cell.label}
          {cell.required && (
            <span style={{ color: "var(--risk-500)", marginLeft: 3 }}>*</span>
          )}
        </span>
        <span
          style={{
            fontSize: 10,
            color: "var(--ink-300)",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {cell.field_name}
        </span>
        {isEdited && (
          <span
            className="pill pill-brand"
            style={{ fontSize: 10, padding: "1px 6px", marginLeft: "auto" }}
          >
            已修改
          </span>
        )}
        {!isEdited && isLow && (
          <span
            className="pill pill-warn"
            style={{ fontSize: 10, padding: "1px 6px", marginLeft: "auto" }}
          >
            低置信
          </span>
        )}
        {!isEdited && !isLow && isInvalid && (
          <span
            className="pill pill-risk"
            style={{ fontSize: 10, padding: "1px 6px", marginLeft: "auto" }}
          >
            校验失败
          </span>
        )}
        {!isEdited &&
          !isLow &&
          !isInvalid &&
          cell.status === "extracted" &&
          cell.confidence !== null &&
          cell.confidence < 0.6 && (
            <span
              className="pill pill-warn"
              style={{ fontSize: 10, padding: "1px 6px", marginLeft: "auto" }}
            >
              {Math.round(cell.confidence * 100)}%
            </span>
          )}
      </div>

      {control}

      {isMissing && (
        <div style={{ fontSize: 11, color: "var(--ink-400)" }}>
          未抽取，可手动填写
        </div>
      )}

      {invalidReason && (
        <div style={{ fontSize: 11, color: "var(--risk-500)" }}>{invalidReason}</div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          flexWrap: "wrap",
          marginTop: 2,
        }}
      >
        {cell.evidence?.excerpt && (
          <EvidenceChip
            type="原文"
            label={
              cell.evidence.page
                ? `p.${cell.evidence.page} · ${truncate(cell.evidence.excerpt, 40)}`
                : truncate(cell.evidence.excerpt, 50)
            }
          />
        )}
        {onReject && !isMissing && (
          <button
            type="button"
            onClick={onReject}
            disabled={disabled}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--ink-500)",
              fontSize: 11,
              cursor: disabled ? "not-allowed" : "pointer",
              padding: "2px 4px",
              textDecoration: "underline",
              fontFamily: "var(--font)",
            }}
          >
            {isRejected ? "恢复" : "拒绝"}
          </button>
        )}
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return `${s.slice(0, n)}…`;
}
