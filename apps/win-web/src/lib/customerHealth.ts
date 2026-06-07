// Per-customer 资料完整度 (data health) — the docx's 数据健康度: instead of
// forcing long required forms, score how complete a customer's high-value
// fields are and show what's still missing, so the owner can fill gaps when it
// matters. Pure, derived from the customer record the UI already has.

import type { CustomerDetail } from "../data/types";

export type HealthField = { key: string; label: string; filled: boolean };
export type CustomerHealth = {
  score: number; // 0..100
  filled: number;
  total: number;
  fields: HealthField[];
  missing: HealthField[];
};

function hasContactPhone(c: CustomerDetail): boolean {
  return Boolean(
    c.contacts?.some((p) => (p.phone && p.phone.trim()) || (p.mobile && p.mobile.trim())),
  );
}

export function customerCompleteness(c: CustomerDetail): CustomerHealth {
  const m = c.metrics;
  const fields: HealthField[] = [
    { key: "industry", label: "行业", filled: Boolean(c.industry && c.industry.trim()) },
    { key: "address", label: "地址", filled: Boolean(c.address && c.address.trim()) },
    { key: "contacts", label: "联系人", filled: (m?.contacts ?? 0) > 0 },
    { key: "phone", label: "联系电话", filled: hasContactPhone(c) },
    {
      key: "contract",
      label: "合同",
      filled: (m?.contracts ?? 0) > 0 || Boolean(c.contracts && c.contracts.length),
    },
    {
      key: "followup",
      label: "最近跟进",
      filled:
        (m?.tasks ?? 0) > 0 ||
        Boolean(c.tasks && c.tasks.length) ||
        Boolean(c.timeline && c.timeline.length),
    },
  ];
  const filled = fields.filter((f) => f.filled).length;
  const total = fields.length;
  return {
    score: total ? Math.round((filled / total) * 100) : 100,
    filled,
    total,
    fields,
    missing: fields.filter((f) => !f.filled),
  };
}
