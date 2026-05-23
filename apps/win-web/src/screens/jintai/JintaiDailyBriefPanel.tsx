import { useState } from "react";
import { useIsDesktop } from "../../lib/breakpoints";
import { dailyBrief } from "./data";
import type { DailyBriefAction, DailyBriefHistory, DailyBriefRisk } from "./data";

/**
 * iter 21：经营日报全面图表化 + 顶部加锦泰品牌头。
 * 设计原则：
 *  - 老板/会计 30 秒扫一眼 → 数字 + 色块 + 进度条 + sparkline，文字仅作 1 行注释
 *  - 锦泰 logo 等比放大 + 公司主标题 = 演示第一印象
 *  - 不引图表库，全部自绘 SVG / CSS
 */

const RISK_META = {
  high: { label: "高", bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4", bar: "var(--risk-500)" },
  medium: { label: "中", bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6", bar: "var(--warn-500)" },
  low: { label: "低", bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2", bar: "var(--ok-500)" },
} as const;

const CATEGORY_META: Record<DailyBriefAction["category"], { color: string; bg: string }> = {
  财务: { color: "var(--ai-700)", bg: "var(--ai-100)" },
  生产: { color: "var(--jintai-red)", bg: "rgba(195,38,41,0.08)" },
  采购: { color: "var(--warn-700)", bg: "var(--warn-100)" },
  销售: { color: "var(--jintai-green-dark)", bg: "rgba(27,127,58,0.08)" },
};

export function JintaiDailyBriefPanel() {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* iter 21.0：锦泰品牌头 — logo 等比放大 + 公司主标题 */}
      <JintaiBrandHeader />

      {/* 顶部要事条 — 5 段堆叠色块 + 3 件大事 */}
      <TodayHeroStrip />

      {/* KPI 网格 — 4 个核心数字 + sparkline */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
          gap: 12,
        }}
      >
        <KpiCard
          label="货币资金"
          value="8,200,000"
          unit="元"
          deltaText="较月初 +170,000"
          deltaTone="positive"
          series={[7980, 8030, 8030, 8030, 8050, 8100, 8200]}
          tone="brand"
        />
        <KpiCard
          label="进行中生产单"
          value="12"
          unit="张"
          deltaText="今日完成 2 张"
          deltaTone="neutral"
          series={[8, 9, 10, 11, 11, 12, 12]}
          tone="red"
        />
        <KpiCard
          label="本月应付"
          value="327,000"
          unit="元"
          deltaText="超期 1 笔 / 30 天内 2 笔"
          deltaTone="warn"
          series={[180, 220, 250, 270, 290, 310, 327]}
          tone="warn"
        />
        <KpiCard
          label="本月回款"
          value="4,800,000"
          unit="元"
          deltaText="今日新增 1,200,000"
          deltaTone="positive"
          series={[800, 1500, 2200, 2800, 3400, 3900, 4800]}
          tone="green"
        />
      </div>

      {/* 风险线索 — 横向 3 色块 */}
      <RisksStrip risks={dailyBrief.risks} />

      {/* AI 建议今日行动 — 时间轴 */}
      <ActionsTimeline actions={dailyBrief.actions} />

      {/* 日报历史 — 横向 mini bars */}
      <HistoryStrip history={dailyBrief.history} />
    </div>
  );
}

/* ============== 锦泰品牌头 ============== */

