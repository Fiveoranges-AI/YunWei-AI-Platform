/**
 * iter 23: 引导式 90 秒演示 — 顶部固定控制条 + 旁白字幕 + 10 步剧本 + 总结
 *
 * 参考光天 GuangtianDemoTour 的引导式播放模式:
 *  - 固定顶部条:step X/N + 进度点 + 标题/旁白/badge + ⏸/⏭/✕
 *  - 演示结束 overlay 总结 + "再看一遍" / "退出演示"
 *  - 自动切 tab 由父组件 watch tourStep 完成
 */
import { TOUR_TOTAL, useJintai } from "./state/store";

export function JintaiDemoTour() {
  const { state, currentTourStep, pauseTour, resumeTour, exitTour, nextTourStep, startTour } =
    useJintai();
  const { tourStep, tourPlaying } = state;

  // 未启动 — 不渲染
  if (tourStep === 0) return null;

  // 演示结束 — 总结 overlay
  if (tourStep > TOUR_TOTAL) {
    return (
      <div style={overlayStyle} onClick={exitTour}>
        <div style={summaryCardStyle} onClick={(e) => e.stopPropagation()}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              color: "var(--jintai-green-dark)",
              marginBottom: 10,
            }}
          >
            DEMO COMPLETE · 90 秒走完
          </div>
          <h2
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 800,
              color: "var(--ink-900)",
              lineHeight: 1.3,
            }}
          >
            从{" "}
            <span style={{ color: "var(--jintai-red)" }}>1 张车间领料单</span> 到{" "}
            <span style={{ color: "var(--jintai-green)" }}>应付台账 KPI 联动</span>,
            <br />
            AI 跑通整条链 · 每一步都王仓管 / 张主管 / 王会计签过字。
          </h2>
          <ul
            style={{
              margin: "12px 0 14px",
              padding: "0 0 0 18px",
              fontSize: 12.5,
              color: "var(--ink-700)",
              lineHeight: 1.7,
            }}
          >
            <li>
              <strong>AI 识别</strong> 张师傅手写领料单 7 字段 (置信度 91%)
            </li>
            <li>
              <strong>王仓管 ✓ 确认</strong> → 库存自动扣减 1,880 → 1,080 kg (跌破安全线飘红)
            </li>
            <li>
              <strong>跨模块预警</strong> 配料单 D 立即标缺 2,920 kg
            </li>
            <li>
              <strong>AI 自动生成申购草稿</strong> PR-2026-017 (山东中铝 / ¥96,000)
            </li>
            <li>
              <strong>张主管 ✓ 批准</strong> → PO-2026-009 自动新增
            </li>
            <li>
              <strong>入库回补</strong> + 应付新增 ¥96,000 + 经营日报 KPI ¥327,000 → ¥423,000
            </li>
          </ul>
          <p
            style={{
              margin: "0 0 16px",
              fontSize: 12,
              color: "var(--ink-600)",
              lineHeight: 1.6,
              padding: "10px 12px",
              background: "var(--surface-2)",
              borderRadius: 8,
              borderLeft: "3px solid var(--jintai-red)",
            }}
          >
            <strong style={{ color: "var(--jintai-red)" }}>AI-NATIVE 模式</strong>:全链
            <strong>不依赖金蝶</strong> · AI 自业务单据 (发票/合同/入库/工资/抄表) 自动归集 · 每一步
            "AI 先填、人确认" 共识落地。
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => startTour()}
              style={{
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 700,
                borderRadius: 9,
                border: "none",
                background: "var(--jintai-red)",
                color: "#fff",
                cursor: "pointer",
                fontFamily: "var(--font)",
                boxShadow: "0 4px 12px rgba(195,38,41,0.30)",
              }}
            >
              ▶ 再看一遍
            </button>
            <button
              onClick={exitTour}
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

  // 演示中
  const step = currentTourStep;
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
            fontFamily: "ui-monospace, monospace",
            letterSpacing: "0.04em",
          }}
        >
          {tourStep} / {TOUR_TOTAL}
        </span>
        <ProgressDots step={tourStep} />
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
        <div
          style={{
            fontSize: 11.5,
            color: "rgba(255,255,255,0.85)",
            marginTop: 3,
            lineHeight: 1.5,
          }}
        >
          {step.narration}
        </div>
      </div>

      {/* 控制按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        {tourPlaying ? (
          <button onClick={pauseTour} style={iconBtnStyle} title="暂停">
            ⏸
          </button>
        ) : (
          <button onClick={resumeTour} style={iconBtnStyle} title="继续">
            ▶
          </button>
        )}
        <button onClick={nextTourStep} style={iconBtnStyle} title="下一步">
          ⏭
        </button>
        <button onClick={exitTour} style={{ ...iconBtnStyle, marginLeft: 4 }} title="退出">
          ✕
        </button>
      </div>
    </div>
  );
}

function ProgressDots({ step }: { step: number }) {
  return (
    <div style={{ display: "flex", gap: 3, marginLeft: 4 }}>
      {Array.from({ length: TOUR_TOTAL }).map((_, i) => (
        <span
          key={i}
          style={{
            width: 12,
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
  // 锦泰红绿渐变 (区别于光天的紫红渐变)
  background: "linear-gradient(95deg, var(--jintai-red) 0%, var(--jintai-green) 100%)",
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
};

const summaryCardStyle: React.CSSProperties = {
  background: "linear-gradient(135deg, #FFFFFF 0%, #F8FBF6 100%)",
  borderRadius: 18,
  padding: "26px 30px",
  maxWidth: 560,
  width: "100%",
  boxShadow: "0 32px 64px rgba(11,18,32,0.30)",
  border: "1px solid var(--ink-100)",
  borderLeft: "5px solid var(--jintai-red)",
};
