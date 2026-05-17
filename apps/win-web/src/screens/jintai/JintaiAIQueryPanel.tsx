import { useState } from "react";
import { I } from "../../icons";
import { presetQuestions } from "./data";
import type { AIBlock } from "./data";
import { JintaiSourceCitation } from "./components";

export function JintaiAIQueryPanel() {
  const [active, setActive] = useState<AIBlock | null>(presetQuestions[0]);
  const [draft, setDraft] = useState("");

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16 }}>
      <div
        className="card"
        style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)", marginBottom: 4 }}>
          老板 AI 助手 · 锦泰试点
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: "var(--surface-2)",
            border: "1px solid var(--ink-100)",
            borderRadius: 22,
            padding: "6px 8px 6px 14px",
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="用中文问 AI · 比如：「这周哪些订单要紧」"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: 12.5,
              fontFamily: "var(--font)",
              color: "var(--ink-800)",
              padding: "6px 0",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim()) {
                const guess =
                  presetQuestions.find((q) => q.question.includes(draft.slice(0, 2))) ??
                  presetQuestions[0];
                setActive(guess);
                setDraft("");
              }
            }}
          />
          <button
            onClick={() => {
              if (!draft.trim()) return;
              const guess =
                presetQuestions.find((q) => q.question.includes(draft.slice(0, 2))) ??
                presetQuestions[0];
              setActive(guess);
              setDraft("");
            }}
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              border: "none",
              background: draft.trim() ? "var(--brand-500)" : "var(--ink-200)",
              color: "#fff",
              cursor: draft.trim() ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.send(15, "#fff")}
          </button>
        </div>

        <div
          style={{
            fontSize: 10.5,
            color: "var(--ink-500)",
            fontWeight: 700,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            marginTop: 6,
          }}
        >
          预设问题
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {presetQuestions.map((q) => {
            const isActive = active?.question === q.question;
            return (
              <button
                key={q.question}
                onClick={() => setActive(q)}
                className="pill"
                style={{
                  display: "block",
                  textAlign: "left",
                  background: isActive ? "var(--ai-100)" : "var(--surface-2)",
                  color: isActive ? "var(--ai-700)" : "var(--ink-700)",
                  border: `1px solid ${isActive ? "#bddff3" : "var(--ink-100)"}`,
                  padding: "9px 12px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                  borderRadius: 10,
                  lineHeight: 1.45,
                  whiteSpace: "normal",
                }}
              >
                {q.question}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {active ? <AIAnswerCard block={active} /> : (
          <div className="card" style={{ padding: 24, color: "var(--ink-400)", fontSize: 13 }}>
            从左侧选一个问题，或自己用中文问 AI 一句。
          </div>
        )}

        <div
          style={{
            padding: 12,
            borderRadius: 10,
            background: "var(--surface-2)",
            border: "1px dashed var(--ink-200)",
            fontSize: 11.5,
            color: "var(--ink-500)",
            lineHeight: 1.55,
          }}
        >
          AI 不直接修改任何业务数据。所有回答均基于已确认入库的订单 / 流转单 / 工艺单 /
          出货单，并附原始来源引用，便于追溯。
        </div>
      </div>
    </div>
  );
}

function AIAnswerCard({ block }: { block: AIBlock }) {
  return (
    <div
      className="card"
      style={{
        padding: 18,
        borderLeft: "3px solid var(--ai-500)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ai-700)",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          marginBottom: 6,
        }}
      >
        {I.spark(12)} AI 回答
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-500)", marginBottom: 8 }}>
        问：{block.question}
      </div>
      <div style={{ fontSize: 14.5, color: "var(--ink-900)", lineHeight: 1.6, fontWeight: 600 }}>
        {block.verdict}
      </div>

      <div className="sep" style={{ margin: "14px 0 10px" }} />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ink-500)",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        数据明细
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 8,
        }}
      >
        {block.details.map((d) => (
          <div
            key={d.key}
            style={{
              padding: "8px 10px",
              borderRadius: 8,
              background: "var(--surface-2)",
              border: "1px solid var(--ink-100)",
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600 }}>{d.key}</div>
            <div style={{ color: "var(--ink-900)", fontWeight: 500, marginTop: 2 }}>{d.value}</div>
          </div>
        ))}
      </div>

      <div className="sep" style={{ margin: "14px 0 10px" }} />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          fontWeight: 700,
          color: "var(--ink-500)",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        来源引用
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {block.evidence.map((e, i) => (
          <JintaiSourceCitation key={i} source={e} />
        ))}
      </div>

      {block.next.length > 0 && (
        <>
          <div className="sep" style={{ margin: "14px 0 10px" }} />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              fontWeight: 700,
              color: "var(--ai-700)",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            {I.bulb(12)} 下一步建议
          </div>
          <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.6, color: "var(--ink-800)" }}>
            {block.next.map((n, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{n}</li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
