// Review workspace — renders ReviewDraft.tables as schema-shaped forms.
//
// Owns:
// - local patch buffer (Map keyed by table/row/field)
// - local row mutations (append empty row for array tables, reject all
//   cells in a row)
// - "确认入库" / "忽略" actions — delegates to onSubmit / onIgnore
//
// Does NOT call the API. Parent (Review.tsx) wires confirm/ignore calls.

import { useEffect, useMemo, useRef, useState } from "react";
import { Section } from "../Section";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import type {
  ConfirmExtractionInvalidCell,
  ReviewCell,
  ReviewCellPatch,
  ReviewCellStatus,
  ReviewDraft,
  ReviewRow,
  ReviewTable,
} from "../../data/types";
import { ReviewCellEditor } from "./ReviewCellEditor";

type Props = {
  draft: ReviewDraft;
  onSubmit: (patches: ReviewCellPatch[]) => Promise<void> | void;
  onIgnore: () => Promise<void> | void;
  busy?: boolean;
  submitError?: string | null;
  invalidCells?: ConfirmExtractionInvalidCell[];
  sourceText?: string | null;
};

type PatchKey = string;

function patchKey(tableName: string, rowId: string, fieldName: string): PatchKey {
  return `${tableName}|${rowId}|${fieldName}`;
}

function emptyCellFromTemplate(template: ReviewCell): ReviewCell {
  return {
    field_name: template.field_name,
    label: template.label,
    data_type: template.data_type,
    required: template.required,
    is_array: template.is_array,
    value: null,
    display_value: "",
    status: "missing",
    confidence: null,
    evidence: null,
    source: "empty",
  };
}

function applyPatchesToTable(
  table: ReviewTable,
  patches: Map<PatchKey, ReviewCellPatch>,
  extraRowsByTable: Record<string, ReviewRow[]>,
): ReviewTable {
  const extraRows = extraRowsByTable[table.table_name] ?? [];
  const allRows = [...table.rows, ...extraRows];
  const nextRows = allRows.map((row) => {
    const nextCells = row.cells.map((cell) => {
      const p = patches.get(patchKey(table.table_name, row.client_row_id, cell.field_name));
      if (!p) return cell;
      return {
        ...cell,
        value: p.value !== undefined ? p.value : cell.value,
        status: p.status ?? cell.status,
      };
    });
    return { ...row, cells: nextCells };
  });
  return { ...table, rows: nextRows };
}

