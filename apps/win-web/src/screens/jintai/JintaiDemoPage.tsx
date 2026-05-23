import { useEffect, useMemo, useRef, useState } from "react";
import {
  confirmJintaiExtraction,
  createJintaiIngestPlaceholder,
  listJintaiExtractions,
} from "../../api/jintai";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { initialExtractionCards } from "./data";
import type { ExtractionCard } from "./data";
import { JintaiUploadInbox } from "./JintaiUploadInbox";
import type { ProcessingCard } from "./JintaiUploadInbox";
import { JintaiWorkflowTimeline } from "./JintaiWorkflowTimeline";
import { JintaiProductionTabs } from "./JintaiProductionTabs";
import { JintaiAIQueryPanel } from "./JintaiAIQueryPanel";
import { JintaiTrustPanel } from "./JintaiTrustPanel";
import { JintaiFinancePanel } from "./JintaiFinancePanel";
import { JintaiPurchasePanel } from "./JintaiPurchasePanel";
import { JintaiDailyBriefPanel } from "./JintaiDailyBriefPanel";

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

type TabKey =
  | "briefing"
  | "inbox"
  | "production"
  | "finance"
  | "purchase"
  | "ask"
  | "trust";

// iter 20：删 概览 tab (信息密度低 + 与经营日报严重重叠) · 默认 tab 改成 经营日报
// 顺序按"老板/会计/采购/AI"业务族重排：经营日报(老板入口) → 财务 → 采购 → 生产 → 收件箱 → 问问 → 可信
const TABS: {
  key: TabKey;
  label: string;
  hint: string;
  icon: typeof I.grid;
  color: string;
}[] = [
  { key: "briefing", label: "经营日报", hint: "陈总 5 分钟看完今天", icon: I.calendar, color: "var(--brand-700)" },
  { key: "finance", label: "财务", hint: "会企三表 · 成本 · 折旧", icon: I.cash, color: "var(--jintai-green)" },
  { key: "purchase", label: "采购", hint: "申购→订单→入库→应付", icon: I.pkg, color: "var(--jintai-red-40)" },
  { key: "production", label: "生产流转", hint: "配料→成型→烧结→检包", icon: I.factory, color: "var(--jintai-red)" },
  { key: "inbox", label: "AI 收件箱", hint: "新单据进系统 · AI 抽取", icon: I.inbox, color: "var(--ai-purple)" },
  { key: "ask", label: "问问 AI", hint: "中文问，答案带来源", icon: I.ask, color: "var(--ai-purple-deep)" },
  { key: "trust", label: "可信 AI", hint: "AI 不瞎编，每条都可追溯", icon: I.shield, color: "var(--jintai-green-dark)" },
];

// 视觉减负：每 tab 副标精简到 1 句，去除长 narration
const TAB_HEAD: Record<TabKey, { title: string; sub: string }> = {
  briefing: {
    title: "经营日报 · 老板 5 分钟",
    sub: "AI 早上 7:55 自动整合 财务 / 生产 / 采购 / 客户 / 风险 5 大模块，陈总醒后 5 分钟看完今天。",
  },
  finance: {
    title: "财务 · 会企三表 + 成本 + 折旧",
    sub: "AI 自动归集 → 资产负债表 / 利润及利润分配表 / 现金流量表 + 成本拆分 + 折旧台账 → 王会计 1 步确认。",
  },
  purchase: {
    title: "采购 · 申购→订单→入库→应付",
    sub: "AI 抽取邮件合同、发票、入库单字段，采购 + 财务双确认入账，防漏付防漏入。",
  },
  production: {
    title: "生产流转 · 配料→成型→烧结→检包",
    sub: "订单 → 计划 → 配料 → 生产 → 入库 → 出货，可回放任意节点；配料单直接关联库存原料。",
  },
  inbox: {
    title: "AI 资料收件箱",
    sub: "上传合同 / 订单 Excel / 纸质流转单 → AI 抽字段 → 1 步确认 → 自动生成业务草稿。",
  },
  ask: {
    title: "老板 AI 助手",
    sub: "用中文问，AI 拿已确认数据作答，每条结论都附原始来源引用。",
  },
  trust: {
    title: "可信 AI · 来源追溯 & 数据安全",
    sub: "每条 AI 抽取都附 OCR 置信度 + 人工确认双重锚点。",
  },
};

