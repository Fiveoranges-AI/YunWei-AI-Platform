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
        padding: isDesktop ? "26px 28px" : "20px 18px",
        marginBottom: 20,
        background:
          "linear-gradient(135deg, #f4faff 0%, #eff7fc 60%, #dcedf8 100%)",
        border: "1px solid #bddff3",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <span
          className="pill pill-ai"
          style={{ fontSize: 11, padding: "3px 9px", letterSpacing: 0.02 }}
        >
          {I.spark(10)} 客户试点演示 · 2026-05
        </span>
        <span className="pill pill-outline" style={{ fontSize: 11, padding: "3px 9px" }}>
          试点周期 2–3 周 · 不替换现有 ERP
        </span>
        <span className="pill pill-outline" style={{ fontSize: 11, padding: "3px 9px" }}>
          按 ISO9001 留档 · 来源 100% 可追溯
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: isDesktop ? 14 : 10, flexWrap: "wrap" }}>
        <img
          src={`${import.meta.env.BASE_URL}jintai-logo.png`}
          alt="锦泰耐火材料"
          style={{ height: isDesktop ? 56 : 44, width: "auto", flexShrink: 0 }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0, flex: 1 }}>
          <h1
            style={{
              margin: 0,
              fontSize: isDesktop ? 26 : 19,
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
              fontSize: 13,
              color: "var(--ai-700)",
              fontWeight: 600,
              letterSpacing: "0.01em",
            }}
          >
            让承烧板从「合同 / 纸质流转单」一路追到「客户验收 + 应收账期」，全过程 AI 辅助 · 人工确认
          </div>
        </div>
      </div>
      <p
        style={{
          margin: "10px 0 18px",
          fontSize: 14,
          color: "var(--ink-600)",
          lineHeight: 1.6,
          maxWidth: 820,
        }}
      >
        面向锦泰<strong>承烧板 / 推板 / 匣钵 / 支柱</strong>的实际生产流程，
        把<strong>客户合同、订单 Excel、微信记录、纸质生产流转单</strong>
        转化为可<strong>确认、可追踪、可查询</strong>的经营数据。
        客户线覆盖锂电正极烧结、磁性材料、MLCC、粉末冶金等下游。
        AI 不直接写入正式业务数据 —— 先生成待确认草稿，由销售 / 生产 / 检验确认后入库。
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
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

      <div
        style={{
          marginTop: 22,
          padding: "14px 16px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.7)",
          border: "1px solid rgba(45,155,216,0.18)",
          fontSize: 12.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 10,
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          <strong style={{ color: "var(--ai-700)", fontSize: 13 }}>
            第一阶段范围 · 不替换现有 ERP
          </strong>
          <span style={{ fontSize: 11, color: "var(--ink-500)" }}>
            建议试点时长 2–3 周 · 单点接入 · 不动账套
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isDesktop ? "repeat(2, 1fr)" : "1fr",
            gap: "6px 16px",
          }}
        >
          {[
            "合同 / 订单 / Excel 自动结构化 + 人工确认",
            "纸质生产流转单照片转电子流转单",
            "三道工序（成型 / 烧结 / 检包）全程记录",
            "工艺单与烧成曲线参数沉淀",
            "成品入库 / 客户出货登记",
            "老板中文查询生产进度 + 不良率 + 应收",
            "每日生产风险简报（高 / 中 / 低 自动分级）",
            "每条 AI 字段附原始来源引用 · 一键回溯",
          ].map((line) => (
            <div
              key={line}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 6,
                fontSize: 12.5,
                color: "var(--ink-700)",
                lineHeight: 1.5,
              }}
            >
              <span
                style={{
                  color: "var(--ai-700)",
                  fontWeight: 700,
                  flexShrink: 0,
                  fontSize: 12,
                  marginTop: 1,
                }}
              >
                ✓
              </span>
              <span>{line}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
