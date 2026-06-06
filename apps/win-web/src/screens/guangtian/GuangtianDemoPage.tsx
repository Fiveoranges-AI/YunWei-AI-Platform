import { useEffect, useState } from "react";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { GuangtianHero } from "./GuangtianHero";
import { GuangtianProvider, useGT } from "./state";
import { ToastContainer } from "./Toast";
import { GuangtianDemoTour, tabForDemoStep } from "./GuangtianDemoTour";
import { DashboardPanel } from "./panels/DashboardPanel";
import { SkuCatalogPanel } from "./panels/SkuCatalogPanel";
import { InboundPanel } from "./panels/InboundPanel";
import { OutboundPanel } from "./panels/OutboundPanel";
import { LedgerPanel } from "./panels/LedgerPanel";
import { ShortageAlertPanel } from "./panels/ShortageAlertPanel";
import { RoiPanel } from "./panels/RoiPanel";
import { readInitialMode, writeModeToUrl, type BackendMode } from "./backendMode";
import { resolveBrand, brandCssVars } from "./branding";
import { GuangtianBackendModePanel } from "./GuangtianBackendModePanel";
import {
  GuangtianKpiOverlay, GuangtianLedgerOverlay,
  GuangtianShortageOverlay, GuangtianSkuOverlay,
} from "./GuangtianBackendOverlays";

type TabKey =
  | "dashboard"
  | "sku"
  | "inbound"
  | "outbound"
  | "ledger"
  | "shortage"
  | "roi"
  | "replenish"
  | "ask"
  | "report";

const TABS: {
  key: TabKey;
  label: string;
  hint: string;
  icon: typeof I.grid;
  color: string;
}[] = [
  { key: "dashboard", label: "工作台", hint: "今天库存什么情况", icon: I.grid, color: "var(--brand-500)" },
  { key: "sku", label: "SKU 档案", hint: "1,286 个产品全景", icon: I.pkg, color: "var(--brand-500)" },
  { key: "inbound", label: "入库登记", hint: "生产 / 采购 入库", icon: I.inbox, color: "var(--guangtian-blue)" },
  { key: "outbound", label: "出库登记", hint: "客户订单 出库", icon: I.upload, color: "var(--guangtian-blue)" },
  { key: "ledger", label: "库存流水", hint: "每一笔变动可追溯", icon: I.clock, color: "var(--guangtian-blue)" },
  { key: "shortage", label: "缺货预警", hint: "本周订单发不发得出", icon: I.warn, color: "var(--guangtian-red)" },
  { key: "roi", label: "省多少钱", hint: "用了能省多少 · 自己算", icon: I.grid, color: "var(--guangtian-blue)" },
];
// R2 砍 tab：AI 补产建议 / 老板助手 / AI 日报 三个"展示性"tab 从导航移除——
// MVP 只留可付费核心闭环（录入→库存→流水→预警→看板）。面板代码保留未删。

const TAB_HEAD: Record<TabKey, { title: string; sub: string }> = {
  dashboard: {
    title: "工作台",
    sub: "今日 KPI、库存风险提醒、AI 助手快捷入口，3 秒看清要紧的事。",
  },
  sku: {
    title: "SKU 产品档案",
    sub: "1,286 个 SKU 全景：编码 / 规格 / 库位 / 库存 / 状态 · AI 帮你统一命名规则。",
  },
  inbound: {
    title: "入库登记",
    sub: "生产入库 / 采购入库 / 退货入库 · AI 自动校验批次号 + 库位匹配。",
  },
  outbound: {
    title: "出库登记",
    sub: "客户订单出库 · 出库前 AI 自动核对库存余量，避免发不出货。",
  },
  ledger: {
    title: "库存流水追溯",
    sub: "每一笔入 / 出 / 调拨 / 盘点 / 报废都留痕 · 60 秒回放任意 SKU 半年流水。",
  },
  shortage: {
    title: "订单缺货预警",
    sub: "AI 把本周下游订单 vs 当前库存 + 在产订单做对账，发不出的提前 3 天告诉你。",
  },
  roi: {
    title: "试点价值 · 省多少钱",
    sub: "按光天的规模与行业平均，算一笔实在账：每月省人工 + 减少差异损失 + 减少缺货损失。",
  },
  replenish: {
    title: "AI 补产建议",
    sub: "AI 综合订单 / 出货趋势 / 安全库存 / 生产周期，给出本周补什么 + 补多少。",
  },
  ask: {
    title: "老板助手",
    sub: "不用打字——点推荐问题，AI 拿实时库存 / 流水 / 订单算出结构化结果，每条附数据来源。",
  },
  report: {
    title: "AI 库存日报",
    sub: "每天 18:30 自动生成 · 老板手机 5 分钟看完今天的库存 / 风险 / 补产 / 异常。",
  },
};

