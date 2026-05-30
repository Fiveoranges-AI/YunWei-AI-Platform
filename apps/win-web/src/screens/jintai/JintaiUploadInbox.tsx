import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import type { ExtractionCard } from "./data";
import { JintaiStatusBadge } from "./components";
import { flashStyle, useJintai } from "./state/store";

export type ProcessingCard = {
  id: string;
  kind: ExtractionCard["kind"];
  filename: string;
  size: string;
  progress: number;
  stage: string;
  startedAt: string;
};

const KIND_HINT: Record<string, string> = {
  合同: "合同 PDF",
  生产流转单: "纸质流转单（拍照）",
  "Excel 订单": "订单 Excel",
  出货单: "出货 / 入库单",
};

// 视觉减负：保留最核心 3 种上传类型（合同 / 订单 Excel / 纸质流转单）
const UPLOAD_TYPES = [
  { label: "合同 PDF", desc: "客户签约文件", icon: "📄" },
  { label: "订单 Excel", desc: "BOM / 数量明细", icon: "🟢" },
  { label: "纸质生产流转单", desc: "车间拍照上传", icon: "📷" },
];

type Props = {
  cards: ExtractionCard[];
  processing?: ProcessingCard[];
  onSimulateUploadContract: () => void;
  onSimulateUploadFlowCard: () => void;
  onSimulateUploadShipping: () => void;
  onConfirm: (id: string) => void;
};

