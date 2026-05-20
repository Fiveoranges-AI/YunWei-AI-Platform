import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { ledgerRows, ledgerAiAnomalies } from "../data";

const OP_COLORS: Record<string, { color: string; bg: string }> = {
  入库: { color: "var(--stock-ok)", bg: "rgba(27,127,58,0.10)" },
  出库: { color: "var(--guangtian-blue)", bg: "rgba(26,63,142,0.10)" },
  调拨: { color: "var(--ai-purple-deep)", bg: "rgba(123,92,250,0.10)" },
  盘点: { color: "var(--stock-low)", bg: "rgba(245,158,11,0.10)" },
  报废: { color: "var(--guangtian-red)", bg: "rgba(217,32,32,0.10)" },
  退货: { color: "var(--ink-600)", bg: "var(--surface-2)" },
};

export function LedgerPanel() {
  const isDesktop = useIsDesktop();
  const [opFilter, setOpFilter] = useState<string>("全部");
  const [skuFilter, setSkuFilter] = useState<string>("");

  const filtered = ledgerRows.filter((r) => {
    if (opFilter !== "全部" && r.op !== opFilter) return false;
    if (skuFilter && !r.sku.includes(skuFilter) && !r.name.includes(skuFilter)) return false;
    return true;
  });

  return (
    <div>
      {/* 筛选 */}
      <div
        className="card"
        style={{
          padding: "12px 14px",
          marginBottom: 14,
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
        }}
      >
        <FilterPills
          label="操作"
          options={["全部", "入库", "出库", "调拨", "盘点", "报废", "退货"]}
          value={opFilter}
          onChange={setOpFilter}
        />
        <span style={{ width: 1, height: 22, background: "var(--ink-100)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 180 }}>
          <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>SKU / 产品</span>
          <input
            type="text"
            placeholder="按 SKU 或产品名搜索"
            value={skuFilter}
            onChange={(e) => setSkuFilter(e.target.value)}
            style={{
              flex: 1,
              padding: "6px 10px",
              fontSize: 12,
              border: "1px solid var(--ink-200)",
              borderRadius: 7,
              outline: "none",
              fontFamily: "var(--font)",
            }}
          />
        </div>
        <span style={{ width: 1, height: 22, background: "var(--ink-100)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>日期</span>
          <input type="date" defaultValue="2026-05-19" style={SMALL_INPUT} />
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>~</span>
          <input type="date" defaultValue="2026-05-19" style={SMALL_INPUT} />
        </div>
        <button
          style={{
            padding: "6px 13px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 7,
            border: "1px solid var(--ink-200)",
            background: "#fff",
            color: "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          导出 Excel
        </button>
      </div>

      {/* 表格 */}
      <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: 14 }}>
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              minWidth: isDesktop ? 1080 : 900,
            }}
          >
            {/* iter G9: 列 10 → 7（合并操作前后为 "前→后"，合并操作人入备注，去掉单独备注列） */}
            <thead style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--ink-100)" }}>
              <tr>
                {["时间", "操作", "SKU", "产品", "变动", "前→后", "关联单据 / 操作人"].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: "10px 12px",
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
              {filtered.map((r, i) => {
                const opStyle = OP_COLORS[r.op] ?? OP_COLORS["入库"];
                const deltaColor =
                  r.delta === "—"
                    ? "var(--ink-500)"
                    : r.delta.startsWith("+")
                    ? "var(--stock-ok)"
                    : "var(--guangtian-red)";
                return (
                  <tr key={i} style={{ borderTop: "1px solid var(--ink-50)" }}>
                    <td style={CELL_MONO}>{r.time}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <span
                        style={{
                          padding: "2px 9px",
                          fontSize: 10.5,
                          fontWeight: 700,
                          borderRadius: 4,
                          background: opStyle.bg,
                          color: opStyle.color,
                        }}
                      >
                        {r.op}
                      </span>
                    </td>
                    <td style={CELL_MONO}>{r.sku}</td>
                    <td style={CELL}>{r.name}</td>
                    <td style={{ ...CELL_MONO, color: deltaColor, fontWeight: 700 }}>{r.delta}</td>
                    <td style={CELL_MONO}>
                      <span style={{ color: "var(--ink-400)" }}>{r.before.toLocaleString()}</span>
                      <span style={{ margin: "0 5px", color: "var(--ink-300)" }}>→</span>
                      <strong>{r.after.toLocaleString()}</strong>
                    </td>
                    <td style={{ ...CELL, fontSize: 11, color: "var(--ink-600)" }}>
                      {r.ref}
                      <span style={{ color: "var(--ink-400)" }}> · {r.user}</span>
                      {r.note && <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 2 }}>{r.note}</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <footer
          style={{
            padding: "9px 14px",
            borderTop: "1px solid var(--ink-100)",
            fontSize: 11,
            color: "var(--ink-500)",
            background: "var(--surface-2)",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>显示 {filtered.length} / {ledgerRows.length} 条流水</span>
          <span>全部流水合计 1,247 条 · 近 30 天</span>
        </footer>
      </div>

      {/* AI 异常识别 */}
      <div
        className="card"
        style={{
          padding: "16px 18px",
          borderLeft: "3px solid var(--ai-purple)",
          background: "linear-gradient(180deg, #FAF8FF 0%, #FFFFFF 60%)",
        }}
      >
        <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <span
            style={{
              width: 26,
              height: 26,
              borderRadius: 7,
              background: "rgba(123,92,250,0.12)",
              color: "var(--ai-purple-deep)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.spark(14, "var(--ai-purple-deep)")}
          </span>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
            AI 流水异常识别
          </h3>
          <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-400)" }}>
            近 7 天扫描 · 最严重 1 条 / 共 3 条
          </span>
        </header>
        {/* iter G9: 3 → 1 最严重 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr",
            gap: 10,
          }}
        >
          {ledgerAiAnomalies.slice(0, 1).map((a, i) => (
            <div
              key={i}
              style={{
                padding: "12px 14px",
                background: "#fff",
                border: "1px solid var(--ink-100)",
                borderRadius: 9,
                borderLeft: "3px solid var(--ai-purple)",
              }}
            >
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 5 }}>
                {a.title}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.6 }}>{a.body}</div>
              <button
                style={{
                  marginTop: 8,
                  padding: "4px 10px",
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 6,
                  border: "1px solid var(--ai-200)",
                  background: "var(--ai-50)",
                  color: "var(--ai-700)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                定位流水 →
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FilterPills({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>{label}</span>
      <div style={{ display: "flex", gap: 4 }}>
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              onClick={() => onChange(opt)}
              style={{
                padding: "4px 9px",
                fontSize: 11.5,
                fontWeight: active ? 700 : 500,
                borderRadius: 6,
                border: active ? "1px solid var(--brand-500)" : "1px solid var(--ink-100)",
                background: active ? "var(--brand-50)" : "#fff",
                color: active ? "var(--brand-700)" : "var(--ink-600)",
                cursor: "pointer",
                fontFamily: "var(--font)",
              }}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const SMALL_INPUT: React.CSSProperties = {
  padding: "5px 9px",
  fontSize: 11.5,
  border: "1px solid var(--ink-200)",
  borderRadius: 6,
  outline: "none",
  fontFamily: "var(--font)",
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
