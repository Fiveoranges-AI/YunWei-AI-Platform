// iter G12-B: 一键演示模式 — 顶部固定控制条 + 6 步剧本 + 总结
import { useGT } from "./state";

// R2: 砍到 4 步核心闭环 — 乱(拍照单据) → AI 结构化录入 → 实时流水 → 缺货预警 → 老板看板。
// 删掉原 5/6 步(老板助手/日报)+ 去掉"置信度 96%"等装饰话术。
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
    title: "乱数据进来 → AI 抽成结构化",
    narration: "销售在微信发来一张入库通知截图。库管只要拍/传上来，AI 当场抽出：莫来石 ML-30 × 500 块 / 批次 / 来源 / 关联订单，并把「30级莫来石砖」归一到标准编码。有一条 AI 没把握的它自己标黄提醒——库管点一下确认即可，不用再手敲 Excel。",
    badge: "📷 微信入库通知.jpg → 已结构化",
  },
  {
    id: 2,
    tab: "ledger",
    title: "确认即写入流水 · 每笔可追溯",
    narration: "AL90 出库 -150 件实时写入库存流水，谁录的、来源哪张单、什么时候，一清二楚。账实不再靠月底盘点对。",
    badge: "✓ 已写入 · 库存实时更新",
  },
  {
    id: 3,
    tab: "shortage",
    title: "库存一变 → 缺货预警自动跳",
    narration: "AL90 扣减后不够发，AI 立刻把订单 SO-20260519-003 标红：可发 72%、缺 72 件。老板不用等库管汇报。",
    badge: "🔴 SO-20260519-003 高风险",
  },
  {
    id: 4,
    tab: "dashboard",
    title: "老板看板 · 一眼今天该处理什么",
    narration: "回到看板：今天必须处理的三件事直接摆在最上面，缺不缺、缺哪几个、谁还没录，30 秒看完。这就是替代 Excel 的那一页。",
    badge: "📋 老板 30 秒看完",
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
            全程 60 秒：<br />
            <span style={{ color: "var(--guangtian-red)" }}>微信里一张乱图</span> → AI 抽成结构化 →
            库管点一下确认 → 库存实时准 → <span style={{ color: "var(--guangtian-red)" }}>缺货自动预警</span>。
          </h2>
          <p style={{ margin: "12px 0 14px", fontSize: 13, color: "var(--ink-600)", lineHeight: 1.65 }}>
            把您现在的 Excel + 库管手工维护，换成"拍照即录、库存即准、缺货即知"。这一页老板每天 30 秒看完。
          </p>
          <div
            style={{
              margin: "0 0 16px",
              padding: "10px 14px",
              borderRadius: 10,
              background: "var(--surface-2)",
              border: "1px solid var(--ink-100)",
              fontSize: 12.5,
              color: "var(--ink-700)",
              lineHeight: 1.6,
            }}
          >
            算笔账：按光天规模，这套每月省下的人工 + 差异 + 缺货损失 ≈{" "}
            <strong style={{ color: "var(--guangtian-blue)" }}>3 万</strong>，月费两三千 —— 点顶部
            <strong>「省多少钱」</strong>自己改数算。
          </div>
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
