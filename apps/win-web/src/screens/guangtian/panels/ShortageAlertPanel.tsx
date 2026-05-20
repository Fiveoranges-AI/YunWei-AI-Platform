import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { shortageOrders } from "../data";
import { useGT } from "../state";

const LEVEL_META: Record<
  "high" | "medium" | "low",
  { label: string; bg: string; color: string; border: string; emoji: string }
> = {
  high:   { label: "高风险", bg: "rgba(217,32,32,0.06)",  color: "var(--guangtian-red)", border: "rgba(217,32,32,0.30)", emoji: "🔴" },
  medium: { label: "中风险", bg: "rgba(245,158,11,0.06)", color: "var(--stock-low)",      border: "rgba(245,158,11,0.30)", emoji: "🟡" },
  low:    { label: "可发", bg: "rgba(27,127,58,0.06)",  color: "var(--stock-ok)",       border: "rgba(27,127,58,0.30)", emoji: "🟢" },
};

export function ShortageAlertPanel() {
  const isDesktop = useIsDesktop();
  const { showToast } = useGT();
  // iter G9: 默认全部折叠（行内已显示风险 + 客户 + 金额），点击展开详情
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const hi = shortageOrders.filter((o) => o.level === "high").length;
  const mid = shortageOrders.filter((o) => o.level === "medium").length;
  const lo = shortageOrders.filter((o) => o.level === "low").length;

  return (
    <div>
      {/* 顶部摘要 */}
      <div
        className="card"
        style={{
          padding: "12px 16px",
          marginBottom: 14,
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 12.5, color: "var(--ink-700)", fontWeight: 600 }}>
          📊 本周（5/19 – 5/25）<strong>{shortageOrders.length}</strong> 笔订单已过 AI 缺货核对：
        </span>
        <Pill color="var(--guangtian-red)" bg="rgba(217,32,32,0.10)">🔴 高风险 {hi}</Pill>
        <Pill color="var(--stock-low)" bg="rgba(245,158,11,0.10)">🟡 中风险 {mid}</Pill>
        <Pill color="var(--stock-ok)" bg="rgba(27,127,58,0.10)">🟢 可发 {lo}</Pill>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-400)" }}>
          AI 已于 10:18 完成最新核对
        </span>
      </div>

      {/* 订单卡片 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {shortageOrders.map((order) => {
          const meta = LEVEL_META[order.level];
          const isOpen = openIds.has(order.id);
          return (
            <div
              key={order.id}
              className="card"
              style={{
                padding: 0,
                borderLeft: `3px solid ${meta.color}`,
                overflow: "hidden",
              }}
            >
              {/* 订单标题行 */}
              <button
                onClick={() => toggle(order.id)}
                style={{
                  width: "100%",
                  padding: "13px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "var(--font)",
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    padding: "3px 9px",
                    borderRadius: 5,
                    background: meta.color,
                    color: "#fff",
                  }}
                >
                  {meta.label}
                </span>
                <span style={{ fontFamily: "var(--font-mono, var(--font))", fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)" }}>
                  {order.id}
                </span>
                <span style={{ fontSize: 12.5, color: "var(--ink-700)" }}>{order.customer}</span>
                <span style={{ fontSize: 11.5, color: "var(--ink-500)" }}>· 交付 {order.deliveryDate}</span>
                {/* iter G9: 行内带 1 行 AI 建议摘要 */}
                {!isOpen && order.level !== "low" && (
                  <span
                    style={{
                      flex: "1 1 100%",
                      fontSize: 11.5,
                      color: "var(--ink-500)",
                      paddingLeft: 48,
                      paddingTop: 4,
                      lineHeight: 1.5,
                    }}
                  >
                    {order.aiSuggestion.split("。")[0]}。
                  </span>
                )}
                <span style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--ink-700)", fontWeight: 600 }}>
                  {order.totalValue}
                </span>
                <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
                  {isOpen ? "收起 ▾" : "展开 ▸"}
                </span>
              </button>

              {/* 展开内容 */}
              {isOpen && (
                <div
                  style={{
                    padding: "0 16px 16px",
                    display: "grid",
                    gridTemplateColumns: isDesktop ? "1.4fr 1fr" : "1fr",
                    gap: 14,
                  }}
                >
                  {/* SKU 明细表 */}
                  <div>
                    <h4 style={{ margin: "0 0 8px", fontSize: 12, fontWeight: 700, color: "var(--ink-700)" }}>
                      订单 SKU 明细 · 库存对比
                    </h4>
                    <div style={{ border: "1px solid var(--ink-100)", borderRadius: 8, overflow: "hidden" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
                        <thead style={{ background: "var(--surface-2)" }}>
                          <tr>
                            <th style={ITEM_TH}>SKU</th>
                            <th style={ITEM_TH}>产品</th>
                            <th style={{ ...ITEM_TH, textAlign: "right" }}>需求</th>
                            <th style={{ ...ITEM_TH, textAlign: "right" }}>现库存</th>
                            <th style={{ ...ITEM_TH, textAlign: "right" }}>缺口</th>
                          </tr>
                        </thead>
                        <tbody>
                          {order.items.map((it) => (
                            <tr key={it.sku} style={{ borderTop: "1px solid var(--ink-50)" }}>
                              <td style={{ ...ITEM_TD, fontFamily: "var(--font-mono, var(--font))" }}>{it.sku}</td>
                              <td style={ITEM_TD}>{it.name}</td>
                              <td style={{ ...ITEM_TD, textAlign: "right" }}>{it.needed} {it.unit}</td>
                              <td style={{ ...ITEM_TD, textAlign: "right" }}>{it.stock.toLocaleString()}</td>
                              <td
                                style={{
                                  ...ITEM_TD,
                                  textAlign: "right",
                                  color: it.gap > 0 ? "var(--guangtian-red)" : "var(--stock-ok)",
                                  fontWeight: 700,
                                }}
                              >
                                {it.gap > 0 ? `缺 ${it.gap}` : "✓"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* AI 建议 */}
                  <div
                    style={{
                      padding: "12px 14px",
                      background: meta.bg,
                      border: `1px solid ${meta.border}`,
                      borderRadius: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                      {I.spark(13, meta.color)}
                      <span style={{ fontSize: 11.5, fontWeight: 700, color: meta.color, letterSpacing: "0.02em" }}>
                        AI 处理建议
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.65 }}>
                      {order.aiSuggestion}
                    </div>
                    <div style={{ marginTop: 9, display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button
                        style={ACTION_PRIMARY}
                        onClick={() => showToast(`✓ 已采纳 · 已为 ${order.id} 生成补产单 + 通知工艺组`, "ok")}
                      >
                        采纳建议 · 生成补产单
                      </button>
                      <button
                        style={ACTION_GHOST}
                        onClick={() => showToast(`已为 ${order.customer} 起草延期通知短信 · 待人工审核`, "info")}
                      >
                        联系客户
                      </button>
                      <button
                        style={ACTION_GHOST}
                        onClick={() => showToast(`${order.customer} 过去 90 天出货 12 笔 · 详情已弹出`, "info")}
                      >
                        查看历史出货
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Pill({ children, color, bg }: { children: React.ReactNode; color: string; bg: string }) {
  return (
    <span
      style={{
        padding: "3px 10px",
        fontSize: 12,
        fontWeight: 700,
        borderRadius: 5,
        background: bg,
        color,
      }}
    >
      {children}
    </span>
  );
}

const ITEM_TH: React.CSSProperties = {
  padding: "7px 10px",
  fontSize: 10.5,
  fontWeight: 700,
  color: "var(--ink-600)",
  textAlign: "left",
};
const ITEM_TD: React.CSSProperties = {
  padding: "7px 10px",
  fontSize: 11.5,
  color: "var(--ink-800)",
};

const ACTION_PRIMARY: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 11.5,
  fontWeight: 600,
  borderRadius: 6,
  border: "none",
  background: "var(--ai-purple)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

const ACTION_GHOST: React.CSSProperties = {
  padding: "6px 12px",
  fontSize: 11.5,
  fontWeight: 500,
  borderRadius: 6,
  border: "1px solid var(--ink-200)",
  background: "#fff",
  color: "var(--ink-700)",
  cursor: "pointer",
  fontFamily: "var(--font)",
};
