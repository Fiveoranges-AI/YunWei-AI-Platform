// Slice ② — review data-health analysis.
//
// Pure, frontend-only derivation over a ReviewDraft: a completeness score
// (how much of the to-be-written data is filled) and a prioritized
// "needs your confirmation" list (missing-required + low-confidence +
// invalid cells). Drives the health bar and the progressive 逐项补全 flow.
// Confidence and completeness are kept separate per the product spec:
// completeness = "is it filled", attention = "should a human look".

import type { ReviewCell, ReviewDraft, ReviewRow } from "../data/types";

export type AttentionReason = "missing_required" | "invalid" | "low_confidence";

export type AttentionItem = {
  tableName: string;
  tableLabel: string;
  rowId: string;
  rowIndex: number; // 0-based position among writable rows of its table
  isArray: boolean;
  field: string;
  reason: AttentionReason;
};

export type ReviewProgress = {
  total: number; // relevant (to-be-written) cells
  filled: number; // of those, how many carry a value
  score: number; // 0..100 completeness
  attention: AttentionItem[];
};

const LOW_CONFIDENCE_CUTOFF = 0.6;

const REASON_ORDER: Record<AttentionReason, number> = {
  missing_required: 0,
  invalid: 1,
  low_confidence: 2,
};

// Only cells that the confirm step will actually persist count toward
// completeness — ignored / link-existing rows write no cell values.
function rowIsWritable(row: ReviewRow): boolean {
  const op = row.row_decision?.operation ?? row.operation;
  if (op === "ignore" || op === "link_existing") return false;
  return row.is_writable !== false;
}

function cellIsRelevant(cell: ReviewCell): boolean {
  if (cell.review_visible === false) return false;
  if (cell.source === "linked") return false; // FK auto-linked at confirm
  return true;
}

function cellIsFilled(cell: ReviewCell): boolean {
  if (cell.status === "missing" || cell.status === "rejected") return false;
  return cell.display_value != null && String(cell.display_value).trim() !== "";
}

function cellIsLowConfidence(cell: ReviewCell): boolean {
  if (cell.status === "low_confidence") return true;
  return (
    cell.status === "extracted" &&
    cell.confidence != null &&
    cell.confidence < LOW_CONFIDENCE_CUTOFF
  );
}

function attentionReason(cell: ReviewCell, filled: boolean): AttentionReason | null {
  if (cell.status === "invalid") return "invalid";
  if (!filled && cell.required) return "missing_required";
  if (filled && cellIsLowConfidence(cell)) return "low_confidence";
  return null;
}

export function analyzeReview(draft: ReviewDraft): ReviewProgress {
  let total = 0;
  let filled = 0;
  const attention: AttentionItem[] = [];

  for (const table of draft.tables) {
    const writableRows = table.rows.filter(rowIsWritable);
    writableRows.forEach((row, rowIndex) => {
      for (const cell of row.cells) {
        if (!cellIsRelevant(cell)) continue;
        total += 1;
        const isFilled = cellIsFilled(cell);
        if (isFilled) filled += 1;
        const reason = attentionReason(cell, isFilled);
        if (reason) {
          attention.push({
            tableName: table.table_name,
            tableLabel: table.label || table.table_name,
            rowId: row.client_row_id,
            rowIndex,
            isArray: table.is_array,
            field: cell.field_name,
            reason,
          });
        }
      }
    });
  }

  attention.sort((a, b) => REASON_ORDER[a.reason] - REASON_ORDER[b.reason]);
  const score = total === 0 ? 100 : Math.round((filled / total) * 100);
  return { total, filled, score, attention };
}

export function findCell(
  draft: ReviewDraft,
  item: { tableName: string; rowId: string; field: string },
): ReviewCell | null {
  const table = draft.tables.find((t) => t.table_name === item.tableName);
  const row = table?.rows.find((r) => r.client_row_id === item.rowId);
  return row?.cells.find((c) => c.field_name === item.field) ?? null;
}

export const REASON_LABEL: Record<AttentionReason, string> = {
  missing_required: "缺必填",
  invalid: "校验未过",
  low_confidence: "低置信",
};

// Plain-language "why am I being asked" — the lightweight 让 AI 澄清.
// (Live model re-ask is a separate backend follow-up.)
export function clarifyText(cell: ReviewCell, reason: AttentionReason): string {
  if (reason === "missing_required") {
    return `AI 在资料里没找到「${cell.label}」，请补充。`;
  }
  if (reason === "invalid") {
    return `「${cell.label}」的格式或必填校验未通过，请修正。`;
  }
  const pct = cell.confidence != null ? `（约 ${Math.round(cell.confidence * 100)}%）` : "";
  return `AI 识别出此值但置信度较低${pct}，请核对是否准确。`;
}
