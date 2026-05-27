import { useEffect, useState } from "react";
import { getJintaiProcessParameter, listJintaiFlowCards } from "../../api/jintai";
import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import { batchRecipes, flowCards, processParameter } from "./data";
import type { BatchRecipe, FlowCard, FlowStep, ProcessParameter, StockLedger } from "./data";
import { JintaiRiskBadge, JintaiStatusBadge, JintaiSourceCitation } from "./components";
import { useJintai } from "./state/store";
import { JintaiProductionBomBackendOverlay } from "./JintaiBackendOverlays";

type Tab = "A" | "B" | "C" | "D";

// iter 20: 新增 D · 配料单 (打通附件需求 5 "配方或配料清单（关联库存原料）")
const TABS: { id: Tab; label: string; sub: string }[] = [
  { id: "A", label: "A · 生产流转单", sub: "成型 / 烧结 / 检包" },
  { id: "D", label: "D · 配料单", sub: "配方 + 库存联动" },
  { id: "B", label: "B · 工艺单 / 参数", sub: "配方 · 曲线 · 标准" },
  { id: "C", label: "C · 出货 / 入库", sub: "成品入库 · 出货" },
];

export function JintaiProductionTabs() {
  const { state: jt, dispatch } = useJintai();
  // iter 23: tab 受 tour 控制 (productionSubtab) + 用户点击也回写
  const tab = jt.productionSubtab as Tab;
  const setTab = (t: Tab) => dispatch({ type: "SET_PRODUCTION_SUBTAB", subtab: t as "A" | "D" | "B" | "C" });
  const [cards, setCards] = useState<FlowCard[]>(flowCards);
  const [parameter, setParameter] = useState<ProcessParameter>(processParameter);

  useEffect(() => {
    let cancelled = false;
    listJintaiFlowCards()
      .then((backendCards) => {
        if (!cancelled && backendCards.length > 0) setCards(backendCards);
      })
      .catch(() => undefined);
    getJintaiProcessParameter()
      .then((backendParameter) => {
        if (!cancelled) setParameter(backendParameter);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

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

      {tab === "A" && <FlowCardPanel flowCards={cards} />}
      {tab === "D" && (
        <>
          {/* Round 6: backend mode overlay — /procurement/boms + explode 实时 */}
          <JintaiProductionBomBackendOverlay />
          <BatchRecipePanel recipes={batchRecipes} />
        </>
      )}
      {tab === "B" && <ProcessParameterPanel processParameter={parameter} />}
      {tab === "C" && <ShippingPanel />}
    </div>
  );
}

/* ---------- Tab D: 配料单 (iter 20 · 附件需求 5) ---------- */

/** iter 22: 从 store stockLedgers 取动态库存余量,主线扣减后这里自动更新 */
function liveStockBalance(
  ledgers: StockLedger[],
  materialName: string,
  fallback: number,
): number {
  for (const l of ledgers) {
    if (l.kind !== "原材料") continue;
    const row = l.rows.find((r) => r.name === materialName);
    if (row) return parseInt(row.balance.replace(/,/g, ""), 10) || 0;
  }
  return fallback;
}

function BatchRecipePanel({ recipes }: { recipes: BatchRecipe[] }) {
  const [idx, setIdx] = useState(0);
  const r = recipes[idx] ?? recipes[0];
  const { state } = useJintai();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* 配料单切换 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 600 }}>
          示例配料单：
        </span>
        {recipes.map((rec, i) => {
          const active = i === idx;
          return (
            <button
              key={rec.recipeNo}
              onClick={() => setIdx(i)}
              style={{
                padding: "6px 12px",
                fontSize: 12,
                borderRadius: 8,
                border: `1px solid ${active ? "var(--brand-500)" : "var(--ink-200)"}`,
                background: active ? "var(--brand-100)" : "var(--surface)",
                color: active ? "var(--brand-700)" : "var(--ink-700)",
                cursor: "pointer",
                fontWeight: active ? 600 : 500,
              }}
            >
              {rec.recipeNo} · {rec.customer}
            </button>
          );
        })}
      </div>

      <div className="card" style={{ padding: 18 }}>
        {/* AI 草稿条 */}
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            background: "var(--ai-100)",
            border: "1px solid #bddff3",
            marginBottom: 14,
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            fontSize: 11.5,
          }}
        >
          <span
            style={{
              padding: "3px 9px",
              borderRadius: 5,
              background: "var(--ai-500)",
              color: "#fff",
              fontSize: 10.5,
              fontWeight: 700,
              letterSpacing: "0.06em",
            }}
          >
            ✨ {r.source}
          </span>
          <span style={{ color: "var(--ink-700)" }}>
            ← 关联生产流转单 <strong>{r.flowCardNo}</strong> · 本批材料成本{" "}
            <strong>¥{r.totalMaterialCost.toLocaleString()}</strong>
          </span>
          <span
            style={{
              marginLeft: "auto",
              fontSize: 11,
              color: "var(--ok-700)",
              fontWeight: 600,
            }}
          >
            ✓ {r.approver} · {r.mixedAt ?? "待领料"}
          </span>
        </div>

        {/* 配料单表头 */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: "var(--ink-900)" }}>
            {r.recipeNo} · {r.product}
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-500)", marginTop: 3 }}>
            {r.spec} · {r.customer} · 本批 {r.batchSize.toLocaleString()} {r.batchUnit} · 操作人 {r.operator}
          </div>
          {r.note && (
            <div style={{ fontSize: 11.5, color: "var(--ink-600)", marginTop: 4, fontStyle: "italic" }}>
              {r.note}
            </div>
          )}
        </div>

        {/* 配方明细表 */}
        <div style={{ border: "1px solid var(--ink-200)", borderRadius: 8, overflow: "hidden" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.4fr 1.2fr 70px 110px 110px 110px 130px",
              background: "var(--surface-2)",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--ink-700)",
              letterSpacing: "0.04em",
              padding: "8px 12px",
              borderBottom: "1px solid var(--ink-200)",
            }}
          >
            <span>原料名称</span>
            <span>规格</span>
            <span style={{ textAlign: "right" }}>配比</span>
            <span style={{ textAlign: "right" }}>本批用量</span>
            <span style={{ textAlign: "right" }}>单价 (元)</span>
            <span style={{ textAlign: "right" }}>金额 (元)</span>
            <span style={{ textAlign: "right" }}>库存余量 (kg)</span>
          </div>
          {r.ingredients.map((ingOrig) => {
            const liveBalance = liveStockBalance(state.stockLedgers, ingOrig.materialName, ingOrig.stockBalance);
            const ing = {
              ...ingOrig,
              stockBalance: liveBalance,
              shortage: liveBalance < ingOrig.batchQty,
            };
            const amount = ing.batchQty * ing.unitCost;
            return (
              <div
                key={ing.materialName}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.4fr 1.2fr 70px 110px 110px 110px 130px",
                  padding: "9px 12px",
                  borderTop: "1px solid var(--ink-50)",
                  fontSize: 11.5,
                  background: ing.shortage ? "var(--warn-100)" : undefined,
                  alignItems: "center",
                }}
              >
                <span style={{ fontWeight: 700, color: "var(--ink-900)" }}>{ing.materialName}</span>
                <span style={{ fontFamily: "ui-monospace, monospace", color: "var(--ink-700)" }}>
                  {ing.spec}
                </span>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    color: "var(--ink-700)",
                  }}
                >
                  {ing.ratio.toFixed(1)}%
                </span>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    fontWeight: 700,
                    color: "var(--ink-900)",
                  }}
                >
                  {ing.batchQty.toLocaleString()} kg
                </span>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    color: "var(--ink-700)",
                  }}
                >
                  {ing.unitCost.toFixed(2)}
                </span>
                <span
                  style={{
                    textAlign: "right",
                    fontFamily: "ui-monospace, monospace",
                    fontWeight: 700,
                    color: "var(--ink-900)",
                  }}
                >
                  {amount.toLocaleString()}
                </span>
                {/* iter 21: 库存覆盖进度条 — 覆盖率 = 库存 ÷ 本批用量 */}
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <div
                    style={{
                      height: 10,
                      borderRadius: 5,
                      background: "var(--surface-2)",
                      border: "1px solid var(--ink-100)",
                      overflow: "hidden",
                    }}
                    title={`库存 ${ing.stockBalance.toLocaleString()} kg · 本批需求 ${ing.batchQty.toLocaleString()} kg`}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${Math.min(100, (ing.stockBalance / ing.batchQty) * 100)}%`,
                        background: ing.shortage ? "var(--risk-500)" : "var(--ok-500)",
                      }}
                    />
                  </div>
                  <div
                    style={{
                      fontSize: 10.5,
                      fontFamily: "ui-monospace, monospace",
                      color: ing.shortage ? "var(--risk-700)" : "var(--ok-700)",
                      fontWeight: 700,
                      textAlign: "right",
                    }}
                  >
                    {ing.shortage
                      ? `⚠ 缺 ${(ing.batchQty - ing.stockBalance).toLocaleString()} kg`
                      : `✓ ${ing.stockBalance.toLocaleString()} kg`}
                  </div>
                </div>
              </div>
            );
          })}
          {/* 合计行 */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "3.6fr 110px 110px 240px",
              padding: "10px 12px",
              borderTop: "2px solid var(--ink-200)",
              background: "var(--brand-100)",
              fontSize: 12.5,
              fontWeight: 800,
              color: "var(--brand-700)",
              alignItems: "center",
            }}
          >
            <span>本批材料成本合计</span>
            <span>—</span>
            <span style={{ textAlign: "right" }}>—</span>
            <span
              style={{
                textAlign: "right",
                fontFamily: "ui-monospace, monospace",
              }}
            >
              ¥ {r.totalMaterialCost.toLocaleString()}
            </span>
          </div>
        </div>

        {/* 库存关联提示条 — iter 22 用 store 实时余量 */}
        {(() => {
          const liveIng = r.ingredients.map((i) => {
            const bal = liveStockBalance(state.stockLedgers, i.materialName, i.stockBalance);
            return { ...i, stockBalance: bal, shortage: bal < i.batchQty };
          });
          const shortItems = liveIng.filter((i) => i.shortage);
          return (
        <div
          style={{
            marginTop: 14,
            padding: "10px 14px",
            borderRadius: 10,
            background: shortItems.length > 0 ? "var(--warn-100)" : "var(--ok-100)",
            border: `1px solid ${shortItems.length > 0 ? "#f1d4a6" : "#c7e4d2"}`,
            fontSize: 11.5,
            color: r.ingredients.some((i) => i.shortage)
              ? "var(--warn-700)"
              : "var(--ok-700)",
            lineHeight: 1.6,
          }}
        >
          <strong>← 已关联库存台账 (采购 tab):</strong>{" "}
          {shortItems.length > 0 ? (
            <>
              本批配料有 <strong>{shortItems.length} 项</strong>{" "}
              库存不足 ({shortItems[0].materialName} 缺{" "}
              {(shortItems[0].batchQty - shortItems[0].stockBalance).toLocaleString()} kg),
              AI 已自动触发申购单草稿,待采购张主管审批。
            </>
          ) : (
            <>本批所有原料库存充足,可立即领料投产。</>
          )}
        </div>
          );
        })()}
      </div>
    </div>
  );
}

/* ---------- Tab A: 生产流转单 ---------- */

function FlowCardPanel({ flowCards }: { flowCards: FlowCard[] }) {
  const [idx, setIdx] = useState(1);
  const fc = flowCards[idx] ?? flowCards[0];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 11.5, color: "var(--ink-500)", fontWeight: 600 }}>
          示例流转单：
        </span>
        {flowCards.map((c, i) => {
          const active = i === idx;
          const done = c.status === "完成";
          return (
            <button
              key={c.flowCardNo}
              onClick={() => setIdx(i)}
              style={{
                padding: "6px 12px",
                fontSize: 12,
                borderRadius: 8,
                border: `1px solid ${active ? "var(--brand-500)" : "var(--ink-200)"}`,
                background: active ? "var(--brand-100)" : "var(--surface)",
                color: active ? "var(--brand-700)" : "var(--ink-700)",
                cursor: "pointer",
                fontWeight: active ? 600 : 500,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: done ? "var(--ok-500)" : "var(--brand-500)",
                }}
              />
              {c.flowCardNo} · {c.customer} {done ? "（已完成）" : "（进行中）"}
            </button>
          );
        })}
      </div>
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
          source={{
            kind: "生产流转单",
            label: `${fc.flowCardNo} · 纸质单照片 · ${fc.steps[0].operator?.replace("成型组 · ", "") ?? "—"} 拍`,
          }}
        />
        <JintaiSourceCitation
          source={{
            kind: "合同",
            label: `${fc.customer}_${fc.product}_采购合同.pdf`,
          }}
        />
      </div>
    </div>
  );
}

function StepCard({ step }: { step: FlowStep }) {
  const allRows = stepRows(step);
  // 视觉减负：每张工序卡只显示前 7 个高优字段，其余 chip 折叠
  const rows = allRows.slice(0, 7);
  const hidden = allRows.length - rows.length;
  const isOngoing = step.status === "进行中";
  return (
    <div
      className="card"
      style={{
        padding: 16,
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
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 12 }}>
        计划完成 {step.plannedDate}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {rows.map((r) => (
          <div
            key={r.key}
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12,
              padding: "5px 0",
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
        {hidden > 0 && (
          <div style={{ fontSize: 11, color: "var(--ink-400)", padding: "6px 0 0", textAlign: "right" }}>
            +{hidden} 项已记录
          </div>
        )}
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

function ProcessParameterPanel({ processParameter }: { processParameter: ProcessParameter }) {
  const p = processParameter;
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "grid", gridTemplateColumns: isDesktop ? "1fr 320px" : "1fr", gap: 14 }}>
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
          {p.groups.map((g) => {
            // 视觉减负：每组工艺参数只显示前 3 行，剩余 chip 折叠
            const visible = g.rows.slice(0, 3);
            const hidden = g.rows.length - visible.length;
            return (
              <div
                key={g.title}
                style={{
                  padding: 14,
                  borderRadius: 10,
                  background: "var(--surface-2)",
                  border: "1px solid var(--ink-100)",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink-700)", marginBottom: 8 }}>
                  {g.title}
                </div>
                {visible.map((r) => (
                  <div
                    key={r.key}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 12,
                      padding: "4px 0",
                      color: "var(--ink-800)",
                      gap: 8,
                    }}
                  >
                    <span style={{ color: "var(--ink-500)" }}>{r.key}</span>
                    <span style={{ fontWeight: 600, textAlign: "right" }}>{r.value}</span>
                  </div>
                ))}
                {hidden > 0 && (
                  <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 6 }}>
                    +{hidden} 项参数
                  </div>
                )}
              </div>
            );
          })}
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
          近 30 天刚玉莫来石承烧板不良率 2.06%，较上月下降 0.39 个百分点。
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-700)", lineHeight: 1.55 }}>
          主要不良项：<strong>翘曲超差 36%</strong> · 边角小掉块 27% · 黑斑 18% · 显气孔率偏高 11%。
          翘曲集中在窑车上层，可能与装窑数量偏多有关；显气孔率偏高疑似坯体密度不稳，建议复核近 30 天电熔白刚玉粒度分布。
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
          AI 建议：本月排产保留 LB-1580 曲线，但建议下批次装窑量限制 ≤ 380 块/车；下次原料进货复核 0521 批电熔白刚玉粒度。
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
          <JintaiSourceCitation source={{ kind: "工艺单", label: "刚玉莫来石承烧板 v2.3" }} />
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
        <RowKV k="产品" v="氧化铝匣钵（厦钨规格）" />
        <RowKV k="入库数量" v="1,500 个" />
        <RowKV k="不良 / 抽检" v="不良 30 · 抽检 75（5%）" />
        <RowKV k="仓库位置" v="B 区 02-08" mono />
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
        <RowKV k="客户" v="厦钨新能（宁德工厂）" />
        <RowKV k="产品 / 规格" v="氧化铝匣钵 · 300×220×100 mm" />
        <RowKV k="出货数量" v="1,500 个" />
        <RowKV k="承运" v="德邦物流 · 整车直送" />
        <RowKV k="单据状态" v="待客户签收" />
        <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
          <JintaiSourceCitation source={{ kind: "出货单", label: "CK-2026-018 PDF" }} />
          <JintaiSourceCitation
            source={{ kind: "合同", label: "厦钨新能_订单_2026Q1.pdf" }}
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
