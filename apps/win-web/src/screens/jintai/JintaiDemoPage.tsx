import { useMemo, useState } from "react";
import { useIsDesktop } from "../../lib/breakpoints";
import { initialExtractionCards } from "./data";
import type { ExtractionCard } from "./data";
import { JintaiSection } from "./components";
import { JintaiHero } from "./JintaiHero";
import { JintaiKpiCards } from "./JintaiKpiCards";
import { JintaiUploadInbox } from "./JintaiUploadInbox";
import { JintaiWorkflowTimeline } from "./JintaiWorkflowTimeline";
import { JintaiProductionTabs } from "./JintaiProductionTabs";
import { JintaiAIQueryPanel } from "./JintaiAIQueryPanel";
import { JintaiDailyBriefing } from "./JintaiDailyBriefing";
import { JintaiTrustPanel } from "./JintaiTrustPanel";

let simCounter = 0;

function makeSimulatedCard(kind: ExtractionCard["kind"]): ExtractionCard {
  simCounter += 1;
  const stamp = `刚刚 · ${new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
  if (kind === "合同") {
    return {
      id: `sim-ct-${simCounter}`,
      kind: "合同",
      source: `模拟合同_${simCounter}.pdf`,
      uploadedAt: stamp,
      status: "待确认",
      confidence: 0.92,
      fields: [
        { key: "客户名称", value: "山东某窑炉客户", confidence: 0.95 },
        { key: "产品", value: "高铝耐火砖", confidence: 0.95 },
        { key: "规格", value: "230×114×65", confidence: 0.98 },
        { key: "数量", value: "9,000 块", confidence: 0.94 },
        { key: "交付日期", value: "2026-07-10", confidence: 0.9 },
        { key: "付款方式", value: "30/60/10", confidence: 0.82 },
      ],
      toBeGenerated: `销售订单 SO-2026-00${simCounter + 3}`,
    };
  }
  if (kind === "生产流转单") {
    return {
      id: `sim-fc-${simCounter}`,
      kind: "生产流转单",
      source: `ZC-2026-0${15 + simCounter} 纸质流转单（拍照）`,
      uploadedAt: stamp,
      status: "待确认",
      confidence: 0.86,
      fields: [
        { key: "计划单号", value: `SC-2026-0${15 + simCounter}`, confidence: 0.95 },
        { key: "产品", value: "高铝耐火砖", confidence: 0.94 },
        { key: "规格", value: "230×114×65", confidence: 0.96 },
        { key: "数量", value: "10,000", confidence: 0.92 },
        { key: "计划交期", value: "2026-07-05", confidence: 0.89 },
        { key: "成型机台", value: "A-04", confidence: 0.82 },
        { key: "成型操作人", value: "李工", confidence: 0.74 },
      ],
      toBeGenerated: `生产流转单 ZC-2026-0${15 + simCounter} + 三个工序卡`,
    };
  }
  // 出货单
  return {
    id: `sim-sh-${simCounter}`,
    kind: "出货单",
    source: `出货单_${simCounter}.pdf`,
    uploadedAt: stamp,
    status: "待确认",
    confidence: 0.93,
    fields: [
      { key: "出货单号", value: `CK-2026-02${simCounter}`, confidence: 0.97 },
      { key: "对应订单", value: "SO-2026-001", confidence: 0.95 },
      { key: "客户", value: "华东客户", confidence: 0.96 },
      { key: "数量", value: "12,000 块", confidence: 0.94 },
      { key: "出货日期", value: "2026-06-21", confidence: 0.92 },
      { key: "承运", value: "顺丰物流", confidence: 0.86 },
    ],
    toBeGenerated: `出货单 CK-2026-02${simCounter}`,
  };
}

export function JintaiDemoPage() {
  const isDesktop = useIsDesktop();
  const [cards, setCards] = useState<ExtractionCard[]>(initialExtractionCards);

  const handleScrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleSimulateUpload = (kind: ExtractionCard["kind"]) => {
    setCards((prev) => [makeSimulatedCard(kind), ...prev]);
    handleScrollTo("ai-inbox");
  };

  const handleConfirm = (id: string) => {
    setCards((prev) =>
      prev.map((c) => {
        if (c.id !== id) return c;
        const newStatus: ExtractionCard["status"] =
          c.kind === "合同" || c.kind === "Excel 订单"
            ? "订单已生成"
            : c.kind === "生产流转单"
              ? "流转单已生成"
              : "出货已记录";
        return { ...c, status: newStatus };
      }),
    );
  };

  const stats = useMemo(
    () => ({
      pending: cards.filter((c) => c.status === "待确认").length,
      done: cards.filter((c) => c.status !== "待确认").length,
    }),
    [cards],
  );

  return (
    <div className="scroll" style={{ flex: 1, background: "var(--bg)" }}>
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: isDesktop ? "24px 32px 64px" : "16px 16px 80px",
        }}
      >
        {/* Module 1 — 试点总览 (Hero + KPI) */}
        <JintaiHero
          onScrollTo={handleScrollTo}
          onSimulateUploadContract={() => handleSimulateUpload("合同")}
          onSimulateUploadFlowCard={() => handleSimulateUpload("生产流转单")}
        />
        <JintaiKpiCards />

        {/* Module 2 — AI 资料收件箱 */}
        <JintaiSection
          id="ai-inbox"
          title={`模块 2 · AI 资料收件箱 — 待确认 ${stats.pending} · 已生成 ${stats.done}`}
          trailing={
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
              AI 抽取后人工确认入库
            </span>
          }
        >
          <JintaiUploadInbox
            cards={cards}
            onSimulateUploadContract={() => handleSimulateUpload("合同")}
            onSimulateUploadFlowCard={() => handleSimulateUpload("生产流转单")}
            onSimulateUploadShipping={() => handleSimulateUpload("出货单")}
            onConfirm={handleConfirm}
          />
        </JintaiSection>

        {/* Module 3 — 主业务流程闭环 */}
        <JintaiSection
          id="workflow"
          title="模块 3 · 主业务流程闭环 — CRM → 订单 → 工单 → 计划单 → 生产流转 → 入库 → 出货"
        >
          <JintaiWorkflowTimeline />
        </JintaiSection>

        {/* Module 4 — 生产三张表 A/B/C */}
        <JintaiSection
          id="production"
          title="模块 4 · 生产三张表（A 流转单 · B 工艺单 · C 出货入库）"
        >
          <JintaiProductionTabs />
        </JintaiSection>

        {/* Module 5 — 老板 AI 查询 */}
        <JintaiSection id="ai-query" title="模块 5 · 老板 AI 助手 — 用中文问，答案带来源">
          <JintaiAIQueryPanel />
        </JintaiSection>

        {/* Module 6 — 每日经营风险简报 */}
        <JintaiSection
          id="briefing"
          title="模块 6 · 每日生产经营简报 — 今天哪里要紧"
        >
          <JintaiDailyBriefing />
        </JintaiSection>

        {/* Module 7 — 来源追溯与数据安全 */}
        <JintaiSection
          id="trust"
          title="模块 7 · 来源追溯 & 数据安全 — AI 不瞎编"
        >
          <JintaiTrustPanel />
        </JintaiSection>

        <div
          style={{
            marginTop: 32,
            padding: "16px 18px",
            borderRadius: 12,
            background: "var(--surface)",
            border: "1px dashed var(--ink-200)",
            color: "var(--ink-500)",
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          演示版本 · 纯前端 · 所有数据均为 mock。本 demo 用于客户演示与方案对齐，不接后端、不写入任何真实业务系统。
        </div>
      </div>
    </div>
  );
}
