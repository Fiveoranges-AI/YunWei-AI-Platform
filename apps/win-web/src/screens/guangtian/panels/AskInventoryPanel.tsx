import { useState } from "react";
import { useIsDesktop } from "../../../lib/breakpoints";
import { I } from "../../../icons";
import { askPresets, askSampleConversation } from "../data";

type Msg =
  | { role: "user"; text: string }
  | { role: "ai"; text: string; sources?: { label: string; count: number }[] };

export function AskInventoryPanel() {
  const isDesktop = useIsDesktop();
  const [messages, setMessages] = useState<Msg[]>(askSampleConversation as Msg[]);
  const [input, setInput] = useState("");

  const send = (q?: string) => {
    const txt = (q ?? input).trim();
    if (!txt) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: txt },
      {
        role: "ai",
        text:
          "（演示版本）这里 AI 会基于实时库存 / 流水 / 订单数据作答。\n上线后将接入 智通 AI 模型 + 光天耐火本地数据库。\n\n您可以试试以下预设问题，看 AI 真实响应。",
        sources: [
          { label: "本地库存数据", count: 1286 },
          { label: "近 30 天流水", count: 1247 },
        ],
      },
    ]);
    setInput("");
  };

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
          minHeight: 540,
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
              style={{
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 10,
                border: "none",
                background: input.trim() ? "var(--ai-purple)" : "var(--ink-200)",
                color: "#fff",
                cursor: input.trim() ? "pointer" : "not-allowed",
                fontFamily: "var(--font)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {I.send(14, "#fff")} 发送
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
              "生成今日日报",
              "缺货清单",
              "本周补产建议",
              "导出 SKU 表",
            ].map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
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
                {q}
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
          <strong style={{ color: "var(--ink-900)" }}>AI 能干什么？</strong>
          <ul style={{ margin: "5px 0 0", paddingLeft: 18 }}>
            <li>查库存：任何 SKU 实时数 + 位置 + 历史</li>
            <li>查订单：本周谁要的多 / 缺什么</li>
            <li>给建议：补产数量 / 优先级 / 排程</li>
            <li>找异常：盘点偏差 / 流水跳变 / 呆滞</li>
            <li>写日报 / 周报 / 月报 一键导出</li>
          </ul>
          <div style={{ marginTop: 8, fontSize: 10.5, color: "var(--ink-400)" }}>
            * AI 不直接修改库存数据，所有变动需仓管 / 老板确认
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
