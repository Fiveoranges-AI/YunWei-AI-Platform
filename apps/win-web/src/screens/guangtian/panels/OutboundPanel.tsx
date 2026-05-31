import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { outboundAiAlerts } from "../data";
import { useGT } from "../state";
import { Spinner } from "../Toast";

const OUTBOUND_TYPES = ["销售出库", "样品出库", "退货退厂", "其他"];

const SKU_OPTIONS = [
  { code: "JT-JZL-JC16",       name: "浇注料 JC-16",      unit: "袋" },
  { code: "JT-HLZ-230-114-65", name: "高铝砖（标准型）",  unit: "块" },
  { code: "JT-MLS-M70",        name: "莫来石砖 M70",      unit: "块" },
  { code: "JT-GZB-AL80",       name: "刚玉砖 AL80",       unit: "块" },
  { code: "JT-JZL-JC18-LR",    name: "低水泥浇注料",      unit: "袋" },
  { code: "JT-HLZ-T3-150",     name: "高铝砖 T3 异型",    unit: "块" },
];

const ORDER_OPTIONS = [
  { id: "SO-20260519-001", customer: "江苏宏泰工程有限公司" },
  { id: "SO-20260519-002", customer: "江苏宏泰工程有限公司" },
  { id: "SO-20260519-003", customer: "常州新材科技有限公司" },
  { id: "SO-20260518-007", customer: "宜兴华能材料" },
];

export function OutboundPanel() {
  const isDesktop = useIsDesktop();
  const { skuStocks, outboundRecords, addOutbound, showToast } = useGT();
  const [sku, setSku] = useState("JT-JZL-JC16");
  const [qty, setQty] = useState(200);
  const [unit, setUnit] = useState("袋");
  const [showMore, setShowMore] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [orderId, setOrderId] = useState(ORDER_OPTIONS[0].id);
  const [type, setType] = useState(OUTBOUND_TYPES[0]);
  const [op, setOp] = useState("张仓管");

  const currentStock = skuStocks[sku] ?? 0;
  const shortage = qty > currentStock;
  const selectedOrder = ORDER_OPTIONS.find((o) => o.id === orderId) ?? ORDER_OPTIONS[0];
  const selectedSku = SKU_OPTIONS.find((s) => s.code === sku) ?? SKU_OPTIONS[0];

  const onSkuChange = (code: string) => {
    setSku(code);
    const s = SKU_OPTIONS.find((x) => x.code === code);
    if (s) setUnit(s.unit);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (shortage || !qty || qty <= 0) return;
    setSubmitting(true);
    window.setTimeout(() => {
      addOutbound({
        sku,
        name: selectedSku.name,
        qty,
        unit,
        customer: selectedOrder.customer,
        order: orderId,
        op,
      });
      setSubmitting(false);
    }, 700);
  };

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
        <form className="card" style={{ padding: "16px 18px" }} onSubmit={onSubmit}>
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
              <select value={orderId} onChange={(e) => setOrderId(e.target.value)} style={SELECT}>
                {ORDER_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.id} · {o.customer}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="出库类型 *">
              <select value={type} onChange={(e) => setType(e.target.value)} style={SELECT}>
                {OUTBOUND_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="SKU *">
              <select value={sku} onChange={(e) => onSkuChange(e.target.value)} style={SELECT}>
                {SKU_OPTIONS.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.code} · {s.name} (库存 {(skuStocks[s.code] ?? 0).toLocaleString()})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="出库数量 *">
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  type="number"
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value) || 0)}
                  style={{ ...INPUT, flex: 1, borderColor: shortage ? "var(--guangtian-red)" : "var(--ink-200)" }}
                  min={1}
                />
                <select value={unit} onChange={(e) => setUnit(e.target.value)} style={{ ...SELECT, width: 80, flex: "none" }}>
                  <option>袋</option>
                  <option>块</option>
                  <option>吨</option>
                </select>
              </div>
              <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 3 }}>
                当前库存：<strong>{currentStock.toLocaleString()}</strong>
                {!shortage && qty > 0 && (
                  <>
                    {" · 出库后剩 "}
                    <strong style={{ color: "var(--stock-ok)" }}>{(currentStock - qty).toLocaleString()}</strong>
                  </>
                )}
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
                  <select value={op} onChange={(e) => setOp(e.target.value)} style={SELECT}>
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
                  <button
                    type="button"
                    style={MINI_BTN_BLUE}
                    onClick={() => {
                      if (currentStock > 0) {
                        setQty(currentStock);
                      }
                    }}
                  >
                    分批出库（先出 {currentStock.toLocaleString()}）
                  </button>
                  <button
                    type="button"
                    style={MINI_BTN_PURPLE}
                    onClick={() =>
                      showToast(
                        `✓ 已为 ${selectedSku.name} 触发补产 ${qty * 2} ${unit} (5/22 出炉)`,
                        "ok",
                      )
                    }
                  >
                    触发补产单
                  </button>
                  <button
                    type="button"
                    style={MINI_BTN_GHOST}
                    onClick={() =>
                      showToast(`已起草延期通知 · 待发 ${selectedOrder.customer}`, "info")
                    }
                  >
                    联系客户
                  </button>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <button
              type="submit"
              disabled={shortage || submitting || qty <= 0}
              style={{
                padding: "9px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 8,
                border: "none",
                background: shortage ? "var(--ink-200)" : submitting ? "var(--brand-400)" : "var(--guangtian-blue)",
                color: "#fff",
                cursor: shortage ? "not-allowed" : submitting ? "wait" : "pointer",
                fontFamily: "var(--font)",
                boxShadow: shortage ? "none" : "0 3px 10px rgba(26,63,142,0.22)",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                minWidth: 130,
                justifyContent: "center",
              }}
            >
              {submitting ? (
                <>
                  <Spinner size={12} color="#fff" />
                  AI 校验中…
                </>
              ) : (
                <>✓ 确认出库</>
              )}
            </button>
            <button
              type="reset"
              onClick={() => setQty(0)}
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
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>近 3 笔 · 共 {outboundRecords.length} 笔</span>
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
                {outboundRecords.slice(0, 3).map((r, i) => (
                  <tr key={`${r.time}-${r.sku}-${i}`} style={{ borderTop: "1px solid var(--ink-50)" }}>
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
