import { useState } from "react";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { dailyBrief } from "./data";
import type {
  DailyBriefAction,
  DailyBriefBlock,
  DailyBriefHistory,
  DailyBriefRisk,
} from "./data";

const RISK_META = {
  high: { dot: "🔴", label: "高", bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4" },
  medium: { dot: "🟡", label: "中", bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6" },
  low: { dot: "🟢", label: "低", bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2" },
} as const;

const CATEGORY_COLOR: Record<DailyBriefAction["category"], string> = {
  财务: "var(--ai-700)",
  生产: "var(--brand-700)",
  采购: "var(--warn-700)",
  销售: "var(--ok-700)",
};

export function JintaiDailyBriefPanel() {
  const isDesktop = useIsDesktop();
  const b = dailyBrief;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 顶部摘要条：日期 + 计数 + AI 草稿条 */}
      <TopSummary />

      {/* 6 分块：4 个 category + 风险 + AI 行动 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "repeat(2, 1fr)" : "1fr",
          gap: 14,
        }}
      >
        {b.blocks.map((blk) => (
          <CategoryBlock key={blk.category} block={blk} />
        ))}
      </div>

      {/* 第 5 块：风险线索（满宽） */}
      <RisksBlock risks={b.risks} />

      {/* 第 6 块：AI 建议今日行动（满宽 + 可勾选） */}
      <ActionsBlock actions={b.actions} />

      {/* 底部：日报历史折叠区 */}
      <HistoryFold history={b.history} />
    </div>
  );
}

/* ---------------- 顶部摘要条 ---------------- */

function TopSummary() {
  const isDesktop = useIsDesktop();
  const b = dailyBrief;
  const total = b.counts.sales + b.counts.finance + b.counts.production + b.counts.purchase + b.counts.risk;

  return (
    <div className="card" style={{ padding: 20 }}>
      {/* AI 草稿 banner */}
      <div
        style={{
          padding: "10px 12px",
          borderRadius: 10,
          background: "var(--ai-100)",
          border: "1px solid #bddff3",
          marginBottom: 14,
          fontSize: 11.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
        }}
      >
        <span style={{ flexShrink: 0, color: "var(--ai-700)", fontWeight: 700, paddingTop: 1 }}>
          {I.spark(12)}
        </span>
        <span>
          <strong style={{ color: "var(--ai-700)" }}>AI 草稿</strong> · 智通 AI 已于{" "}
          <strong>{b.generatedAt}</strong> 自动生成今日经营日报，
          整合财务、生产、采购、客户、风险 5 大模块数据。陈总，您醒后 5 分钟看完。
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 10,
          flexWrap: "wrap",
          marginBottom: 10,
        }}
      >
        <span
          style={{
            fontSize: isDesktop ? 22 : 18,
            fontWeight: 800,
            color: "var(--ink-900)",
            letterSpacing: "-0.01em",
          }}
        >
          {b.date}
        </span>
        <span style={{ fontSize: 13, color: "var(--ink-600)", fontWeight: 600 }}>
          {b.weekday} · 早上 8:00
        </span>
        <span style={{ flex: 1 }} />
        <span
          className="pill"
          style={{
            background: "var(--brand-100)",
            color: "var(--brand-700)",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          今日要事 {total}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          marginBottom: 12,
        }}
      >
        <CountPill icon="🤝" label="销售" n={b.counts.sales} />
        <CountPill icon="💰" label="财务" n={b.counts.finance} />
        <CountPill icon="🏭" label="生产" n={b.counts.production} />
        <CountPill icon="📦" label="采购" n={b.counts.purchase} />
        <CountPill icon="⚠️" label="风险" n={b.counts.risk} risk />
      </div>

      <div
        style={{
          padding: "12px 14px",
          borderRadius: 10,
          background: "var(--surface-2)",
          border: "1px solid var(--ink-100)",
          fontSize: 13,
          color: "var(--ink-800)",
          lineHeight: 1.65,
        }}
      >
        {b.aiSummary}
      </div>
    </div>
  );
}

