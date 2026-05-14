// Progressive review wizard for vNext ingest.
//
// Renders a fixed step list driven by ``draft.steps``: customer →
// contacts → commercial → finance → logistics_product → memory →
// summary. Empty steps were already filtered server-side. The
// active step shows only its tables, in card or table presentation,
// alongside a source panel for the currently focused cell.

import { useMemo, useState } from "react";
import { ReviewCard } from "./ReviewCard";
import { ReviewDetailTable } from "./ReviewDetailTable";
import { ReviewSourcePanel } from "./ReviewSourcePanel";
import { ReviewSummary } from "./ReviewSummary";
import type {
  ConfirmExtractionInvalidCell,
  ReviewCellPatch,
  ReviewDraft,
  ReviewRowDecisionPatch,
  ReviewSourceRef,
} from "../../data/types";

type Props = {
  draft: ReviewDraft;
  readOnly: boolean;
  busy: boolean;
  error: string | null;
  invalidCells: ConfirmExtractionInvalidCell[];
  onCellPatch: (patch: ReviewCellPatch) => void;
  onRowPatch: (patch: ReviewRowDecisionPatch) => void;
  onStepChange: (step: string) => void;
  onConfirm: () => void | Promise<void>;
  onIgnore?: () => void | Promise<void>;
  onDelete?: () => void | Promise<void>;
  sourceText: string | null;
  originalFileUrl: string | null;
  originalFileContentType: string | null;
  lockBanner?: string | null;
};

function buildInvalidMap(
  invalidCells: ConfirmExtractionInvalidCell[],
): Map<string, Map<string, string>> {
  const byTable = new Map<string, Map<string, string>>();
  for (const ic of invalidCells) {
    let inner = byTable.get(ic.table_name);
    if (!inner) {
      inner = new Map();
      byTable.set(ic.table_name, inner);
    }
    inner.set(`${ic.client_row_id}:${ic.field_name}`, ic.reason);
  }
  return byTable;
}

function activeCellRefs(
  draft: ReviewDraft,
  active: { tableName: string; rowId: string; field: string } | null,
): { table: string; field: string; label: string; refs: ReviewSourceRef[] } | null {
  if (!active) return null;
  const table = draft.tables.find((t) => t.table_name === active.tableName);
  if (!table) return null;
  const row = table.rows.find((r) => r.client_row_id === active.rowId);
  if (!row) return null;
  const cell = row.cells.find((c) => c.field_name === active.field);
  if (!cell) return null;
  return {
    table: table.label || table.table_name,
    field: cell.field_name,
    label: cell.label,
    refs: cell.source_refs ?? [],
  };
}

