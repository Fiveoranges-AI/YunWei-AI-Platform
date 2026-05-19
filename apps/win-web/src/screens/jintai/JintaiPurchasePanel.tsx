import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { purchaseInboxCards, purchaseOrders, suppliers } from "./data";
import type { PurchaseInboxCard, PurchaseOrder, Supplier } from "./data";
import { JintaiSourceCitation, JintaiStatusBadge } from "./components";

export function JintaiPurchasePanel() {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* Section 1: 采购订单列表 */}
      <SectionHeader
        title="本月采购订单"
        sub="6 张已下单 · 总金额 ¥327K · 全部来自 AI 抽取的纸质合同 / 邮件订单，财务确认后入账"
      />
      <PurchaseOrderTable orders={purchaseOrders} />

      {/* Section 2: 供应商档案 */}
      <SectionHeader
        title="主要供应商"
        sub="5 家长期供应商 · 每月采购总额 ¥405K · 账期 30–60 天 · AI 维护账期与质量评分"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop
            ? "repeat(auto-fit, minmax(260px, 1fr))"
            : "1fr",
          gap: 12,
        }}
      >
        {suppliers.map((s) => (
          <SupplierCard key={s.shortName} supplier={s} />
        ))}
      </div>

      {/* Section 3: AI 采购信息收件箱 */}
      <SectionHeader
        title="AI 采购信息收件箱"
        sub="发票 / 合同 / 入库单 AI 自动抽取，财务 + 采购双确认才入账 · 防止重复付款 + 漏入库"
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {purchaseInboxCards.map((c) => (
          <PurchaseInboxCardView key={c.id} card={c} />
        ))}
      </div>
    </div>
  );
}

function SectionHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>{title}</div>
      <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3, lineHeight: 1.55 }}>
        {sub}
      </div>
    </div>
  );
}

/* ---------------- Section 1: 采购订单表 ---------------- */

function PurchaseOrderTable({ orders }: { orders: PurchaseOrder[] }) {
  const isDesktop = useIsDesktop();
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* AI 草稿提示条 */}
      <div
        style={{
          padding: "10px 16px",
          background: "var(--ai-100)",
          borderBottom: "1px solid #bddff3",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          fontSize: 11.5,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontWeight: 700,
            color: "var(--ai-700)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            fontSize: 10.5,
          }}
        >
          {I.spark(11)} AI 草稿
        </span>
        <span style={{ color: "var(--ink-700)" }}>
          智通 AI 已从 6 封邮件合同 / 3 张纸质订单中自动抽取建单
        </span>
        <span
          style={{
            color: "var(--ok-700)",
            fontWeight: 600,
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          {/* iter 14：锦泰绿确认 dot */}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 4,
              background: "var(--jintai-green)",
              flexShrink: 0,
            }}
          />
          ✓ 采购 · 张主管 · 2026-05-17 09:42 复核确认
        </span>
      </div>

      {isDesktop ? (
        <DesktopTable orders={orders} />
      ) : (
        <MobileList orders={orders} />
      )}
    </div>
  );
}

function DesktopTable({ orders }: { orders: PurchaseOrder[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          fontFamily: "var(--font)",
        }}
      >
        <thead>
          <tr style={{ background: "var(--surface-2)" }}>
            <Th>订单号</Th>
            <Th>供应商</Th>
            <Th>物料</Th>
            <Th>规格</Th>
            <Th align="right">数量</Th>
            <Th align="right">单价</Th>
            <Th align="right">金额</Th>
            <Th>交货</Th>
            <Th>状态</Th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.poNo} style={{ borderTop: "1px solid var(--ink-100)" }}>
              <Td mono>{o.poNo}</Td>
              <Td>{o.supplier}</Td>
              <Td bold>{o.material}</Td>
              <Td mono>{o.spec}</Td>
              <Td align="right" mono>{o.qty}</Td>
              <Td align="right" mono>{o.unitPrice}</Td>
              <Td align="right" mono bold>{o.amount}</Td>
              <Td mono>{o.deliveryDate}</Td>
              <Td>
                <JintaiStatusBadge status={o.status} />
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MobileList({ orders }: { orders: PurchaseOrder[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {orders.map((o) => (
        <div
          key={o.poNo}
          style={{
            padding: 14,
            borderTop: "1px solid var(--ink-100)",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)" }}>
              {o.material}
            </span>
            <JintaiStatusBadge status={o.status} />
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
            <span style={{ fontFamily: "ui-monospace, monospace" }}>{o.poNo}</span> · {o.supplier}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-700)", marginTop: 2 }}>
            {o.qty} · {o.unitPrice} · <strong>{o.amount}</strong> · 交 {o.deliveryDate}
          </div>
        </div>
      ))}
    </div>
  );
}

function Th({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right";
}) {
  return (
    <th
      style={{
        padding: "10px 14px",
        textAlign: align ?? "left",
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-500)",
        letterSpacing: "0.04em",
        textTransform: "uppercase",
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align,
  mono,
  bold,
}: {
  children: React.ReactNode;
  align?: "right";
  mono?: boolean;
  bold?: boolean;
}) {
  return (
    <td
      style={{
        padding: "10px 14px",
        textAlign: align ?? "left",
        color: bold ? "var(--ink-900)" : "var(--ink-800)",
        fontFamily: mono ? "ui-monospace, monospace" : "var(--font)",
        fontWeight: bold ? 700 : 500,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {children}
    </td>
  );
}

/* ---------------- Section 2: 供应商卡片 ---------------- */

function SupplierCard({ supplier }: { supplier: Supplier }) {
  return (
    <div className="card-flat" style={{ padding: 14, borderRadius: 12 }}>
      <div
        style={{
          fontSize: 13.5,
          fontWeight: 700,
          color: "var(--ink-900)",
          marginBottom: 3,
        }}
      >
        {supplier.shortName}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 10 }}>
        {supplier.fullName}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 4,
          fontSize: 12,
          color: "var(--ink-700)",
        }}
      >
        <Row k="主要品类" v={supplier.category} />
        <Row k="月均采购" v={supplier.monthlySpend} bold />
        <Row k="账期" v={supplier.paymentTerm} />
      </div>
      <div
        style={{
          marginTop: 10,
          paddingTop: 10,
          borderTop: "1px dashed var(--ink-100)",
          fontSize: 11,
          color: "var(--ai-700)",
          lineHeight: 1.55,
        }}
      >
        <span style={{ fontWeight: 700, marginRight: 4 }}>AI 备注：</span>
        {supplier.trustNote}
      </div>
    </div>
  );
}

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
      <span style={{ color: "var(--ink-500)" }}>{k}</span>
      <span
        style={{
          color: "var(--ink-900)",
          fontWeight: bold ? 700 : 500,
          textAlign: "right",
        }}
      >
        {v}
      </span>
    </div>
  );
}

