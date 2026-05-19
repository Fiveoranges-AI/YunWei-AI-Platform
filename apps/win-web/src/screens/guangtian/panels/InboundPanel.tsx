import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { recentInbounds, inboundAiChecks } from "../data";

const INBOUND_TYPES = ["生产入库", "采购入库", "退货入库", "其他"];

export function InboundPanel() {
  const isDesktop = useIsDesktop();
  const [toast, setToast] = useState<string | null>(null);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setToast("入库登记成功 · 已写入流水 + 触发 AI 校验");
    setTimeout(() => setToast(null), 3000);
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
              <select defaultValue="JT-HLZ-230-114-65" style={SELECT}>
                <option>JT-HLZ-230-114-65 · 高铝砖 230×114×65</option>
                <option>JT-MLS-M70 · 莫来石砖 M70</option>
                <option>JT-JZL-JC16 · 浇注料 JC-16</option>
                <option>JT-GZB-AL80 · 刚玉砖 AL80</option>
              </select>
            </Field>
            <Field label="数量 *">
              <div style={{ display: "flex", gap: 6 }}>
                <input type="number" defaultValue={800} style={{ ...INPUT, flex: 1 }} />
                <select defaultValue="块" style={{ ...SELECT, width: 80, flex: "none" }}>
                  <option>块</option>
                  <option>袋</option>
                  <option>吨</option>
                  <option>桶</option>
                </select>
              </div>
            </Field>
            <Field label="入库类型 *">
              <select defaultValue="生产入库" style={SELECT}>
                {INBOUND_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="批次号 *">
              <input type="text" defaultValue="P20260519-01" style={INPUT} />
            </Field>
            <Field label="库位 *">
              <select defaultValue="A-03" style={SELECT}>
                <option>A-03 (高铝砖区)</option>
                <option>A-04 (高铝砖区)</option>
                <option>A-05 (莫来石区)</option>
                <option>B-02 (浇注料区)</option>
                <option>B-03 (浇注料区)</option>
                <option>C-01 (刚玉砖区)</option>
                <option>C-02 (刚玉砖区)</option>
              </select>
            </Field>
            <Field label="关联生产单 / 采购单">
              <input type="text" defaultValue="SC-2026-0521" style={INPUT} />
            </Field>
            <Field label="操作人">
              <select defaultValue="王主管" style={SELECT}>
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
          </div>

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

          <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center" }}>
            <button
              type="submit"
              style={{
                padding: "9px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 8,
                border: "none",
                background: "var(--guangtian-blue)",
                color: "#fff",
                cursor: "pointer",
                fontFamily: "var(--font)",
                boxShadow: "0 3px 10px rgba(26,63,142,0.22)",
              }}
            >
              ✓ 确认入库
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
            {toast && (
              <span
                style={{
                  fontSize: 12,
                  color: "var(--stock-ok)",
                  background: "rgba(27,127,58,0.08)",
                  padding: "5px 11px",
                  borderRadius: 6,
                  border: "1px solid rgba(27,127,58,0.20)",
                  fontWeight: 600,
                }}
              >
                ✓ {toast}
              </span>
            )}
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
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>近 48 小时 · 5 笔</span>
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
                  {["时间", "SKU", "产品", "数量", "批次", "库位", "操作人", "来源"].map((h) => (
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
                {recentInbounds.map((r, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--ink-50)" }}>
                    <td style={CELL_MONO}>{r.time}</td>
                    <td style={CELL_MONO}>{r.sku}</td>
                    <td style={CELL}>{r.name}</td>
                    <td style={{ ...CELL, color: "var(--stock-ok)", fontWeight: 700 }}>{r.qty} {r.unit}</td>
                    <td style={CELL_MONO}>{r.batch}</td>
                    <td style={CELL_MONO}>{r.location}</td>
                    <td style={CELL}>{r.op}</td>
                    <td style={{ ...CELL, fontSize: 11, color: "var(--ink-500)" }}>{r.source}</td>
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
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {inboundAiChecks.map((c, i) => (
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
        <div
          style={{
            marginTop: 12,
            paddingTop: 10,
            borderTop: "1px dashed var(--ai-200)",
            fontSize: 11,
            color: "var(--ai-700)",
            lineHeight: 1.55,
          }}
        >
          <strong>AI 入库小贴士：</strong>
          <ul style={{ margin: "5px 0 0", paddingLeft: 18 }}>
            <li>批次号统一格式 <code>P+日期+序号</code> 便于追溯</li>
            <li>生产入库尽量关联生产单，AI 才能算实际成品率</li>
            <li>大宗采购可拍合格证照片，OCR 自动提取数据</li>
          </ul>
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