function JintaiBrandHeader() {
  const isDesktop = useIsDesktop();
  const b = dailyBrief;
  return (
    <div
      className="card"
      style={{
        padding: 0,
        overflow: "hidden",
        borderTop: "3px solid var(--jintai-red)",
      }}
    >
      <div
        style={{
          padding: isDesktop ? "20px 24px" : "16px 18px",
          display: "flex",
          alignItems: "center",
          gap: isDesktop ? 20 : 14,
          flexWrap: "wrap",
        }}
      >
        <img
          src={`${import.meta.env.BASE_URL}jintai-logo.png`}
          alt="宜兴市锦泰耐火材料"
          style={{
            height: isDesktop ? 72 : 56,
            width: "auto",
            flexShrink: 0,
            borderRadius: 8,
          }}
        />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div
            style={{
              fontSize: isDesktop ? 24 : 20,
              fontWeight: 800,
              color: "var(--ink-900)",
              letterSpacing: "0.02em",
              lineHeight: 1.2,
            }}
          >
            宜兴市锦泰耐火材料
          </div>
          <div
            style={{
              fontSize: isDesktop ? 13 : 12,
              color: "var(--ink-500)",
              marginTop: 4,
              fontWeight: 500,
              letterSpacing: "0.04em",
            }}
          >
            AI 生产流转 · 经营助手 · 2026 试点
          </div>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 4,
          }}
        >
          <div
            style={{
              fontSize: isDesktop ? 20 : 17,
              fontWeight: 800,
              color: "var(--ink-900)",
              fontFamily: "ui-monospace, monospace",
              letterSpacing: "-0.01em",
            }}
          >
            {b.date}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
            {b.weekday} · AI 草稿 {b.generatedAt.slice(-5)} 已生成
          </div>
        </div>
      </div>
      {/* 锦泰红绿色带 */}
      <div
        style={{
          height: 3,
          background:
            "linear-gradient(90deg, var(--jintai-red) 0%, var(--jintai-red) 50%, var(--jintai-green) 50%, var(--jintai-green) 100%)",
        }}
      />
    </div>
  );
}

/* ============== 顶部要事条:5 段彩色堆叠 + 3 件大事 ============== */