function CountPill({
  icon,
  label,
  n,
  risk,
}: {
  icon: string;
  label: string;
  n: number;
  risk?: boolean;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "5px 10px",
        borderRadius: 8,
        background: risk && n > 0 ? "var(--risk-100)" : "var(--surface-2)",
        color: risk && n > 0 ? "var(--risk-700)" : "var(--ink-700)",
        border: risk && n > 0 ? "1px solid #f2c7c4" : "1px solid var(--ink-100)",
        fontSize: 11.5,
        fontWeight: 600,
      }}
    >
      <span>{icon}</span> {label} <strong style={{ fontFamily: "ui-monospace, monospace" }}>{n}</strong>
    </span>
  );
}

/* ---------------- 4 个 category 分块 ---------------- */

function CategoryBlock({ block }: { block: DailyBriefBlock }) {
  return (
    <div
      className="card"
      style={{
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 18 }}>{block.icon}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
          {block.category}一句话
        </span>
      </div>
      <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
        {block.bullets.map((line, i) => (
          <li
            key={i}
            style={{
              fontSize: 12.5,
              color: "var(--ink-700)",
              lineHeight: 1.6,
              paddingLeft: 14,
              position: "relative",
            }}
          >
            <span
              style={{
                position: "absolute",
                left: 0,
                top: 8,
                width: 4,
                height: 4,
                borderRadius: 2,
                background: "var(--ink-300)",
              }}
            />
            <BulletText text={line} />
          </li>
        ))}
      </ul>
      <div
        style={{
          padding: "8px 12px",
          borderRadius: 8,
          background: "var(--ai-100)",
          border: "1px solid #bddff3",
          fontSize: 11.5,
          color: "var(--ai-700)",
          lineHeight: 1.55,
          display: "flex",
          alignItems: "flex-start",
          gap: 6,
        }}
      >
        <span style={{ flexShrink: 0, fontWeight: 700, marginTop: 1 }}>{I.spark(10)}</span>
        <span style={{ color: "var(--ink-700)" }}>
          <strong style={{ color: "var(--ai-700)" }}>AI 提示</strong> · {block.aiHint}
        </span>
      </div>
    </div>
  );
}

/**
 * 把 「」包裹的内容加粗等宽显示。
 */
