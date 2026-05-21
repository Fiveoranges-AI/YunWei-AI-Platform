// iter G12-B: 一键演示模式 — 顶部固定控制条 + 6 步剧本 + 总结
import { useGT } from "./state";

export const DEMO_STEPS: {
  id: number;
  tab: string;
  title: string;
  narration: string;
  badge?: string;
}[] = [
  {
    id: 1,
    tab: "inbound",
    title: "上传出库单照片",
    narration: "销售刚发来「常州新材出库单」拍照，王主管打开 AI 库存管家。",
    badge: "📷 出货单_常州新材_20260520.jpg",
  },
  {
    id: 2,
    tab: "inbound",
    title: "AI 自动识别字段",
    narration: "AI 识别到「刚玉砖 AL90 × 150 件 / 关联订单 SO-20260519-003」，整体置信度 96%。",
    badge: "✦ AI 识别中…",
  },
  {
    id: 3,
    tab: "sku",
    title: "系统检查 SKU 库存",
    narration: "系统对 AL90 当前库存 78 块 vs 出库需求 150 块比对 — 缺口 72 块。",
    badge: "🔴 AL90 库存不足",
  },
  {
    id: 4,
    tab: "shortage",
    title: "自动触发缺货预警",
    narration: "常州新材订单 SO-003 被标记为「高风险」，AI 计算可发货比例 72%。",
    badge: "⚠ SO-20260519-003 高风险",
  },
  {
    id: 5,
    tab: "ask",
    title: "AI 库存管家给建议",
    narration: "AI 建议立即排产 AL90 250 块（5/26 出炉），先发 72% 库存 + 5/28 补 72 件。",
    badge: "✦ AI 综合答案",
  },
  {
    id: 6,
    tab: "replenish",
    title: "生成补产计划",
    narration: "AL90 列为「中优先」加入本周补产，一键发给工艺组陈工。",
    badge: "✓ AL90 已入计划",
  },
];

const TOTAL = DEMO_STEPS.length;

