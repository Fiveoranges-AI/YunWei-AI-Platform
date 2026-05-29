import { I } from "../../icons";
import type { ExtractionCard } from "./data";
import { JintaiStatusBadge } from "./components";

const KIND_HINT: Record<string, string> = {
  合同: "合同 PDF",
  生产流转单: "纸质流转单（拍照）",
  "Excel 订单": "订单 Excel",
  出货单: "出货 / 入库单",
};

const UPLOAD_TYPES = [
  { label: "合同 PDF", desc: "客户签约文件", icon: "📄" },
  { label: "订单 Excel", desc: "BOM / 数量明细", icon: "🟢" },
  { label: "微信聊天记录", desc: "客户沟通截图", icon: "💬" },
  { label: "纸质生产流转单", desc: "车间拍照上传", icon: "📷" },
  { label: "工艺参数表", desc: "Excel / 拍照", icon: "⚙️" },
  { label: "出货 / 入库单", desc: "纸质 / 扫描件", icon: "📦" },
];

type Props = {
  cards: ExtractionCard[];
  onSimulateUploadContract: () => void;
  onSimulateUploadFlowCard: () => void;
  onSimulateUploadShipping: () => void;
  onConfirm: (id: string) => void;
};

export function JintaiUploadInbox({
  cards,
  onSimulateUploadContract,
  onSimulateUploadFlowCard,
  onSimulateUploadShipping,
  onConfirm,
}: Props) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 320px) 1fr", gap: 18 }}>
      {/* Left: upload area */}
      <div>
        <div
          className="card"
          style={{ padding: 18, marginBottom: 12, background: "var(--surface-2)" }}
        >
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
            上传客户与生产资料
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-600)", lineHeight: 1.55, marginBottom: 14 }}>
            支持合同、订单、纸质流转单、出货单、工艺参数表、微信截图等格式，AI 自动结构化字段。
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
            {UPLOAD_TYPES.map((t) => (
              <div
                key={t.label}
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: "var(--surface)",
                  border: "1px solid var(--ink-100)",
                  fontSize: 11.5,
                  color: "var(--ink-700)",
                }}
              >
                <div style={{ fontSize: 16 }}>{t.icon}</div>
                <div style={{ fontWeight: 600, marginTop: 4 }}>{t.label}</div>
                <div style={{ color: "var(--ink-400)", marginTop: 2 }}>{t.desc}</div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button
              className="btn btn-primary"
              style={{ width: "100%", padding: "10px 14px", fontSize: 13 }}
              onClick={onSimulateUploadContract}
            >
              {I.cloud(16, "#fff")} 模拟上传合同
            </button>
            <button
              className="btn btn-secondary"
              style={{ width: "100%", padding: "10px 14px", fontSize: 13 }}
              onClick={onSimulateUploadFlowCard}
            >
              {I.camera(16)} 模拟上传生产流转单
            </button>
            <button
              className="btn btn-secondary"
              style={{ width: "100%", padding: "10px 14px", fontSize: 13 }}
              onClick={onSimulateUploadShipping}
            >
              {I.layers(16)} 模拟上传出货单
            </button>
          </div>
        </div>
      </div>

      {/* Right: AI 待确认收件箱 */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-700)" }}>
            <span style={{ color: "var(--ai-500)", marginRight: 6 }}>{I.spark(13)}</span>
            AI 待确认收件箱 · {cards.length}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-400)" }}>
            AI 不直接入库，需人工确认
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {cards.map((c) => (
            <ExtractionCardItem key={c.id} card={c} onConfirm={onConfirm} />
          ))}
          {cards.length === 0 && (
            <div
              style={{
                padding: 24,
                borderRadius: 10,
                border: "1px dashed var(--ink-200)",
                color: "var(--ink-400)",
                fontSize: 13,
                textAlign: "center",
              }}
            >
              暂无待确认草稿
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ExtractionCardItem({
  card,
  onConfirm,
}: {
  card: ExtractionCard;
  onConfirm: (id: string) => void;
}) {
  const isPending = card.status === "待确认";
  return (
    <article
      className="card"
      style={{
        padding: 14,
        borderLeft: `3px solid ${isPending ? "var(--ai-500)" : "var(--ok-500)"}`,
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
          gap: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span className="pill pill-ai" style={{ fontSize: 11 }}>
            {I.spark(10)} AI 识别 · {card.kind}
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{card.uploadedAt}</span>
        </div>
        <JintaiStatusBadge status={card.status} />
      </header>

      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-900)", marginBottom: 4 }}>
        {card.source}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 10 }}>
        识别字段 {card.fields.length} 项 · 整体置信度{" "}
        <span style={{ color: card.confidence >= 0.9 ? "var(--ok-700)" : "var(--warn-700)" }}>
          {(card.confidence * 100).toFixed(0)}%
        </span>{" "}
        · 待生成：{card.toBeGenerated}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 6,
          marginBottom: 12,
        }}
      >
        {card.fields.map((f) => {
          const low = (f.confidence ?? 1) < 0.85;
          return (
            <div
              key={f.key}
              style={{
                padding: "7px 9px",
                borderRadius: 8,
                background: low ? "var(--warn-50)" : "var(--surface-2)",
                border: `1px solid ${low ? "#fbe6c5" : "var(--ink-100)"}`,
                fontSize: 11.5,
                color: "var(--ink-800)",
                lineHeight: 1.4,
              }}
            >
              <div
                style={{
                  fontSize: 10.5,
                  color: "var(--ink-500)",
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span>{f.key}</span>
                {f.confidence !== undefined && (
                  <span style={{ color: low ? "var(--warn-700)" : "var(--ink-400)" }}>
                    {(f.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>{f.value}</div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {isPending ? (
          <>
            <button
              className="btn btn-primary"
              onClick={() => onConfirm(card.id)}
              style={{ padding: "8px 14px", fontSize: 12.5 }}
            >
              {I.check(14, "#fff")}
              {card.kind === "合同" || card.kind === "Excel 订单"
                ? "确认生成订单"
                : card.kind === "生产流转单"
                  ? "确认生成流转单"
                  : "确认入库"}
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: "8px 14px", fontSize: 12.5 }}
            >
              修改字段
            </button>
            <button
              className="btn btn-secondary"
              style={{ padding: "8px 14px", fontSize: 12.5 }}
            >
              查看原件
            </button>
            <span
              style={{
                fontSize: 11,
                color: "var(--ink-400)",
                alignSelf: "center",
                marginLeft: "auto",
              }}
            >
              {KIND_HINT[card.kind] ?? card.kind}
            </span>
          </>
        ) : (
          <>
            <span
              className="pill pill-ok"
              style={{ padding: "5px 10px", fontSize: 11.5, fontWeight: 600 }}
            >
              {I.check(11)} 已确认入库
            </span>
            <button
              className="btn btn-ghost"
              style={{ padding: "6px 10px", fontSize: 12 }}
            >
              查看生成结果
            </button>
          </>
        )}
      </div>
    </article>
  );
}