export function ReviewWizard({
  draft,
  readOnly,
  busy,
  error,
  invalidCells,
  onCellPatch,
  onRowPatch,
  onStepChange,
  onConfirm,
  onIgnore,
  onDelete,
  sourceText,
  originalFileUrl,
  originalFileContentType,
  lockBanner,
}: Props) {
  const steps = draft.steps && draft.steps.length > 0 ? draft.steps : [];
  const fallbackStepKey = steps[0]?.key ?? "summary";
  const initialStep = draft.current_step ?? fallbackStepKey;
  const [activeStep, setActiveStep] = useState<string>(initialStep);
  const [activeCell, setActiveCell] = useState<
    { tableName: string; rowId: string; field: string } | null
  >(null);

  function setStep(next: string) {
    setActiveStep(next);
    setActiveCell(null);
    onStepChange(next);
  }

  const invalidByTable = useMemo(() => buildInvalidMap(invalidCells), [invalidCells]);
  const activeSrc = activeCellRefs(draft, activeCell);

  const tablesForStep = useMemo(
    () =>
      draft.tables.filter((t) => (t.review_step ?? null) === activeStep),
    [draft.tables, activeStep],
  );

  const isSummary = activeStep === "summary";

  return (
    <div
      className="screen"
      style={{
        background: "var(--bg)",
        display: "flex",
        flexDirection: "column",
        padding: 16,
        gap: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)" }}>
            {draft.document.filename}
          </div>
          {draft.document.summary ? (
            <div style={{ fontSize: 13, color: "var(--ink-500)" }}>
              {draft.document.summary}
            </div>
          ) : null}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {onIgnore ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onIgnore()}
              disabled={busy || readOnly}
            >
              忽略此文档
            </button>
          ) : null}
          {onDelete ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onDelete()}
              disabled={busy}
              style={{ color: "var(--risk-700)" }}
            >
              删除任务
            </button>
          ) : null}
        </div>
      </div>

      {lockBanner ? (
        <div
          style={{
            background: "var(--warn-100, var(--surface-2))",
            color: "var(--warn-700, var(--ink-700))",
            border: "1px solid var(--warn-500, var(--ink-100))",
            padding: "8px 12px",
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          {lockBanner}
        </div>
      ) : null}

      {error ? (
        <div
          style={{
            background: "var(--risk-100, var(--surface-2))",
            color: "var(--risk-700)",
            border: "1px solid var(--risk-500)",
            padding: "8px 12px",
            borderRadius: 8,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      ) : null}

      <nav
        style={{
          display: "flex",
          gap: 4,
          overflowX: "auto",
          background: "var(--surface)",
          border: "1px solid var(--ink-100)",
          borderRadius: 999,
          padding: 4,
          alignSelf: "flex-start",
        }}
      >
        {steps.map((step) => {
          const active = step.key === activeStep;
          return (
            <button
              key={step.key}
              type="button"
              onClick={() => setStep(step.key)}
              style={{
                padding: "6px 14px",
                borderRadius: 999,
                border: "none",
                background: active ? "var(--brand-500)" : "transparent",
                color: active ? "#fff" : "var(--ink-700)",
                fontWeight: active ? 600 : 500,
                fontSize: 13,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {step.label}
            </button>
          );
        })}
      </nav>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 360px)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
          {isSummary ? (
            <ReviewSummary draft={draft} invalidCells={invalidCells} />
          ) : tablesForStep.length === 0 ? (
            <div
              style={{
                fontSize: 13,
                color: "var(--ink-400)",
                padding: 16,
                background: "var(--surface)",
                border: "1px dashed var(--ink-100)",
                borderRadius: 12,
              }}
            >
              本步骤暂无可复核的表。
            </div>
          ) : (
            tablesForStep.map((table) => {
              const presentation = table.presentation ?? (table.is_array ? "table" : "card");
              const invalidMap = invalidByTable.get(table.table_name) ?? new Map();
              if (presentation === "card") {
                return (
                  <div
                    key={table.table_name}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 12,
                    }}
                  >
                    {table.rows.map((row) => (
                      <ReviewCard
                        key={row.client_row_id}
                        table={table}
                        row={row}
                        readOnly={readOnly}
                        invalidByCell={invalidMap}
                        activeCellKey={
                          activeCell &&
                          activeCell.tableName === table.table_name &&
                          activeCell.rowId === row.client_row_id
                            ? `${activeCell.rowId}:${activeCell.field}`
                            : null
                        }
                        onActivateCell={(rowId, field) =>
                          setActiveCell({
                            tableName: table.table_name,
                            rowId,
                            field,
                          })
                        }
                        onCellPatch={onCellPatch}
                        onRowPatch={onRowPatch}
                      />
                    ))}
                  </div>
                );
              }
              return (
                <ReviewDetailTable
                  key={table.table_name}
                  table={table}
                  readOnly={readOnly}
                  invalidByCell={invalidMap}
                  activeCellKey={
                    activeCell && activeCell.tableName === table.table_name
                      ? `${activeCell.rowId}:${activeCell.field}`
                      : null
                  }
                  onActivateCell={(rowId, field) =>
                    setActiveCell({ tableName: table.table_name, rowId, field })
                  }
                  onCellPatch={onCellPatch}
                  onRowPatch={onRowPatch}
                />
              );
            })
          )}

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginTop: 4,
            }}
          >
            {isSummary ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy || readOnly}
                onClick={() => void onConfirm()}
              >
                {busy ? "提交中..." : "确认入库"}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  const idx = steps.findIndex((s) => s.key === activeStep);
                  const next = steps[idx + 1];
                  if (next) setStep(next.key);
                }}
              >
                继续
              </button>
            )}
          </div>
        </div>
        <ReviewSourcePanel
          sourceText={sourceText}
          originalFileUrl={originalFileUrl}
          originalFileContentType={originalFileContentType}
          activeCell={activeSrc}
        />
      </div>
    </div>
  );
}
