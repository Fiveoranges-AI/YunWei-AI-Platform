import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { workflowNodes } from "./data";
import { JintaiSourceCitation } from "./components";

const STATUS_STYLE: Record<
  "done" | "current" | "pending",
  { fg: string; bg: string; line: string; label: string }
> = {
  done: { fg: "var(--ok-700)", bg: "var(--ok-100)", line: "var(--ok-500)", label: "已完成" },
  current: { fg: "var(--brand-700)", bg: "var(--brand-100)", line: "var(--brand-500)", label: "进行中" },
  pending: { fg: "var(--ink-500)", bg: "var(--ink-100)", line: "var(--ink-200)", label: "未开始" },
};

// 视觉减负：长 title 缩到 ≤ 4 字（已用色环 + icon 表达状态，desc 已说明细节）
const SHORT_TITLE: Record<string, string> = {
  "CRM / 客户": "客户",
  订单: "订单",
  工单: "工单",
  计划单: "计划",
  生产流转: "流转",
  成型: "成型",
  烧结: "烧结",
  检包: "检包",
  成品入库: "入库",
  出货: "出货",
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
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginBottom: 18 }}>
          CRM → 订单 → 工单 → 计划单 → 生产流转 → 成型 → 烧结 → 检包 → 成品入库 → 出货容百宁波
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            minWidth: 880,
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
                    minHeight: 22,
                  }}
                >
                  <div style={{ flex: 1, height: 2, background: i === 0 ? "transparent" : s.line }} />
                  <div
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 11,
                      background: s.bg,
                      color: s.fg,
                      border: `2px solid ${s.line}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {n.status === "done" ? I.check(11) : n.status === "current" ? I.spark(11) : null}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      height: 2,
                      background:
                        i === workflowNodes.length - 1
                          ? "transparent"
                          : STATUS_STYLE[workflowNodes[i + 1].status].line,
                    }}
                  />
                </div>
                <div style={{ textAlign: "center", marginTop: 10, padding: "0 4px" }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)" }}>
                    {SHORT_TITLE[n.title] ?? n.title}
                  </div>
                  <div
                    style={{
                      fontSize: 10.5,
                      color: "var(--ink-400)",
                      marginTop: 4,
                      lineHeight: 1.4,
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
