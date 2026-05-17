import { useState } from "react";
import { I } from "../../icons";
import { flowCards, processParameter } from "./data";
import type { FlowStep } from "./data";
import { JintaiRiskBadge, JintaiStatusBadge, JintaiSourceCitation } from "./components";

type Tab = "A" | "B" | "C";

const TABS: { id: Tab; label: string; sub: string }[] = [
  { id: "A", label: "A · 生产流转单", sub: "成型 / 烧结 / 检包" },
  { id: "B", label: "B · 工艺单 / 参数", sub: "配方 · 曲线 · 标准" },
  { id: "C", label: "C · 出货 / 入库", sub: "成品入库 · 出货" },
];

export function JintaiProductionTabs() {
  const [tab, setTab] = useState<Tab>("A");
  return (
    <div>
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: 4,
          borderRadius: 12,
          background: "var(--surface-2)",
          border: "1px solid var(--ink-100)",
          marginBottom: 14,
          width: "fit-content",
        }}
      >
        {TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: "8px 14px",
                borderRadius: 8,
                border: "none",
                background: active ? "var(--surface)" : "transparent",
                boxShadow: active ? "var(--shadow-card-soft)" : "none",
                color: active ? "var(--ink-900)" : "var(--ink-600)",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                lineHeight: 1.2,
                gap: 2,
              }}
            >
              <span>{t.label}</span>
              <span style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 500 }}>
                {t.sub}
              </span>
            </button>
          );
        })}
      </div>

      {tab === "A" && <FlowCardPanel />}
      {tab === "B" && <ProcessParameterPanel />}
      {tab === "C" && <ShippingPanel />}
    </div>
  );
}

/* ---------- Tab A: 生产流转单 ---------- */

function FlowCardPanel() {
  const fc = flowCards[0];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="card" style={{ padding: 16 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 12,
            marginBottom: 12,
          }}
        >
          <Field label="流转单号" value={fc.flowCardNo} mono />
          <Field label="计划单号" value={fc.planNo} mono />
          <Field label="订单号" value={fc.orderNo} mono />
          <Field label="客户" value={fc.customer} />
          <Field label="产品" value={fc.product} />
          <Field label="规格" value={fc.specification} mono />
          <Field label="计划数量" value={fc.plannedQty.toLocaleString()} />
          <Field label="交付日期" value={fc.deliveryDate} />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <JintaiStatusBadge status={fc.status} />
          <JintaiRiskBadge risk={fc.risk} />
          <span className="pill pill-brand" style={{ fontSize: 11 }}>
            当前工序：{fc.currentStep}
          </span>
          <span style={{ fontSize: 11, color: "var(--ink-400)", marginLeft: "auto" }}>
            源自 AI 抽取 · 已人工确认
          </span>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 12,
        }}
      >
        {fc.steps.map((s) => (
          <StepCard key={s.name} step={s} />
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: "var(--ink-500)", fontWeight: 600 }}>来源</span>
        <JintaiSourceCitation
          source={{ kind: "生产流转单", label: "ZC-2026-015 · 纸质单照片" }}
        />
        <JintaiSourceCitation source={{ kind: "合同", label: "华东客户_设备采购合同_2026Q2.pdf" }} />
      </div>
    </div>
  );
}

