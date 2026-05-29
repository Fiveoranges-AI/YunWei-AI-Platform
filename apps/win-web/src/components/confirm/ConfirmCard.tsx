// ConfirmCard — pure presentational card for one CandidateEntity.
//
// Renders one card per entity:
//   header: entity_type label + per-card "确认入库" action chip
//   body: per-field row → name | value (editable) | confidence pill | "查看原文"
//   footer: missing_required list ("待补充")
//
// Lives entirely in the display layer: no fetch calls, no global state.
// Edits are surfaced via callbacks the host (ConfirmDemo / hook) wires up.

import { useState } from "react";
import type {
  CandidateEntity,
  CandidateField,
  CandidateSourceSpan,
} from "../../data/candidate";

const LOW_CONFIDENCE_THRESHOLD = 0.6;
const MED_CONFIDENCE_THRESHOLD = 0.8;

const ENTITY_LABEL: Record<string, string> = {
  Customer: "客户",
  Contact: "联系人",
  Contract: "合同",
  Order: "订单",
  OrderLine: "订单明细",
  OrderItem: "订单明细",
  Product: "产品",
  Invoice: "发票",
  Payment: "回款",
};

export type FieldEdit = {
  fieldName: string;
  value: unknown;
};

export type ConfirmCardProps = {
  entity: CandidateEntity;
  edits: Record<string, unknown>; // fieldName → new value (only present if user edited)
  confirmed: boolean;
  busy: boolean;
  onEditField: (edit: FieldEdit) => void;
  onConfirm: () => void;
};

export function ConfirmCard(props: ConfirmCardProps) {
  const { entity, edits, confirmed, busy, onEditField, onConfirm } = props;
  const editedNames = new Set(Object.keys(edits));
  const lowFields = entity.fields.filter((f) => f.confidence < LOW_CONFIDENCE_THRESHOLD);
  const label = ENTITY_LABEL[entity.entity_type] ?? entity.entity_type;

  return (
    <section
      style={{
        background: "#fff",
        border: "1px solid var(--ink-100)",
        borderRadius: 14,
        marginBottom: 16,
        overflow: "hidden",
        opacity: confirmed ? 0.7 : 1,
      }}
      data-testid={`confirm-card-${entity.temp_id}`}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 18px",
          borderBottom: "1px solid var(--ink-100)",
          background: "var(--surface-2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "var(--ink-900)",
              letterSpacing: "-0.01em",
            }}
          >
            {label}
          </span>
          <span
            style={{
              fontSize: 11,
              color: "var(--ink-400)",
              fontFamily: "var(--font-mono, monospace)",
            }}
          >
            #{entity.temp_id}
          </span>
          {lowFields.length > 0 && !confirmed ? (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--risk-700)",
                background: "var(--risk-100, #FEE2E2)",
                padding: "2px 8px",
                borderRadius: 999,
              }}
            >
              {lowFields.length} 项请重点核对
            </span>
          ) : null}
          {confirmed ? (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--ok-700, #047857)",
                background: "var(--ok-100, #D1FAE5)",
                padding: "2px 8px",
                borderRadius: 999,
              }}
            >
              已确认入库 · 人工
            </span>
          ) : null}
        </div>
        <button
          onClick={onConfirm}
          disabled={confirmed || busy}
          style={{
            height: 30,
            padding: "0 14px",
            borderRadius: 999,
            border: "none",
            background: confirmed ? "var(--ink-300)" : "var(--ink-900)",
            color: "#fff",
            fontSize: 12,
            fontWeight: 600,
            cursor: confirmed || busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.6 : 1,
            fontFamily: "var(--font)",
          }}
          data-testid={`confirm-entity-${entity.temp_id}`}
        >
          {confirmed ? "已入库" : busy ? "提交中…" : "确认本条入库"}
        </button>
      </header>

      <div style={{ padding: "8px 0" }}>
        {entity.fields.map((f) => (
          <FieldRow
            key={f.name}
            field={f}
            edited={editedNames.has(f.name)}
            currentValue={editedNames.has(f.name) ? edits[f.name] : f.value}
            readOnly={confirmed || busy}
            onEdit={(value) => onEditField({ fieldName: f.name, value })}
          />
        ))}
      </div>

      {entity.missing_required.length > 0 ? (
        <footer
          style={{
            padding: "10px 18px 14px",
            borderTop: "1px dashed var(--ink-100)",
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
            background: "var(--surface-2)",
          }}
        >
          <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>
            待补充
          </span>
          {entity.missing_required.map((name) => (
            <button
              key={name}
              onClick={() => onEditField({ fieldName: name, value: "" })}
              disabled={confirmed || busy}
              style={{
                height: 24,
                padding: "0 10px",
                borderRadius: 999,
                border: "1px dashed var(--risk-500, #EF4444)",
                background: "transparent",
                color: "var(--risk-700, #B91C1C)",
                fontSize: 11,
                fontWeight: 600,
                cursor: confirmed || busy ? "not-allowed" : "pointer",
                fontFamily: "var(--font)",
              }}
            >
              + {name}
            </button>
          ))}
        </footer>
      ) : null}
    </section>
  );
}