export function ReviewTableWorkspace({
  draft,
  onSubmit,
  onIgnore,
  busy = false,
  submitError = null,
  invalidCells = [],
  sourceText = null,
}: Props) {
  const isDesktop = useIsDesktop();
  const [patches, setPatches] = useState<Map<PatchKey, ReviewCellPatch>>(new Map());
  // Locally appended rows for array tables — keyed by table_name. These
  // get materialized into ReviewCellPatch entries on submit.
  const [extraRowsByTable, setExtraRowsByTable] = useState<Record<string, ReviewRow[]>>({});
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Build a quick lookup map for invalid cells -> reason.
  const invalidIndex = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of invalidCells) {
      m.set(patchKey(c.table_name, c.client_row_id, c.field_name), c.reason);
    }
    return m;
  }, [invalidCells]);

  // On new invalidCells: scroll first invalid into view.
  useEffect(() => {
    if (!invalidCells.length) return;
    const first = invalidCells[0]!;
    const id = `cell-${patchKey(first.table_name, first.client_row_id, first.field_name)}`;
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [invalidCells]);

  function setCellPatch(
    tableName: string,
    rowId: string,
    fieldName: string,
    next: { value?: unknown; status?: ReviewCellStatus; entity_id?: string | null; operation?: ReviewRow["operation"] },
  ): void {
    setPatches((prev) => {
      const k = patchKey(tableName, rowId, fieldName);
      const existing = prev.get(k);
      const merged: ReviewCellPatch = {
        table_name: tableName,
        client_row_id: rowId,
        field_name: fieldName,
        ...(existing ?? {}),
        ...next,
      };
      const out = new Map(prev);
      out.set(k, merged);
      return out;
    });
  }

  // Reject every cell in the row by writing a `rejected` status patch
  // for each. We use the latest known cells (with patches applied) so the
  // user keeps any in-progress values when they hit "删除此行".
  function rejectRow(table: ReviewTable, row: ReviewRow): void {
    setPatches((prev) => {
      const out = new Map(prev);
      for (const cell of row.cells) {
        const k = patchKey(table.table_name, row.client_row_id, cell.field_name);
        const existing = out.get(k);
        out.set(k, {
          table_name: table.table_name,
          client_row_id: row.client_row_id,
          field_name: cell.field_name,
          ...(existing ?? {}),
          status: "rejected",
        });
      }
      return out;
    });
  }

  function restoreRow(table: ReviewTable, row: ReviewRow): void {
    setPatches((prev) => {
      const out = new Map(prev);
      for (const cell of row.cells) {
        const k = patchKey(table.table_name, row.client_row_id, cell.field_name);
        const existing = out.get(k);
        if (!existing) continue;
        if (existing.status === "rejected") {
          // Strip the rejected status. If patch only carried status,
          // drop it entirely.
          const cleaned: ReviewCellPatch = { ...existing };
          delete cleaned.status;
          const hasOtherFields =
            cleaned.value !== undefined ||
            cleaned.entity_id !== undefined ||
            cleaned.operation !== undefined;
          if (hasOtherFields) {
            out.set(k, cleaned);
          } else {
            out.delete(k);
          }
        }
      }
      return out;
    });
  }

  function appendRow(table: ReviewTable): void {
    // Build an empty row using the catalog fields from the first existing
    // row (server always ships at least one row, even for arrays with no
    // extracted items). When there is no template row, skip silently.
    const template = table.rows[0];
    if (!template) return;
    const newRowId = `${table.table_name}:local-${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 7)}`;
    const newCells = template.cells.map(emptyCellFromTemplate);
    const newRow: ReviewRow = {
      client_row_id: newRowId,
      entity_id: null,
      operation: "create",
      cells: newCells,
    };
    setExtraRowsByTable((prev) => ({
      ...prev,
      [table.table_name]: [...(prev[table.table_name] ?? []), newRow],
    }));
  }

  // Render-time tables with patches applied — used for the filled count
  // and child render only. Patches themselves are sent verbatim on submit.
  const renderedTables = useMemo(() => {
    return draft.tables.map((t) => applyPatchesToTable(t, patches, extraRowsByTable));
  }, [draft.tables, patches, extraRowsByTable]);

  async function handleSubmit(): Promise<void> {
    if (busy) return;
    // The patches map already has user edits. Locally-added rows are
    // implicit: their cell patches only get created when the user fills
    // them. So we materialize an `operation=create` row marker by
    // emitting any-cell patch for each extra row to make the row exist
    // server-side; otherwise the server has no awareness of the row.
    const out: ReviewCellPatch[] = Array.from(patches.values());
    for (const [tableName, extras] of Object.entries(extraRowsByTable)) {
      for (const row of extras) {
        // Ensure at least one patch carries the row's client_row_id so the
        // server creates it. Use the first cell as a marker (operation +
        // current value, which may be null if the user did not type).
        const hasAny = out.some(
          (p) => p.table_name === tableName && p.client_row_id === row.client_row_id,
        );
        if (!hasAny) {
          const firstCell = row.cells[0];
          if (firstCell) {
            out.push({
              table_name: tableName,
              client_row_id: row.client_row_id,
              field_name: firstCell.field_name,
              value: firstCell.value,
              operation: "create",
            });
          }
        } else {
          // Make sure the operation marker is set on at least one patch.
          for (const p of out) {
            if (
              p.table_name === tableName &&
              p.client_row_id === row.client_row_id &&
              !p.operation
            ) {
              p.operation = "create";
              break;
            }
          }
        }
      }
    }
    await onSubmit(out);
  }

  async function handleIgnore(): Promise<void> {
    if (busy) return;
    await onIgnore();
  }

  const filename = draft.document?.filename ?? "(未命名文档)";
  const summary = draft.document?.summary;
  const routeChips = draft.route_plan?.selected_pipelines ?? [];
  const showSourcePanel = sourceText !== undefined;
  const hasSource = typeof sourceText === "string" && sourceText.trim().length > 0;

  return (
    <div
      ref={containerRef}
      className="screen"
      style={{ background: "var(--bg)" }}
    >
      {/* Sticky top bar */}
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 5,
          background: "var(--bg)",
          borderBottom: "1px solid var(--ink-100)",
          padding: isDesktop ? "12px 32px" : "10px 16px",
        }}
      >
        <div
          style={{
            maxWidth: isDesktop ? 1080 : undefined,
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                color: "var(--ink-900)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {filename}
            </div>
            {summary && (
              <div
                style={{
                  fontSize: 12,
                  color: "var(--ink-500)",
                  marginTop: 2,
                  lineHeight: 1.4,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {summary}
              </div>
            )}
            {routeChips.length > 0 && (
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  marginTop: 6,
                  flexWrap: "wrap",
                }}
              >
                {routeChips.map((c) => (
                  <span
                    key={c.name}
                    className="pill pill-brand"
                    style={{ fontSize: 11, padding: "2px 8px" }}
                  >
                    {c.name}
                    {typeof c.confidence === "number" && (
                      <span style={{ marginLeft: 4, opacity: 0.7 }}>
                        {Math.round(c.confidence * 100)}%
                      </span>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-secondary"
              onClick={() => void handleIgnore()}
              disabled={busy}
              style={{ padding: "8px 14px" }}
            >
              忽略
            </button>
            <button
              className="btn btn-primary"
              onClick={() => void handleSubmit()}
              disabled={busy}
              style={{ padding: "8px 18px" }}
            >
              {I.check(15, "#fff")}
              <span>{busy ? "确认中…" : "确认入库"}</span>
            </button>
          </div>
        </div>
      </div>

      <div
        className="scroll"
        style={{
          flex: 1,
          padding: isDesktop ? "20px 32px 100px" : "12px 16px 100px",
          maxWidth: isDesktop && showSourcePanel ? 1320 : isDesktop ? 1080 : undefined,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {submitError && (
          <div
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid var(--risk-100)",
              background: "#fff1f0",
              color: "var(--risk-500)",
              fontSize: 12,
              lineHeight: 1.5,
              marginBottom: 12,
            }}
          >
            {submitError}
          </div>
        )}

        <div
          style={
            isDesktop && showSourcePanel
              ? {
                  display: "grid",
                  gridTemplateColumns: "minmax(0, 1fr) 360px",
                  gap: 16,
                  alignItems: "start",
                }
              : undefined
          }
        >
          {showSourcePanel && !isDesktop && (
            <SourceTextPanel sourceText={sourceText ?? null} hasSource={hasSource} />
          )}

          <div style={{ minWidth: 0 }}>
            {renderedTables.length === 0 && (
              <div
                className="card"
                style={{
                  padding: 24,
                  textAlign: "center",
                  color: "var(--ink-500)",
                  fontSize: 13,
                }}
              >
                未识别到任何 schema 表。请检查文档质量或调整路由设置。
              </div>
            )}

            {renderedTables.map((table) => (
              <TableSection
                key={table.table_name}
                table={table}
                invalidIndex={invalidIndex}
                disabled={busy}
                onChangeCell={(rowId, fieldName, patch) =>
                  setCellPatch(table.table_name, rowId, fieldName, patch)
                }
                onRejectCell={(rowId, fieldName, currentlyRejected) => {
                  if (currentlyRejected) {
                    setCellPatch(table.table_name, rowId, fieldName, { status: "extracted" });
                  } else {
                    setCellPatch(table.table_name, rowId, fieldName, { status: "rejected" });
                  }
                }}
                onRejectRow={(row) => rejectRow(table, row)}
                onRestoreRow={(row) => restoreRow(table, row)}
                onAppendRow={() => appendRow(table)}
              />
            ))}

            {(draft.schema_warnings.length > 0 || draft.general_warnings.length > 0) && (
              <Section title="提示">
                <div className="card" style={{ padding: 12 }}>
                  {[...draft.schema_warnings, ...draft.general_warnings].map((w, i) => (
                    <div
                      key={i}
                      style={{
                        fontSize: 11.5,
                        color: "var(--warn-700)",
                        background: "var(--warn-50)",
                        border: "1px solid var(--warn-100)",
                        borderRadius: 6,
                        padding: "6px 8px",
                        marginBottom: 6,
                        lineHeight: 1.4,
                      }}
                    >
                      {w}
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>

          {showSourcePanel && isDesktop && (
            <aside
              style={{
                position: "sticky",
                top: 12,
                maxHeight: "calc(100vh - 160px)",
                overflow: "auto",
                background: "var(--surface)",
                border: "1px solid var(--ink-100)",
                borderRadius: 10,
                padding: 14,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--ink-500)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  marginBottom: 8,
                }}
              >
                源文件内容
              </div>
              {hasSource ? (
                <pre
                  style={{
                    margin: 0,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                    fontSize: 12,
                    lineHeight: 1.55,
                    color: "var(--ink-700)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {sourceText}
                </pre>
              ) : (
                <div style={{ color: "var(--ink-400)", fontSize: 12.5 }}>
                  暂无可展示的源文件文本
                </div>
              )}
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────

function TableSection({
  table,
  invalidIndex,
  disabled,
  onChangeCell,
  onRejectCell,
  onRejectRow,
  onRestoreRow,
  onAppendRow,
}: {
  table: ReviewTable;
  invalidIndex: Map<string, string>;
  disabled: boolean;
  onChangeCell: (
    rowId: string,
    fieldName: string,
    patch: { value?: unknown; status?: ReviewCellStatus },
  ) => void;
  onRejectCell: (rowId: string, fieldName: string, currentlyRejected: boolean) => void;
  onRejectRow: (row: ReviewRow) => void;
  onRestoreRow: (row: ReviewRow) => void;
  onAppendRow: () => void;
}) {
  const filledCount = useMemo(() => {
    let filled = 0;
    let total = 0;
    for (const row of table.rows) {
      for (const c of row.cells) {
        total += 1;
        if (c.status === "rejected") continue;
        const present =
          c.value !== null &&
          c.value !== undefined &&
          !(typeof c.value === "string" && c.value === "");
        if (present) filled += 1;
      }
    }
    return { filled, total };
  }, [table.rows]);

  const requiredMissing = useMemo(() => {
    let n = 0;
    for (const row of table.rows) {
      for (const c of row.cells) {
        if (!c.required) continue;
        if (c.status === "rejected") continue;
        const present =
          c.value !== null &&
          c.value !== undefined &&
          !(typeof c.value === "string" && c.value === "");
        if (!present) n += 1;
      }
    }
    return n;
  }, [table.rows]);

  return (
    <Section
      title={table.label}
      trailing={
        <span
          style={{
            fontSize: 11,
            color: "var(--ink-400)",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {table.table_name}
        </span>
      }
    >
      {table.purpose && (
        <div
          style={{
            fontSize: 12,
            color: "var(--ink-500)",
            padding: "0 4px 6px",
            lineHeight: 1.4,
          }}
        >
          {table.purpose}
        </div>
      )}

      {table.is_array
        ? table.rows.map((row, idx) => (
            <RowCard
              key={row.client_row_id}
              table={table}
              row={row}
              index={idx}
              invalidIndex={invalidIndex}
              disabled={disabled}
              onChangeCell={onChangeCell}
              onRejectCell={onRejectCell}
              onRejectRow={onRejectRow}
              onRestoreRow={onRestoreRow}
            />
          ))
        : table.rows[0] && (
            <CellGrid
              table={table}
              row={table.rows[0]}
              invalidIndex={invalidIndex}
              disabled={disabled}
              onChangeCell={onChangeCell}
              onRejectCell={onRejectCell}
            />
          )}

      {table.is_array && (
        <button
          type="button"
          onClick={onAppendRow}
          disabled={disabled}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            marginTop: 8,
            padding: "8px 12px",
            fontSize: 12,
            color: "var(--brand-600)",
            background: "var(--brand-50)",
            border: "1px dashed var(--brand-300)",
            borderRadius: 8,
            cursor: disabled ? "not-allowed" : "pointer",
            fontFamily: "var(--font)",
          }}
        >
          {I.plus(12, "var(--brand-600)")}
          <span>添加一行</span>
        </button>
      )}

      <div
        style={{
          marginTop: 8,
          paddingLeft: 4,
          fontSize: 11,
          color: requiredMissing > 0 ? "var(--warn-700)" : "var(--ink-400)",
        }}
      >
        {filledCount.filled}/{filledCount.total} 已填
        {requiredMissing > 0 && ` · ${requiredMissing} 个必填项待补充`}
      </div>
    </Section>
  );
}

// One block of (label + input) cells, 2-column grid on wide screens.
function CellGrid({
  table,
  row,
  invalidIndex,
  disabled,
  onChangeCell,
  onRejectCell,
}: {
  table: ReviewTable;
  row: ReviewRow;
  invalidIndex: Map<string, string>;
  disabled: boolean;
  onChangeCell: (
    rowId: string,
    fieldName: string,
    patch: { value?: unknown; status?: ReviewCellStatus },
  ) => void;
  onRejectCell: (rowId: string, fieldName: string, currentlyRejected: boolean) => void;
}) {
  return (
    <div
      className="card"
      style={{
        padding: 14,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: 14,
      }}
    >
      {row.cells.map((cell) => {
        const key = patchKey(table.table_name, row.client_row_id, cell.field_name);
        return (
          <div key={cell.field_name} id={`cell-${key}`}>
            <ReviewCellEditor
              cell={cell}
              rowId={row.client_row_id}
              tableName={table.table_name}
              disabled={disabled}
              invalidReason={invalidIndex.get(key) ?? null}
              onChange={(p) => onChangeCell(row.client_row_id, cell.field_name, p)}
              onReject={() =>
                onRejectCell(row.client_row_id, cell.field_name, cell.status === "rejected")
              }
            />
          </div>
        );
      })}
    </div>
  );
}

function RowCard({
  table,
  row,
  index,
  invalidIndex,
  disabled,
  onChangeCell,
  onRejectCell,
  onRejectRow,
  onRestoreRow,
}: {
  table: ReviewTable;
  row: ReviewRow;
  index: number;
  invalidIndex: Map<string, string>;
  disabled: boolean;
  onChangeCell: (
    rowId: string,
    fieldName: string,
    patch: { value?: unknown; status?: ReviewCellStatus },
  ) => void;
  onRejectCell: (rowId: string, fieldName: string, currentlyRejected: boolean) => void;
  onRejectRow: (row: ReviewRow) => void;
  onRestoreRow: (row: ReviewRow) => void;
}) {
  const allRejected = row.cells.length > 0 && row.cells.every((c) => c.status === "rejected");
  return (
    <div
      className="card"
      style={{
        padding: 14,
        marginBottom: 10,
        opacity: allRejected ? 0.5 : 1,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-700)" }}>
          第 {index + 1} 行
          {row.entity_id && (
            <span
              style={{
                marginLeft: 6,
                fontSize: 10,
                color: "var(--ink-400)",
                fontFamily: "ui-monospace, SFMono-Regular, monospace",
              }}
            >
              {row.operation === "update" ? `更新 · ${row.entity_id.slice(0, 8)}…` : ""}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => (allRejected ? onRestoreRow(row) : onRejectRow(row))}
          disabled={disabled}
          style={{
            background: "transparent",
            border: "none",
            color: allRejected ? "var(--brand-600)" : "var(--ink-500)",
            fontSize: 12,
            cursor: disabled ? "not-allowed" : "pointer",
            padding: "2px 4px",
            textDecoration: "underline",
            fontFamily: "var(--font)",
          }}
        >
          {allRejected ? "恢复此行" : "删除此行"}
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 14,
        }}
      >
        {row.cells.map((cell) => {
          const key = patchKey(table.table_name, row.client_row_id, cell.field_name);
          return (
            <div key={cell.field_name} id={`cell-${key}`}>
              <ReviewCellEditor
                cell={cell}
                rowId={row.client_row_id}
                tableName={table.table_name}
                disabled={disabled}
                invalidReason={invalidIndex.get(key) ?? null}
                onChange={(p) => onChangeCell(row.client_row_id, cell.field_name, p)}
                onReject={() =>
                  onRejectCell(row.client_row_id, cell.field_name, cell.status === "rejected")
                }
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Mobile-only collapsible source-text panel. Rendered above tables in a
// single column. Starts collapsed so it never dominates the small screen.
function SourceTextPanel({
  sourceText,
  hasSource,
}: {
  sourceText: string | null;
  hasSource: boolean;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        border: "1px solid var(--ink-100)",
        background: "var(--surface)",
        borderRadius: 10,
        marginBottom: 12,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "var(--font)",
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: "var(--ink-500)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          源文件内容
        </span>
        <span
          style={{
            color: "var(--ink-400)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 150ms ease",
            display: "inline-flex",
          }}
        >
          {I.chev(13)}
        </span>
      </button>
      {open && (
        <div
          style={{
            padding: "0 12px 12px",
            maxHeight: 280,
            overflow: "auto",
          }}
        >
          {hasSource ? (
            <pre
              style={{
                margin: 0,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                fontSize: 12,
                lineHeight: 1.55,
                color: "var(--ink-700)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {sourceText}
            </pre>
          ) : (
            <div style={{ color: "var(--ink-400)", fontSize: 12.5 }}>
              暂无可展示的源文件文本
            </div>
          )}
        </div>
      )}
    </div>
  );
}