function StepCard({ step }: { step: FlowStep }) {
  const rows = stepRows(step);
  const isOngoing = step.status === "进行中";
  return (
    <div
      className="card"
      style={{
        padding: 14,
        borderTop: `3px solid ${
          step.status === "已完成"
            ? "var(--ok-500)"
            : isOngoing
              ? "var(--brand-500)"
              : "var(--ink-200)"
        }`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 4,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>
          {step.name}
        </div>
        <JintaiStatusBadge status={step.status} />
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 10 }}>
        计划完成 {step.plannedDate}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {rows.map((r) => (
          <div
            key={r.key}
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12,
              padding: "4px 0",
              borderBottom: "1px dashed var(--ink-100)",
            }}
          >
            <span style={{ color: "var(--ink-500)" }}>{r.key}</span>
            <span
              style={{
                color: r.empty ? "var(--ink-400)" : "var(--ink-900)",
                fontWeight: r.empty ? 400 : 600,
                fontFamily: r.mono ? "ui-monospace, monospace" : undefined,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {r.empty ? "— 待录入" : r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function stepRows(
  s: FlowStep,
): { key: string; value: string; empty?: boolean; mono?: boolean }[] {
  if (s.name === "成型") {
    return [
      { key: "机台号", value: s.machineNo ?? "—", empty: !s.machineNo, mono: true },
      { key: "模具号", value: s.moldNo ?? "—", empty: !s.moldNo, mono: true },
      { key: "流转卡号", value: s.flowCardNo ?? "—", empty: !s.flowCardNo, mono: true },
      { key: "料号", value: s.materialNo ?? "—", empty: !s.materialNo, mono: true },
      { key: "领料数量", value: fmtNum(s.materialQty) },
      { key: "剩料", value: fmtNum(s.remainingMaterialQty) },
      { key: "成品数量", value: fmtNum(s.completedQty) },
      { key: "废坯数量", value: fmtNum(s.wasteBlankQty) },
      { key: "操作人", value: s.operator ?? "—", empty: !s.operator },
    ];
  }
  if (s.name === "烧结") {
    return [
      { key: "接收数量", value: fmtNum(s.receivedQty) },
      { key: "窑炉编号", value: s.kilnNo ?? "—", empty: !s.kilnNo, mono: true },
      { key: "曲线号", value: s.curveNo ?? "—", empty: !s.curveNo, mono: true },
      { key: "装窑日期", value: s.loadingDate ?? "—", empty: !s.loadingDate },
      { key: "烧成开始", value: s.burningStartTime ?? "—", empty: !s.burningStartTime },
      { key: "装窑数量", value: fmtNum(s.kilnLoadingQty) },
      { key: "出窑数量", value: fmtNum(s.kilnOutputQty) },
      { key: "不良数量", value: fmtNum(s.defectQty) },
      { key: "操作人", value: s.operator ?? "—", empty: !s.operator },
    ];
  }
  // 检包
  return [
    { key: "接收数量", value: fmtNum(s.receivedQty) },
    { key: "合格数量", value: fmtNum(s.qualifiedQty) },
    { key: "可修复", value: fmtNum(s.repairableQty) },
    { key: "小坍块", value: fmtNum(s.smallChipQty) },
    { key: "大坍块", value: fmtNum(s.largeChipQty) },
    { key: "黑斑", value: fmtNum(s.blackSpotQty) },
    { key: "裂纹", value: fmtNum(s.crackQty) },
    { key: "严重缺陷", value: fmtNum(s.severeDamageQty) },
    { key: "黑料", value: fmtNum(s.blackMaterialQty) },
    { key: "废品", value: fmtNum(s.scrapQty) },
    { key: "操作人", value: s.operator ?? "—", empty: !s.operator },
  ];
}

function fmtNum(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString();
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600 }}>{label}</div>
      <div
        style={{
          fontSize: 13,
          color: "var(--ink-900)",
          fontWeight: 600,
          marginTop: 2,
          fontFamily: mono ? "ui-monospace, monospace" : undefined,
        }}
      >
        {value}
      </div>
    </div>
  );
}

/* ---------- Tab B: 工艺单 / 参数 ---------- */

function ProcessParameterPanel() {
  const p = processParameter;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 14 }}>
      <div className="card" style={{ padding: 16 }}>
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>{p.product}</div>
          <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 2 }}>
            工艺版本 {p.version}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-700)", marginTop: 6, lineHeight: 1.6 }}>
            工艺路线：{p.route}
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
            marginTop: 12,
          }}
        >
          {p.groups.map((g) => (
            <div
              key={g.title}
              style={{
                padding: 12,
                borderRadius: 10,
                background: "var(--surface-2)",
                border: "1px solid var(--ink-100)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-700)", marginBottom: 6 }}>
                {g.title}
              </div>
              {g.rows.map((r) => (
                <div
                  key={r.key}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    padding: "3px 0",
                    color: "var(--ink-800)",
                  }}
                >
                  <span style={{ color: "var(--ink-500)" }}>{r.key}</span>
                  <span style={{ fontWeight: 600 }}>{r.value}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div
        className="ai-surface"
        style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 700,
            color: "var(--ai-700)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {I.spark(12)} AI 工艺洞察
        </div>
        <div style={{ fontSize: 13.5, color: "var(--ink-900)", lineHeight: 1.55, fontWeight: 600 }}>
          近 30 天高铝耐火砖不良率 2.06%，较上月下降 0.39 个百分点。
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>
          主要不良项：<strong>黑斑 38%</strong> · 轻微坍块 27% · 小裂纹 18%。
          黑斑占比偏高，可能与粘结剂含碳量有关，建议核查近 30 天粘结剂供应商批次。
        </div>
        <div
          style={{
            marginTop: 4,
            padding: "10px 12px",
            borderRadius: 10,
            background: "rgba(255,255,255,0.7)",
            border: "1px solid #bddff3",
            fontSize: 11.5,
            color: "var(--ink-700)",
          }}
        >
          AI 建议：本月排产保留 QX-08 曲线，但下次进料时复核粘结剂成分。
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
          <JintaiSourceCitation source={{ kind: "工艺单", label: "高铝耐火砖 v2.3" }} />
          <JintaiSourceCitation source={{ kind: "生产流转单", label: "ZC-2026-010 ~ 014 检包段" }} />
        </div>
      </div>
    </div>
  );
}

/* ---------- Tab C: 出货 / 入库 ---------- */

function ShippingPanel() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
        gap: 14,
      }}
    >
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span className="pill pill-brand" style={{ fontSize: 11 }}>📥 成品入库</span>
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>2026-05-14</span>
        </div>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
          IK-2026-022
        </div>
        <RowKV k="对应流转单" v="ZC-2026-012" mono />
        <RowKV k="产品" v="莫来石砖（定制规格）" />
        <RowKV k="入库数量" v="1,500 块" />
        <RowKV k="不良 / 抽检" v="不良 30 · 抽检 75" />
        <RowKV k="仓库位置" v="A 区 03-12" mono />
        <RowKV k="操作人" v="王仓管" />
        <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
          <JintaiSourceCitation
            source={{ kind: "入库单", label: "IK-2026-022 纸质单照片" }}
          />
        </div>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span className="pill pill-warn" style={{ fontSize: 11 }}>📦 出货</span>
          <span style={{ fontSize: 11, color: "var(--ink-400)" }}>计划 2026-05-17</span>
        </div>
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)", marginBottom: 8 }}>
          CK-2026-018
        </div>
        <RowKV k="对应订单" v="SO-2026-010" mono />
        <RowKV k="客户" v="浙江外贸客户" />
        <RowKV k="产品 / 规格" v="莫来石砖 · 定制" />
        <RowKV k="出货数量" v="1,500 块" />
        <RowKV k="承运" v="顺丰物流 · 自提" />
        <RowKV k="单据状态" v="待客户签收" />
        <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
          <JintaiSourceCitation source={{ kind: "出货单", label: "CK-2026-018 PDF" }} />
          <JintaiSourceCitation
            source={{ kind: "合同", label: "浙江外贸_订单_2026Q2.pdf" }}
          />
        </div>
      </div>
    </div>
  );
}

function RowKV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        fontSize: 12.5,
        padding: "5px 0",
        borderBottom: "1px dashed var(--ink-100)",
      }}
    >
      <span style={{ color: "var(--ink-500)" }}>{k}</span>
      <span
        style={{
          color: "var(--ink-900)",
          fontWeight: 600,
          fontFamily: mono ? "ui-monospace, monospace" : undefined,
        }}
      >
        {v}
      </span>
    </div>
  );
}
