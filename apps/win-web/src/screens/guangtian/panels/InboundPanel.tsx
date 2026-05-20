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

// iter G11: AI 单据上传识别三段 mock 模板
type DocIngestState = "idle" | "scanning" | "result";
const DOC_PRESETS = [
  {
    kind: "📄 江苏华峰采购入库单 · 扫描件.pdf",
    fields: [
      { key: "SKU 编码", value: "JT-GZB-AL80", conf: 98 },
      { key: "产品名称", value: "刚玉砖 AL80 等级", conf: 96 },
      { key: "数量", value: "300", conf: 99 },
      { key: "批次", value: "P20260520-J3", conf: 94 },
      { key: "库位", value: "C-01", conf: 92 },
      { key: "供应商", value: "江苏华峰耐火", conf: 89 },
      { key: "采购单号", value: "PO-2026-0091", conf: 76 },
      { key: "送货日期", value: "2026-05-20 11:30", conf: 84 },
    ],
    anomalies: [
      "采购单号 PO-2026-0091 在系统中未找到，疑似遗漏录入或编号笔误",
      "批次号 P20260520-J3 含字母 J，与近 30 天命名规则不一致（建议 P20260520-03）",
    ],
  },
  {
    kind: "📷 王主管 5/20 13:42 拍照入库单.jpg",
    fields: [
      { key: "SKU 编码", value: "JT-HLZ-230-114-65", conf: 95 },
      { key: "产品名称", value: "高铝砖（标准型）", conf: 97 },
      { key: "数量", value: "600", conf: 98 },
      { key: "批次", value: "P20260520-02", conf: 92 },
      { key: "库位", value: "A-03", conf: 96 },
      { key: "操作人", value: "王主管", conf: 88 },
    ],
    anomalies: ["照片角度倾斜 12°，AI 已自动校正后识别"],
  },
];