// ---- field row + evidence popover --------------------------------------

function FieldRow({
  field,
  edited,
  currentValue,
  readOnly,
  onEdit,
}: {
  field: CandidateField;
  edited: boolean;
  currentValue: unknown;
  readOnly: boolean;
  onEdit: (value: unknown) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const conf = field.confidence;
  const tone =
    conf >= MED_CONFIDENCE_THRESHOLD
      ? "high"
      : conf >= LOW_CONFIDENCE_THRESHOLD
        ? "med"
        : "low";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "120px 1fr 92px 96px",
        alignItems: "center",
        gap: 12,
        padding: "10px 18px",
        borderBottom: "1px solid var(--ink-100)",
        background:
          tone === "low" && !edited
            ? "var(--risk-100, #FEE2E2)55"
            : "transparent",
      }}
    >
      <span
        style={{
          fontSize: 12.5,
          color: "var(--ink-500)",
          fontWeight: 600,
          letterSpacing: "-0.01em",
        }}
      >
        {field.name}
      </span>

      <FieldEditor
        field={field}
        currentValue={currentValue}
        edited={edited}
        readOnly={readOnly}
        onEdit={onEdit}
      />

      <ConfidencePill tone={tone} confidence={conf} edited={edited} />

      <div style={{ position: "relative" }}>
        <button
          onClick={() => setShowEvidence((s) => !s)}
          style={{
            height: 26,
            padding: "0 10px",
            borderRadius: 6,
            border: "1px solid var(--ink-100)",
            background: showEvidence ? "var(--ink-900)" : "transparent",
            color: showEvidence ? "#fff" : "var(--ink-700)",
            fontSize: 11.5,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
          aria-expanded={showEvidence}
          data-testid={`evidence-toggle-${field.name}`}
        >
          {showEvidence ? "收起" : "查看原文"}
        </button>
        {showEvidence ? (
          <EvidencePopover
            sourceSpan={field.source_span}
            onClose={() => setShowEvidence(false)}
          />
        ) : null}
      </div>
    </div>
  );
}

function FieldEditor({
  field,
  currentValue,
  edited,
  readOnly,
  onEdit,
}: {
  field: CandidateField;
  currentValue: unknown;
  edited: boolean;
  readOnly: boolean;
  onEdit: (value: unknown) => void;
}) {
  const inputType = inferInputType(field.name, field.value);
  const displayValue =
    currentValue === null || currentValue === undefined ? "" : String(currentValue);

  if (readOnly) {
    return (
      <span
        style={{
          fontSize: 13.5,
          color: "var(--ink-900)",
          fontWeight: 500,
        }}
      >
        {displayValue || <em style={{ color: "var(--ink-400)" }}>（空）</em>}
      </span>
    );
  }

  return (
    <input
      type={inputType}
      value={displayValue}
      onChange={(e) => onEdit(coerceInputValue(inputType, e.target.value))}
      data-testid={`field-input-${field.name}`}
      style={{
        height: 32,
        border: edited
          ? "1.5px solid var(--brand-500, #2D6EA8)"
          : "1px solid var(--ink-100)",
        borderRadius: 8,
        padding: "0 10px",
        fontSize: 13.5,
        fontFamily: "var(--font)",
        color: "var(--ink-900)",
        background: edited ? "var(--brand-50, #EEF4FB)" : "#fff",
        outline: "none",
        width: "100%",
        boxSizing: "border-box",
      }}
    />
  );
}

