import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";

type Props = {
  onScrollTo: (id: string) => void;
  onSimulateUploadContract: () => void;
  onSimulateUploadFlowCard: () => void;
};

export function JintaiHero({
  onScrollTo,
  onSimulateUploadContract,
  onSimulateUploadFlowCard,
}: Props) {
  const isDesktop = useIsDesktop();
  return (
    <div
      className="card"
      style={{
        padding: isDesktop ? "28px 32px" : "22px 18px",
        marginBottom: 24,
        background: "var(--surface)",
        border: "1px solid var(--ink-100)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <span
          className="pill pill-ai"
          style={{ fontSize: 11, padding: "3px 9px", letterSpacing: 0.02 }}
        >
          {I.spark(10)} 客户试点演示 · 2026-05
        </span>
        <span className="pill pill-outline" style={{ fontSize: 11, padding: "3px 9px" }}>
          试点 2–3 周 · 不替换 ERP · 来源 100% 可追溯
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: isDesktop ? 16 : 12, flexWrap: "wrap" }}>
        <img
          src={`${import.meta.env.BASE_URL}jintai-logo.png`}
          alt="锦泰耐火材料"
          style={{ height: isDesktop ? 52 : 44, width: "auto", flexShrink: 0 }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0, flex: 1 }}>
          <h1
            style={{
              margin: 0,
              fontSize: isDesktop ? 28 : 20,
              fontWeight: 700,
              color: "var(--ink-900)",
              letterSpacing: "-0.01em",
              lineHeight: 1.2,
            }}
          >
            宜兴市锦泰耐火材料 · AI 生产流转试点
          </h1>
          <div
            style={{
              fontSize: 14,
              color: "var(--ink-600)",
              fontWeight: 500,
              lineHeight: 1.55,
              maxWidth: 820,
            }}
          >
            让承烧板从合同 / 纸质流转单，一路追到客户验收 + 应收账期。
            AI 辅助抽取，人工确认入库，不直接写业务数据。
          </div>
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 22 }}>
        <button
          className="btn btn-primary"
          onClick={onSimulateUploadContract}
          style={{ padding: "10px 16px", fontSize: 13.5 }}
        >
          {I.cloud(16, "#fff")} 模拟上传合同
        </button>
        <button
          className="btn btn-secondary"
          onClick={onSimulateUploadFlowCard}
          style={{ padding: "10px 16px", fontSize: 13.5 }}
        >
          {I.camera(16)} 模拟上传生产流转单
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => onScrollTo("ai-query")}
          style={{ padding: "10px 16px", fontSize: 13.5 }}
        >
          {I.ask(16)} 询问 AI 助手
        </button>
      </div>

      {/* 副导航：财务 + 采购入口（iter 10） */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          marginTop: 14,
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 11.5, color: "var(--ink-500)" }}>或直接查看：</span>
        <button
          onClick={() => onScrollTo("finance")}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 8,
            border: "1px solid var(--ink-200)",
            background: "var(--surface-2)",
            color: "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {I.cash(14)} 财务 AI 三表
        </button>
        <button
          onClick={() => onScrollTo("purchase")}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 8,
            border: "1px solid var(--ink-200)",
            background: "var(--surface-2)",
            color: "var(--ink-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {I.pkg(14)} 采购订单 + 供应商
        </button>
        <button
          onClick={() => onScrollTo("briefing")}
          style={{
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 8,
            border: "1px solid var(--ai-500)",
            background: "var(--ai-100)",
            color: "var(--ai-700)",
            cursor: "pointer",
            fontFamily: "var(--font)",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          {I.calendar(14)} 今日经营日报
        </button>
      </div>
    </div>
  );
}
