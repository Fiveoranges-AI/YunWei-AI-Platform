import { I } from "../../icons";
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

export function JintaiWorkflowTimeline() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 16 }}>
      <div
        className="card"
        style={{
          padding: "22px 18px 18px",
          overflowX: "auto",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
          示例订单 SO-2026-001（华东客户 · 高铝耐火砖 12,000 块）
        </div>
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginBottom: 18 }}>
          CRM → 订单 → 工单 → 计划单 → 生产流转 → 成型 → 烧结 → 检包 → 成品入库 → 出货
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
                <div style={{ textAlign: "center", marginTop: 8, padding: "0 4px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-900)" }}>
                    {n.title}
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: s.fg,
                      fontWeight: 600,
                      marginTop: 2,
                    }}
                  >
                    {s.label}
                  </div>
                  <div
                    style={{
                      fontSize: 10.5,
                      color: "var(--ink-500)",
                      marginTop: 3,
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
          订单已完成成型、正在烧结，预计 06-18 进入检包；最终交付 06-20，与合同交期持平。
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>
          烧结环节有 24 小时缓冲已用尽，建议密切观察 Y-02 窑温升曲线。客户华东已签合同 ¥114 万、首付已收。
        </div>
        <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 10, color: "var(--ink-500)", fontWeight: 600, letterSpacing: "0.05em" }}>
            来源
          </div>
          <JintaiSourceCitation
            source={{ kind: "合同", label: "华东客户_设备采购合同_2026Q2.pdf" }}
          />
          <JintaiSourceCitation source={{ kind: "生产流转单", label: "ZC-2026-015" }} />
          <JintaiSourceCitation source={{ kind: "工艺单", label: "QX-08 烧结曲线 v2.3" }} />
        </div>
      </div>
    </div>
  );
}