function ConfidencePill({
  tone,
  confidence,
  edited,
}: {
  tone: "high" | "med" | "low";
  confidence: number;
  edited: boolean;
}) {
  if (edited) {
    return (
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--brand-700, #1B4670)",
          background: "var(--brand-50, #EEF4FB)",
          padding: "3px 8px",
          borderRadius: 999,
          textAlign: "center",
          letterSpacing: "0.02em",
        }}
        title="人工修改后,系统不再用 AI 置信度"
      >
        人工修改
      </span>
    );
  }
  const bg =
    tone === "high"
      ? "var(--ok-100, #D1FAE5)"
      : tone === "med"
        ? "var(--warn-100, #FEF3C7)"
        : "var(--risk-100, #FEE2E2)";
  const fg =
    tone === "high"
      ? "var(--ok-700, #047857)"
      : tone === "med"
        ? "var(--warn-700, #B45309)"
        : "var(--risk-700, #B91C1C)";
  const label = tone === "high" ? "高" : tone === "med" ? "中" : "低";
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: fg,
        background: bg,
        padding: "3px 8px",
        borderRadius: 999,
        textAlign: "center",
        letterSpacing: "0.02em",
      }}
      title={`AI 置信度 ${(confidence * 100).toFixed(0)}%`}
    >
      {label} · {(confidence * 100).toFixed(0)}%
    </span>
  );
}

function EvidencePopover({
  sourceSpan,
  onClose,
}: {
  sourceSpan: CandidateSourceSpan;
  onClose: () => void;
}) {
  const lines: Array<{ label: string; value: string }> = [];
  if (typeof sourceSpan.page === "number") {
    lines.push({ label: "页码", value: `第 ${sourceSpan.page} 页` });
  }
  if (typeof sourceSpan.cell === "string" && sourceSpan.cell) {
    lines.push({ label: "单元格", value: sourceSpan.cell });
  }
  if (Array.isArray(sourceSpan.bbox) && sourceSpan.bbox.length === 4) {
    lines.push({ label: "区域", value: sourceSpan.bbox.map((v) => v.toFixed(0)).join(", ") });
  }
  const text =
    typeof sourceSpan.text === "string" && sourceSpan.text.trim()
      ? sourceSpan.text
      : "(无原文片段)";

  return (
    <div
      role="dialog"
      onClick={(e) => e.stopPropagation()}
      style={{
        position: "absolute",
        top: 32,
        right: 0,
        width: 320,
        maxWidth: "calc(100vw - 48px)",
        background: "#fff",
        border: "1px solid var(--ink-100)",
        borderRadius: 10,
        boxShadow: "0 8px 24px rgba(15,35,64,0.12)",
        padding: 12,
        zIndex: 20,
        textAlign: "left",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink-500)" }}>
          原文出处
        </span>
        <button
          onClick={onClose}
          aria-label="关闭"
          style={{
            background: "transparent",
            border: "none",
            color: "var(--ink-400)",
            fontSize: 14,
            cursor: "pointer",
            padding: 4,
          }}
        >
          ×
        </button>
      </div>
      {lines.map((l) => (
        <div
          key={l.label}
          style={{ fontSize: 11.5, color: "var(--ink-500)", marginBottom: 4 }}
        >
          {l.label}: <span style={{ color: "var(--ink-900)" }}>{l.value}</span>
        </div>
      ))}
      <div
        style={{
          marginTop: 8,
          padding: "8px 10px",
          borderRadius: 6,
          background: "var(--surface-2)",
          fontSize: 12.5,
          color: "var(--ink-900)",
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: 200,
          overflow: "auto",
        }}
      >
        {text}
      </div>
    </div>
  );
}

// ---- helpers -----------------------------------------------------------

function inferInputType(name: string, sample: unknown): "text" | "number" | "date" {
  if (typeof sample === "number") return "number";
  if (
    typeof sample === "string" &&
    /^\d{4}-\d{2}-\d{2}/.test(sample)
  ) {
    return "date";
  }
  const lower = name.toLowerCase();
  if (lower.endsWith("_date") || lower.endsWith("_at")) return "date";
  if (
    lower.includes("amount") ||
    lower.includes("price") ||
    lower.includes("quantity") ||
    lower.includes("ratio")
  ) {
    return "number";
  }
  return "text";
}

function coerceInputValue(
  inputType: "text" | "number" | "date",
  raw: string,
): unknown {
  if (raw === "") return null;
  if (inputType === "number") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : raw;
  }
  // date inputs come back as "YYYY-MM-DD" — keep them as string so the
  // backend coerce_value can parse them.
  return raw;
}
