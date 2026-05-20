import { useEffect, useRef, useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { askPresets, askSampleConversation } from "../data";
import { useGT } from "../state";
import { Spinner } from "../Toast";

type Msg =
  | { role: "user"; text: string }
  | { role: "ai"; text: string; sources?: { label: string; count: number }[] };

// 预设问题 → mock 答案库
const PRESET_ANSWERS: Record<string, { text: string; sources: { label: string; count: number }[] }> = {
  "今天哪些订单可能发不出去？": {
    text:
      "今天有 3 笔订单存在交付风险，其中 1 笔高风险：\n\n🔴 高风险 1 笔\n• SO-20260519-001 · 江苏宏泰工程 · 5/22 交付 · 缺浇注料 JC-16 200 袋（库存 0）\n\n🟢 关注 2 笔\n• SO-20260517-012 · 常州新材 · M70 部分出库后剩 50 块未补 — 36 小时无动作\n• SO-20260519-003 · 常州新材 · 下周四交付 · 缺 M70 180 + AL90 72\n\n建议优先处理 SO-20260519-001，AI 已草拟 400 袋 JC-16 补产单（B-02 库位）。",
    sources: [
      { label: "下游订单表 · 实时拉取", count: 7 },
      { label: "SKU 库存快照", count: 1286 },
      { label: "近 7 天出货流水", count: 156 },
    ],
  },
  "哪些 SKU 应该补产？": {
    text:
      "本周推荐补产 3 个紧迫 SKU，按优先级：\n\n1. 🔴 JC-16 浇注料 · 已缺货 14 天 · 建议补 400 袋（5/22 出炉）\n2. 🔴 M70 莫来石砖 · 库存 320 / 安全 800 · 建议补 600 块（5/23 出炉）\n3. 🟡 AL90 高纯刚玉砖 · 库存 78 / 安全 200 · 建议补 250 块（5/26 出炉）\n\n合计 1,250 单位 · 已为您挂到 AI 补产建议 tab，一键发给工艺组陈工。",
    sources: [
      { label: "SKU 库存快照", count: 1286 },
      { label: "近 30 天出货趋势", count: 1247 },
      { label: "下游订单需求", count: 7 },
    ],
  },
  "JC-16 浇注料过去半年的出货趋势？": {
    text:
      "JC-16 浇注料 · 近 6 个月趋势分析：\n\n• 月均出货 350 袋（峰值 5 月 480 袋 / 谷值 2 月 220 袋）\n• 主要客户：江苏宏泰工程（占 47%）· 常州新材（占 28%）\n• 季节性：春秋高峰（窑炉检修季）· 冬季低谷\n• 5 月已出 280 袋，预计本月总出货 380 袋\n\nAI 建议：当前安全库存 200 袋偏低，应调整至 400 袋（按月均出货 1.2 倍）。",
    sources: [
      { label: "JC-16 出货流水 · 半年", count: 1842 },
      { label: "客户订单历史", count: 76 },
    ],
  },
  "给我生成今天的库存日报": {
    text:
      "✓ 今日库存日报已生成（5 大块）：\n\n1. 流水：入库 18 / 出库 23 / 净流入 +1,040\n2. 风险：1 红（JC-16 缺货）+ 2 黄（M70 / AL90 低库存）\n3. AI 补产：3 个 SKU 合计 1,250 单位 · 已挂工艺组\n4. 库位：A 区紧张 76% / B 区宽裕 / C 区正常\n5. 操作绩效：王主管 12 入库 100% 合规\n\n→ 切到「AI 库存日报」tab 看完整版，可一键发陈总微信。",
    sources: [
      { label: "全天流水", count: 41 },
      { label: "风险扫描", count: 5 },
      { label: "补产建议", count: 3 },
    ],
  },
};

const FALLBACK_ANSWER = (q: string) => ({
  text: `（演示版本）AI 已收到您的问题："${q}"\n\n上线后 AI 会基于实时库存（1,286 SKU）/ 近 30 天流水（1,247 条）/ 7 个下游订单 综合作答，并附数据来源引用。\n\n建议您试试左侧预设问题，看 AI 真实响应效果。`,
  sources: [
    { label: "本地库存数据", count: 1286 },
    { label: "近 30 天流水", count: 1247 },
  ],
});

export function AskInventoryPanel() {
  const isDesktop = useIsDesktop();
  const { showToast, pendingAsk, setPendingAsk } = useGT();
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
      const answer = preset ?? FALLBACK_ANSWER(txt);
      setMessages((prev) => [...prev, { role: "ai", text: answer.text, sources: answer.sources }]);
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
            <MessageBubble key={i} msg={m} />
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

function MessageBubble({ msg }: { msg: Msg }) {
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
      </div>
    </div>
  );
}
