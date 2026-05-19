import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { workflowNodes } from "./data";
import { JintaiSourceCitation } from "./components";

// iter 18：简化为 5 节点后视觉升级 — 已完成用锦泰绿（与 finance tab 同源）
// 进行中保留 brand-500 蓝（与右栏 AI 摘要呼应），未开始低饱和灰
const STATUS_STYLE: Record<
  "done" | "current" | "pending",
  { fg: string; bg: string; line: string; label: string }
> = {
  done: { fg: "#fff", bg: "var(--jintai-green)", line: "var(--jintai-green)", label: "已完成" },
  current: { fg: "#fff", bg: "var(--brand-500)", line: "var(--brand-500)", label: "进行中" },
  pending: { fg: "var(--ink-400)", bg: "var(--surface-2)", line: "var(--ink-200)", label: "未开始" },
};

export function JintaiWorkflowTimeline() {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "grid", gridTemplateColumns: isDesktop ? "1fr 320px" : "1fr", gap: 16 }}>
      <div
        className="card"
        style={{
          padding: "22px 18px 18px",
          overflowX: "auto",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
          示例订单 SO-2026-001 · 容百锂电 · 刚玉莫来石承烧板 18,000 块 · ¥327.6 万
        </div>
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginBottom: 22 }}>
          订单 → 计划 → 生产 → 入库 → 出货
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            gap: 0,
          }}
        >
          {workflowNodes.map((n, i) => {
            const s = STATUS_STYLE[n.status];
            return (
              <div
                key={n.id}
                style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "stretch" }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    minHeight: 28,
                  }}
                >
                  {/* iter 18：5 节点 — 圆圈 28px / 连线 2.5px / 段间距更宽 */}
                  <div
                    style={{
                      flex: 1,
                      height: 2.5,
                      background: i === 0 ? "transparent" : s.line,
                      borderRadius: 1,
                    }}
                  />
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 14,
                      background: s.bg,
                      color: s.fg,
                      border: `2px solid ${s.line}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      boxShadow: n.status === "current" ? "0 0 0 4px rgba(45,155,216,0.18)" : "none",
                    }}
                  >
                    {n.status === "done" ? I.check(14) : n.status === "current" ? I.spark(13) : null}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      height: 2.5,
                      background:
                        i === workflowNodes.length - 1
                          ? "transparent"
                          : STATUS_STYLE[workflowNodes[i + 1].status].line,
                      borderRadius: 1,
                    }}
                  />
                </div>
                <div style={{ textAlign: "center", marginTop: 12, padding: "0 6px" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
                    {n.title}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--ink-500)",
                      marginTop: 4,
                      lineHeight: 1.5,
                    }}
                  >
                    {n.desc}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div
        className="ai-surface"
        style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 700,
            color: "var(--ai-700)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {I.spark(12)} AI 摘要
        </div>
        <div style={{ fontSize: 13.5, color: "var(--ink-900)", lineHeight: 1.55, fontWeight: 600 }}>
          订单已完成等静压成型，正在 SK-02 梭式窑烧结，预计 06-18 进入检包；最终交付 06-20 上午到容百宁波，与合同交期持平。
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>
          烧结段 24 小时缓冲已用尽，建议密切观察 SK-02 在 1450–1580 ℃ 段温升。客户容百锂电已签 ¥327.6 万、首付 ¥98.28 万已收。
        </div>
        <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 10, color: "var(--ink-500)", fontWeight: 600, letterSpacing: "0.05em" }}>
            来源
          </div>
          <JintaiSourceCitation
            source={{ kind: "合同", label: "容百锂电_承烧板采购合同_2026Q2.pdf" }}
          />
          <JintaiSourceCitation source={{ kind: "生产流转单", label: "ZC-2026-015" }} />
          <JintaiSourceCitation source={{ kind: "工艺单", label: "LB-1580 烧结曲线 v2.3" }} />
        </div>
      </div>
    </div>
  );
}