const HASH_TO_TAB: Record<string, TabKey> = {
  "#dashboard": "dashboard",
  "#sku": "sku",
  "#inbound": "inbound",
  "#outbound": "outbound",
  "#ledger": "ledger",
  "#shortage": "shortage",
  "#roi": "roi",
  "#replenish": "replenish",
  "#ask": "ask",
  "#report": "report",
};

function tabFromHash(hash: string): TabKey | null {
  return HASH_TO_TAB[hash] ?? null;
}

function hashForTab(t: TabKey): string {
  return `#${t}`;
}

export function GuangtianDemoPage() {
  return (
    <GuangtianProvider>
      <GuangtianDemoInner />
      <GuangtianDemoTour />
      <ToastContainer />
    </GuangtianProvider>
  );
}

function GuangtianDemoInner() {
  const isDesktop = useIsDesktop();
  const { demoStep } = useGT();
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (typeof window === "undefined") return "dashboard";
    return tabFromHash(window.location.hash) ?? "dashboard";
  });
  const [mode, setModeState] = useState<BackendMode>(() => readInitialMode());
  const setMode = (m: BackendMode) => { setModeState(m); writeModeToUrl(m); };
  const backend = mode === "backend";

  // iter G12-B: demo step 推进时自动切对应 tab
  useEffect(() => {
    const target = tabForDemoStep(demoStep);
    if (target && target !== activeTab) {
      setActiveTab(target as TabKey);
      if (typeof window !== "undefined") {
        const next = `#${target}`;
        if (window.location.hash !== next) history.pushState(null, "", next);
        window.scrollTo({ top: 0, behavior: "auto" });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoStep]);

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
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  };

  const head = TAB_HEAD[activeTab];
  const demoActive = demoStep > 0 && demoStep <= 6;
  // 跨客户换肤: 把品牌色注入 CSS 变量,全站 var(--guangtian-*) 自动跟随
  // (?customer=guangtian|jintai|yinhu|haina)。
  const brand = resolveBrand();

  return (
    <div
      className="scroll"
      style={{ flex: 1, background: "var(--bg)", ...brandCssVars(brand) }}
    >
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: isDesktop
            ? `${demoActive ? 80 : 20}px 32px 64px`
            : `${demoActive ? 70 : 12}px 16px 80px`,
          transition: "padding-top 0.25s ease",
        }}
      >
        {/* Tab navigation */}
        <nav
          aria-label="光天试点 演示分页"
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

        {/* Per-tab header */}
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
            {brand.id === "guangtian" ? "光天试点" : brand.company} <span style={{ color: "var(--ink-300)" }}>/</span>{" "}
            <span style={{ color: "var(--guangtian-red)" }}>{head.title}</span>
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

        {/* Panels — kept mounted (display toggle) so each panel's internal state survives tab switches */}

        <div role="tabpanel" hidden={activeTab !== "dashboard"}>
          <GuangtianKpiOverlay enabled={backend} />
          <GuangtianHero
            onGoSku={() => switchTab("sku")}
            onGoInbound={() => switchTab("inbound")}
            onGoAsk={() => switchTab("shortage")}
          />
          <DashboardPanel onGoTab={(t) => switchTab(t as TabKey)} />
        </div>

        <div role="tabpanel" hidden={activeTab !== "sku"}>
          <GuangtianSkuOverlay enabled={backend} />
          <SkuCatalogPanel />
        </div>

        <div role="tabpanel" hidden={activeTab !== "inbound"}>
          <InboundPanel />
        </div>

        <div role="tabpanel" hidden={activeTab !== "outbound"}>
          <OutboundPanel />
        </div>

        <div role="tabpanel" hidden={activeTab !== "ledger"}>
          <GuangtianLedgerOverlay enabled={backend} />
          <LedgerPanel />
        </div>

        <div role="tabpanel" hidden={activeTab !== "shortage"}>
          <GuangtianShortageOverlay enabled={backend} />
          <ShortageAlertPanel />
        </div>

        <div role="tabpanel" hidden={activeTab !== "roi"}>
          <RoiPanel />
        </div>

        {/* R2: 补产建议 / 老板助手 / 日报 三个 tabpanel 已随导航砍掉 */}

        {/* footer */}
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
              src={`${import.meta.env.BASE_URL}guangtian-logo.png`}
              alt="光天科技"
              style={{ height: 16, width: "auto" }}
            />
            宜兴光天耐火材料
          </span>
          <span>定制 · v2026.05 演示版本 {backend ? "(真后端模式 · /api/win/guangtian)" : "(默认 mock · ?mode=backend 接真后端)"}</span>
        </div>
      </div>
      <GuangtianBackendModePanel mode={mode} onSetMode={setMode} />
    </div>
  );
}
