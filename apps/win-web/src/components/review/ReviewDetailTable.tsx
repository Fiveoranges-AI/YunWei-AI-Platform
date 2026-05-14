// Detail/table presentation for the vNext review wizard.
//
// Used for tables marked ``presentation === "table"`` — milestones,
// invoice items, shipment items, product requirements. Each row gets a
// row-decision dropdown in the leading column; cells render with the
// shared ``ReviewCellEditor`` in a stable grid so column widths don't
// shift between rows.

import type {
  ReviewCell,
  ReviewCellPatch,
  ReviewCellStatus,
  ReviewRow,
  ReviewRowDecisionPatch,
  ReviewRowOperation,
  ReviewTable,
} from "../../data/types";
import { ReviewCellEditor } from "./ReviewCellEditor";

type Props = {
  table: ReviewTable;
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
  link_existing: "关联",
  ignore: "忽略",
};

function decisionOperation(row: ReviewRow): ReviewRowOperation {
  return row.row_decision?.operation ?? row.operation ?? "create";
}

function visibleColumns(table: ReviewTable): string[] {
  // Use the first row with cells as the column source so the header stays
  // stable even when later rows have a strict subset of fields.
  for (const row of table.rows) {
    if (row.cells.length === 0) continue;
    return row.cells
      .filter((c) => c.review_visible !== false)
      .map((c) => c.field_name);
  }
  return [];
}

function fieldLabel(table: ReviewTable, fieldName: string): string {
  for (const row of table.rows) {
    for (const c of row.cells) {
      if (c.field_name === fieldName) return c.label;
    }
  }
  return fieldName;
}

function cellByField(row: ReviewRow, field: string): ReviewCell | null {
  for (const c of row.cells) if (c.field_name === field) return c;
  return null;
}

export function ReviewDetailTable({
  table,
  readOnly,
  invalidByCell,
  activeCellKey,
  onActivateCell,
  onCellPatch,
  onRowPatch,
}: Props) {
  const columns = visibleColumns(table);

  if (columns.length === 0) {
    return (
      <div
        style={{
          fontSize: 13,
          color: "var(--ink-400)",
          padding: 12,
          border: "1px dashed var(--ink-100)",
          borderRadius: 8,
        }}
      >
        {table.label}：暂无可编辑字段。
      </div>
    );
  }

  function handleCellChange(
    row: ReviewRow,
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

  function handleReject(row: ReviewRow, cell: ReviewCell) {
    onCellPatch({
      table_name: table.table_name,
      client_row_id: row.client_row_id,
      field_name: cell.field_name,
      status: cell.status === "rejected" ? "extracted" : "rejected",
    });
  }

  return (
    <div
      style={{
        border: "1px solid var(--ink-100)",
        background: "var(--surface)",
        borderRadius: 12,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-700)" }}>
        {table.label}
        <span style={{ color: "var(--ink-400)", fontWeight: 400, marginLeft: 6 }}>
          {table.rows.length} 条
        </span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "separate",
            borderSpacing: 0,
            fontSize: 13,
          }}
        >
          <thead>
            <tr>
              <th
                style={{
                  textAlign: "left",
                  padding: "6px 8px",
                  background: "var(--surface-2)",
                  color: "var(--ink-500)",
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                }}
              >
                决策
              </th>
              {columns.map((field) => (
                <th
                  key={field}
                  style={{
                    textAlign: "left",
                    padding: "6px 8px",
                    background: "var(--surface-2)",
                    color: "var(--ink-500)",
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                  }}
                >
                  {fieldLabel(table, field)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => {
              const op = decisionOperation(row);
              const ignored = op === "ignore";
              const linked = op === "link_existing";
              return (
                <tr key={row.client_row_id}>
                  <td
                    style={{
                      padding: "6px 8px",
                      borderTop: "1px solid var(--ink-100)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    <select
                      value={op}
                      disabled={readOnly}
                      onChange={(e) =>
                        onRowPatch({
                          table_name: table.table_name,
                          client_row_id: row.client_row_id,
                          operation: e.target.value as ReviewRowOperation,
                        })
                      }
                      style={{
                        fontSize: 12,
                        padding: "4px 6px",
                        borderRadius: 6,
                        border: "1px solid var(--ink-100)",
                        background: "var(--surface)",
                        color: "var(--ink-900)",
                      }}
                    >
                      {(Object.keys(OPERATION_LABEL) as ReviewRowOperation[]).map(
                        (o) => (
                          <option key={o} value={o}>
                            {OPERATION_LABEL[o]}
                          </option>
                        ),
                      )}
                    </select>
                  </td>
                  {columns.map((field) => {
                    const cell = cellByField(row, field);
                    if (!cell) {
                      return (
                        <td
                          key={field}
                          style={{
                            padding: "6px 8px",
                            borderTop: "1px solid var(--ink-100)",
                            color: "var(--ink-400)",
                          }}
                        >
                          —
                        </td>
                      );
                    }
                    const key = `${row.client_row_id}:${cell.field_name}`;
                    const invalidReason = invalidByCell.get(key) ?? null;
                    const active = activeCellKey === key;
                    return (
                      <td
                        key={field}
                        onMouseDown={() =>
                          onActivateCell(row.client_row_id, cell.field_name)
                        }
                        onFocus={() =>
                          onActivateCell(row.client_row_id, cell.field_name)
                        }
                        style={{
                          padding: "6px 8px",
                          borderTop: "1px solid var(--ink-100)",
                          background: active ? "var(--brand-50)" : "transparent",
                          minWidth: 160,
                        }}
                      >
                        <ReviewCellEditor
                          cell={cell}
                          rowId={row.client_row_id}
                          tableName={table.table_name}
                          onChange={(change) =>
                            handleCellChange(row, cell, change)
                          }
                          onReject={() => handleReject(row, cell)}
                          invalidReason={invalidReason}
                          disabled={readOnly || ignored || linked}
                          readOnly={readOnly}
                        />
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