/* ---------------- Section 3: AI 采购收件箱卡片 ---------------- */

const KIND_META: Record<
  PurchaseInboxCard["kind"],
  { bg: string; fg: string; icon: string }
> = {
  采购发票: { bg: "var(--ai-100)", fg: "var(--ai-700)", icon: "🧾" },
  采购合同: { bg: "var(--brand-100)", fg: "var(--brand-700)", icon: "📄" },
  字段缺失: { bg: "var(--warn-100)", fg: "var(--warn-700)", icon: "⚠️" },
};

function PurchaseInboxCardView({ card }: { card: PurchaseInboxCard }) {
  const meta = KIND_META[card.kind];
  const isMissing = card.kind === "字段缺失";
  return (
    <div
      className="card"
      style={{
        padding: 16,
        borderLeft: `3px solid ${isMissing ? "var(--warn-500)" : "var(--ai-500)"}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <span
          className="pill"
          style={{
            background: meta.bg,
            color: meta.fg,
            fontSize: 11,
            fontWeight: 600,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span>{meta.icon}</span> {card.kind}
        </span>
        <span style={{ fontSize: 11.5, color: "var(--ink-800)", fontWeight: 600 }}>
          {card.source}
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-400)", marginLeft: "auto" }}>
          {card.uploadedAt}
        </span>
      </div>

      <div
        style={{
          fontSize: 12.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
          marginBottom: 12,
        }}
      >
        {card.aiSummary}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 6,
          marginBottom: 12,
        }}
      >
        {card.fields.map((f) => {
          const missing = f.value.includes("未识别");
          return (
            <div
              key={f.key}
              style={{
                padding: "8px 10px",
                borderRadius: 8,
                background: missing ? "var(--warn-100)" : "var(--surface-2)",
                border: missing ? "1px solid #f1d4a6" : "1px solid var(--ink-100)",
                fontSize: 11.5,
                lineHeight: 1.4,
              }}
            >
              <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600 }}>
                {f.key}
              </div>
              <div
                style={{
                  color: missing ? "var(--warn-700)" : "var(--ink-900)",
                  fontWeight: 600,
                  marginTop: 2,
                  fontFamily:
                    /\d/.test(f.value) && !f.key.includes("货物") && !f.key.includes("供应商")
                      ? "ui-monospace, monospace"
                      : undefined,
                }}
              >
                {f.value}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          padding: "10px 12px",
          borderRadius: 8,
          background: isMissing ? "var(--warn-100)" : "var(--ai-100)",
          border: isMissing ? "1px solid #f1d4a6" : "1px solid #bddff3",
          fontSize: 12,
          color: isMissing ? "var(--warn-700)" : "var(--ai-700)",
          lineHeight: 1.55,
          marginBottom: 10,
        }}
      >
        <span style={{ fontWeight: 700 }}>建议动作：</span>
        {card.suggestedAction.replace(/^建议[：:]\s?/, "")}
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <button
          className="pill"
          style={{
            background: "var(--brand-500)",
            color: "#fff",
            border: "none",
            padding: "6px 14px",
            fontSize: 11.5,
            fontWeight: 600,
            cursor: "pointer",
            borderRadius: 6,
          }}
        >
          {isMissing ? "补充字段" : "确认入账"}
        </button>
        <button
          className="pill"
          style={{
            background: "var(--surface-2)",
            color: "var(--ink-700)",
            border: "1px solid var(--ink-200)",
            padding: "6px 14px",
            fontSize: 11.5,
            fontWeight: 500,
            cursor: "pointer",
            borderRadius: 6,
          }}
        >
          驳回
        </button>
        <JintaiSourceCitation source={{ kind: "合同", label: card.source }} />
      </div>
    </div>
  );
}
