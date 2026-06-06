import { useEffect, useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { replenishmentItems } from "../data";
import { useGT } from "../state";
import { Spinner } from "../Toast";
import { resolveBrand } from "../branding";

type Props = { onGoShortage: () => void };

const PRIORITY_META: Record<
  "高" | "中" | "低",
  { color: string; bg: string; border: string }
> = {
  高: { color: "var(--guangtian-red)", bg: "rgba(217,32,32,0.08)", border: "rgba(217,32,32,0.26)" },
  中: { color: "var(--stock-low)", bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.26)" },
  低: { color: "var(--ink-500)", bg: "var(--surface-2)", border: "var(--ink-100)" },
};

export function ReplenishmentPanel(_props: Props) {
  const isDesktop = useIsDesktop();
  const { showToast, highlightSku, demoStep } = useGT();
  const terms = resolveBrand().terms; // 行业话术随客户切换 (窑炉/工艺组 ↔ 产线/生产组)
  const [showSummary, setShowSummary] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [assigned, setAssigned] = useState<Set<string>>(new Set());

  const onGenerate = () => {
    setGenerating(true);
    window.setTimeout(() => {
      setGenerating(false);
      setShowSummary(true);
    }, 1200);
  };

  const onAssign = (sku: string, name: string) => {
    setAssigned((s) => new Set(s).add(sku));
    showToast(`✓ ${name} 已挂到工艺组 · 工单号 SC-2026-${(Math.floor(Math.random() * 900) + 100).toString()}`, "ok");
  };

  // iter G13: demo 步 4 (改) 自动把高亮 SKU 加入计划
  useEffect(() => {
    if (demoStep === 4 && highlightSku) {
      const item = replenishmentItems.find((i) => i.sku === highlightSku);
      if (item && !assigned.has(highlightSku)) {
        setAssigned((s) => new Set(s).add(highlightSku));
        showToast(`✓ ${item.name} 已加入本周生产计划 · 高优先`, "ok");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoStep, highlightSku]);

  return (
    <div>
      {/* 顶部 CTA + 说明 */}
      <div
        className="card"
        style={{
          padding: "14px 18px",
          marginBottom: 14,
          display: "flex",
          alignItems: "center",
          gap: 14,
          flexWrap: "wrap",
          background: "linear-gradient(135deg, #FAF8FF 0%, #FFFFFF 70%)",
          borderLeft: "3px solid var(--ai-purple)",
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
          {I.factory(18, "#fff")}
        </span>
        <div style={{ flex: 1, minWidth: 240 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
            AI 已推荐本周补产 {replenishmentItems.length} 个 SKU
          </h3>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--ink-500)", lineHeight: 1.5 }}>
            综合订单需求 / 历史出货趋势 / 安全库存 / 生产周期，按优先级排序。
          </p>
        </div>
        <button
          onClick={onGenerate}
          disabled={generating}
          style={{
            padding: "9px 16px",
            fontSize: 12.5,
            fontWeight: 700,
            borderRadius: 8,
            border: "none",
            background: generating ? "var(--ai-300)" : "var(--ai-purple)",
            color: "#fff",
            cursor: generating ? "wait" : "pointer",
            fontFamily: "var(--font)",
            boxShadow: "0 3px 10px rgba(123,92,250,0.25)",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            minWidth: 160,
            justifyContent: "center",
          }}
        >
          {generating ? (
            <>
              <Spinner size={12} color="#fff" />
              AI 综合订单中…
            </>
          ) : (
            <>✓ 生成本周补产计划</>
          )}
        </button>
      </div>

      {/* 补产卡片 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {replenishmentItems.map((item, i) => {
          const p = PRIORITY_META[item.priority];
          const stockRatio = Math.round((item.currentStock / item.safety) * 100) || 0;
          const isHL = highlightSku === item.sku;
          return (
            <div
              key={item.sku}
              className="card"
              style={{
                padding: "14px 16px",
                display: "grid",
                gridTemplateColumns: isDesktop ? "60px 1.5fr 1fr 1fr 1.2fr" : "1fr",
                gap: 14,
                alignItems: "center",
                borderLeft: `${isHL ? 4 : 3}px solid ${isHL ? "var(--guangtian-red)" : p.color}`,
                boxShadow: isHL ? "0 0 0 2px rgba(195,38,41,0.22), var(--shadow-card)" : undefined,
                animation: isHL ? "gt-pulse-urgent 1.8s ease-in-out 6" : undefined,
              }}
            >
              {/* 优先级标记 + 排序 */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <span
                  style={{
                    fontSize: 18,
                    fontWeight: 800,
                    color: p.color,
                    fontFamily: "var(--font-display)",
                  }}
                >
                  #{i + 1}
                </span>
                <span
                  style={{
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    borderRadius: 4,
                    background: p.bg,
                    color: p.color,
                    border: `1px solid ${p.border}`,
                  }}
                >
                  {item.priority}优先
                </span>
              </div>

              {/* SKU + 名称 */}
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 3 }}>
                  {item.name}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-500)",
                    fontFamily: "var(--font-mono, var(--font))",
                  }}
                >
                  {item.sku}
                </div>
              </div>

              {/* 当前库存进度 */}
              <div>
                <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 4 }}>
                  当前 {item.currentStock.toLocaleString()} {item.unit} / 安全 {item.safety.toLocaleString()}
                </div>
                <div
                  style={{
                    height: 6,
                    background: "var(--ink-100)",
                    borderRadius: 3,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.min(stockRatio, 100)}%`,
                      background: p.color,
                      borderRadius: 3,
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
                <div style={{ fontSize: 10, color: "var(--ink-400)", marginTop: 3 }}>
                  {stockRatio}% · 缺 {Math.max(item.safety - item.currentStock, 0)} {item.unit}
                </div>
              </div>

              {/* 建议数量 + 完成时间 */}
              <div>
                <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 3 }}>建议补产</div>
                <div
                  style={{
                    fontSize: 19,
                    fontWeight: 800,
                    color: p.color,
                    fontFamily: "var(--font-display)",
                    lineHeight: 1.1,
                  }}
                >
                  {item.suggestQty.toLocaleString()} {item.unit}
                </div>
                <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 3 }}>
                  预计 <strong>{item.estDate}</strong> 出炉
                </div>
              </div>

              {/* AI 推理:展开综合的因子 + 置信度 + 结论,让老板看着像 AI 在算 */}
              <div>
                {(() => {
                  const parts = item.reason.split("·").map((s) => s.trim()).filter(Boolean);
                  // 最后一段通常是结论(建议补到…),前面是 AI 权衡的因子
                  const conclusion = parts.length > 1 ? parts[parts.length - 1] : "";
                  const factors = parts.length > 1 ? parts.slice(0, -1) : parts;
                  const conf = item.priority === "高" ? 94 : item.priority === "中" ? 90 : 87;
                  return (
                    <div style={{ marginBottom: 8 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          marginBottom: 6,
                        }}
                      >
                        <strong style={{ fontSize: 11.5, color: "var(--ai-purple-deep)" }}>
                          ✦ AI 推理 · 综合 {factors.length} 项因子
                        </strong>
                        <span
                          style={{
                            fontSize: 10.5,
                            fontWeight: 700,
                            color: "var(--ai-purple-deep)",
                            background: "var(--ai-100, #F3F0FF)",
                            padding: "1px 7px",
                            borderRadius: 999,
                          }}
                        >
                          置信度 {conf}%
                        </span>
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 7 }}>
                        {factors.map((f, i) => (
                          <span
                            key={i}
                            style={{
                              fontSize: 11,
                              color: "var(--ink-700)",
                              background: "var(--surface-2)",
                              border: "1px solid var(--ink-100)",
                              padding: "2px 8px",
                              borderRadius: 6,
                              lineHeight: 1.5,
                            }}
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                      {conclusion && (
                        <div style={{ fontSize: 11.5, color: "var(--ink-800)", lineHeight: 1.55 }}>
                          <strong style={{ color: "var(--ai-purple-deep)" }}>→ AI 结论：</strong>
                          {conclusion}
                        </div>
                      )}
                    </div>
                  );
                })()}
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button
                    style={{
                      ...CTA_PRIMARY,
                      background: assigned.has(item.sku) ? "var(--stock-ok)" : "var(--ai-purple)",
                    }}
                    onClick={() => onAssign(item.sku, item.name)}
                    disabled={assigned.has(item.sku)}
                  >
                    {assigned.has(item.sku) ? `✓ 已挂${terms.team}` : `挂到${terms.team}`}
                  </button>
                  <button
                    style={CTA_GHOST}
                    onClick={() => showToast(`${item.name} · AI 综合订单 + 月均出货 + 生产周期算得这个数量`, "info")}
                  >
                    查看详情
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 补产计划生成弹窗 */}
      {showSummary && (
        <ReplenishmentSummaryModal onClose={() => setShowSummary(false)} />
      )}
    </div>
  );
}

function ReplenishmentSummaryModal({ onClose }: { onClose: () => void }) {
  const { showToast } = useGT();
  const terms = resolveBrand().terms;
  const total = replenishmentItems.reduce((acc, it) => acc + it.suggestQty, 0);
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
          maxWidth: 580,
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
              本周补产计划 · 已生成
            </h3>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--ink-500)", lineHeight: 1.5 }}>
              AI 综合 7 个下游订单 + 30 天出货趋势的最终方案
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--ink-400)", padding: 4 }}
            aria-label="关闭"
          >
            {I.close(20, "var(--ink-400)")}
          </button>
        </header>

        <div
          style={{
            padding: "12px 14px",
            background: "var(--ai-50)",
            border: "1px solid var(--ai-100)",
            borderRadius: 8,
            marginBottom: 14,
          }}
        >
          <div style={{ fontSize: 12, color: "var(--ai-700)", lineHeight: 1.65 }}>
            <strong style={{ color: "var(--ai-900)" }}>计划摘要：</strong>本周（5/19 – 5/25）共需补产{" "}
            <strong style={{ color: "var(--guangtian-red)" }}>{total.toLocaleString()}</strong> 单位，
            覆盖 {replenishmentItems.length} 个紧迫 SKU。预计{terms.line}占用 4 天，{terms.team}人力 8 人 · 班。
            如本周生产能力允许，可同步排产 JT-HLZ-T3-150 备货 800 块（应对下周潜在订单）。
          </div>
        </div>

        <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--ink-800)", lineHeight: 1.7 }}>
          {replenishmentItems.map((it) => (
            <li key={it.sku} style={{ marginBottom: 6 }}>
              <strong>{it.name}</strong> · {it.suggestQty.toLocaleString()} {it.unit} ·
              排产 {it.estDate} ·
              <span style={{ color: it.priority === "高" ? "var(--guangtian-red)" : it.priority === "中" ? "var(--stock-low)" : "var(--ink-500)", fontWeight: 700 }}>
                {" "}{it.priority}优先
              </span>
            </li>
          ))}
        </ol>

        <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
          <button
            onClick={() => {
              showToast(`✓ 补产计划 ${total.toLocaleString()} 单位已发送 · 陈工（工艺组）微信收到`, "ok");
              onClose();
            }}
            style={{
              padding: "9px 16px",
              fontSize: 12.5,
              fontWeight: 700,
              borderRadius: 8,
              border: "none",
              background: "var(--ai-purple)",
              color: "#fff",
              cursor: "pointer",
              fontFamily: "var(--font)",
            }}
          >
            发送给{terms.team}（陈工）
          </button>
          <button
            onClick={onClose}
            style={{
              padding: "9px 14px",
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
            稍后处理
          </button>
        </div>
      </div>
    </div>
  );
}

const CTA_PRIMARY: React.CSSProperties = {
  padding: "5px 11px",
  fontSize: 11.5,
  fontWeight: 600,
  borderRadius: 6,
  border: "none",
  background: "var(--ai-purple)",
  color: "#fff",
  cursor: "pointer",
  fontFamily: "var(--font)",
};

const CTA_GHOST: React.CSSProperties = {
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
