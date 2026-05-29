import { I } from "../../icons";

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
  return (
    <div
      className="card"
      style={{
        padding: "26px 28px",
        marginBottom: 20,
        background:
          "linear-gradient(135deg, #f4faff 0%, #eff7fc 60%, #dcedf8 100%)",
        border: "1px solid #bddff3",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span
          className="pill pill-ai"
          style={{ fontSize: 11, padding: "3px 9px", letterSpacing: 0.02 }}
        >
          {I.spark(10)} 客户试点 · 演示版（无后端，纯前端）
        </span>
        <span className="pill pill-outline" style={{ fontSize: 11, padding: "3px 9px" }}>
          基于 / 智通客户 延展
        </span>
      </div>
      <h1
        style={{
          margin: 0,
          fontSize: 26,
          fontWeight: 700,
          color: "var(--ink-900)",
          letterSpacing: "-0.01em",
          lineHeight: 1.2,
        }}
      >
        宜兴市锦泰耐火材料 · AI 生产流转试点
      </h1>
      <p
        style={{
          margin: "10px 0 18px",
          fontSize: 14,
          color: "var(--ink-600)",
          lineHeight: 1.6,
          maxWidth: 760,
        }}
      >
        基于智通客户已有的「资料抽取 + AI 问答 + 来源可追溯」能力，
        把<strong>合同、订单 Excel、微信记录、纸质生产流转单</strong>
        转化为可<strong>确认、可追踪、可查询</strong>的生产经营数据。
        AI 不直接写入正式业务数据 —— 先生成待确认草稿，经人工确认后入库。
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
          padding: "12px 14px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.7)",
          border: "1px solid rgba(45,155,216,0.18)",
          fontSize: 12.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
        }}
      >
        <strong style={{ color: "var(--ai-700)" }}>第一阶段范围 · 不替换现有 ERP</strong>
        <ul style={{ margin: "6px 0 0 0", paddingLeft: 18 }}>
          <li>合同 / 订单 / Excel 自动结构化 + 人工确认</li>
          <li>纸质生产流转单照片转电子流转单</li>
          <li>三道工序（成型 / 烧结 / 检包）记录</li>
          <li>工艺单与工艺参数沉淀</li>
          <li>简易入库 / 出货登记</li>
          <li>老板自然语言查询生产进度与不良率</li>
          <li>每日生产风险简报</li>
          <li>每条 AI 回答都附原始来源引用</li>
        </ul>
      </div>
    </div>
  );
}
