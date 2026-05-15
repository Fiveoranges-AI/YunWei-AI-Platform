// Review cell editor — a controlled input for a single ReviewCell.
//
// The parent (ReviewCard / ReviewDetailTable in ReviewWizard) decides
// when an edit becomes a server-side autosave PATCH; this component
// stays presentational. It renders the right control for the cell's
// data_type, surfaces status (missing / edited / low_confidence /
// rejected / invalid) via border + chips, and pipes edits back through
// ``onChange``.

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
  // When true, hide the 拒绝/恢复 affordance. The `disabled` prop is the
  // authoritative gate for input editability — `readOnly` is purely for
  // hiding write-intent UI controls on historical / non-editable views.
  readOnly?: boolean;
  // Render the field's Chinese label inside the editor's header so the
  // label, the dev-hint field_name, and the status pill all live in the
  // same visual box. Card view (ReviewCard) opts in; table view
  // (ReviewDetailTable) leaves it off because the column header already
  // shows the label.
  showLabel?: boolean;
};

// Parent-table display labels for FK cells the system auto-links at
// confirm time. Kept small + UI-only; keep in sync with FK_FIELD_PARENTS
// on the backend if the FK map grows.
const FK_PARENT_LABEL: Record<string, string> = {
  customer_id: "客户",
  contract_id: "合同",
  invoice_id: "发票",
  order_id: "订单",
  shipment_id: "货运",
  product_id: "产品",
  document_id: "源文档",
  source_document_id: "源文档",
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
  readOnly,
  showLabel = false,
}: Props) {
  const isRejected = cell.status === "rejected";
  const isMissing = cell.status === "missing";
  const isEdited = cell.status === "edited";
  const isLow = cell.status === "low_confidence";
  const isInvalid = cell.status === "invalid" || Boolean(invalidReason);
  const isLinked = cell.source === "linked";

  if (isLinked && !isEdited) {
    // Rendered as an auto-link chip. Confirm writeback fills the UUID from
    // the same-confirm parent row; the user does not need to enter anything.
    const parentLabel = FK_PARENT_LABEL[cell.field_name] ?? "关联记录";
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {showLabel && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 18 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--ink-700)",
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
          </div>
        )}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "7px 10px",
            fontSize: 13.5,
            border: "1px dashed var(--ink-200)",
            borderRadius: 8,
            background: "var(--surface-2)",
            color: "var(--ink-600)",
            fontFamily: "var(--font)",
            boxSizing: "border-box",
          }}
        >
          <span>↪ 本次新建的{parentLabel}</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-400)" }}>
          确认时由系统自动关联
        </div>
      </div>
    );
  }

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
    // Use type="text" so OCR-style strings like "90%", "30,000.00", "90 天"
    // display without the browser warning ("value cannot be parsed") that
    // <input type="number"> emits for non-numeric content. inputMode keeps
    // mobile keyboards on the numeric layout. The onChange below still
    // coerces clean numbers; backend normalization happens at confirm.
    control = (
      <input
        type="text"
        inputMode={cell.data_type === "integer" ? "numeric" : "decimal"}
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
      <div style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 18, flexWrap: "wrap" }}>
        {showLabel && (
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--ink-700)",
            }}
          >
            {cell.label}
            {cell.required && (
              <span style={{ color: "var(--risk-500)", marginLeft: 3 }}>*</span>
            )}
          </span>
        )}
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
        {onReject && !isMissing && !readOnly && (
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
