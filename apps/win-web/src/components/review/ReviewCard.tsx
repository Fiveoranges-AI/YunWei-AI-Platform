// Master/card presentation for the vNext review wizard.
//
// One ``ReviewCard`` per ReviewRow. Used for tables marked
// ``presentation === "card"`` (customers, contacts, contracts, orders,
// invoices). Renders the row's cells in a 2-column grid, plus a row-
// decision segmented control (create / update / link_existing / ignore)
// that maps to ``onRowPatch`` on the parent.

import type {
  ReviewCell,
  ReviewCellPatch,
  ReviewCellStatus,
  ReviewRow,
  ReviewRowDecision,
  ReviewRowDecisionPatch,
  ReviewRowOperation,
  ReviewTable,
} from "../../data/types";
import { ReviewCellEditor } from "./ReviewCellEditor";

// (Local helper removed: cellsByField was unused after the card switched to
// iterating ``row.cells`` directly to preserve catalog field order.)

type Props = {
  table: ReviewTable;
  row: ReviewRow;
  readOnly: boolean;
  invalidByCell: Map<string, string>;
  activeCellKey: string | null;
  onActivateCell: (rowId: string, fieldName: string) => void;
  onCellPatch: (patch: ReviewCellPatch) => void;
  onRowPatch: (patch: ReviewRowDecisionPatch) => void;
};

const OPERATION_LABEL: Record<ReviewRowOperation, string> = {
  create: "新建",
  update: "更新",
  link_existing: "关联现有",
  ignore: "忽略",
};

const DECISION_OPTIONS: ReviewRowOperation[] = [
  "create",
  "update",
  "link_existing",
  "ignore",
];

function decisionOperation(row: ReviewRow): ReviewRowOperation {
  return row.row_decision?.operation ?? row.operation ?? "create";
}

