import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { inboundAiChecks } from "../data";
import { useGT } from "../state";
import { Spinner } from "../Toast";

const INBOUND_TYPES = ["生产入库", "采购入库", "退货入库", "其他"];

// SKU 下拉选项（联动产品名 / 单位 / 库位）
const SKU_OPTIONS = [
  { code: "JT-HLZ-230-114-65", name: "高铝砖（标准型）",  unit: "块", loc: "A-03" },
  { code: "JT-MLS-M70",        name: "莫来石砖 M70",      unit: "块", loc: "A-05" },
  { code: "JT-JZL-JC16",       name: "浇注料 JC-16",      unit: "袋", loc: "B-02" },
  { code: "JT-GZB-AL80",       name: "刚玉砖 AL80",       unit: "块", loc: "C-01" },
  { code: "JT-HLZ-T3-150",     name: "高铝砖 T3 异型",    unit: "块", loc: "A-04" },
  { code: "JT-JZL-JC18-LR",    name: "低水泥浇注料",      unit: "袋", loc: "B-03" },
  { code: "JT-GZB-AL90",       name: "高纯刚玉砖 AL90",   unit: "块", loc: "C-02" },
];

export function InboundPanel() {
  const isDesktop = useIsDesktop();
  const { inboundRecords, addInbound, skuStocks } = useGT();
  const [showMore, setShowMore] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 表单 state — iter G10 全部受控
  const [sku, setSku] = useState(SKU_OPTIONS[0].code);
  const [qty, setQty] = useState<number>(800);
  const [unit, setUnit] = useState(SKU_OPTIONS[0].unit);
  const [type, setType] = useState(INBOUND_TYPES[0]);
  const [batch, setBatch] = useState("P20260520-01");
  const [loc, setLoc] = useState(SKU_OPTIONS[0].loc);
  const [source, setSource] = useState("SC-2026-0521");
  const [op, setOp] = useState("王主管");

  const currentStock = skuStocks[sku] ?? 0;
  const selectedSku = SKU_OPTIONS.find((s) => s.code === sku) ?? SKU_OPTIONS[0];

  const onSkuChange = (code: string) => {
    setSku(code);
    const s = SKU_OPTIONS.find((x) => x.code === code);
    if (s) {
      setUnit(s.unit);
      setLoc(s.loc);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!qty || qty <= 0) return;
    setSubmitting(true);
    window.setTimeout(() => {
      addInbound({
        sku,
        name: selectedSku.name,
        qty,
        unit,
        batch,
        location: loc,
        op,
        source: `${type} · ${source}`,
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
              {I.inbox(14, "var(--guangtian-blue)")}
            </span>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
              新建入库登记
            </h3>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                color: "var(--ink-400)",
                padding: "3px 9px",
                borderRadius: 5,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
              }}
            >
              扫码 / 手动录入
            </span>
          </header>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: isDesktop ? "repeat(2, 1fr)" : "1fr",
              gap: 12,
            }}
          >
            <Field label="SKU 编码 *">
              <select value={sku} onChange={(e) => onSkuChange(e.target.value)} style={SELECT}>
                {SKU_OPTIONS.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.code} · {s.name} (库存 {(skuStocks[s.code] ?? 0).toLocaleString()})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="数量 *">
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  type="number"
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value) || 0)}
                  style={{ ...INPUT, flex: 1 }}
                  min={1}
                />
                <select value={unit} onChange={(e) => setUnit(e.target.value)} style={{ ...SELECT, width: 80, flex: "none" }}>
                  <option>块</option>
                  <option>袋</option>
                  <option>吨</option>
                  <option>桶</option>
                </select>
              </div>
              <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 3 }}>
                提交后库存 <strong>{currentStock.toLocaleString()}</strong> →{" "}
                <strong style={{ color: "var(--stock-ok)" }}>{(currentStock + qty).toLocaleString()}</strong>
              </div>
            </Field>
            <Field label="入库类型 *">
              <select value={type} onChange={(e) => setType(e.target.value)} style={SELECT}>
                {INBOUND_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="批次号 *">
              <input
                type="text"
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
                style={INPUT}
              />
            </Field>
            <Field label="库位 *">
              <select value={loc} onChange={(e) => setLoc(e.target.value)} style={SELECT}>
                <option>A-03 (高铝砖区)</option>
                <option>A-04 (高铝砖区)</option>
                <option>A-05 (莫来石区)</option>
                <option>B-02 (浇注料区)</option>
                <option>B-03 (浇注料区)</option>
                <option>C-01 (刚玉砖区)</option>
                <option>C-02 (刚玉砖区)</option>
              </select>
            </Field>
            {showMore && (
              <>
                <Field label="关联生产单 / 采购单">
                  <input
                    type="text"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    style={INPUT}
                  />
                </Field>
                <Field label="操作人">
                  <select value={op} onChange={(e) => setOp(e.target.value)} style={SELECT}>
                    <option>王主管</option>
                    <option>李师傅</option>
                    <option>张仓管</option>
                  </select>
                </Field>
                <Field label="附件（合格证 / 验收单 / 照片）">
                  <button
                    type="button"
                    style={{
                      ...INPUT,
                      textAlign: "left",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      cursor: "pointer",
                      color: "var(--ink-500)",
                      background: "#fff",
                    }}
                  >
                    <span>📎 点击上传 (PDF / 图片)</span>
                    <span style={{ color: "var(--ink-400)", fontSize: 10.5 }}>≤ 10 MB</span>
                  </button>
                </Field>
              </>
            )}
          </div>

          {/* iter G9: 折叠按钮 + 备注（备注收进展开） */}
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
            {showMore ? "收起更多字段 ▾" : "更多字段（关联单据 / 操作人 / 附件 / 备注）▸"}
          </button>
          {showMore && (
            <Field label="备注" full>
              <textarea
                rows={2}
                defaultValue=""
                placeholder="如有异常说明请记录，AI 会自动归档"
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

          <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center" }}>
            <button
              type="submit"
              disabled={submitting || qty <= 0}
              style={{
                padding: "9px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 8,
                border: "none",
                background: submitting ? "var(--brand-400)" : "var(--guangtian-blue)",
                color: "#fff",
                cursor: submitting ? "wait" : "pointer",
                fontFamily: "var(--font)",
                boxShadow: "0 3px 10px rgba(26,63,142,0.22)",
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
                <>✓ 确认入库</>
              )}
            </button>
            <button
              type="reset"
              onClick={() => {
                setQty(800);
                setBatch("P20260520-01");
              }}
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

        {/* 最近入库记录 */}
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
              最近入库记录
            </h3>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>近 3 笔 · 共 {inboundRecords.length} 笔</span>
          </header>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 12,
                minWidth: 640,
              }}
            >
              <thead style={{ background: "var(--surface-2)" }}>
                <tr>
                  {["时间", "SKU", "产品", "数量", "批次", "库位", "来源"].map((h) => (
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
                {inboundRecords.slice(0, 3).map((r, i) => (
                  <tr key={`${r.time}-${r.sku}-${i}`} style={{ borderTop: "1px solid var(--ink-50)" }}>
                    <td style={CELL_MONO}>{r.time}</td>
                    <td style={CELL_MONO}>{r.sku}</td>
                    <td style={CELL}>{r.name}</td>
                    <td style={{ ...CELL, color: "var(--stock-ok)", fontWeight: 700 }}>{r.qty} {r.unit}</td>
                    <td style={CELL_MONO}>{r.batch}</td>
                    <td style={CELL_MONO}>{r.location}</td>
                    <td style={{ ...CELL, fontSize: 11, color: "var(--ink-500)" }}>{r.source} · {r.op}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 右：AI 校验 */}
      <div
        className="card"
        style={{
          padding: "16px 18px",
          background: "linear-gradient(180deg, #FAF8FF 0%, #FFFFFF 60%)",
          borderLeft: "3px solid var(--ai-purple)",
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
            AI 入库校验
          </h3>
        </header>
        <p style={{ margin: "0 0 12px", fontSize: 11.5, color: "var(--ink-500)", lineHeight: 1.5 }}>
          AI 实时核对批次号 / 库位 / 数量 / 关联单据，发现问题立即提示，不让错误数据落库。
        </p>
        {/* iter G9: 2 → 1 最严重提醒 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {inboundAiChecks.slice(0, 1).map((c, i) => (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                borderRadius: 8,
                background: c.level === "warn" ? "rgba(245,158,11,0.06)" : "rgba(27,127,58,0.06)",
                border: c.level === "warn" ? "1px solid rgba(245,158,11,0.22)" : "1px solid rgba(27,127,58,0.22)",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  marginBottom: 4,
                  color: c.level === "warn" ? "var(--stock-low)" : "var(--stock-ok)",
                  letterSpacing: "0.02em",
                }}
              >
                {c.level === "warn" ? "⚠ 校验提醒" : "✓ 校验通过"}
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", marginBottom: 3 }}>
                {c.title}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.55 }}>{c.body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
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