const HASH_TO_TAB: Record<string, TabKey> = {
  "#briefing": "briefing",
  "#inbox": "inbox",
  "#production": "production",
  "#finance": "finance",
  "#purchase": "purchase",
  "#ask": "ask",
  "#trust": "trust",
};

function hashForTab(t: TabKey): string {
  return `#${t}`;
}

function tabFromHash(hash: string): TabKey | null {
  return HASH_TO_TAB[hash] ?? null;
}

import { JintaiProvider, TOUR_TOTAL, useJintai } from "./state/store";
import { JintaiDemoTour } from "./JintaiDemoTour";

export function JintaiDemoPage() {
  return (
    <JintaiProvider>
      <JintaiDemoTour />
      <JintaiDemoPageInner />
    </JintaiProvider>
  );
}

function JintaiDemoPageInner() {
  const isDesktop = useIsDesktop();
  const { state: jt, currentTourStep } = useJintai();
  const [cards, setCards] = useState<ExtractionCard[]>(initialExtractionCards);
  const [processing, setProcessing] = useState<ProcessingCard[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (typeof window === "undefined") return "briefing";
    return tabFromHash(window.location.hash) ?? "briefing";
  });
  const timers = useRef<Set<number>>(new Set());
  const simCounterRef = useRef(0);

  // Backend pending cards on first mount.
  useEffect(() => {
    let cancelled = false;
    listJintaiExtractions("pending")
      .then((backendCards) => {
        if (cancelled || backendCards.length === 0) return;
        setCards((cur) => {
          const seen = new Set(cur.map((c) => c.id));
          return [...backendCards.filter((c) => !seen.has(c.id)), ...cur];
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      timers.current.forEach((id) => window.clearInterval(id));
      timers.current.clear();
    };
  }, []);

  // Hash <-> tab sync. Tab change writes hash without scroll jump;
  // back/forward + manual hash edits restore the tab.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onHash = () => {
      const next = tabFromHash(window.location.hash);
      if (next) setActiveTab(next);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const switchTab = (t: TabKey) => {
    setActiveTab(t);
    if (typeof window !== "undefined") {
      const next = hashForTab(t);
      if (window.location.hash !== next) {
        history.pushState(null, "", next);
      }
      // Scroll page top so each tab opens at its header, not mid-scroll.
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  };

  // iter 23: 引导式 tour 步骤推进 → 自动切对应 tab + 滚到锚点
  useEffect(() => {
    if (!currentTourStep) return;
    const targetTab = currentTourStep.tab as TabKey;
    if (targetTab !== activeTab) setActiveTab(targetTab);
    if (typeof window !== "undefined") {
      // 顶部 tour bar 占位 ~60px,scrollTo 偏移
      window.scrollTo({ top: 0, behavior: "auto" });
    }
    // 延迟到 DOM 更新后滚动到锚点 (若有)
    if (currentTourStep.scrollAnchor) {
      window.setTimeout(() => {
        const el = document.querySelector(`[data-anchor="${currentTourStep.scrollAnchor}"]`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 300);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jt.tourStep]);

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
    switchTab("inbox");
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
            createJintaiIngestPlaceholder(
              kind,
              KIND_FILENAME[kind],
              Object.fromEntries(newCard.fields.map((f) => [f.key, f.value])),
            )
              .then((backendCard) => {
                setCards((cur) => {
                  if (cur.some((c) => c.id === backendCard.id)) return cur;
                  return [backendCard, ...cur];
                });
              })
              .catch(() => {
                setCards((cur) => (cur.some((c) => c.id === newCard.id) ? cur : [newCard, ...cur]));
              });
          }, 450);
        }
        return next;
      });
    }, 280);
    timers.current.add(interval);
  };

  const handleConfirm = (id: string) => {
    if (id.startsWith("AIQ-JT-")) {
      confirmJintaiExtraction(id).catch(() => undefined);
    }
    setCards((prev) =>
      prev.map((c) => {
        if (c.id !== id) return c;
        let newStatus: ExtractionCard["status"] = "出货已记录";
        if (id.startsWith("AIQ-JT-")) {
          newStatus = "已确认";
        } else if (c.kind === "合同" || c.kind === "Excel 订单") {
          newStatus = "订单已生成";
        } else if (c.kind === "生产流转单") {
          newStatus = "流转单已生成";
        }
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

  const head = TAB_HEAD[activeTab];

  // iter 23: tour 进行中,顶部留位给固定控制条 (~64px desktop / ~84px mobile,字幕较长)
  const tourActive = jt.tourStep > 0 && jt.tourStep <= TOUR_TOTAL;
  return (
    <div className="scroll" style={{ flex: 1, background: "var(--bg)" }}>
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: isDesktop
            ? `${tourActive ? 84 : 20}px 32px 64px`
            : `${tourActive ? 96 : 12}px 16px 80px`,
          transition: "padding-top 0.25s ease",
        }}
      >
        {/* Tab navigation — sticky-ish top bar, horizontally scrollable on small screens */}
        <nav
          aria-label="锦泰试点 演示分页"
          style={{
            display: "flex",
            gap: 6,
            padding: 4,
            borderRadius: 12,
            background: "var(--surface-2)",
            border: "1px solid var(--ink-100)",
            marginBottom: 18,
            overflowX: "auto",
          }}
        >
          {TABS.map((t) => {
            const active = t.key === activeTab;
            return (
              <button
                key={t.key}
                onClick={() => switchTab(t.key)}
                aria-current={active ? "page" : undefined}
                style={{
                  position: "relative",
                  padding: isDesktop ? "10px 14px" : "9px 11px",
                  borderRadius: 9,
                  border: "none",
                  // iter 16: active 用 tab 主色背景，inactive 透明（保留底部 indicator 显色）
                  background: active ? t.color : "transparent",
                  color: active ? "#fff" : "var(--ink-700)",
                  fontSize: isDesktop ? 13 : 12.5,
                  fontWeight: active ? 700 : 600,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  lineHeight: 1.2,
                  gap: 3,
                  minWidth: 0,
                  fontFamily: "var(--font)",
                  boxShadow: active ? "var(--shadow-card-soft)" : "none",
                  transition: "background 0.15s ease, transform 0.15s ease",
                }}
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    color: active ? "#fff" : "var(--ink-700)",
                  }}
                >
                  {/* iter 16：icon 用 tab 主色 (active 白 / inactive 本色 0.6 opacity)，
                      active 时 scale 1.05 强化层级 */}
                  <span
                    style={{
                      display: "inline-flex",
                      opacity: active ? 1 : 0.6,
                      transform: active ? "scale(1.05)" : "scale(1)",
                      transition: "opacity 0.15s ease, transform 0.15s ease",
                    }}
                  >
                    {t.icon(16, active ? "#fff" : t.color)}
                  </span>
                  {t.label}
                </span>
                <span
                  style={{
                    fontSize: 10.5,
                    fontWeight: 500,
                    color: active ? "rgba(255,255,255,0.85)" : "var(--ink-500)",
                    paddingLeft: 24,
                  }}
                >
                  {t.hint}
                </span>
                {/* iter 16：active tab 底部 2px 颜色 indicator (与 icon 主色呼应) */}
                {active && (
                  <span
                    aria-hidden
                    style={{
                      position: "absolute",
                      left: 8,
                      right: 8,
                      bottom: -1,
                      height: 2,
                      borderRadius: 1,
                      background: "rgba(255,255,255,0.6)",
                    }}
                  />
                )}
              </button>
            );
          })}
        </nav>

        {/* Per-tab header: breadcrumb + title + 1-sentence narration */}
        <header style={{ marginBottom: 16 }}>
          <div
            style={{
              fontSize: 11.5,
              color: "var(--ink-500)",
              fontWeight: 600,
              letterSpacing: "0.04em",
              marginBottom: 6,
            }}
          >
            锦泰试点 <span style={{ color: "var(--ink-300)" }}>/</span>{" "}
            <span style={{ color: "var(--brand-700)" }}>{head.title}</span>
          </div>
          <h2
            style={{
              margin: 0,
              fontSize: isDesktop ? 20 : 18,
              fontWeight: 700,
              color: "var(--ink-900)",
              lineHeight: 1.3,
            }}
          >
            {head.title}
          </h2>
          <p
            style={{
              margin: "6px 0 0",
              fontSize: 12.5,
              lineHeight: 1.6,
              color: "var(--ink-600)",
              maxWidth: 820,
            }}
          >
            {head.sub}
          </p>
        </header>

        {/* Tab panels — kept mounted (display toggle) so each panel's internal
            state (selected preset Q, A/B/C tab, flow card variant, etc.) survives
            tab switches. */}

        {/* iter 20: 概览 tab 已删 (信息密度低 + 与经营日报严重重叠). 默认 tab 现为 经营日报. */}

        {/* Tab: AI 收件箱 */}
        <div role="tabpanel" hidden={activeTab !== "inbox"}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 12.5, color: "var(--ink-600)", fontWeight: 600 }}>
              待确认 {stats.pending} · 已确认 {stats.done}
            </span>
            <span style={{ fontSize: 11, color: "var(--ink-400)" }}>
              AI 抽取后人工确认入库 · AI 不直接写入业务表
            </span>
          </div>
          <JintaiUploadInbox
            cards={cards}
            processing={processing}
            onSimulateUploadContract={() => handleSimulateUpload("合同")}
            onSimulateUploadFlowCard={() => handleSimulateUpload("生产流转单")}
            onSimulateUploadShipping={() => handleSimulateUpload("出货单")}
            onConfirm={handleConfirm}
          />
        </div>

        {/* Tab 3: 生产流转 — Workflow timeline + 生产三张表 */}
        <div role="tabpanel" hidden={activeTab !== "production"}>
          <JintaiWorkflowTimeline />
          <div style={{ height: 22 }} />
          <JintaiProductionTabs />
        </div>

        {/* Tab 4: 💰 财务 — AI 三表草稿 + 复核 */}
        <div role="tabpanel" hidden={activeTab !== "finance"}>
          <JintaiFinancePanel />
        </div>

        {/* Tab 5: 📦 采购 — 订单 + 供应商 + AI 收件箱 */}
        <div role="tabpanel" hidden={activeTab !== "purchase"}>
          <JintaiPurchasePanel />
        </div>

        {/* Tab 6: 📅 经营日报 — 老板 5 分钟摘要 */}
        <div role="tabpanel" hidden={activeTab !== "briefing"}>
          <JintaiDailyBriefPanel />
        </div>

        {/* Tab 7: 问问 AI */}
        <div role="tabpanel" hidden={activeTab !== "ask"}>
          <JintaiAIQueryPanel />
        </div>

        {/* Tab 8: 可信 AI */}
        <div role="tabpanel" hidden={activeTab !== "trust"}>
          <JintaiTrustPanel />
        </div>

        {/* iter 14：footer 加锦泰定制字样 + logo */}
        <div
          style={{
            marginTop: 36,
            paddingTop: 16,
            borderTop: "1px solid var(--ink-100)",
            color: "var(--ink-400)",
            fontSize: 11.5,
            lineHeight: 1.6,
            textAlign: "center",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span>Powered by 智通 AI · © 2026 Five Oranges AI · 为</span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              color: "var(--ink-700)",
              fontWeight: 600,
            }}
          >
            <img
              src={`${import.meta.env.BASE_URL}jintai-logo.png`}
              alt="锦泰耐火材料"
              style={{ height: 16, width: "auto" }}
            />
            宜兴市锦泰耐火材料
          </span>
          <span>定制 · 演示版本 (纯前端 mock，不接后端)</span>
        </div>
      </div>
    </div>
  );
}

/* ---------------- 概览 → 经营日报 跳转入口（iter 11） ---------------- */