function BulletText({ text }: { text: string }) {
  const parts = text.split(/(「[^」]+」)/);
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith("「") && p.endsWith("」")) {
          return (
            <strong
              key={i}
              style={{
                color: "var(--ink-900)",
                fontWeight: 700,
                fontFamily: "ui-monospace, monospace",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {p.slice(1, -1)}
            </strong>
          );
        }
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}

/* ---------------- 风险线索 ---------------- */

function RisksBlock({ risks }: { risks: DailyBriefRisk[] }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 16 }}>⚠️</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
          风险线索（最多 3 条 · 按严重度）
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {risks.map((r, i) => {
          const m = RISK_META[r.level];
          return (
            <div
              key={i}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "var(--surface)",
                border: `1px solid ${m.border}`,
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
              }}
            >
              <span
                style={{
                  width: 32,
                  height: 22,
                  borderRadius: 6,
                  background: m.bg,
                  color: m.fg,
                  fontSize: 11,
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {m.dot} {m.label}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)", lineHeight: 1.5, marginBottom: 4 }}>
                  <BulletText text={r.title} />
                </div>
                <div style={{ fontSize: 11.5, color: "var(--ink-600)", lineHeight: 1.55 }}>
                  <strong style={{ color: "var(--ai-700)" }}>建议</strong> · {r.recommendation}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- AI 建议今日行动 ---------------- */

function ActionsBlock({ actions }: { actions: DailyBriefAction[] }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setDone((cur) => {
      const next = new Set(cur);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  const allDone = done.size === actions.length;

  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 16 }}>🎯</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
          AI 建议今日行动
        </span>
        <span style={{ flex: 1 }} />
        <span
          style={{
            fontSize: 11,
            color: allDone ? "var(--ok-700)" : "var(--ink-500)",
            fontWeight: allDone ? 700 : 500,
          }}
        >
          已处理 {done.size} / {actions.length}
          {allDone && " ✓"}
        </span>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginBottom: 12 }}>
        点一下勾选「已处理」，AI 会同步到日报历史里。
      </div>
      {allDone && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            background: "var(--ok-100)",
            border: "1px solid #c7e4d2",
            color: "var(--ok-700)",
            fontSize: 12.5,
            fontWeight: 600,
            marginBottom: 10,
            lineHeight: 1.55,
          }}
        >
          🎉 今日 AI 建议 100% 已执行。明早 7:55 AI 会自动准备明日日报。
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {actions.map((a, i) => {
          const isDone = done.has(i);
          return (
            <button
              key={i}
              onClick={() => toggle(i)}
              style={{
                textAlign: "left",
                padding: "12px 14px",
                borderRadius: 10,
                background: isDone ? "var(--surface-2)" : "var(--surface)",
                border: `1px solid ${isDone ? "var(--ok-500)" : "var(--ink-100)"}`,
                cursor: "pointer",
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                fontFamily: "var(--font)",
              }}
            >
              <span
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 4,
                  border: `1.5px solid ${isDone ? "var(--ok-500)" : "var(--ink-300)"}`,
                  background: isDone ? "var(--ok-500)" : "transparent",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  fontWeight: 700,
                  flexShrink: 0,
                  marginTop: 1,
                }}
              >
                {isDone ? "✓" : ""}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 4,
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--ink-900)",
                      fontFamily: "ui-monospace, monospace",
                    }}
                  >
                    {a.time}
                  </span>
                  <span
                    className="pill"
                    style={{
                      fontSize: 10.5,
                      background: "var(--surface-2)",
                      color: CATEGORY_COLOR[a.category],
                      fontWeight: 600,
                      border: "1px solid var(--ink-100)",
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

/* ---------------- 历史折叠区 ---------------- */

function HistoryFold({ history }: { history: DailyBriefHistory[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="card-flat"
      style={{
        padding: "12px 16px",
        borderRadius: 12,
        background: "var(--surface-2)",
        border: "1px solid var(--ink-100)",
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          background: "transparent",
          border: "none",
          padding: 0,
          cursor: "pointer",
          color: "var(--ink-700)",
          fontSize: 12.5,
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontFamily: "var(--font)",
        }}
      >
        <span>{open ? "▼" : "▶"}</span> 日报历史（最近 5 天）
      </button>
      {open && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          {history.map((h) => (
            <div
              key={h.date}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 12px",
                borderRadius: 8,
                background: "var(--surface)",
                border: "1px solid var(--ink-100)",
                fontSize: 12,
                flexWrap: "wrap",
              }}
            >
              <span style={{ color: "var(--ink-700)", fontWeight: 600, minWidth: 110 }}>{h.date}</span>
              <span
                className="pill"
                style={{
                  fontSize: 10.5,
                  background: "var(--ok-100)",
                  color: "var(--ok-700)",
                  fontWeight: 600,
                }}
              >
                {h.status}
              </span>
              <span style={{ color: "var(--risk-700)", fontFamily: "ui-monospace, monospace", fontWeight: 600 }}>
                🔴 {h.red}
              </span>
              <span style={{ color: "var(--warn-700)", fontFamily: "ui-monospace, monospace", fontWeight: 600 }}>
                🟡 {h.yellow}
              </span>
              <span style={{ color: "var(--ink-600)", fontFamily: "ui-monospace, monospace" }}>
                🎯 {h.actions} 行动
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
