// Final summary step for the vNext review wizard.
//
// Counts rows by row_decision.operation, lists schema/general warnings,
// surfaces missing-required / invalid cells, and shows how many cells
// the user edited away from the AI proposal. The "confirm" button lives
// on the parent (ReviewWizard) — this component is presentation only.

import type {
  ConfirmExtractionInvalidCell,
  ReviewDraft,
  ReviewRow,
  ReviewRowOperation,
} from "../../data/types";

type Props = {
  draft: ReviewDraft;
  invalidCells: ConfirmExtractionInvalidCell[];
};

function decisionOp(row: ReviewRow): ReviewRowOperation {
  return row.row_decision?.operation ?? row.operation ?? "create";
}

const REASON_LABEL: Record<string, string> = {
  missing_required: "缺少必填值",
  invalid_value: "格式不符合字段类型",
  catalog_field_has_no_orm_destination: "字段无对应数据列",
  link_existing_missing_target: "未选择关联记录,请改为 “新建” 或在候选项中选一条",
  missing_parent_link: "缺少父级记录,请先在父表中新建或关联一条",
};

function describeInvalid(reason: string): string {
  return REASON_LABEL[reason] ?? reason;
}

function describeFieldName(fieldName: string): string {
  // Backend uses the pseudo-field "_row_decision" for row-level errors
  // (e.g. link_existing without a target). Surface this as 行决策 so
  // reviewers don't see an internal sentinel.
  if (fieldName === "_row_decision") return "行决策";
  return fieldName;
}

type Counts = Record<ReviewRowOperation, number>;

function countDecisions(draft: ReviewDraft): {
  byTable: Map<string, Counts>;
  total: Counts;
  editedCells: number;
} {
  const total: Counts = {
    create: 0,
    update: 0,
    link_existing: 0,
    ignore: 0,
  };
  const byTable = new Map<string, Counts>();
  let editedCells = 0;
  for (const table of draft.tables) {
    const c: Counts = { create: 0, update: 0, link_existing: 0, ignore: 0 };
    for (const row of table.rows) {
      const op = decisionOp(row);
      c[op] += 1;
      total[op] += 1;
      for (const cell of row.cells) {
        if (cell.status === "edited") editedCells += 1;
      }
    }
    byTable.set(table.table_name, c);
  }
  return { byTable, total, editedCells };
}

const OPERATION_LABEL: Record<ReviewRowOperation, string> = {
  create: "新建",
  update: "更新",
  link_existing: "关联",
  ignore: "忽略",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
        borderRadius: 12,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-700)" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export function ReviewSummary({ draft, invalidCells }: Props) {
  const { byTable, total, editedCells } = countDecisions(draft);
  const tableByName = new Map(draft.tables.map((t) => [t.table_name, t]));

  const warnings = [...(draft.schema_warnings ?? []), ...(draft.general_warnings ?? [])];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Section title="本次确认概览">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
            gap: 8,
          }}
        >
          {(Object.keys(total) as ReviewRowOperation[]).map((op) => (
            <div
              key={op}
              style={{
                background: "var(--surface-2)",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 12, color: "var(--ink-500)" }}>
                {OPERATION_LABEL[op]}
              </div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: "var(--ink-900)",
                }}
              >
                {total[op]}
              </div>
            </div>
          ))}
          <div
            style={{
              background: "var(--surface-2)",
              borderRadius: 8,
              padding: "10px 12px",
            }}
          >
            <div style={{ fontSize: 12, color: "var(--ink-500)" }}>已修改字段</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--ink-900)" }}>
              {editedCells}
            </div>
          </div>
        </div>
      </Section>

      <Section title="按表分布">
        <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
          {[...byTable.entries()].map(([name, counts]) => {
            const t = tableByName.get(name);
            const parts = (Object.keys(counts) as ReviewRowOperation[])
              .filter((op) => counts[op] > 0)
              .map((op) => `${OPERATION_LABEL[op]} ${counts[op]}`);
            return (
              <li
                key={name}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 13,
                  padding: "4px 0",
                  borderBottom: "1px dashed var(--ink-100)",
                }}
              >
                <span style={{ color: "var(--ink-900)" }}>
                  {t?.label || name}
                </span>
                <span style={{ color: "var(--ink-500)" }}>
                  {parts.length > 0 ? parts.join(" · ") : "全部忽略"}
                </span>
              </li>
            );
          })}
        </ul>
      </Section>

      {invalidCells.length > 0 ? (
        <Section title="待修复字段">
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {invalidCells.map((c, idx) => (
              <li
                key={`${c.table_name}:${c.client_row_id}:${c.field_name}:${idx}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  fontSize: 13,
                  padding: "6px 0",
                  borderBottom: "1px dashed var(--ink-100)",
                  color: "var(--risk-700)",
                }}
              >
                <span style={{ minWidth: 0, flexShrink: 0 }}>
                  {c.table_name} · {c.client_row_id} · {describeFieldName(c.field_name)}
                </span>
                <span
                  style={{
                    color: "var(--risk-500)",
                    textAlign: "right",
                    minWidth: 0,
                  }}
                >
                  {describeInvalid(c.reason)}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {warnings.length > 0 ? (
        <Section title="提醒">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--ink-700)" }}>
            {warnings.map((w, idx) => (
              <li key={`${idx}:${w}`}>{w}</li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
