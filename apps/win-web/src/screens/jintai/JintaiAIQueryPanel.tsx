import { useState } from "react";
import { askJintai } from "../../api/jintai";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { presetQuestions } from "./data";
import type { AIBlock } from "./data";
import { JintaiSourceCitation } from "./components";

export function JintaiAIQueryPanel() {
  const isDesktop = useIsDesktop();
  // iter 20 精简：11 → 6 预设 (生产 2 + 财务 2 + 采购 2)
  const visibleQuestions = presetQuestions.slice(0, 6);
  const productionQs = visibleQuestions.slice(0, 2);
  const financeQs = visibleQuestions.slice(2, 4);
  const briefingQs = visibleQuestions.slice(4, 6);
  const [active, setActive] = useState<AIBlock | null>(presetQuestions[0]);
  const [draft, setDraft] = useState("");
  const [isAsking, setIsAsking] = useState(false);

  const ask = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed) return;
    const fallback =
      presetQuestions.find((q) => q.question.includes(trimmed.slice(0, 2))) ??
      presetQuestions[0];
    setIsAsking(true);
    try {
      setActive(await askJintai(trimmed));
    } catch {
      setActive(fallback);
    } finally {
      setIsAsking(false);
      setDraft("");
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: isDesktop ? "280px 1fr" : "1fr", gap: 16 }}>
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
            placeholder="试着问问看：这单到哪了？还有多少没收钱？哪个客户该跟进？"
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
                void ask(draft);
              }
            }}
          />
          <button
            onClick={() => {
              void ask(draft);
            }}
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              border: "none",
              background: draft.trim() && !isAsking ? "var(--brand-500)" : "var(--ink-200)",
              color: "#fff",
              cursor: draft.trim() && !isAsking ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {I.send(15, "#fff")}
          </button>
        </div>

        <QuestionGroup
          label="生产"
          items={productionQs}
          activeQuestion={active?.question}
          onPick={ask}
        />
        <QuestionGroup
          label="财务"
          items={financeQs}
          activeQuestion={active?.question}
          onPick={ask}
        />
        <QuestionGroup
          label="采购"
          items={briefingQs}
          activeQuestion={active?.question}
          onPick={ask}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {active ? <AIAnswerCard block={active} /> : (
          <div className="card" style={{ padding: 24, color: "var(--ink-400)", fontSize: 13 }}>
            从左侧选一个问题，或自己用中文问 AI 一句。
          </div>
        )}
      </div>
    </div>
  );
}

function QuestionGroup({
  label,
  items,
  activeQuestion,
  onPick,
}: {
  label: string;
  items: AIBlock[];
  activeQuestion?: string;
  onPick: (q: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
      <div
        style={{
          fontSize: 10.5,
          color: "var(--ink-500)",
          fontWeight: 700,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      {items.map((q) => {
        const isActive = activeQuestion === q.question;
        return (
          <button
            key={q.question}
            onClick={() => void onPick(q.question)}
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
        {/* 视觉减负：明细只展示前 4 项 */}
        {block.details.slice(0, 4).map((d) => (
          <div
            key={d.key}
            style={{
              padding: "10px 12px",
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

      <div className="sep" style={{ margin: "16px 0 12px" }} />

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
    </div>
  );
}
