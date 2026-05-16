// Progressive review wizard for vNext ingest.
//
// Renders a fixed step list driven by ``draft.steps``: customer →
// contacts → commercial → finance → logistics_product → memory →
// summary. Empty steps were already filtered server-side. The
// active step shows only its tables, in card or table presentation,
// alongside a source panel for the currently focused cell.

import { useMemo, useState } from "react";
import { fmtRelative } from "../../lib/format";
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
  // True when the underlying job/draft is in a terminal state
  // (confirmed / failed / canceled) — distinct from readOnly, which
  // also covers the "someone else is editing" case where confirm is
  // merely disabled rather than meaningless.
  finalized: boolean;
  finalizedKind?: "confirmed" | "failed" | "canceled" | null;
  finalizedAt?: string | null;
  finalizedBy?: string | null;
  busy: boolean;
  error: string | null;
  invalidCells: ConfirmExtractionInvalidCell[];
  onCellPatch: (patch: ReviewCellPatch) => void;
  onRowPatch: (patch: ReviewRowDecisionPatch) => void;
  onConfirm: () => void | Promise<void>;
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
  finalized,
  finalizedKind,
  finalizedAt,
  finalizedBy,
  busy,
  error,
  invalidCells,
  onCellPatch,
  onRowPatch,
  onConfirm,
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

  // Step navigation is purely client-side state — flipping between wizard
  // tabs must not bump the server's review_version. The autosave PATCH is
  // reserved for cell/row edits; confirm carries the latest version
  // regardless of which step the user is currently looking at.
  function setStep(next: string) {
    setActiveStep(next);
    setActiveCell(null);
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
        minHeight: 0,
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          flexWrap: "wrap",
          gap: 8,
          flexShrink: 0,
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
          {onDelete && !finalized ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void onDelete()}
              disabled={busy}
              style={{ color: "var(--risk-700)" }}
            >
              丢弃此草稿
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
            flexShrink: 0,
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
            flexShrink: 0,
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
          maxWidth: "100%",
          flexShrink: 0,
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
          alignItems: "stretch",
          flex: 1,
          minHeight: 0,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            minWidth: 0,
            minHeight: 0,
            overflowY: "auto",
            paddingRight: 4,
          }}
        >
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
              alignItems: "center",
              gap: 8,
              marginTop: 4,
            }}
          >
            {isSummary && finalized ? (
              <FinalizedStatusBadge
                kind={finalizedKind ?? "confirmed"}
                at={finalizedAt ?? null}
                by={finalizedBy ?? null}
              />
            ) : isSummary ? (
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
        <div style={{ minHeight: 0, overflowY: "auto" }}>
          <ReviewSourcePanel
            sourceText={sourceText}
            originalFileUrl={originalFileUrl}
            originalFileContentType={originalFileContentType}
            activeCell={activeSrc}
          />
        </div>
      </div>
    </div>
  );
}

function FinalizedStatusBadge({
  kind,
  at,
  by,
}: {
  kind: "confirmed" | "failed" | "canceled";
  at: string | null;
  by: string | null;
}) {
  const palette =
    kind === "confirmed"
      ? { bg: "var(--ok-100)", fg: "var(--ok-700)", label: "已归档" }
      : kind === "failed"
        ? { bg: "var(--risk-100, var(--surface-2))", fg: "var(--risk-700)", label: "处理失败" }
        : { bg: "var(--surface-2)", fg: "var(--ink-500)", label: "已取消" };
  const when = at ? fmtRelative(at) : null;
  const detail = [when, by ? `由 ${by} 确认` : null].filter(Boolean).join(" · ");
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 14px",
        borderRadius: 999,
        background: palette.bg,
        color: palette.fg,
        fontSize: 13,
        fontWeight: 600,
      }}
    >
      <span>{palette.label}</span>
      {detail ? (
        <span style={{ fontWeight: 500, opacity: 0.85 }}>{detail}</span>
      ) : null}
    </div>
  );
}