function TodayHeroStrip() {
  const b = dailyBrief;
  const counts = [
    { key: "销售", n: b.counts.sales, color: "var(--jintai-green-dark)" },
    { key: "财务", n: b.counts.finance, color: "var(--ai-700)" },
    { key: "生产", n: b.counts.production, color: "var(--jintai-red)" },
    { key: "采购", n: b.counts.purchase, color: "var(--warn-700)" },
    { key: "风险", n: b.counts.risk, color: "var(--risk-700)" },
  ];
  const total = counts.reduce((a, c) => a + c.n, 0);
  return (
    <div className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
      {/* 横向堆叠条 — 5 段比例 */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 8,
            marginBottom: 8,
          }}
        >
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-700)" }}>
            今日要事
          </span>
          <span style={{ fontSize: 24, fontWeight: 800, color: "var(--ink-900)", fontFamily: "ui-monospace, monospace" }}>
            {total}
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-500)" }}>条 · 跨 5 模块</span>
          <span style={{ flex: 1 }} />
          <span
            style={{
              fontSize: 10.5,
              color: "var(--ai-700)",
              fontWeight: 700,
              padding: "3px 9px",
              borderRadius: 5,
              background: "var(--ai-100)",
              border: "1px solid #bddff3",
              letterSpacing: "0.04em",
            }}
          >
            ✨ AI 先填 → 陈总扫一眼
          </span>
        </div>
        <div
          style={{
            display: "flex",
            height: 28,
            borderRadius: 6,
            overflow: "hidden",
            border: "1px solid var(--ink-100)",
          }}
        >
          {counts.map((c) => (
            <div
              key={c.key}
              style={{
                flex: c.n,
                background: c.color,
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11.5,
                fontWeight: 700,
                minWidth: c.n > 0 ? 0 : 0,
              }}
              title={`${c.key}: ${c.n}`}
            >
              {c.n > 0 && `${c.key} ${c.n}`}
            </div>
          ))}
        </div>
      </div>

      {/* 3 件大事 — 高亮色块,1 句话 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 10,
        }}
      >
        <BigThingCard
          tone="risk"
          icon="🏭"
          title="容百 SC-2026-016 烧结晚 2 天"
          sub="可能影响 06-20 交期"
        />
        <BigThingCard
          tone="ai"
          icon="💰"
          title="5 月三表已生成"
          sub="净利润 1,189,000 · 毛利率 35.0% · 等您一眼"
        />
        <BigThingCard
          tone="warn"
          icon="📦"
          title="α 氧化铝粉涨价 +6.7%"
          sub="下批采购前建议先问行情"
        />
      </div>
    </div>
  );
}

function BigThingCard({
  tone,
  icon,
  title,
  sub,
}: {
  tone: "risk" | "ai" | "warn";
  icon: string;
  title: string;
  sub: string;
}) {
  const tones = {
    risk: { bg: "var(--risk-100)", border: "#f2c7c4", fg: "var(--risk-700)" },
    ai: { bg: "var(--ai-100)", border: "#bddff3", fg: "var(--ai-700)" },
    warn: { bg: "var(--warn-100)", border: "#f1d4a6", fg: "var(--warn-700)" },
  };
  const t = tones[tone];
  return (
    <div
      style={{
        padding: "10px 12px",
        borderRadius: 8,
        background: t.bg,
        borderLeft: `3px solid ${t.fg}`,
        border: `1px solid ${t.border}`,
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
      }}
    >
      <span style={{ fontSize: 16, lineHeight: 1.2, flexShrink: 0 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", lineHeight: 1.4 }}>
          {title}
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-600)", marginTop: 2, lineHeight: 1.5 }}>
          {sub}
        </div>
      </div>
    </div>
  );
}

/* ============== KPI 卡 + sparkline (自绘 SVG) ============== */

function KpiCard({
  label,
  value,
  unit,
  deltaText,
  deltaTone,
  series,
  tone,
}: {
  label: string;
  value: string;
  unit: string;
  deltaText: string;
  deltaTone: "positive" | "neutral" | "warn";
  series: number[];
  tone: "brand" | "red" | "green" | "warn";
}) {
  const toneColor: Record<typeof tone, string> = {
    brand: "var(--brand-700)",
    red: "var(--jintai-red)",
    green: "var(--jintai-green-dark)",
    warn: "var(--warn-700)",
  };
  const toneFill: Record<typeof tone, string> = {
    brand: "rgba(56,138,210,0.12)",
    red: "rgba(195,38,41,0.10)",
    green: "rgba(27,127,58,0.10)",
    warn: "rgba(217,142,26,0.12)",
  };
  const deltaColor =
    deltaTone === "positive"
      ? "var(--ok-700)"
      : deltaTone === "warn"
      ? "var(--warn-700)"
      : "var(--ink-500)";
  return (
    <div
      className="card"
      style={{
        padding: 14,
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 600 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: "var(--ink-900)",
            fontFamily: "ui-monospace, monospace",
            letterSpacing: "-0.01em",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {value}
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 500 }}>{unit}</span>
      </div>
      <Sparkline series={series} color={toneColor[tone]} fill={toneFill[tone]} />
      <div style={{ fontSize: 11, color: deltaColor, fontWeight: 500, lineHeight: 1.5 }}>
        {deltaText}
      </div>
    </div>
  );
}

function Sparkline({
  series,
  color,
  fill,
  width = 160,
  height = 32,
}: {
  series: number[];
  color: string;
  fill: string;
  width?: number;
  height?: number;
}) {
  if (series.length < 2) return null;
  const max = Math.max(...series);
  const min = Math.min(...series);
  const range = max - min || 1;
  const step = width / (series.length - 1);
  const pts = series.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return [x, y];
  });
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${path} L ${width} ${height} L 0 ${height} Z`;
  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ display: "block", marginTop: 2 }}
    >
      <path d={area} fill={fill} />
      <path d={path} stroke={color} strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={2.5} fill={color} />
    </svg>
  );
}

/* ============== 风险线索 — 横向 3 色块 ============== */

function RisksStrip({ risks }: { risks: DailyBriefRisk[] }) {
  const isDesktop = useIsDesktop();
  return (
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>风险线索</span>
        <span style={{ fontSize: 11, color: "var(--ink-500)" }}>按严重度排序</span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "repeat(3, 1fr)" : "1fr",
          gap: 10,
        }}
      >
        {risks.map((r, i) => {
          const m = RISK_META[r.level];
          return (
            <div
              key={i}
              style={{
                padding: "10px 12px",
                borderRadius: 8,
                background: "var(--surface)",
                border: `1px solid ${m.border}`,
                borderLeft: `3px solid ${m.fg}`,
                display: "flex",
                flexDirection: "column",
                gap: 5,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: m.bg,
                    color: m.fg,
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.05em",
                  }}
                >
                  {m.label}风险
                </span>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-900)", lineHeight: 1.45 }}>
                {stripBracket(r.title)}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-600)", lineHeight: 1.5 }}>
                <span style={{ color: "var(--ai-700)", fontWeight: 600 }}>建议</span> · {r.recommendation}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function stripBracket(s: string) {
  return s.replace(/「/g, "").replace(/」/g, "");
}

/* ============== AI 建议今日行动 — 时间轴 ============== */

function ActionsTimeline({ actions }: { actions: DailyBriefAction[] }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setDone((cur) => {
      const next = new Set(cur);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  return (
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
          AI 建议今日行动
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "var(--ink-500)", fontFamily: "ui-monospace, monospace" }}>
          {done.size} / {actions.length}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 0, position: "relative" }}>
        {actions.map((a, i) => {
          const isDone = done.has(i);
          const meta = CATEGORY_META[a.category];
          const isLast = i === actions.length - 1;
          return (
            <button
              key={i}
              onClick={() => toggle(i)}
              style={{
                textAlign: "left",
                background: "transparent",
                border: "none",
                padding: "8px 0 8px 0",
                cursor: "pointer",
                display: "grid",
                gridTemplateColumns: "60px 22px 1fr",
                gap: 10,
                alignItems: "flex-start",
                fontFamily: "var(--font)",
                position: "relative",
              }}
            >
              {/* 时间 */}
              <span
                style={{
                  fontSize: 11,
                  color: "var(--ink-500)",
                  fontWeight: 600,
                  fontFamily: "ui-monospace, monospace",
                  paddingTop: 3,
                }}
              >
                {a.time}
              </span>
              {/* 时间轴竖线 + 圆点 */}
              <span
                style={{
                  position: "relative",
                  width: 22,
                  display: "flex",
                  justifyContent: "center",
                  paddingTop: 4,
                }}
              >
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 6,
                    background: isDone ? "var(--ok-500)" : meta.bg,
                    border: `2px solid ${isDone ? "var(--ok-500)" : meta.color}`,
                    color: "#fff",
                    fontSize: 9,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 1,
                  }}
                >
                  {isDone ? "✓" : ""}
                </span>
                {!isLast && (
                  <span
                    style={{
                      position: "absolute",
                      top: 16,
                      bottom: -16,
                      width: 2,
                      background: "var(--ink-100)",
                    }}
                  />
                )}
              </span>
              {/* 内容 */}
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "1px 6px",
                      borderRadius: 4,
                      background: meta.bg,
                      color: meta.color,
                      letterSpacing: "0.04em",
                    }}
                  >
                    {a.category}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: isDone ? "var(--ink-400)" : "var(--ink-800)",
                    lineHeight: 1.55,
                    textDecoration: isDone ? "line-through" : "none",
                  }}
                >
                  {a.action}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ============== 日报历史 — 横向 mini bars ============== */

function HistoryStrip({ history }: { history: DailyBriefHistory[] }) {
  const maxRed = Math.max(...history.map((h) => h.red), 1);
  const maxYellow = Math.max(...history.map((h) => h.yellow), 1);
  return (
    <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
          近 5 天日报历史
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-500)" }}>红高风险 · 黄中风险</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
        {history.map((h) => (
          <div
            key={h.date}
            style={{
              padding: 10,
              borderRadius: 8,
              border: "1px solid var(--ink-100)",
              background: "var(--surface)",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600 }}>
              {h.date.split(" ")[0].slice(5)}
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", height: 36, gap: 4 }}>
              <Bar value={h.red} max={maxRed} color="var(--risk-500)" />
              <Bar value={h.yellow} max={maxYellow} color="var(--warn-500)" />
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--ink-500)",
                fontFamily: "ui-monospace, monospace",
                display: "flex",
                gap: 6,
              }}
            >
              <span style={{ color: "var(--risk-700)" }}>{h.red}</span>
              <span style={{ color: "var(--warn-700)" }}>{h.yellow}</span>
              <span>·🎯{h.actions}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const h = max > 0 ? Math.max(2, (value / max) * 100) : 2;
  return (
    <div
      style={{
        flex: 1,
        height: `${h}%`,
        background: color,
        borderRadius: 2,
        opacity: value === 0 ? 0.2 : 1,
      }}
      title={`${value}`}
    />
  );
}
