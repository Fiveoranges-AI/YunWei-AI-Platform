import { useMemo, useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { skuRows, type SkuRow, type StockStatus } from "../data";

const STATUS_COLORS: Record<
  StockStatus,
  { bg: string; color: string; border: string }
> = {
  正常:    { bg: "rgba(27,127,58,0.08)",  color: "var(--stock-ok)",   border: "rgba(27,127,58,0.20)" },
  低库存:  { bg: "rgba(245,158,11,0.10)", color: "var(--stock-low)",  border: "rgba(245,158,11,0.28)" },
  缺货风险:{ bg: "rgba(217,32,32,0.08)",  color: "var(--guangtian-red)",border:"rgba(217,32,32,0.22)" },
  已缺货:  { bg: "rgba(195,38,41,0.10)",  color: "var(--stock-out)",  border: "rgba(195,38,41,0.26)" },
  呆滞:    { bg: "rgba(107,114,128,0.08)",color: "var(--stock-dead)", border: "rgba(107,114,128,0.20)" },
};

const CATEGORIES = ["全部", "高铝砖", "莫来石砖", "浇注料", "刚玉砖"];
const STATUS_FILTERS: ("全部" | StockStatus)[] = ["全部", "正常", "低库存", "缺货风险", "已缺货", "呆滞"];

export function SkuCatalogPanel() {
  const isDesktop = useIsDesktop();
  const [cat, setCat] = useState<string>("全部");
  const [status, setStatus] = useState<string>("全部");
  const [query, setQuery] = useState<string>("");
  const [showAiModal, setShowAiModal] = useState(false);

  const filtered = useMemo(() => {
    return skuRows.filter((r) => {
      if (cat !== "全部" && r.category !== cat) return false;
      if (status !== "全部" && r.status !== status) return false;
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        if (!r.code.toLowerCase().includes(q) && !r.name.includes(query.trim())) return false;
      }
      return true;
    });
  }, [cat, status, query]);

  return (
    <div>
      {/* 筛选条 */}
      <div
        className="card"
        style={{
          padding: "12px 14px",
          marginBottom: 14,
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          alignItems: "center",
        }}
      >
        <FilterGroup
          label="类别"
          options={CATEGORIES}
          value={cat}
          onChange={setCat}
        />
        <span style={{ width: 1, height: 22, background: "var(--ink-100)" }} />
        <FilterGroup
          label="状态"
          options={STATUS_FILTERS}
          value={status}
          onChange={setStatus}
        />
        <span style={{ width: 1, height: 22, background: "var(--ink-100)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 200 }}>
          <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>搜索</span>
          <input
            type="text"
            placeholder="按 SKU 编码 / 产品名 搜索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
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
          AI 帮我整理 SKU 命名
        </button>
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
              minWidth: isDesktop ? 920 : 720,
            }}
          >
            <thead>
              <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--ink-100)" }}>
                <Th>SKU 编码</Th>
                <Th>产品名称</Th>
                <Th>规格</Th>
                <Th>类别</Th>
                <Th>单位</Th>
                <Th>库位</Th>
                <Th align="right">当前库存</Th>
                <Th align="right">安全库存</Th>
                <Th>状态</Th>
                <Th>操作</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <SkuTableRow key={r.code} row={r} />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} style={{ padding: "24px 16px", textAlign: "center", color: "var(--ink-400)", fontSize: 12 }}>
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

function SkuTableRow({ row }: { row: SkuRow }) {
  const s = STATUS_COLORS[row.status];
  return (
    <tr style={{ borderBottom: "1px solid var(--ink-50)" }}>
      <Td mono>{row.code}</Td>
      <Td>{row.name}</Td>
      <Td>{row.spec}</Td>
      <Td>{row.category}</Td>
      <Td>{row.unit}</Td>
      <Td mono>{row.location}</Td>
      <Td align="right">
        <strong>{row.stock.toLocaleString()}</strong>
      </Td>
      <Td align="right">{row.safety.toLocaleString()}</Td>
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
          {row.status}
        </span>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <div style={{ display: "inline-flex", gap: 4 }}>
          <ActionBtn>详情</ActionBtn>
          <ActionBtn>流水</ActionBtn>
        </div>
      </td>
    </tr>
  );
}

function ActionBtn({ children }: { children: React.ReactNode }) {
  return (
    <button
      style={{
        padding: "3px 8px",
        fontSize: 10.5,
        fontWeight: 500,
        borderRadius: 5,
        border: "1px solid var(--ink-100)",
        background: "#fff",
        color: "var(--ink-600)",
        cursor: "pointer",
        fontFamily: "var(--font)",
      }}
    >
      {children}
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
            >
              让 AI 生成迁移映射表
            </button>
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
