// Client-side data export for the 设置 → 数据导出 panel.
//
// No backend or third-party deps: CSV is serialized here (with a UTF-8 BOM
// so Excel reads CJK), JSON is the full customer envelope ("备份"), and
// "PDF" reuses the browser print dialog (Save as PDF) on a printable table.

import type { CustomerDetail } from "../data/types";

const CSV_COLUMNS: { header: string; value: (c: CustomerDetail) => string | number }[] = [
  { header: "客户名称", value: (c) => c.name },
  { header: "简称", value: (c) => c.shortName ?? "" },
  { header: "标签", value: (c) => c.tag ?? "" },
  { header: "税号", value: (c) => c.taxId ?? "" },
  { header: "地址", value: (c) => c.address ?? "" },
  { header: "合同总额", value: (c) => c.metrics?.contractTotal ?? 0 },
  { header: "应收", value: (c) => c.metrics?.receivable ?? 0 },
  { header: "合同数", value: (c) => c.metrics?.contracts ?? 0 },
  { header: "联系人数", value: (c) => c.metrics?.contacts ?? 0 },
  { header: "待办数", value: (c) => c.metrics?.tasks ?? 0 },
  { header: "风险等级", value: (c) => c.risk?.label ?? "" },
  { header: "风险说明", value: (c) => c.risk?.note ?? "" },
  { header: "更新", value: (c) => c.updated ?? "" },
];

function csvCell(v: string | number): string {
  const s = String(v ?? "");
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function customersToCsv(customers: CustomerDetail[]): string {
  const head = CSV_COLUMNS.map((col) => csvCell(col.header)).join(",");
  const rows = customers.map((c) =>
    CSV_COLUMNS.map((col) => csvCell(col.value(c))).join(","),
  );
  // BOM keeps Excel from mangling CJK.
  return "﻿" + [head, ...rows].join("\r\n");
}

/** Trigger a browser download of arbitrary text content. */
export function downloadText(filename: string, mime: string, content: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke on next tick so the download has started.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function todayStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
}

export function exportCustomersCsv(customers: CustomerDetail[]): void {
  downloadText(`客户名单_${todayStamp()}.csv`, "text/csv;charset=utf-8", customersToCsv(customers));
}

export function exportCustomersBackup(customers: CustomerDetail[]): void {
  const payload = {
    exported_at: new Date().toISOString(),
    count: customers.length,
    customers,
  };
  downloadText(
    `客户备份_${todayStamp()}.json`,
    "application/json;charset=utf-8",
    JSON.stringify(payload, null, 2),
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Open a print-friendly window for the customer summary; user saves as PDF. */
export function printCustomers(customers: CustomerDetail[]): boolean {
  const w = window.open("", "_blank", "width=900,height=700");
  if (!w) return false; // popup blocked — caller surfaces a hint
  const rows = customers
    .map((c) => {
      const cells = CSV_COLUMNS.map((col) => `<td>${escapeHtml(String(col.value(c)))}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  const head = CSV_COLUMNS.map((col) => `<th>${escapeHtml(col.header)}</th>`).join("");
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>客户名单</title>
    <style>
      body{font-family:-apple-system,"PingFang SC",sans-serif;color:#15233f;padding:24px;}
      h1{font-size:18px;margin:0 0 4px;} .sub{color:#6b7a90;font-size:12px;margin-bottom:16px;}
      table{border-collapse:collapse;width:100%;font-size:11px;}
      th,td{border:1px solid #d6deea;padding:6px 8px;text-align:left;}
      th{background:#f1f5fb;} tr:nth-child(even) td{background:#fafcff;}
      @media print{button{display:none;}}
    </style></head><body>
    <h1>客户名单 · 智通客户</h1>
    <div class="sub">导出时间 ${escapeHtml(new Date().toLocaleString("zh-CN"))} · 共 ${customers.length} 家</div>
    <button onclick="window.print()" style="margin-bottom:12px;padding:6px 14px;">打印 / 存为 PDF</button>
    <table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>
    </body></html>`);
  w.document.close();
  return true;
}