function CandidatesPanel({
  decision,
  onPick,
  disabled,
}: {
  decision: ReviewRowDecision | null | undefined;
  onPick: (id: string) => void;
  disabled: boolean;
}) {
  const candidates = decision?.candidate_entities ?? [];
  if (candidates.length === 0) return null;
  return (
    <div
      style={{
        background: "var(--surface-2)",
        border: "1px solid var(--ink-100)",
        borderRadius: 8,
        padding: 10,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
        AI 找到的相似实体（点击关联）
      </div>
      {candidates.map((c) => {
        const selected = decision?.selected_entity_id === c.entity_id;
        return (
          <button
            key={c.entity_id}
            type="button"
            onClick={() => onPick(c.entity_id)}
            disabled={disabled}
            style={{
              textAlign: "left",
              padding: "6px 10px",
              borderRadius: 6,
              border: selected
                ? "1px solid var(--brand-500)"
                : "1px solid var(--ink-100)",
              background: selected ? "var(--brand-50)" : "var(--surface)",
              color: "var(--ink-900)",
              fontSize: 13,
              display: "flex",
              flexDirection: "column",
              gap: 2,
              cursor: disabled ? "default" : "pointer",
            }}
          >
            <div style={{ fontWeight: 600 }}>{c.label}</div>
            <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
              {c.match_level} · {(c.match_keys ?? []).join(", ") || "—"}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function ReviewCard({
  table,
  row,
  readOnly,
  invalidByCell,
  activeCellKey,
  onActivateCell,
  onCellPatch,
  onRowPatch,
}: Props) {
  const op = decisionOperation(row);
  const ignored = op === "ignore";
  const linked = op === "link_existing";
  const decision = row.row_decision ?? null;
  const hasCandidates = (decision?.candidate_entities ?? []).length > 0;

  function handleCellChange(
    cell: ReviewCell,
    change: { value: unknown; status?: ReviewCellStatus },
  ) {
    onCellPatch({
      table_name: table.table_name,
      client_row_id: row.client_row_id,
      field_name: cell.field_name,
      value: change.value,
      status: change.status,
    });
  }

  function handleReject(cell: ReviewCell) {
    onCellPatch({
      table_name: table.table_name,
      client_row_id: row.client_row_id,
      field_name: cell.field_name,
      status: cell.status === "rejected" ? "extracted" : "rejected",
    });
  }

  function handleOperation(next: ReviewRowOperation) {
    onRowPatch({
      table_name: table.table_name,
      client_row_id: row.client_row_id,
      operation: next,
    });
  }

  return (
    <div
      style={{
        border: "1px solid var(--ink-100)",
        background: "var(--surface)",
        borderRadius: 12,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "baseline",
          justifyContent: "space-between",
          flexWrap: "wrap",
        }}
      >
        <div
          style={{
            fontSize: 13,
            color: "var(--ink-500)",
            fontWeight: 600,
          }}
        >
          {table.label} · {row.client_row_id}
        </div>
        <div
          role="radiogroup"
          aria-label="行决策"
          style={{
            display: "flex",
            gap: 4,
            background: "var(--surface-2)",
            border: "1px solid var(--ink-100)",
            borderRadius: 8,
            padding: 2,
          }}
        >
          {DECISION_OPTIONS.map((o) => {
            const active = o === op;
            // "关联现有" requires at least one candidate to attach to.
            // Without candidates the only valid path forward is to keep
            // the existing op (so users can switch off it) or to pick
            // another option. Disable so the radio can't enter the
            // link_existing+no-target state that confirm rejects.
            const blocked = o === "link_existing" && !hasCandidates && !active;
            return (
              <button
                key={o}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => handleOperation(o)}
                disabled={readOnly || blocked}
                title={blocked ? "未找到可关联的候选记录" : undefined}
                style={{
                  fontSize: 12,
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "none",
                  background: active ? "var(--surface)" : "transparent",
                  color: active
                    ? "var(--ink-900)"
                    : blocked
                      ? "var(--ink-300)"
                      : "var(--ink-500)",
                  boxShadow: active ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
                  fontWeight: active ? 600 : 500,
                  cursor: readOnly || blocked ? "not-allowed" : "pointer",
                }}
              >
                {OPERATION_LABEL[o]}
              </button>
            );
          })}
        </div>
      </div>

      <CandidatesPanel
        decision={decision}
        disabled={readOnly}
        onPick={(id) =>
          onRowPatch({
            table_name: table.table_name,
            client_row_id: row.client_row_id,
            operation: "update",
            selected_entity_id: id,
          })
        }
      />

      {linked ? (
        <div
          style={{
            background: "var(--brand-50)",
            color: "var(--brand-700)",
            borderRadius: 8,
            padding: 10,
            fontSize: 13,
          }}
        >
          已关联到 {decision?.selected_entity_id || "未选择"}，确认时系统会写入关联，不会更新单元格。
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 12,
        }}
      >
        {row.cells
          .filter((c) => c.review_visible !== false)
          .map((cell) => {
            const key = `${row.client_row_id}:${cell.field_name}`;
            const invalidReason = invalidByCell.get(key) ?? null;
            const active = activeCellKey === key;
            return (
              <div
                key={cell.field_name}
                onMouseDown={() =>
                  onActivateCell(row.client_row_id, cell.field_name)
                }
                onFocus={() =>
                  onActivateCell(row.client_row_id, cell.field_name)
                }
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  padding: 8,
                  borderRadius: 8,
                  background: active ? "var(--brand-50)" : "transparent",
                  cursor: "default",
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--ink-500)",
                    fontWeight: 500,
                  }}
                >
                  {cell.label}
                  {cell.required ? <span style={{ color: "var(--risk-700)" }}> *</span> : null}
                </div>
                <ReviewCellEditor
                  cell={cell}
                  rowId={row.client_row_id}
                  tableName={table.table_name}
                  onChange={(change) => handleCellChange(cell, change)}
                  onReject={() => handleReject(cell)}
                  invalidReason={invalidReason}
                  disabled={readOnly || ignored || linked}
                  readOnly={readOnly}
                />
              </div>
            );
          })}
      </div>
    </div>
  );
}
