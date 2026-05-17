import { useEffect, useMemo, useRef, useState } from "react";
import { useIsDesktop } from "../../lib/breakpoints";
import { initialExtractionCards } from "./data";
import type { ExtractionCard } from "./data";
import { JintaiSection } from "./components";
import { JintaiHero } from "./JintaiHero";
import { JintaiKpiCards } from "./JintaiKpiCards";
import { JintaiUploadInbox } from "./JintaiUploadInbox";
import type { ProcessingCard } from "./JintaiUploadInbox";
import { JintaiWorkflowTimeline } from "./JintaiWorkflowTimeline";
import { JintaiProductionTabs } from "./JintaiProductionTabs";
import { JintaiAIQueryPanel } from "./JintaiAIQueryPanel";
import { JintaiDailyBriefing } from "./JintaiDailyBriefing";
import { JintaiTrustPanel } from "./JintaiTrustPanel";

function makeSimulatedCard(
  kind: ExtractionCard["kind"],
  simCounter: number,
): ExtractionCard {
  const stamp = `刚刚 · ${new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
  const contractPresets = [
    {
      customer: "当升科技股份有限公司",
      product: "刚玉莫来石承烧板",
      spec: "330×330×16 mm",
      qty: "12,000 块",
      unitPrice: "¥182 / 块",
      date: "2026-07-10",
      fname: "当升科技_承烧板采购合同_2026Q3.pdf",
    },
    {
      customer: "宁波容百新能源 · 二供",
      product: "刚玉莫来石承烧板",
      spec: "330×330×16 mm",
      qty: "8,000 块",
      unitPrice: "¥185 / 块",
      date: "2026-07-18",
      fname: "容百二供_补充订单_2026Q3.pdf",
    },
    {
      customer: "广东三环集团（陶瓷研究院）",
      product: "氧化铝技术陶瓷板",
      spec: "200×200×6 mm",
      qty: "5,000 片",
      unitPrice: "¥96 / 片",
      date: "2026-07-25",
      fname: "三环集团_技术陶瓷订单_2026Q3.pdf",
    },
  ];
  if (kind === "合同") {
    const p = contractPresets[simCounter % contractPresets.length];
    return {
      id: `sim-ct-${simCounter}`,
      kind: "合同",
      source: p.fname,
      uploadedAt: stamp,
      status: "待确认",
      confidence: 0.92,
      fields: [
        { key: "客户名称", value: p.customer, confidence: 0.96 },
        { key: "产品", value: p.product, confidence: 0.95 },
        { key: "规格", value: p.spec, confidence: 0.98 },
        { key: "数量", value: p.qty, confidence: 0.94 },
        { key: "单价", value: p.unitPrice, confidence: 0.92 },
        { key: "交付日期", value: p.date, confidence: 0.9 },
        { key: "付款方式", value: "30/60/10，验收后 90 天结清", confidence: 0.82 },
      ],
      toBeGenerated: `销售订单 SO-2026-00${simCounter + 4}`,
    };
  }
  if (kind === "生产流转单") {
    return {
      id: `sim-fc-${simCounter}`,
      kind: "生产流转单",
      source: `ZC-2026-0${15 + simCounter} 纸质流转单（车间手机拍照）`,
      uploadedAt: stamp,
      status: "待确认",
      confidence: 0.86,
      fields: [
        { key: "计划单号", value: `SC-2026-0${15 + simCounter}`, confidence: 0.95 },
        { key: "产品", value: "刚玉莫来石承烧板", confidence: 0.94 },
        { key: "规格", value: "330×330×16 mm", confidence: 0.96 },
        { key: "数量", value: "12,000", confidence: 0.92 },
        { key: "计划交期", value: "2026-07-05", confidence: 0.89 },
        { key: "成型机台", value: "等静压 IP-04", confidence: 0.82 },
        { key: "烧成曲线", value: "LB-1580", confidence: 0.84 },
        { key: "成型操作人", value: "陈师傅", confidence: 0.74 },
      ],
      toBeGenerated: `生产流转单 ZC-2026-0${15 + simCounter} + 三个工序卡`,
    };
  }
  // 出货单
  return {
    id: `sim-sh-${simCounter}`,
    kind: "出货单",
    source: `出货单_容百宁波_${simCounter}.pdf`,
    uploadedAt: stamp,
    status: "待确认",
    confidence: 0.93,
    fields: [
      { key: "出货单号", value: `CK-2026-02${simCounter}`, confidence: 0.97 },
      { key: "对应订单", value: "SO-2026-001", confidence: 0.95 },
      { key: "客户", value: "容百锂电 · 宁波厂", confidence: 0.96 },
      { key: "产品", value: "刚玉莫来石承烧板 330×330×16", confidence: 0.95 },
      { key: "数量", value: "18,000 块", confidence: 0.94 },
      { key: "出货日期", value: "2026-06-21", confidence: 0.92 },
      { key: "承运", value: "德邦物流 · 整车直送", confidence: 0.86 },
    ],
    toBeGenerated: `出货单 CK-2026-02${simCounter}`,
  };
}

const PROCESSING_STAGES = [
  { label: "上传中", upTo: 18 },
  { label: "PDF / 图片解析", upTo: 38 },
  { label: "AI 抽取字段", upTo: 72 },
  { label: "置信度评估", upTo: 92 },
  { label: "生成待确认草稿", upTo: 100 },
];

function stageForProgress(p: number) {
  for (const s of PROCESSING_STAGES) if (p < s.upTo) return s.label;
  return PROCESSING_STAGES[PROCESSING_STAGES.length - 1].label;
}

const KIND_FILENAME: Record<ExtractionCard["kind"], string> = {
  合同: "当升科技_承烧板采购合同_2026Q3.pdf",
  生产流转单: "ZC-2026-016 纸质流转单_车间手机拍照.jpg",
  出货单: "出货单_容百宁波_扫描件.pdf",
  "Excel 订单": "横店东磁_订单明细_2026Q3.xlsx",
};

const KIND_SIZE: Record<ExtractionCard["kind"], string> = {
  合同: "1.4 MB · 3 页",
  生产流转单: "2.1 MB · 1 张",
  出货单: "0.9 MB · 2 页",
  "Excel 订单": "76 KB · 1 sheet · 12 行",
};

export function JintaiDemoPage() {
  const isDesktop = useIsDesktop();
  const [cards, setCards] = useState<ExtractionCard[]>(initialExtractionCards);
  const [processing, setProcessing] = useState<ProcessingCard[]>([]);
  const timers = useRef<Set<number>>(new Set());
  const simCounterRef = useRef(0);

  useEffect(() => {
    return () => {
      timers.current.forEach((id) => window.clearInterval(id));
      timers.current.clear();
    };
  }, []);

  const handleScrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleSimulateUpload = (kind: ExtractionCard["kind"]) => {
    const pid = `proc-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const startedAt = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    setProcessing((prev) => [
      { id: pid, kind, filename: KIND_FILENAME[kind], size: KIND_SIZE[kind], progress: 0, stage: PROCESSING_STAGES[0].label, startedAt },
      ...prev,
    ]);
    handleScrollTo("ai-inbox");
    const interval = window.setInterval(() => {
      setProcessing((prev) => {
        const next = prev.map((p) => {
          if (p.id !== pid) return p;
          const bump = 6 + Math.floor(Math.random() * 8);
          const np = Math.min(100, p.progress + bump);
          return { ...p, progress: np, stage: stageForProgress(np) };
        });
        const target = next.find((p) => p.id === pid);
        if (target && target.progress >= 100) {
          window.clearInterval(interval);
          timers.current.delete(interval);
          window.setTimeout(() => {
            setProcessing((cur) => cur.filter((p) => p.id !== pid));
            simCounterRef.current += 1;
            const newCard = makeSimulatedCard(kind, simCounterRef.current);
            setCards((cur) => (cur.some((c) => c.id === newCard.id) ? cur : [newCard, ...cur]));
          }, 450);
        }
        return next;
      });
    }, 280);
    timers.current.add(interval);
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
            processing={processing}
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
