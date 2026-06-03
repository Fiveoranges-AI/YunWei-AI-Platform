// DEV-only mock ReviewDraft, used to exercise the review wizard (incl. the
// Slice ② health bar + 逐项补全 flow) without a live backend. Reached via
// go("review", { jobId: "demo" }) and only honored when import.meta.env.DEV.
// Tree-shaken out of production builds (pure const, only referenced behind
// `import.meta.env.DEV` dead branches).

import type {
  ReviewCell,
  ReviewCellPatch,
  ReviewDraft,
  ReviewRow,
  ReviewTable,
} from "./types";

function cell(partial: Partial<ReviewCell> & Pick<ReviewCell, "field_name" | "label" | "data_type">): ReviewCell {
  const value = partial.value ?? null;
  return {
    required: false,
    is_array: false,
    value,
    display_value: partial.display_value ?? (value == null ? "" : String(value)),
    status: "extracted",
    confidence: null,
    evidence: null,
    source: "ai",
    source_refs: [],
    review_visible: true,
    ...partial,
  };
}

function row(client_row_id: string, cells: ReviewCell[]): ReviewRow {
  return { client_row_id, entity_id: null, operation: "create", cells, is_writable: true };
}

const customers: ReviewTable = {
  table_name: "customers",
  label: "客户",
  is_array: false,
  presentation: "card",
  review_step: "customer",
  rows: [
    row("customers:0", [
      cell({
        field_name: "name",
        label: "客户名称",
        data_type: "string",
        required: true,
        value: "邦普循环科技有限公司",
        confidence: 0.96,
        status: "extracted",
        evidence: { page: 1, excerpt: "甲方：邦普循环科技有限公司" },
      }),
      cell({
        field_name: "industry",
        label: "行业",
        data_type: "string",
        value: "新能源材料",
        confidence: 0.48,
        status: "low_confidence",
        evidence: { page: 1, excerpt: "……锂电池正极材料前驱体……" },
      }),
      cell({ field_name: "region", label: "地区", data_type: "string", status: "missing" }),
    ]),
  ],
};

const contracts: ReviewTable = {
  table_name: "contracts",
  label: "合同",
  is_array: false,
  presentation: "card",
  review_step: "commercial",
  rows: [
    row("contracts:0", [
      cell({
        field_name: "contract_no_external",
        label: "合同编号",
        data_type: "string",
        value: "BP-2026-001",
        confidence: 0.92,
        status: "extracted",
        evidence: { page: 1, excerpt: "合同编号：BP-2026-001" },
      }),
      cell({
        field_name: "amount",
        label: "合同金额",
        data_type: "decimal",
        required: true,
        value: 420000,
        display_value: "420000",
        confidence: 0.55,
        status: "low_confidence",
        evidence: { page: 2, excerpt: "合同总金额为人民币肆拾贰万元整" },
      }),
      cell({ field_name: "currency", label: "币种", data_type: "string", value: "CNY", confidence: 0.9, status: "extracted" }),
      cell({
        field_name: "signing_date",
        label: "签约日期",
        data_type: "date",
        required: true,
        status: "missing",
      }),
    ]),
  ],
};

const payments: ReviewTable = {
  table_name: "payments",
  label: "回款计划",
  is_array: true,
  presentation: "table",
  review_step: "finance",
  rows: [
    row("payments:0", [
      cell({ field_name: "payment_type", label: "类型", data_type: "string", value: "预付款", status: "extracted", confidence: 0.85 }),
      cell({
        field_name: "amount",
        label: "金额",
        data_type: "decimal",
        required: true,
        value: 126000,
        display_value: "126000",
        confidence: 0.82,
        status: "extracted",
        evidence: { page: 2, excerpt: "预付款 30%，计人民币 126,000 元" },
      }),
    ]),
    row("payments:1", [
      cell({ field_name: "payment_type", label: "类型", data_type: "string", value: "尾款", status: "extracted", confidence: 0.8 }),
      cell({
        field_name: "amount",
        label: "金额",
        data_type: "decimal",
        required: true,
        status: "missing",
        evidence: { page: 2, excerpt: "尾款于签收后 7 日内支付" },
      }),
    ]),
  ],
};

export const MOCK_REVIEW_DRAFT: ReviewDraft = {
  extraction_id: "demo",
  document_id: "demo-doc",
  schema_version: 1,
  status: "pending_review",
  review_version: 1,
  current_step: "customer",
  document: {
    filename: "邦普采购合同.pdf",
    summary: "一份客户采购合同，涉及石墨匣钵采购与 30/70 分期付款。",
    source_text:
      "采购合同\n甲方：邦普循环科技有限公司\n合同编号：BP-2026-001\n合同总金额为人民币肆拾贰万元整（¥420,000）。\n付款方式：预付款 30%，尾款于签收后 7 日内支付。",
  },
  steps: [
    { key: "customer", label: "客户", table_names: ["customers"], status: "in_progress" },
    { key: "commercial", label: "商业", table_names: ["contracts"], status: "in_progress" },
    { key: "finance", label: "财务", table_names: ["payments"], status: "in_progress" },
    { key: "summary", label: "概要", table_names: [], status: "empty" },
  ],
  tables: [customers, contracts, payments],
  schema_warnings: [],
  general_warnings: ["尾款依赖签收节点，建议确认后设置回款提醒。"],
};

// Local-only patch application for the DEV mock (no autosave round-trip).
export function applyMockReviewPatch(draft: ReviewDraft, patch: ReviewCellPatch): ReviewDraft {
  return {
    ...draft,
    tables: draft.tables.map((t) =>
      t.table_name !== patch.table_name
        ? t
        : {
            ...t,
            rows: t.rows.map((r) =>
              r.client_row_id !== patch.client_row_id
                ? r
                : {
                    ...r,
                    cells: r.cells.map((c) =>
                      c.field_name !== patch.field_name
                        ? c
                        : {
                            ...c,
                            value: patch.value ?? null,
                            display_value: patch.value == null ? "" : String(patch.value),
                            status: patch.status ?? "edited",
                          },
                    ),
                  },
            ),
          },
    ),
  };
}