export function GuangtianDemoTour() {
  const { demoStep, demoPlaying, pauseDemo, resumeDemo, exitDemo, nextDemoStep, startDemo } = useGT();

  // 未启动 — 不渲染
  if (demoStep === 0) return null;

  // 总结
  if (demoStep > TOTAL) {
    return (
      <div style={overlayStyle} onClick={exitDemo}>
        <div style={summaryCardStyle} onClick={(e) => e.stopPropagation()}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ai-purple-deep)", marginBottom: 10 }}>
            DEMO COMPLETE
          </div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "var(--ink-900)", lineHeight: 1.3 }}>
            全程 90 秒：<br />
            <span style={{ color: "var(--guangtian-red)" }}>一张照片</span> → AI 识别 →
            库存更新 → <span style={{ color: "var(--guangtian-red)" }}>风险预警</span> →
            补产决策。
          </h2>
          <p style={{ margin: "12px 0 16px", fontSize: 13, color: "var(--ink-600)", lineHeight: 1.65 }}>
            这就是 AI 库存管家 — 让 1,000+ SKU 自己讲话，告别 Excel 与人工记忆。
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => startDemo()}
              style={{
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 9,
                border: "none",
                background: "var(--ai-purple)",
                color: "#fff",
                cursor: "pointer",
                fontFamily: "var(--font)",
                boxShadow: "0 4px 12px rgba(123,92,250,0.30)",
              }}
            >
              ▶ 再看一遍
            </button>
            <button
              onClick={exitDemo}
              style={{
                padding: "10px 16px",
                fontSize: 13,
                fontWeight: 600,
                borderRadius: 9,
                border: "1px solid var(--ink-200)",
                background: "#fff",
                color: "var(--ink-700)",
                cursor: "pointer",
                fontFamily: "var(--font)",
              }}
            >
              退出演示
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 步骤中
  const step = DEMO_STEPS.find((s) => s.id === demoStep);
  if (!step) return null;

  return (
    <div style={barStyle}>
      {/* 步骤指示 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <span
          style={{
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 800,
            borderRadius: 5,
            background: "rgba(255,255,255,0.20)",
            color: "#fff",
            fontFamily: "var(--font-mono, var(--font))",
            letterSpacing: "0.04em",
          }}
        >
          {demoStep} / {TOTAL}
        </span>
        <ProgressDots step={demoStep} />
      </div>

      {/* 标题 + 旁白 */}
      <div style={{ flex: 1, minWidth: 0, padding: "0 8px" }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#fff", lineHeight: 1.3 }}>
          {step.title}
          {step.badge && (
            <span
              style={{
                marginLeft: 10,
                padding: "2px 8px",
                fontSize: 10.5,
                fontWeight: 600,
                borderRadius: 4,
                background: "rgba(255,255,255,0.15)",
                color: "rgba(255,255,255,0.92)",
              }}
            >
              {step.badge}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11.5, color: "rgba(255,255,255,0.78)", marginTop: 3, lineHeight: 1.45 }}>
          {step.narration}
        </div>
      </div>

      {/* 控制按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        {demoPlaying ? (
          <button onClick={pauseDemo} style={iconBtnStyle} title="暂停">
            ⏸
          </button>
        ) : (
          <button onClick={resumeDemo} style={iconBtnStyle} title="继续">
            ▶
          </button>
        )}
        <button onClick={nextDemoStep} style={iconBtnStyle} title="下一步">
          ⏭
        </button>
        <button onClick={exitDemo} style={{ ...iconBtnStyle, marginLeft: 4 }} title="退出">
          ✕
        </button>
      </div>
    </div>
  );
}

function ProgressDots({ step }: { step: number }) {
  return (
    <div style={{ display: "flex", gap: 4, marginLeft: 4 }}>
      {Array.from({ length: TOTAL }).map((_, i) => (
        <span
          key={i}
          style={{
            width: 14,
            height: 4,
            borderRadius: 2,
            background: i < step ? "#fff" : "rgba(255,255,255,0.28)",
            transition: "background 0.3s ease",
          }}
        />
      ))}
    </div>
  );
}

const barStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  zIndex: 9999,
  padding: "10px 18px",
  display: "flex",
  alignItems: "center",
  gap: 10,
  background: "linear-gradient(95deg, var(--ai-purple-deep) 0%, var(--guangtian-red) 100%)",
  color: "#fff",
  boxShadow: "0 4px 16px rgba(11,18,32,0.20)",
  fontFamily: "var(--font)",
};

const iconBtnStyle: React.CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: 7,
  border: "1px solid rgba(255,255,255,0.30)",
  background: "rgba(255,255,255,0.10)",
  color: "#fff",
  cursor: "pointer",
  fontSize: 13,
  fontWeight: 700,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font)",
};

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(11,18,32,0.55)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 10000,
  padding: 20,
  animation: "gt-toast-in 280ms cubic-bezier(0.32, 0.72, 0.24, 1.0)",
};

const summaryCardStyle: React.CSSProperties = {
  background: "linear-gradient(135deg, #FFFFFF 0%, #FAF8FF 100%)",
  borderRadius: 18,
  padding: "26px 30px",
  maxWidth: 520,
  width: "100%",
  boxShadow: "0 32px 64px rgba(11,18,32,0.30)",
  border: "1px solid var(--ai-200)",
  borderLeft: "5px solid var(--ai-purple)",
};

// 启动按钮（嵌入 Hero 旁）
export function DemoStartButton() {
  const { demoStep, startDemo } = useGT();
  if (demoStep > 0) return null;
  return (
    <button
      onClick={startDemo}
      style={{
        padding: "10px 16px",
        fontSize: 13,
        fontWeight: 700,
        borderRadius: 10,
        border: "none",
        background: "linear-gradient(95deg, var(--ai-purple) 0%, var(--guangtian-red) 100%)",
        color: "#fff",
        cursor: "pointer",
        fontFamily: "var(--font)",
        boxShadow: "0 4px 14px rgba(123,92,250,0.30)",
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
      }}
      title="自动播放：从出库单到补产决策"
    >
      <span style={{ fontSize: 14 }}>▶</span>
      一键演示 · 90 秒看懂 AI 库存管家
    </button>
  );
}

// 演示步骤号 → tab key（供 GuangtianDemoInner watch 用）
export function tabForDemoStep(step: number): string | null {
  if (step <= 0 || step > TOTAL) return null;
  return DEMO_STEPS[step - 1].tab;
}
