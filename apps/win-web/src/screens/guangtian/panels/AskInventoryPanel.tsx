import { useEffect, useRef, useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { askPresets, askSampleConversation } from "../data";
import { useGT } from "../state";
import { Spinner } from "../Toast";

type Msg =
  | { role: "user"; text: string }
  | { role: "ai"; text: string; sources?: { label: string; count: number }[] }
  | { role: "ai-block"; block: AnswerBlock };

// iter G11: 答案块支持结构化 + 可点击明细链接
type AnswerBlock = {
  // 结论
  conclusion: string;
  // 数据依据 (chips)
  evidence: { label: string; count: number }[];
  // 风险等级
  risk: "urgent" | "high" | "medium" | "low" | "info";
  // 建议动作
  actions: string[];
  // 可点击明细 — 跳对应 tab
  links: { label: string; target: "sku" | "shortage" | "ledger" | "replenish" | "report" }[];
};

const PRESET_ANSWERS: Record<string, AnswerBlock> = {
  "今天哪些产品库存不够？": {
    conclusion:
      "今天 3 个 SKU 低于安全线，其中 1 个已完全缺货：\n• 🔴 JC-16 浇注料 — 库存 0 / 安全 200（缺货 14 天）\n• 🟡 M70 莫来石砖 — 库存 320 / 安全 800（11 天耗尽）\n• 🟡 AL90 高纯刚玉砖 — 库存 78 / 安全 200",
    evidence: [
      { label: "SKU 库存快照 · 10:18", count: 1286 },
      { label: "近 30 天出货流水", count: 1247 },
    ],
    risk: "high",
    actions: [
      "立即排产 JC-16 浇注料 400 袋（5/22 可出炉）",
      "M70 莫来石砖 补产 600 块（5/23 出炉）",
      "AL90 高纯刚玉砖 补产 250 块（5/26 出炉）",
    ],
    links: [
      { label: "查看 SKU 档案 · 低库存筛选", target: "sku" },
      { label: "去 AI 补产建议 一键挂工艺组", target: "replenish" },
    ],
  },
  "江苏宏泰订单现在能不能发？": {
    conclusion:
      "江苏宏泰 2 笔在手订单，1 紧急 + 1 可发：\n• 🚨 SO-20260519-001 · 5/22 交付 · 仅 23% 可发（JC-16 完全缺货 200 袋 / JC18-LR 60 袋齐）\n• 🟢 SO-20260519-002 · 5/25 交付 · 100% 可发（JC18-LR 60 袋齐备）",
    evidence: [
      { label: "下游订单表 · 江苏宏泰", count: 2 },
      { label: "SKU 库存 · 实时", count: 1286 },
    ],
    risk: "urgent",
    actions: [
      "001 单分批：先发 JC18-LR 60 袋，JC-16 延 3 天",
      "起草延期通知短信发江苏宏泰李经理",
      "立即生成 JC-16 400 袋补产单",
    ],
    links: [
      { label: "看 SO-20260519-001 完整明细", target: "shortage" },
      { label: "去出库登记 操作分批发货", target: "ledger" },
    ],
  },
  "哪些 SKU 最近出库最快？": {
    conclusion:
      "近 7 天出库 TOP 3：\n• #1 JT-HLZ-230-114-65 高铝砖 — 累计出货 4,800 块（占总 35%）\n• #2 JT-JZL-JC18-LR 低水泥浇注料 — 320 袋（占 18%）\n• #3 JT-MLS-M70 莫来石砖 — 280 块（占 15%）\n\n高铝砖出货异常高，疑似单一大客户集中采购（宜兴华能 5/19 一单 1,500 块）。",
    evidence: [
      { label: "近 7 天出库流水", count: 156 },
      { label: "TOP 客户分析", count: 12 },
    ],
    risk: "medium",
    actions: [
      "对高铝砖供应链做风险评估（单一大客户依赖）",
      "适当上调高铝砖安全库存到 3,000 块",
    ],
    links: [{ label: "去库存流水 看完整出货明细", target: "ledger" }],
  },
  "哪些产品可能漏记了？": {
    conclusion:
      "AI 流水交叉比对，发现 2 条疑似漏记 / 数据异常：\n• JT-GZB-AL80 刚玉砖 — 5/18 盘点账实差 +12 块（待复核）\n• JT-HLZ-T3-150 高铝砖 — 5/18 调拨方向异常（B-05 备货区 → A-04 常备区 +1,200，与低活跃标签矛盾）",
    evidence: [
      { label: "流水扫描 · 近 7 天", count: 41 },
      { label: "盘点单 · PD-20260518", count: 1 },
    ],
    risk: "medium",
    actions: [
      "请张仓管核对 PO-2026-0089 实物清点",
      "AL80 标记为「数据异常」状态，限制出库直到确认",
    ],
    links: [
      { label: "去库存流水 看 AI 异常识别", target: "ledger" },
      { label: "去 SKU 档案 看 AL80 状态", target: "sku" },
    ],
  },
  "明天应该优先生产什么？": {
    conclusion:
      "AI 综合 7 个在手订单 + 30 天出货趋势 + 安全库存 + 窑炉空闲 4 天，明日（5/21）排产推荐：\n\n#1 JC-16 浇注料 200 袋（紧急，对应江苏宏泰 SO-20260519-001 + 安全库存补 200）\n#2 M70 莫来石砖 600 块（高，对应常州新材 SO-003）\n\n若产能允许，可同步排产 #3 AL90 250 块（中优，下周四前需用）。",
    evidence: [
      { label: "在手订单需求", count: 7 },
      { label: "近 30 天出货预测", count: 1247 },
      { label: "工艺组窑炉空闲", count: 4 },
    ],
    risk: "high",
    actions: [
      "优先 JC-16 200 袋（明日 5/21 排产，5/22 出炉勉强可发 001 单）",
      "M70 600 块同步排（4 天工期，5/24 入库）",
      "把补产计划发陈工微信",
    ],
    links: [
      { label: "去 AI 补产建议 一键发陈工", target: "replenish" },
      { label: "去缺货预警 看订单倒推", target: "shortage" },
    ],
  },
};

const FALLBACK_ANSWER = (q: string): AnswerBlock => ({
  conclusion: `（演示版本）AI 已收到您的问题："${q}"。上线后 AI 会基于实时库存（1,286 SKU）/ 近 30 天流水（1,247 条）/ 7 个下游订单综合作答，并给出结构化结论 + 数据依据 + 建议动作 + 可点击明细。`,
  evidence: [
    { label: "本地库存数据", count: 1286 },
    { label: "近 30 天流水", count: 1247 },
  ],
  risk: "info",
  actions: ["试试左侧 5 个预设问题，看 AI 真实响应"],
  links: [],
});

type AskProps = { onGoTab?: (key: string) => void };

export function AskInventoryPanel({ onGoTab }: AskProps = {}) {
  const isDesktop = useIsDesktop();
  const { showToast, pendingAsk, setPendingAsk, demoStep } = useGT();
  const [messages, setMessages] = useState<Msg[]>(askSampleConversation as Msg[]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const send = (q?: string) => {
    const txt = (q ?? input).trim();
    if (!txt || thinking) return;
    setMessages((prev) => [...prev, { role: "user", text: txt }]);
    setInput("");
    setThinking(true);
    window.setTimeout(() => {
      const preset = PRESET_ANSWERS[txt];
      const block = preset ?? FALLBACK_ANSWER(txt);
      setMessages((prev) => [...prev, { role: "ai-block", block }]);
      setThinking(false);
    }, 1000);
  };

  // 从 Dashboard 等其他 tab 触发的快捷问题
  useEffect(() => {
    if (pendingAsk) {
      send(pendingAsk);
      setPendingAsk(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAsk]);

  // iter G12-B: demo 步 5 自动 send
  useEffect(() => {
    if (demoStep === 5) {
      // 避免重复 send（demo 内可能重新进入 step 5）
      const last = messages[messages.length - 1];
      if (!last || last.role !== "user" || (last.role === "user" && last.text !== "明天应该优先生产什么？")) {
        send("明天应该优先生产什么？");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoStep]);

  // 滚到底部（双重 rAF 确保 DOM 已 paint）
  useEffect(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
    });
  }, [messages, thinking]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: isDesktop ? "1.7fr 1fr" : "1fr",
        gap: 16,
      }}
    >
      {/* 左：对话区 */}
      <div
        className="card"
        style={{
          padding: 0,
          display: "flex",
          flexDirection: "column",
          height: 600,
          maxHeight: 600,
        }}
      >
        {/* 顶部 */}
        <header
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid var(--ink-100)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "linear-gradient(180deg, #FAF8FF 0%, #FFFFFF 100%)",
          }}
        >
          <span
            style={{
              width: 30,
              height: 30,
              borderRadius: 9,
              background: "var(--ai-purple)",
              color: "#fff",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.chat(16, "#fff")}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
              AI 库存管家
            </h3>
            <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>
              用中文问，秒答 · 每条结论附数据来源
            </div>
          </div>
          <span
            style={{
              padding: "3px 10px",
              fontSize: 10.5,
              fontWeight: 700,
              borderRadius: 5,
              background: "rgba(27,127,58,0.10)",
              color: "var(--stock-ok)",
              border: "1px solid rgba(27,127,58,0.22)",
            }}
          >
            ● 实时连接
          </span>
        </header>

        {/* 对话流 */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} onGoTab={onGoTab} onLinkToast={(label) => showToast(`已跳转 · ${label}`, "info")} />
          ))}
          {thinking && (
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: 36 }}>
              <Spinner size={14} color="var(--ai-purple)" />
              <span style={{ fontSize: 12, color: "var(--ai-purple-deep)", fontWeight: 600 }}>
                AI 正在查询库存数据…
              </span>
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div
          style={{
            padding: "12px 14px 14px",
            borderTop: "1px solid var(--ink-100)",
            background: "var(--surface-2)",
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            style={{ display: "flex", gap: 8 }}
          >
            <input
              type="text"
              placeholder="问任何问题，例如：JT-MLS-M70 还能撑多久？"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              style={{
                flex: 1,
                padding: "10px 14px",
                fontSize: 13,
                border: "1px solid var(--ink-200)",
                borderRadius: 10,
                background: "#fff",
                outline: "none",
                fontFamily: "var(--font)",
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || thinking}
              style={{
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 10,
                border: "none",
                background: input.trim() && !thinking ? "var(--ai-purple)" : "var(--ink-200)",
                color: "#fff",
                cursor: input.trim() && !thinking ? "pointer" : "not-allowed",
                fontFamily: "var(--font)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {thinking ? <Spinner size={12} color="#fff" /> : I.send(14, "#fff")} 发送
            </button>
          </form>
          {/* 底部快捷 */}
          <div
            style={{
              marginTop: 10,
              display: "flex",
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            {[
              { label: "生成今日日报", q: "给我生成今天的库存日报" },
              { label: "缺货清单",   q: "今天哪些订单可能发不出去？" },
              { label: "本周补产",   q: "哪些 SKU 应该补产？" },
              { label: "导出 SKU 表", q: "__export__" },
            ].map(({ label, q }) => (
              <button
                key={label}
                onClick={() => {
                  if (q === "__export__") {
                    showToast("✓ 已开始导出 1,286 SKU 列表 · Excel 邮件发送中", "info");
                    return;
                  }
                  send(q);
                }}
                style={{
                  padding: "5px 11px",
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 5,
                  border: "1px solid var(--ai-200)",
                  background: "var(--ai-50)",
                  color: "var(--ai-700)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 右：预设问题 + 说明 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14, alignSelf: "flex-start", position: "sticky", top: 12 }}>
        <div className="card" style={{ padding: "14px 16px" }}>
          <h4 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>
            常问的问题（点击直接发送）
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {askPresets.map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
                style={{
                  padding: "8px 11px",
                  fontSize: 12,
                  fontWeight: 500,
                  textAlign: "left",
                  borderRadius: 7,
                  border: "1px solid var(--ink-100)",
                  background: "#fff",
                  color: "var(--ink-700)",
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* iter G9: AI 能干什么精简到 3 行 */}
        <div
          className="card"
          style={{
            padding: "12px 14px",
            background: "linear-gradient(120deg, #FAF8FF 0%, #FFFFFF 80%)",
            borderLeft: "3px solid var(--ai-purple)",
            fontSize: 11.5,
            color: "var(--ink-600)",
            lineHeight: 1.65,
          }}
        >
          <strong style={{ color: "var(--ink-900)" }}>AI 能查 · 能算 · 能写</strong>
          <div style={{ marginTop: 5 }}>
            实时库存 · 缺货风险 · 补产建议 · 异常识别 · 日报周报。
          </div>
          <div style={{ marginTop: 6, fontSize: 10.5, color: "var(--ink-400)" }}>
            * AI 不直接改库存，所有变动需仓管 / 老板确认
          </div>
        </div>
      </div>
    </div>
  );
}

const RISK_META: Record<
  AnswerBlock["risk"],
  { label: string; color: string; bg: string; border: string }
> = {
  urgent: { label: "🚨 紧急", color: "#fff",                       bg: "var(--stock-out)",          border: "var(--stock-out)" },
  high:   { label: "🔴 高风险", color: "var(--guangtian-red)",      bg: "rgba(217,32,32,0.08)",     border: "rgba(217,32,32,0.30)" },
  medium: { label: "🟡 中风险", color: "var(--stock-low)",          bg: "rgba(245,158,11,0.08)",    border: "rgba(245,158,11,0.30)" },
  low:    { label: "🟢 可控",   color: "var(--stock-ok)",           bg: "rgba(27,127,58,0.08)",     border: "rgba(27,127,58,0.30)" },
  info:   { label: "ℹ 信息",    color: "var(--brand-700)",          bg: "rgba(31,95,163,0.08)",     border: "rgba(31,95,163,0.22)" },
};

function MessageBubble({
  msg,
  onGoTab,
  onLinkToast,
}: {
  msg: Msg;
  onGoTab?: (key: string) => void;
  onLinkToast?: (label: string) => void;
}) {
  if (msg.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            maxWidth: "78%",
            padding: "9px 14px",
            background: "var(--brand-700)",
            color: "#fff",
            borderRadius: "14px 14px 4px 14px",
            fontSize: 12.5,
            lineHeight: 1.55,
            boxShadow: "0 2px 6px rgba(31,95,163,0.18)",
          }}
        >
          {msg.text}
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
      <span
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "var(--ai-purple)",
          color: "#fff",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginTop: 2,
        }}
      >
        {I.spark(14, "#fff")}
      </span>
      <div
        style={{
          maxWidth: "calc(100% - 40px)",
          padding: "11px 14px",
          background: "#fff",
          border: "1px solid var(--ink-100)",
          borderRadius: "4px 14px 14px 14px",
          fontSize: 12.5,
          lineHeight: 1.65,
          color: "var(--ink-800)",
          whiteSpace: "pre-line",
          boxShadow: "var(--shadow-card-soft)",
        }}
      >
        {msg.role === "ai-block" ? (
          <BlockAnswer block={msg.block} onGoTab={onGoTab} onLinkToast={onLinkToast} />
        ) : (
          <>
            {msg.text}
            {msg.sources && msg.sources.length > 0 && (
              <div
                style={{
                  marginTop: 10,
                  paddingTop: 9,
                  borderTop: "1px dashed var(--ink-100)",
                  fontSize: 10.5,
                  color: "var(--ai-700)",
                }}
              >
                <strong style={{ fontWeight: 700, color: "var(--ai-900)" }}>数据来源：</strong>
                <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 3 }}>
                  {msg.sources.map((s, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span>• {s.label}</span>
                      <span style={{ fontFamily: "var(--font-mono, var(--font))" }}>{s.count.toLocaleString()} 条</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// iter G11: 结构化答案块（结论 / 数据依据 / 风险等级 / 建议动作 / 可点击明细）
function BlockAnswer({
  block,
  onGoTab,
  onLinkToast,
}: {
  block: AnswerBlock;
  onGoTab?: (key: string) => void;
  onLinkToast?: (label: string) => void;
}) {
  const r = RISK_META[block.risk];
  return (
    <div>
      {/* 结论 */}
      <div style={{ fontSize: 12.5, lineHeight: 1.65, color: "var(--ink-800)", whiteSpace: "pre-line" }}>
        {block.conclusion}
      </div>

      {/* 风险等级 + 数据依据 */}
      <div
        style={{
          marginTop: 10,
          paddingTop: 9,
          borderTop: "1px dashed var(--ink-100)",
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
          fontSize: 10.5,
          color: "var(--ai-700)",
        }}
      >
        <span
          style={{
            padding: "2px 9px",
            fontSize: 10.5,
            fontWeight: 700,
            borderRadius: 5,
            background: r.bg,
            color: r.color,
            border: `1px solid ${r.border}`,
          }}
        >
          风险 · {r.label}
        </span>
        <span style={{ color: "var(--ink-500)" }}>数据依据</span>
        {block.evidence.map((e, i) => (
          <span
            key={i}
            style={{
              padding: "2px 8px",
              borderRadius: 4,
              background: "var(--surface-2)",
              color: "var(--ink-700)",
              fontSize: 10.5,
              border: "1px solid var(--ink-100)",
            }}
          >
            {e.label} · {e.count.toLocaleString()} 条
          </span>
        ))}
      </div>

      {/* 建议动作 */}
      {block.actions.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--ai-900)", marginBottom: 4 }}>
            建议动作
          </div>
          <ol style={{ margin: 0, paddingLeft: 18, fontSize: 11.5, color: "var(--ink-700)", lineHeight: 1.65 }}>
            {block.actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ol>
        </div>
      )}

      {/* 可点击明细 */}
      {block.links.length > 0 && (
        <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {block.links.map((l, i) => (
            <button
              key={i}
              onClick={() => {
                onGoTab?.(l.target);
                onLinkToast?.(l.label);
              }}
              style={{
                padding: "5px 11px",
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 6,
                border: "1px solid var(--ai-200)",
                background: "var(--ai-50)",
                color: "var(--ai-700)",
                cursor: "pointer",
                fontFamily: "var(--font)",
              }}
            >
              {l.label} →
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