export function JintaiUploadInbox({
  cards,
  processing = [],
  onSimulateUploadContract,
  onSimulateUploadFlowCard,
  onSimulateUploadShipping,
  onConfirm,
}: Props) {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "grid", gridTemplateColumns: isDesktop ? "minmax(260px, 320px) 1fr" : "1fr", gap: 18 }}>
      {/* Left: upload area */}
      <div>
        <div
          className="card"
          style={{ padding: 22, marginBottom: 12 }}
        >
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", marginBottom: 6 }}>
            上传客户与生产资料
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", lineHeight: 1.55, marginBottom: 16 }}>
            AI 自动结构化字段，人工 1 步确认后入库
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 8, marginBottom: 16 }}>
            {UPLOAD_TYPES.map((t) => (
              <div
                key={t.label}
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: "var(--surface-2)",
                  border: "1px solid var(--ink-100)",
                  fontSize: 12,
                  color: "var(--ink-700)",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                <span style={{ fontSize: 18 }}>{t.icon}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{t.label}</div>
                  <div style={{ color: "var(--ink-400)", fontSize: 11, marginTop: 1 }}>{t.desc}</div>
                </div>
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
            <MainlineKickoffButton />
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
            {processing.length > 0 && (
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--ai-700)",
                  background: "var(--ai-100)",
                  padding: "2px 8px",
                  borderRadius: 999,
                }}
              >
                正在处理 {processing.length}
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-400)" }}>
            AI 不直接入库，需人工确认
          </div>
        </div>
        <StoreInboxCards />
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {processing.map((p) => (
            <ProcessingCardItem key={p.id} card={p} />
          ))}
          {cards.map((c) => (
            <ExtractionCardItem key={c.id} card={c} onConfirm={onConfirm} />
          ))}
          {cards.length === 0 && processing.length === 0 && (
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

/* iter 22: 主线领料单 kickoff 按钮 (调 store dispatch) */
function MainlineKickoffButton() {
  const { dispatch, state, consts } = useJintai();
  const alreadyTriggered = state.inboxCards.some((c) => c.id === consts.newInboxId);
  return (
    <button
      onClick={() => dispatch({ type: "SIMULATE_RAW_ISSUE" })}
      style={{
        width: "100%",
        padding: "10px 14px",
        fontSize: 13,
        background: alreadyTriggered ? "var(--surface-2)" : "var(--jintai-red)",
        color: alreadyTriggered ? "var(--ink-500)" : "#fff",
        border: alreadyTriggered ? "1px solid var(--ink-200)" : "none",
        borderRadius: 8,
        cursor: alreadyTriggered ? "not-allowed" : "pointer",
        fontWeight: 700,
        fontFamily: "var(--font)",
      }}
      title="主线 demo 起点 — 模拟成型车间张师傅扫码领 α 氧化铝粉 800 kg"
      disabled={alreadyTriggered}
    >
      📋 模拟车间领料单 (主线起点)
    </button>
  );
}

/* iter 22: 渲染 store-managed 收件箱草稿 (来自主线 dispatch) */
function StoreInboxCards() {
  const { state, dispatch, isFlashing } = useJintai();
  const pending = state.inboxCards.filter((c) => c.status === "待确认");
  if (pending.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 10 }}>
      {pending.map((c) => {
        const flashing = isFlashing(`inbox:${c.id}`);
        return (
          <article
            key={c.id}
            className="card"
            style={{
              padding: 14,
              borderLeft: "3px solid var(--jintai-red)",
              background: "rgba(195,38,41,0.04)",
              ...flashStyle(flashing),
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--jintai-red)", letterSpacing: "0.04em" }}>
                  ✨ AI 抽取 · {c.kind} · 主线
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)", marginTop: 2 }}>
                  {c.source}
                </div>
              </div>
              <JintaiStatusBadge status={c.status} />
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: 6,
                marginBottom: 10,
              }}
            >
              {c.fields.map((f) => (
                <div
                  key={f.key}
                  style={{
                    padding: "6px 9px",
                    borderRadius: 6,
                    background: "var(--surface-2)",
                    border: "1px solid var(--ink-100)",
                    fontSize: 11,
                  }}
                >
                  <div style={{ fontSize: 10, color: "var(--ink-500)", fontWeight: 600 }}>{f.key}</div>
                  <div style={{ color: "var(--ink-900)", fontWeight: 600, marginTop: 1 }}>{f.value}</div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button
                onClick={() => dispatch({ type: "CONFIRM_INBOX", cardId: c.id })}
                style={{
                  padding: "6px 14px",
                  fontSize: 11.5,
                  fontWeight: 700,
                  background: "var(--jintai-green)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                ✓ 王仓管 确认入账
              </button>
              <button
                onClick={() => dispatch({ type: "REJECT_INBOX", cardId: c.id })}
                style={{
                  padding: "6px 14px",
                  fontSize: 11.5,
                  fontWeight: 500,
                  background: "var(--surface-2)",
                  color: "var(--ink-700)",
                  border: "1px solid var(--ink-200)",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontFamily: "var(--font)",
                }}
              >
                驳回
              </button>
              <span style={{ fontSize: 11, color: "var(--ink-500)", marginLeft: "auto" }}>
                {c.uploadedAt} · 即将生成: <strong style={{ color: "var(--ink-700)" }}>{c.toBeGenerated}</strong>
              </span>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ProcessingCardItem({ card }: { card: ProcessingCard }) {
  const pct = Math.min(100, Math.max(0, card.progress));
  return (
    <article
      className="card"
      style={{
        padding: 14,
        borderLeft: "3px solid var(--ai-500)",
        background:
          "linear-gradient(120deg, rgba(45,155,216,0.04) 0%, rgba(45,155,216,0.10) 50%, rgba(45,155,216,0.04) 100%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 6,
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span className="pill pill-ai" style={{ fontSize: 11 }}>
            {I.spark(10)} AI 处理中 · {card.kind}
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>{card.startedAt}</span>
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--ai-700)",
            background: "rgba(255,255,255,0.7)",
            padding: "3px 8px",
            borderRadius: 999,
            border: "1px solid #d8e8f4",
          }}
        >
          {card.stage}
        </span>
      </header>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--ink-900)",
          marginBottom: 4,
          display: "flex",
          alignItems: "baseline",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <span>{card.filename}</span>
        <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 500 }}>
          {card.size}
        </span>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 10 }}>
        正在从文件抽取结构化字段 · 暂未入库
      </div>
      <div
        style={{
          height: 6,
          background: "rgba(45,155,216,0.12)",
          borderRadius: 999,
          overflow: "hidden",
          marginBottom: 8,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background:
              "linear-gradient(90deg, var(--ai-500) 0%, var(--brand-500) 100%)",
            transition: "width 0.28s ease-out",
            borderRadius: 999,
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "var(--ink-500)",
        }}
      >
        <span>{pct}%</span>
        <span>下一步：人工确认 → 待生成草稿</span>
      </div>
    </article>
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
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 12 }}>
        识别 {card.fields.length} 项 · 整体置信度{" "}
        <span style={{ color: card.confidence >= 0.9 ? "var(--ok-700)" : "var(--warn-700)" }}>
          {(card.confidence * 100).toFixed(0)}%
        </span>{" "}
        · 待生成：{card.toBeGenerated}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 8,
          marginBottom: 12,
        }}
      >
        {/* 视觉减负：每张卡只展示前 6 个高优字段，其余以 "+N 字段" chip 折叠 */}
        {card.fields.slice(0, 6).map((f) => {
          const low = (f.confidence ?? 1) < 0.85;
          return (
            <div
              key={f.key}
              style={{
                padding: "8px 10px",
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
                {/* 只对低置信度 (< 90%) 显示百分比，减少视觉噪声 */}
                {f.confidence !== undefined && f.confidence < 0.9 && (
                  <span style={{ color: low ? "var(--warn-700)" : "var(--ink-400)" }}>
                    {(f.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <div style={{ fontWeight: 600, marginTop: 2 }}>{f.value}</div>
            </div>
          );
        })}
        {card.fields.length > 6 && (
          <div
            style={{
              padding: "8px 10px",
              borderRadius: 8,
              background: "var(--surface)",
              border: "1px dashed var(--ink-200)",
              fontSize: 11.5,
              color: "var(--ink-500)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            +{card.fields.length - 6} 项字段
          </div>
        )}
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
                ? "确认订单草稿"
                : card.kind === "生产流转单"
                  ? "确认流转单草稿"
                  : "确认出货草稿"}
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
              {I.check(11)} 已人工确认
            </span>
            <button
              className="btn btn-ghost"
              style={{ padding: "6px 10px", fontSize: 12 }}
            >
              查看队列记录
            </button>
          </>
        )}
      </div>
    </article>
  );
}