export function InboundPanel() {
  const isDesktop = useIsDesktop();
  const { inboundRecords, addInbound, skuStocks, showToast } = useGT();
  const [showMore, setShowMore] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  // iter G11: AI 单据上传
  const [docState, setDocState] = useState<DocIngestState>("idle");
  const [docPreset, setDocPreset] = useState(DOC_PRESETS[0]);

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

  // iter G11: AI 单据上传 → 1.5s 扫描 → 显示识别结果三段
  const onUploadDoc = (presetIdx: 0 | 1) => {
    setDocPreset(DOC_PRESETS[presetIdx]);
    setDocState("scanning");
    showToast(`✦ AI 正在识别 ${DOC_PRESETS[presetIdx].kind} …`, "ai");
    window.setTimeout(() => setDocState("result"), 1500);
  };

  // 把 AI 识别结果填入表单
  const applyAiResult = () => {
    const get = (k: string) => docPreset.fields.find((f) => f.key === k)?.value ?? "";
    const newSku = get("SKU 编码");
    const newQty = Number(get("数量")) || qty;
    const newBatch = get("批次");
    const newLoc = get("库位");
    if (newSku && SKU_OPTIONS.find((s) => s.code === newSku)) {
      onSkuChange(newSku);
    }
    setQty(newQty);
    if (newBatch) setBatch(newBatch);
    if (newLoc) setLoc(newLoc);
    setDocState("idle");
    showToast("✓ AI 识别结果已填入表单，请人工复核后提交", "ok");
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
        {/* iter G11: AI 单据上传识别（顶部条 + 展开三段） */}
        <DocIngestSection
          state={docState}
          preset={docPreset}
          onUpload={onUploadDoc}
          onApply={applyAiResult}
          onCancel={() => setDocState("idle")}
        />

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

// iter G11: AI 单据上传识别区
function DocIngestSection({
  state,
  preset,
  onUpload,
  onApply,
  onCancel,
}: {
  state: DocIngestState;
  preset: (typeof DOC_PRESETS)[number];
  onUpload: (idx: 0 | 1) => void;
  onApply: () => void;
  onCancel: () => void;
}) {
  if (state === "idle") {
    return (
      <div
        className="card"
        style={{
          padding: "14px 18px",
          background: "linear-gradient(120deg, #FAF8FF 0%, #F4F5FA 80%)",
          borderLeft: "3px solid var(--ai-purple)",
          display: "flex",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            width: 34,
            height: 34,
            borderRadius: 9,
            background: "var(--ai-purple)",
            color: "#fff",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {I.spark(16, "#fff")}
        </span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h3 style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)" }}>
            AI 单据录入 · 上传扫描件 / 拍照
          </h3>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3 }}>
            AI 自动识别字段 → 复核 → 入库（90% 字段免手工）
          </div>
        </div>
        <button
          onClick={() => onUpload(0)}
          style={{
            padding: "7px 12px",
            fontSize: 11.5,
            fontWeight: 700,
            borderRadius: 7,
            border: "none",
            background: "var(--ai-purple)",
            color: "#fff",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          📄 上传采购单 PDF
        </button>
        <button
          onClick={() => onUpload(1)}
          style={{
            padding: "7px 12px",
            fontSize: 11.5,
            fontWeight: 600,
            borderRadius: 7,
            border: "1px solid var(--ai-purple)",
            background: "#fff",
            color: "var(--ai-purple-deep)",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          📷 王主管拍照入库单
        </button>
      </div>
    );
  }

  if (state === "scanning") {
    return (
      <div
        className="card"
        style={{
          padding: "16px 20px",
          background: "linear-gradient(120deg, #FAF8FF 0%, #F4F5FA 80%)",
          borderLeft: "3px solid var(--ai-purple)",
          display: "flex",
          alignItems: "center",
          gap: 14,
        }}
      >
        <Spinner size={18} color="var(--ai-purple-deep)" />
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ai-purple-deep)" }}>
            AI 正在识别字段…
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3 }}>
            {preset.kind} · OCR + 字段抽取 + 置信度评估
          </div>
        </div>
      </div>
    );
  }

  // result — 三段：识别结果 / 待确认字段 / 异常提示
  const highConf = preset.fields.filter((f) => f.conf >= 90);
  const lowConf = preset.fields.filter((f) => f.conf < 90);
  return (
    <div className="card" style={{ padding: "16px 20px", borderLeft: "3px solid var(--ai-purple)" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)" }}>
          ✦ AI 识别完成 · {preset.kind}
        </span>
        <span
          style={{
            padding: "2px 9px",
            fontSize: 10.5,
            fontWeight: 700,
            borderRadius: 4,
            background: "rgba(27,127,58,0.10)",
            color: "var(--stock-ok)",
          }}
        >
          整体置信度 {Math.round(preset.fields.reduce((s, f) => s + f.conf, 0) / preset.fields.length)}%
        </span>
        <button
          onClick={onCancel}
          style={{
            marginLeft: "auto",
            border: "none",
            background: "transparent",
            color: "var(--ink-400)",
            cursor: "pointer",
            fontSize: 12,
            padding: 4,
          }}
        >
          取消
        </button>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 12,
        }}
      >
        {/* 段 1: AI 识别结果（高置信） */}
        <SectionBlock
          title="① AI 识别字段"
          color="var(--stock-ok)"
          bg="rgba(27,127,58,0.05)"
          subtitle={`${highConf.length} 个高置信 ≥90%`}
        >
          {highConf.map((f) => (
            <FieldRow key={f.key} field={f} />
          ))}
        </SectionBlock>

        {/* 段 2: 待确认字段（低置信） */}
        <SectionBlock
          title="② 待确认字段"
          color="var(--stock-low)"
          bg="rgba(245,158,11,0.06)"
          subtitle={`${lowConf.length} 个 < 90% 需复核`}
        >
          {lowConf.length === 0 ? (
            <div style={{ fontSize: 11.5, color: "var(--ink-500)", fontStyle: "italic" }}>无 · 字段全部高置信</div>
          ) : (
            lowConf.map((f) => <FieldRow key={f.key} field={f} highlight />)
          )}
        </SectionBlock>

        {/* 段 3: 异常提示 */}
        <SectionBlock
          title="③ 异常提示"
          color="var(--guangtian-red)"
          bg="rgba(217,32,32,0.05)"
          subtitle={`${preset.anomalies.length} 条 AI 发现的异常`}
        >
          {preset.anomalies.length === 0 ? (
            <div style={{ fontSize: 11.5, color: "var(--ink-500)", fontStyle: "italic" }}>无异常</div>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11.5, color: "var(--ink-700)", lineHeight: 1.6 }}>
              {preset.anomalies.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
        </SectionBlock>
      </div>

      <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
        <button
          onClick={onApply}
          style={{
            padding: "8px 16px",
            fontSize: 12.5,
            fontWeight: 700,
            borderRadius: 8,
            border: "none",
            background: "var(--ai-purple)",
            color: "#fff",
            cursor: "pointer",
            fontFamily: "var(--font)",
            boxShadow: "0 3px 10px rgba(123,92,250,0.25)",
          }}
        >
          ✓ 采纳 AI 识别 · 填入下方表单
        </button>
        <button
          onClick={onCancel}
          style={{
            padding: "8px 14px",
            fontSize: 12.5,
            fontWeight: 500,
            borderRadius: 8,
            border: "1px solid var(--ink-200)",
            background: "#fff",
            color: "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          手工录入
        </button>
      </div>
    </div>
  );
}

function SectionBlock({
  title,
  color,
  bg,
  subtitle,
  children,
}: {
  title: string;
  color: string;
  bg: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        padding: "10px 12px",
        background: bg,
        borderRadius: 8,
        border: `1px solid ${color}33`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, color }}>{title}</span>
        <span style={{ fontSize: 10, color: "var(--ink-500)" }}>{subtitle}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>{children}</div>
    </div>
  );
}

function FieldRow({
  field,
  highlight = false,
}: {
  field: { key: string; value: string; conf: number };
  highlight?: boolean;
}) {
  const confColor =
    field.conf >= 90 ? "var(--stock-ok)" : field.conf >= 75 ? "var(--stock-low)" : "var(--guangtian-red)";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "4px 8px",
        background: highlight ? "rgba(245,158,11,0.10)" : "#fff",
        border: highlight ? "1px dashed var(--stock-low)" : "1px solid var(--ink-100)",
        borderRadius: 5,
        fontSize: 11,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <span style={{ color: "var(--ink-500)", fontSize: 10 }}>{field.key}</span>
        <span style={{ color: "var(--ink-900)", fontWeight: 600 }}>{field.value}</span>
      </div>
      <span style={{ color: confColor, fontWeight: 700, fontFamily: "var(--font-mono, var(--font))" }}>
        {field.conf}%
      </span>
    </div>
  );
}
