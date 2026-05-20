import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { recentOutbounds, outboundAiAlerts } from "../data";

const OUTBOUND_TYPES = ["销售出库", "样品出库", "退货退厂", "其他"];

export function OutboundPanel() {
  const isDesktop = useIsDesktop();
  const [sku, setSku] = useState("JT-JZL-JC16");
  const [qty, setQty] = useState(200);
  const [showMore, setShowMore] = useState(false); // iter G9

  // 模拟库存 vs 出货数对比
  const skuStock: Record<string, number> = {
    "JT-JZL-JC16": 0,
    "JT-HLZ-230-114-65": 4280,
    "JT-MLS-M70": 320,
    "JT-GZB-AL80": 1850,
  };
  const currentStock = skuStock[sku] ?? 0;
  const shortage = qty > currentStock;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: isDesktop ? "1.4fr 1fr" : "1fr",
        gap: 16,
      }}
    >
      {/* 左：表单 + 最近记录 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* 表单 */}
        <form className="card" style={{ padding: "16px 18px" }} onSubmit={(e) => e.preventDefault()}>
          <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span
              style={{
                width: 26,
                height: 26,
                borderRadius: 7,
                background: "rgba(26,63,142,0.10)",
                color: "var(--guangtian-blue)",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {I.upload(14, "var(--guangtian-blue)")}
            </span>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
              新建出库登记
            </h3>
          </header>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: isDesktop ? "repeat(2, 1fr)" : "1fr",
              gap: 12,
            }}
          >
            <Field label="客户订单 *">
              <select defaultValue="SO-20260519-001" style={SELECT}>
                <option>SO-20260519-001 · 江苏宏泰工程</option>
                <option>SO-20260519-002 · 江苏宏泰工程</option>
                <option>SO-20260519-003 · 常州新材科技</option>
                <option>SO-20260518-007 · 宜兴华能材料</option>
              </select>
            </Field>
            <Field label="出库类型 *">
              <select defaultValue="销售出库" style={SELECT}>
                {OUTBOUND_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="SKU *">
              <select
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                style={SELECT}
              >
                <option value="JT-JZL-JC16">JT-JZL-JC16 · 浇注料 JC-16 (库存 0)</option>
                <option value="JT-HLZ-230-114-65">JT-HLZ-230-114-65 · 高铝砖 (库存 4,280)</option>
                <option value="JT-MLS-M70">JT-MLS-M70 · 莫来石砖 (库存 320)</option>
                <option value="JT-GZB-AL80">JT-GZB-AL80 · 刚玉砖 (库存 1,850)</option>
              </select>
            </Field>
            <Field label="出库数量 *">
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  type="number"
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value))}
                  style={{ ...INPUT, flex: 1 }}
                />
                <select defaultValue="袋" style={{ ...SELECT, width: 80, flex: "none" }}>
                  <option>袋</option>
                  <option>块</option>
                  <option>吨</option>
                </select>
              </div>
              <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 3 }}>
                当前库存：<strong>{currentStock.toLocaleString()}</strong>
              </div>
            </Field>
            {showMore && (
              <>
                <Field label="库位">
                  <select defaultValue="B-02" style={SELECT}>
                    <option>B-02 (浇注料区)</option>
                    <option>A-03 (高铝砖区)</option>
                    <option>A-05 (莫来石区)</option>
                    <option>C-01 (刚玉砖区)</option>
                  </select>
                </Field>
                <Field label="批次（先进先出推荐）">
                  <input type="text" defaultValue="P20260515-03" style={INPUT} />
                </Field>
                <Field label="承运 / 物流">
                  <input type="text" defaultValue="德邦物流 · 整车" style={INPUT} />
                </Field>
                <Field label="操作人">
                  <select defaultValue="张仓管" style={SELECT}>
                    <option>张仓管</option>
                    <option>李师傅</option>
                    <option>王主管</option>
                  </select>
                </Field>
              </>
            )}
          </div>

          {/* iter G9: 折叠按钮 */}
          <button
            type="button"
            onClick={() => setShowMore((v) => !v)}
            style={{
              marginTop: 12,
              padding: "5px 11px",
              fontSize: 11.5,
              fontWeight: 600,
              borderRadius: 6,
              border: "1px solid var(--ink-100)",
              background: "transparent",
              color: "var(--ink-600)",
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            {showMore ? "收起更多字段 ▾" : "更多字段（库位 / 批次 / 物流 / 操作人 / 备注）▸"}
          </button>
          {showMore && (
            <Field label="备注" full>
              <textarea
                rows={2}
                defaultValue=""
                placeholder="客户对接人、特殊要求等"
                style={{
                  ...INPUT,
                  width: "100%",
                  resize: "vertical",
                  minHeight: 50,
                  fontFamily: "var(--font)",
                }}
              />
            </Field>
          )}

          {/* 库存不足红色警告 */}
          {shortage && (
            <div
              style={{
                marginTop: 12,
                padding: "12px 14px",
                background: "rgba(195,38,41,0.06)",
                border: "1px solid rgba(195,38,41,0.28)",
                borderRadius: 8,
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <span
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: 7,
                  background: "var(--guangtian-red)",
                  color: "#fff",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  fontWeight: 700,
                }}
              >
                ⚠
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--guangtian-red)", marginBottom: 4 }}>
                  库存不足 · 无法完整出库
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>
                  出库 {qty.toLocaleString()} 袋，当前库存仅 {currentStock.toLocaleString()} 袋，缺口 {(qty - currentStock).toLocaleString()} 袋。
                  <br />
                  AI 建议：① 改为分批出库（先出 {currentStock.toLocaleString()} 袋，剩余等补产）；② 同时触发补产单
                  {qty * 2} 袋（5 月 22 日出炉）；③ 提前通知客户江苏宏泰工程预期延期 3 天。
                </div>
                <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button type="button" style={MINI_BTN_BLUE}>分批出库</button>
                  <button type="button" style={MINI_BTN_PURPLE}>触发补产单</button>
                  <button type="button" style={MINI_BTN_GHOST}>联系客户</button>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <button
              type="submit"
              disabled={shortage}
              style={{
                padding: "9px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 8,
                border: "none",
                background: shortage ? "var(--ink-200)" : "var(--guangtian-blue)",
                color: "#fff",
                cursor: shortage ? "not-allowed" : "pointer",
                fontFamily: "var(--font)",
                boxShadow: shortage ? "none" : "0 3px 10px rgba(26,63,142,0.22)",
              }}
            >
              ✓ 确认出库
            </button>
            <button
              type="reset"
              style={{
                padding: "9px 14px",
                fontSize: 12.5,
                fontWeight: 500,
                borderRadius: 8,
                border: "1px solid var(--ink-200)",
                background: "#fff",
                color: "var(--ink-600)",
                cursor: "pointer",
                fontFamily: "var(--font)",
              }}
            >
              重置
            </button>
          </div>
        </form>

        {/* 最近出库记录 */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <header
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--ink-100)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)" }}>
              最近出库记录
            </h3>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>近 3 笔 · <a href="#" style={{ color: "var(--brand-700)", textDecoration: "none" }}>查看全部 →</a></span>
          </header>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 12,
                minWidth: 720,
              }}
            >
              <thead style={{ background: "var(--surface-2)" }}>
                <tr>
                  {["时间", "SKU", "产品", "数量", "客户", "订单", "状态"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "8px 12px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--ink-600)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentOutbounds.slice(0, 3).map((r, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--ink-50)" }}>
                    <td style={CELL_MONO}>{r.time}</td>
                    <td style={CELL_MONO}>{r.sku}</td>
                    <td style={CELL}>{r.name}</td>
                    <td style={{ ...CELL, color: r.status === "库存不足" ? "var(--guangtian-red)" : "var(--guangtian-blue)", fontWeight: 700 }}>{r.qty}</td>
                    <td style={CELL}>{r.customer}</td>
                    <td style={CELL_MONO}>{r.order}</td>
                    <td style={CELL}>
                      <OutboundStatusBadge status={r.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 右：AI 缺货风险提示 */}
      <div
        className="card"
        style={{
          padding: "16px 18px",
          background: "linear-gradient(180deg, #FFF5F5 0%, #FFFFFF 60%)",
          borderLeft: "3px solid var(--guangtian-red)",
          alignSelf: "flex-start",
          position: "sticky",
          top: 12,
        }}
      >
        <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: 7,
              background: "rgba(217,32,32,0.10)",
              color: "var(--guangtian-red)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.warn(14, "var(--guangtian-red)")}
          </span>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
            AI 出货风险提示
          </h3>
        </header>
        <p style={{ margin: "0 0 12px", fontSize: 11.5, color: "var(--ink-500)", lineHeight: 1.5 }}>
          AI 实时核对订单需求 vs 库存，缺货 / 部分出库 / 安全线警告即时弹出。
        </p>
        {/* iter G9: 2 → 1 最严重风险 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {outboundAiAlerts.slice(0, 1).map((a, i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                borderRadius: 8,
                background: a.level === "danger" ? "rgba(217,32,32,0.06)" : "rgba(245,158,11,0.06)",
                border: a.level === "danger" ? "1px solid rgba(217,32,32,0.22)" : "1px solid rgba(245,158,11,0.22)",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  marginBottom: 4,
                  color: a.level === "danger" ? "var(--guangtian-red)" : "var(--stock-low)",
                  letterSpacing: "0.02em",
                }}
              >
                {a.level === "danger" ? "🔴 高风险" : "🟡 关注"}
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 3 }}>
                {a.title}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.55 }}>{a.body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function OutboundStatusBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    已出库: { color: "var(--stock-ok)", bg: "rgba(27,127,58,0.10)" },
    部分出库: { color: "var(--stock-low)", bg: "rgba(245,158,11,0.10)" },
    库存不足: { color: "var(--guangtian-red)", bg: "rgba(217,32,32,0.10)" },
  };
  const s = map[status] ?? map["已出库"];
  return (
    <span
      style={{
        padding: "2px 7px",
        fontSize: 10.5,
        fontWeight: 700,
        borderRadius: 4,
        background: s.bg,
        color: s.color,
      }}
    >
      {status}
    </span>
  );
}

const INPUT: React.CSSProperties = {
  padding: "7px 10px",
  fontSize: 12.5,
  border: "1px solid var(--ink-200)",
  borderRadius: 7,
  outline: "none",
  background: "#fff",
  fontFamily: "var(--font)",
  color: "var(--ink-800)",
};

const SELECT: React.CSSProperties = {
  ...INPUT,
  width: "100%",
  cursor: "pointer",
};

const CELL: React.CSSProperties = {
  padding: "8px 12px",
  fontSize: 11.5,
  color: "var(--ink-800)",
  whiteSpace: "nowrap",
  textAlign: "left",
};

const CELL_MONO: React.CSSProperties = {
  ...CELL,
  fontFamily: "var(--font-mono, var(--font))",
};

const MINI_BTN_BLUE: React.CSSProperties = {
  padding: "5px 11px",
  fontSize: 11.5,
  fontWeight: 600,
  borderRadius: 6,
  border: "none",
  background: "var(--guangtian-blue)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

const MINI_BTN_PURPLE: React.CSSProperties = {
  ...MINI_BTN_BLUE,
  background: "var(--ai-purple)",
};

const MINI_BTN_GHOST: React.CSSProperties = {
  padding: "5px 11px",
  fontSize: 11.5,
  fontWeight: 500,
  borderRadius: 6,
  border: "1px solid var(--ink-200)",
  background: "#fff",
  color: "var(--ink-700)",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

function Field({
  label,
  children,
  full = false,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5, gridColumn: full ? "1 / -1" : undefined, marginTop: full ? 10 : 0 }}>
      <label style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-600)" }}>{label}</label>
      {children}
    </div>
  );
}
