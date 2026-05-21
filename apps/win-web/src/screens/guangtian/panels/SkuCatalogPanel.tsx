import { useMemo, useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { skuRows, type SkuRow, type StockStatus } from "../data";
import { useGT } from "../state";

// iter G15: 状态 4 档（正常/低库存/缺货/数据异常）
const STATUS_COLORS: Record<
  StockStatus,
  { bg: string; color: string; border: string }
> = {
  正常:    { bg: "rgba(27,127,58,0.08)",  color: "var(--stock-ok)",     border: "rgba(27,127,58,0.20)" },
  低库存:  { bg: "rgba(245,158,11,0.10)", color: "var(--stock-low)",    border: "rgba(245,158,11,0.28)" },
  缺货风险:{ bg: "rgba(195,38,41,0.10)",  color: "var(--stock-out)",    border: "rgba(195,38,41,0.26)" },
  已缺货:  { bg: "rgba(195,38,41,0.10)",  color: "var(--stock-out)",    border: "rgba(195,38,41,0.26)" },
  数据异常: { bg: "rgba(123,92,250,0.10)", color: "var(--ai-purple-deep)", border: "rgba(123,92,250,0.26)" },
};

const CATEGORIES = ["全部", "高铝砖", "莫来石砖", "浇注料", "刚玉砖"];

export function SkuCatalogPanel() {
  const isDesktop = useIsDesktop();
  const { skuStocks, showToast, highlightSku } = useGT();
  const [cat, setCat] = useState<string>("全部");
  const [status, setStatus] = useState<string>("全部");
  const [query, setQuery] = useState<string>("");
  const [showAiModal, setShowAiModal] = useState(false);
  const [showAdvFilter, setShowAdvFilter] = useState(false); // iter G9

  const filtered = useMemo(() => {
    return skuRows.filter((r) => {
      if (cat !== "全部" && r.category !== cat) return false;
      if (status !== "全部") {
        // iter G9: 合并 缺货风险 / 已缺货 都按 "缺货" 处理
        if (status === "缺货" && r.status !== "缺货风险" && r.status !== "已缺货") return false;
        if (status !== "缺货" && r.status !== status) return false;
      }
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        if (!r.code.toLowerCase().includes(q) && !r.name.includes(query.trim())) return false;
      }
      return true;
    });
  }, [cat, status, query]);

  return (
    <div>
      {/* iter G9: 筛选条精简 — 搜索 + 高级筛选折叠按钮 + AI 主 CTA */}
      <div
        className="card"
        style={{
          padding: "14px 18px",
          marginBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 240 }}>
          {I.search(14, "var(--ink-400)")}
          <input
            type="text"
            placeholder="按 SKU 编码 / 产品名 搜索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              flex: 1,
              padding: "8px 4px",
              fontSize: 13,
              border: "none",
              outline: "none",
              fontFamily: "var(--font)",
              background: "transparent",
            }}
          />
        </div>
        <button
          onClick={() => setShowAdvFilter((v) => !v)}
          style={{
            padding: "7px 13px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 7,
            border: "1px solid var(--ink-200)",
            background: showAdvFilter ? "var(--brand-50)" : "#fff",
            color: showAdvFilter ? "var(--brand-700)" : "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
          }}
        >
          高级筛选 {showAdvFilter ? "▾" : "▸"}
        </button>
        <button
          onClick={() => setShowAiModal(true)}
          style={{
            padding: "7px 13px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 8,
            border: "none",
            background: "var(--ai-purple)",
            color: "#fff",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontFamily: "var(--font)",
            boxShadow: "0 2px 6px rgba(123,92,250,0.22)",
          }}
        >
          {I.spark(12, "#fff")}
          AI 整理 SKU 命名
        </button>
        {showAdvFilter && (
          <div
            style={{
              width: "100%",
              paddingTop: 10,
              marginTop: 4,
              borderTop: "1px solid var(--ink-100)",
              display: "flex",
              flexWrap: "wrap",
              gap: 14,
              alignItems: "center",
            }}
          >
            <FilterGroup label="类别" options={CATEGORIES} value={cat} onChange={setCat} />
            <span style={{ width: 1, height: 22, background: "var(--ink-100)" }} />
            <FilterGroup
              label="状态"
              options={["全部", "正常", "低库存", "缺货", "数据异常"]}
              value={status === "已缺货" || status === "缺货风险" ? "缺货" : status}
              onChange={(v) => setStatus(v === "缺货" ? "已缺货" : v)}
            />
          </div>
        )}
      </div>

      {/* 表格 */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              fontFamily: "var(--font)",
              minWidth: isDesktop ? 820 : 720,
            }}
          >
            {/* iter G17 第一性原理：删材质列(冗余)，最近入/出库合并为"最近动销" — 7 列 */}
            <thead>
              <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--ink-100)" }}>
                <Th>SKU 编码</Th>
                <Th>产品名称 / 规格</Th>
                <Th>库位</Th>
                <Th align="right">库存</Th>
                <Th align="right">安全线</Th>
                <Th>最近动销</Th>
                <Th>状态</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const liveStock = skuStocks[r.code] ?? r.stock;
                let liveStatus: StockStatus = r.status;
                // iter G15: 仅 "数据异常" 状态不被库存阈值覆盖
                if (r.status === "数据异常") liveStatus = "数据异常";
                else if (liveStock <= 0) liveStatus = "已缺货";
                else if (liveStock < r.safety) liveStatus = "低库存";
                else liveStatus = "正常";
                return (
                  <SkuTableRow
                    key={r.code}
                    row={{ ...r, stock: liveStock, status: liveStatus }}
                    onClick={() => showToast(`${r.code} · ${r.name} · 当前库存 ${liveStock.toLocaleString()} ${r.unit}`, "info")}
                    highlight={highlightSku === r.code}
                  />
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: "24px 16px", textAlign: "center", color: "var(--ink-400)", fontSize: 12 }}>
                    没有匹配的 SKU
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <footer
          style={{
            padding: "10px 14px",
            borderTop: "1px solid var(--ink-100)",
            fontSize: 11,
            color: "var(--ink-500)",
            display: "flex",
            justifyContent: "space-between",
            background: "var(--surface-2)",
          }}
        >
          <span>显示 {filtered.length} / {skuRows.length} 条 SKU</span>
          <span>共 1,286 个 SKU（演示展示 {skuRows.length} 条）</span>
        </footer>
      </div>

      {/* AI 命名规则弹窗 */}
      {showAiModal && (
        <AiNamingModal onClose={() => setShowAiModal(false)} />
      )}
    </div>
  );
}

function FilterGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
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

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      style={{
        padding: "10px 12px",
        textAlign: align,
        fontSize: 11,
        fontWeight: 700,
        color: "var(--ink-600)",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align = "left",
  mono = false,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
  mono?: boolean;
}) {
  return (
    <td
      style={{
        padding: "10px 12px",
        textAlign: align,
        fontSize: 12,
        color: "var(--ink-800)",
        fontFamily: mono ? "var(--font-mono, var(--font))" : "var(--font)",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </td>
  );
}

function SkuTableRow({
  row,
  onClick,
  highlight = false,
}: {
  row: SkuRow;
  onClick?: () => void;
  highlight?: boolean;
}) {
  const s = STATUS_COLORS[row.status];
  const displayStatus = row.status === "缺货风险" || row.status === "已缺货" ? "缺货" : row.status;
  return (
    <tr
      onClick={onClick}
      style={{
        borderBottom: "1px solid var(--ink-50)",
        cursor: onClick ? "pointer" : "default",
        transition: "background 0.12s ease, box-shadow 0.2s ease",
        background: highlight ? "rgba(195,38,41,0.06)" : undefined,
        boxShadow: highlight ? "inset 4px 0 0 var(--guangtian-red), 0 0 0 2px rgba(195,38,41,0.18)" : undefined,
        animation: highlight ? "gt-pulse-urgent 1.6s ease-in-out infinite" : undefined,
      }}
      onMouseEnter={(e) => {
        if (!highlight) (e.currentTarget as HTMLTableRowElement).style.background = "var(--surface-2)";
      }}
      onMouseLeave={(e) => {
        if (!highlight) (e.currentTarget as HTMLTableRowElement).style.background = "";
      }}
    >
      <Td mono>{row.code}</Td>
      <td style={{ padding: "10px 12px", fontSize: 12, whiteSpace: "nowrap" }}>
        <div style={{ color: "var(--ink-800)" }}>{row.name}</div>
        <div style={{ fontSize: 10.5, color: "var(--ink-500)", marginTop: 2 }}>{row.spec}</div>
      </td>
      <Td mono>{row.location}</Td>
      <Td align="right">
        <strong>{row.stock.toLocaleString()}</strong>
        <span style={{ marginLeft: 3, fontSize: 10.5, color: "var(--ink-400)" }}>{row.unit}</span>
      </Td>
      <Td align="right">{row.safety.toLocaleString()}</Td>
      <td style={{ padding: "10px 12px", whiteSpace: "nowrap", fontSize: 11, color: "var(--ink-600)", fontFamily: "var(--font-mono, var(--font))" }}>
        <div>入 {row.lastIn ?? "—"}</div>
        <div style={{ color: "var(--ink-400)", marginTop: 2 }}>出 {row.lastOut ?? "—"}</div>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <span
          style={{
            display: "inline-flex",
            padding: "3px 9px",
            fontSize: 11,
            fontWeight: 700,
            borderRadius: 5,
            background: s.bg,
            color: s.color,
            border: `1px solid ${s.border}`,
          }}
        >
          {displayStatus}
        </span>
      </td>
    </tr>
  );
}

function ModalMigrateBtn({ onClose }: { onClose: () => void }) {
  const { showToast } = useGT();
  return (
    <button
      style={{
        padding: "6px 12px",
        fontSize: 11.5,
        fontWeight: 600,
        borderRadius: 6,
        border: "none",
        background: "var(--ai-purple)",
        color: "#fff",
        cursor: "pointer",
        fontFamily: "var(--font)",
      }}
      onClick={() => {
        showToast("✓ AI 已生成 1,286 SKU 迁移映射表 · Excel 已发邮件，待您审批后一次性切换", "ai");
        onClose();
      }}
    >
      让 AI 生成迁移映射表
    </button>
  );
}

function AiNamingModal({ onClose }: { onClose: () => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(11,18,32,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff",
          borderRadius: 14,
          padding: "20px 22px",
          maxWidth: 620,
          width: "100%",
          maxHeight: "85vh",
          overflow: "auto",
          boxShadow: "var(--shadow-pop)",
        }}
      >
        <header style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 14 }}>
          <span
            style={{
              width: 32,
              height: 32,
              borderRadius: 9,
              background: "rgba(123,92,250,0.12)",
              color: "var(--ai-purple-deep)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {I.spark(16, "var(--ai-purple-deep)")}
          </span>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--ink-900)" }}>
              AI 建议的 SKU 命名规则
            </h3>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--ink-500)", lineHeight: 1.5 }}>
              统一编码 + 命名后，老板搜库存 5 秒能找到任何 SKU。
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--ink-400)",
              padding: 4,
            }}
            aria-label="关闭"
          >
            {I.close(20, "var(--ink-400)")}
          </button>
        </header>

        <section style={{ marginBottom: 14 }}>
          <h4 style={{ margin: "0 0 6px", fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
            统一编码格式（4 段）
          </h4>
          <div
            style={{
              padding: "10px 12px",
              background: "var(--surface-2)",
              borderRadius: 8,
              fontFamily: "var(--font-mono, var(--font))",
              fontSize: 12.5,
              color: "var(--ink-800)",
              border: "1px solid var(--ink-100)",
              lineHeight: 1.7,
            }}
          >
            <strong style={{ color: "var(--guangtian-red)" }}>JT</strong> -{" "}
            <strong style={{ color: "var(--brand-700)" }}>HLZ</strong> -{" "}
            <strong style={{ color: "var(--stock-low)" }}>230-114-65</strong>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 6, fontFamily: "var(--font)" }}>
              [厂商代码] - [品类代码] - [规格/等级]
              <br />
              示例：JT-HLZ-230-114-65 = 光天 / 高铝砖 / 230×114×65
            </div>
          </div>
        </section>

        <section style={{ marginBottom: 14 }}>
          <h4 style={{ margin: "0 0 6px", fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
            品类代码对照（建议）
          </h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, fontSize: 12 }}>
            {[
              ["HLZ", "高铝砖"],
              ["MLS", "莫来石砖"],
              ["JZL", "浇注料"],
              ["GZB", "刚玉砖"],
              ["QZB", "轻质保温砖"],
              ["FHM", "防火泥"],
              ["TLS", "碳化硅"],
              ["ZRB", "锆刚玉砖"],
            ].map(([code, name]) => (
              <div
                key={code}
                style={{
                  padding: "6px 10px",
                  background: "var(--surface-2)",
                  borderRadius: 6,
                  display: "flex",
                  justifyContent: "space-between",
                  border: "1px solid var(--ink-100)",
                }}
              >
                <span style={{ fontFamily: "var(--font-mono, var(--font))", color: "var(--ink-800)", fontWeight: 700 }}>
                  {code}
                </span>
                <span style={{ color: "var(--ink-600)" }}>{name}</span>
              </div>
            ))}
          </div>
        </section>

        <section
          style={{
            padding: "10px 12px",
            background: "var(--ai-50)",
            border: "1px solid var(--ai-100)",
            borderRadius: 8,
            fontSize: 11.5,
            color: "var(--ai-700)",
            lineHeight: 1.6,
          }}
        >
          <strong style={{ fontWeight: 700 }}>AI 现状评估：</strong>当前 1,286 个 SKU 中，
          约 <strong>340 个</strong>命名不符合此规则（多为旧编码 / 手工命名）。
          AI 可以批量生成迁移映射表，老板审批后一次性切换 — 历史流水自动重写 SKU 字段。
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <ModalMigrateBtn onClose={onClose} />
            <button
              onClick={onClose}
              style={{
                padding: "6px 12px",
                fontSize: 11.5,
                fontWeight: 500,
                borderRadius: 6,
                border: "1px solid var(--ink-200)",
                background: "#fff",
                color: "var(--ink-700)",
                cursor: "pointer",
                fontFamily: "var(--font)",
              }}
            >
              稍后再说
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
