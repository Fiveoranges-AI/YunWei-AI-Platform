import { I } from "../../icons";
import { useIsDesktop } from "../../lib/breakpoints";
import {
  payableLedger,
  purchaseInboxCards,
  purchaseOrders,
  purchaseRequisitions,
  stockLedgers,
  suppliers,
} from "./data";
import type {
  PayableRow,
  PurchaseInboxCard,
  PurchaseOrder,
  PurchaseRequisition,
  StockLedger,
  Supplier,
} from "./data";
import { JintaiSourceCitation, JintaiStatusBadge } from "./components";

export function JintaiPurchasePanel() {
  const isDesktop = useIsDesktop();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
      {/* iter 19.1：AI-native 模式定位条 — "脱离金蝶也能跑" */}
      <AINativePurchaseBanner />

      {/* iter 19 链路提示条：申购 → 订单 → 入库 → 库存 → 应付 */}
      <PurchaseChainHint />

      {/* Section 1: 物资申购单（链路起点 · 新增） */}
      <SectionHeader
        title="物资申购单"
        sub="申购 → 审批 → 转采购订单 · AI 自动从车间领料群 / 纸质单抽取，仓管 + 采购 + 老板分级审批"
      />
      <RequisitionList requisitions={purchaseRequisitions} />

      {/* Section 2: 采购订单列表 */}
      <SectionHeader
        title="本月采购订单"
        sub="6 张已下单 · 总金额 ¥327,000 · 全部来自 AI 抽取的纸质合同 / 邮件订单，财务确认后入账"
      />
      <PurchaseOrderTable orders={purchaseOrders} />

      {/* Section 3: 供应商档案 */}
      <SectionHeader
        title="主要供应商"
        sub="5 家长期供应商 · 每月采购总额 ¥405,000 · 账期 30–60 天 · AI 维护账期与质量评分"
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop
            ? "repeat(auto-fit, minmax(260px, 1fr))"
            : "1fr",
          gap: 12,
        }}
      >
        {suppliers.map((s) => (
          <SupplierCard key={s.shortName} supplier={s} />
        ))}
      </div>

      {/* Section 4: AI 采购信息收件箱 */}
      <SectionHeader
        title="AI 采购信息收件箱"
        sub="发票 / 合同 / 入库单 AI 自动抽取，财务 + 采购双确认才入账 · 防止重复付款 + 漏入库"
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {purchaseInboxCards.map((c) => (
          <PurchaseInboxCardView key={c.id} card={c} />
        ))}
      </div>

      {/* Section 5: 库存台账（原材料 + 成品）— 新增进销存核心 */}
      <SectionHeader
        title="库存台账 · 进销存月报"
        sub="原材料月报表 + 成品月报表 · 起始 + 入 − 出 = 结存 自动滚算 · 低于安全库存自动预警"
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {stockLedgers.map((sl) => (
          <StockLedgerTable key={sl.kind} ledger={sl} />
        ))}
      </div>

      {/* Section 6: 应付账款台账 + 账期提醒 */}
      <SectionHeader
        title="应付账款台账"
        sub="从入库单 / 发票自动汇总应付 · 按到期日排序 · AI 提前 X 天提醒 · 接经营日报「本月待付」"
      />
      <PayableLedgerTable rows={payableLedger} />
    </div>
  );
}

/* ============== AI-native 模式定位条 ============== */

function AINativePurchaseBanner() {
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 10,
        background:
          "linear-gradient(90deg, rgba(173,30,38,0.04) 0%, rgba(15,69,42,0.06) 50%, rgba(56,138,210,0.06) 100%)",
        border: "1px solid var(--ink-100)",
        display: "flex",
        gap: 10,
        alignItems: "center",
        flexWrap: "wrap",
        fontSize: 11.5,
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "3px 9px",
          borderRadius: 5,
          background: "var(--jintai-red)",
          color: "#fff",
          fontSize: 10.5,
          fontWeight: 700,
          letterSpacing: "0.06em",
        }}
      >
        AI-NATIVE 模式
      </span>
      <span style={{ color: "var(--ink-700)", lineHeight: 1.55, flex: 1, minWidth: 280 }}>
        本套采购<strong style={{ color: "var(--jintai-green-dark)" }}>不依赖金蝶</strong>。
        AI 从 微信群语音 / 邮件合同 / 纸质表单 OCR / 发票 自动抽取申购 + 订单 + 入库 + 应付 →
        采购张主管 + 财务王会计 1 步确认即可入账。
        <span style={{ color: "var(--ink-500)" }}>
          (每条数据带"AI 抽取"或"人工录入"标签，全程可追溯)
        </span>
      </span>
    </div>
  );
}

/* 通用 数据来源 tag (AI 抽取 / 人工录入) */
function DataSourceTag({ source }: { source: string }) {
  const isAI = source.startsWith("AI");
  return (
    <span
      className="pill"
      style={{
        background: isAI ? "var(--ai-100)" : "var(--surface-2)",
        color: isAI ? "var(--ai-700)" : "var(--ink-600)",
        fontSize: 10,
        fontWeight: 600,
        padding: "2px 7px",
        borderRadius: 5,
        whiteSpace: "nowrap",
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
      }}
      title={isAI ? "AI 自动抽取，已待人工确认" : "由人工手动录入，无 AI 草稿"}
    >
      {isAI ? "✨" : "👤"} {source}
    </span>
  );
}

/* ============== 链路提示条 ============== */

function PurchaseChainHint() {
  const steps = [
    { label: "申购单", n: "3 张", color: "var(--ai-purple)" },
    { label: "采购订单", n: "6 张", color: "var(--brand-700)" },
    { label: "入库", n: "5 张", color: "var(--jintai-red)" },
    { label: "库存台账", n: "原料 6 项 / 成品 4 项", color: "var(--jintai-green-dark)" },
    { label: "应付账款", n: "¥327,000", color: "var(--warn-700)" },
  ];
  return (
    <div
      className="card-flat"
      style={{
        padding: "12px 16px",
        borderRadius: 12,
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        alignItems: "center",
        background: "var(--surface-2)",
        border: "1px dashed var(--ink-200)",
        fontSize: 11.5,
      }}
    >
      <span style={{ fontWeight: 700, color: "var(--ink-700)", letterSpacing: "0.04em" }}>
        采购链路：
      </span>
      {steps.map((s, i) => (
        <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              display: "inline-flex",
              flexDirection: "column",
              alignItems: "center",
              padding: "4px 10px",
              borderRadius: 8,
              background: "var(--surface)",
              border: "1px solid var(--ink-100)",
            }}
          >
            <span style={{ fontWeight: 700, color: s.color, fontSize: 11.5 }}>{s.label}</span>
            <span style={{ fontSize: 10, color: "var(--ink-500)", marginTop: 1 }}>{s.n}</span>
          </span>
          {i < steps.length - 1 && <span style={{ color: "var(--ink-300)", fontSize: 14 }}>→</span>}
        </span>
      ))}
    </div>
  );
}

/* ============== Section 1: 物资申购单 ============== */

function RequisitionList({ requisitions }: { requisitions: PurchaseRequisition[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {requisitions.map((r) => (
        <RequisitionCard key={r.prNo} req={r} />
      ))}
    </div>
  );
}

const PR_STATUS_META: Record<PurchaseRequisition["status"], { bg: string; fg: string }> = {
  待审批: { bg: "var(--ai-100)", fg: "var(--ai-700)" },
  已审批: { bg: "var(--brand-100)", fg: "var(--brand-700)" },
  已转订单: { bg: "var(--ok-100)", fg: "var(--ok-700)" },
  已驳回: { bg: "var(--risk-100)", fg: "var(--risk-700)" },
};

function RequisitionCard({ req }: { req: PurchaseRequisition }) {
  const meta = PR_STATUS_META[req.status];
  const pending = req.status === "待审批";
  return (
    <div
      className="card"
      style={{
        padding: 16,
        borderLeft: `3px solid ${pending ? "var(--ai-500)" : "var(--jintai-green)"}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            color: "var(--ink-900)",
            fontFamily: "ui-monospace, monospace",
          }}
        >
          {req.prNo}
        </span>
        <span className="pill" style={{ background: meta.bg, color: meta.fg, fontWeight: 600 }}>
          {req.status}
        </span>
        <span style={{ fontSize: 11.5, color: "var(--ink-700)" }}>
          {req.dept} · {req.applicant} · {req.applyDate}
        </span>
        {req.poRef && (
          <span
            className="pill"
            style={{
              background: "var(--brand-100)",
              color: "var(--brand-700)",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            → 已转 {req.poRef}
          </span>
        )}
        <span style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--ink-500)" }}>
          {req.source}
        </span>
      </div>

      {req.sourceNote && (
        <div
          style={{
            fontSize: 11.5,
            color: "var(--ai-700)",
            lineHeight: 1.5,
            marginBottom: 10,
            padding: "6px 10px",
            background: "var(--ai-100)",
            borderRadius: 6,
            border: "1px dashed #bddff3",
          }}
        >
          <span style={{ fontWeight: 700, marginRight: 4 }}>来源：</span>
          {req.sourceNote}
        </div>
      )}

      {/* 申购明细 */}
      <div style={{ border: "1px solid var(--ink-100)", borderRadius: 8, overflow: "hidden" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.6fr 1.4fr 60px 90px 110px 1fr",
            columnGap: 10,
            background: "var(--surface-2)",
            fontSize: 10.5,
            fontWeight: 700,
            color: "var(--ink-600)",
            letterSpacing: "0.04em",
            padding: "6px 10px",
            borderBottom: "1px solid var(--ink-100)",
          }}
        >
          <span>物品名称</span>
          <span>规格型号</span>
          <span style={{ textAlign: "center" }}>单位</span>
          <span style={{ textAlign: "right" }}>申购数量</span>
          <span>到货日期</span>
          <span>备注</span>
        </div>
        {req.items.map((it, idx) => (
          <div
            key={idx}
            style={{
              display: "grid",
              gridTemplateColumns: "1.6fr 1.4fr 60px 90px 110px 1fr",
            columnGap: 10,
              padding: "8px 10px",
              borderTop: idx > 0 ? "1px solid var(--ink-50)" : "none",
              fontSize: 11.5,
              color: "var(--ink-800)",
            }}
          >
            <span style={{ fontWeight: 600 }}>{it.name}</span>
            <span style={{ fontFamily: "ui-monospace, monospace" }}>{it.spec}</span>
            <span style={{ textAlign: "center" }}>{it.unit}</span>
            <span
              style={{
                textAlign: "right",
                fontFamily: "ui-monospace, monospace",
                fontWeight: 700,
              }}
            >
              {it.qty}
            </span>
            <span style={{ fontFamily: "ui-monospace, monospace" }}>{it.arriveDate}</span>
            <span style={{ color: "var(--ink-500)" }}>{it.note ?? "—"}</span>
          </div>
        ))}
      </div>

      {/* 审批 / 操作区 */}
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          flexWrap: "wrap",
          marginTop: 10,
        }}
      >
        {req.approver && (
          <span
            style={{
              fontSize: 11,
              color: "var(--ok-700)",
              fontWeight: 600,
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: 4,
                background: "var(--jintai-green)",
              }}
            />
            ✓ {req.approver} · {req.approvedAt}
          </span>
        )}
        {pending && (
          <>
            <button
              className="pill"
              style={{
                background: "var(--brand-500)",
                color: "#fff",
                border: "none",
                padding: "6px 14px",
                fontSize: 11.5,
                fontWeight: 600,
                cursor: "pointer",
                borderRadius: 6,
              }}
            >
              批准 → 转采购订单
            </button>
            <button
              className="pill"
              style={{
                background: "var(--surface-2)",
                color: "var(--ink-700)",
                border: "1px solid var(--ink-200)",
                padding: "6px 14px",
                fontSize: 11.5,
                fontWeight: 500,
                cursor: "pointer",
                borderRadius: 6,
              }}
            >
              驳回
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ============== Section 5: 库存台账 ============== */

function StockLedgerTable({ ledger }: { ledger: StockLedger }) {
  const isRaw = ledger.kind === "原材料";
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* 表头 */}
      <div
        style={{
          padding: "10px 16px",
          background: isRaw ? "rgba(15,69,42,0.06)" : "rgba(173,30,38,0.06)",
          borderBottom: "1px solid var(--ink-100)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
          fontSize: 11.5,
        }}
      >
        <span
          style={{
            fontWeight: 700,
            color: isRaw ? "var(--jintai-green-dark)" : "var(--jintai-red)",
            fontSize: 13,
          }}
        >
          {ledger.kind}月报表
        </span>
        <span style={{ color: "var(--ink-500)" }}>
          {ledger.period} · {ledger.warehouse}
        </span>
        <span style={{ marginLeft: "auto", color: "var(--ink-500)" }}>
          仓管员：{ledger.keeper}
        </span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 11.5,
            fontFamily: "var(--font)",
          }}
        >
          <thead>
            <tr style={{ background: "var(--surface-2)" }}>
              <SLTh>序号</SLTh>
              <SLTh>物品名称</SLTh>
              <SLTh>规格型号</SLTh>
              {!isRaw && <SLTh>形状</SLTh>}
              <SLTh>单位</SLTh>
              <SLTh align="right">起始数</SLTh>
              <SLTh align="right">本月入库</SLTh>
              <SLTh align="right">本月出库</SLTh>
              <SLTh align="right">期末库存</SLTh>
              {isRaw && <SLTh align="right">安全库存</SLTh>}
              <SLTh>录入方式</SLTh>
              <SLTh>备注</SLTh>
            </tr>
          </thead>
          <tbody>
            {ledger.rows.map((r) => {
              const lowStock = r.warning === "low";
              return (
                <tr
                  key={r.no}
                  style={{
                    borderTop: "1px solid var(--ink-50)",
                    background: lowStock ? "var(--warn-100)" : undefined,
                  }}
                >
                  <SLTd center>{r.no}</SLTd>
                  <SLTd bold>{r.name}</SLTd>
                  <SLTd mono>{r.spec}</SLTd>
                  {!isRaw && <SLTd>{r.shape ?? "—"}</SLTd>}
                  <SLTd center>{r.unit}</SLTd>
                  <SLTd align="right" mono>
                    {r.opening}
                  </SLTd>
                  <SLTd align="right" mono pos>
                    +{r.inQty}
                  </SLTd>
                  <SLTd align="right" mono neg>
                    −{r.outQty}
                  </SLTd>
                  <SLTd
                    align="right"
                    mono
                    bold
                    style={lowStock ? { color: "var(--warn-700)" } : undefined}
                  >
                    {r.balance}
                  </SLTd>
                  {isRaw && (
                    <SLTd align="right" mono style={{ color: "var(--ink-500)" }}>
                      {r.safetyStock ?? "—"}
                    </SLTd>
                  )}
                  <SLTd>
                    <DataSourceTag source={r.recordedBy} />
                  </SLTd>
                  <SLTd>
                    {lowStock && (
                      <span
                        className="pill"
                        style={{
                          background: "var(--warn-100)",
                          color: "var(--warn-700)",
                          fontSize: 10.5,
                          fontWeight: 700,
                          marginRight: 6,
                        }}
                      >
                        ⚠ 低库存
                      </span>
                    )}
                    {r.note && <span style={{ color: "var(--ink-600)" }}>{r.note}</span>}
                  </SLTd>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SLTh({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right" | "center";
}) {
  return (
    <th
      style={{
        padding: "8px 10px",
        textAlign: align ?? "left",
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-500)",
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

function SLTd({
  children,
  align,
  mono,
  bold,
  center,
  pos,
  neg,
  style,
}: {
  children: React.ReactNode;
  align?: "right";
  mono?: boolean;
  bold?: boolean;
  center?: boolean;
  pos?: boolean;
  neg?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <td
      style={{
        padding: "8px 10px",
        textAlign: center ? "center" : align ?? "left",
        color: pos ? "var(--ok-700)" : neg ? "var(--risk-700)" : bold ? "var(--ink-900)" : "var(--ink-800)",
        fontFamily: mono ? "ui-monospace, monospace" : "var(--font)",
        fontWeight: bold ? 700 : 500,
        fontVariantNumeric: "tabular-nums",
        ...style,
      }}
    >
      {children}
    </td>
  );
}

/* ============== Section 6: 应付账款台账 ============== */

const AGING_META: Record<PayableRow["aging"], { bg: string; fg: string; icon: string }> = {
  已超期: { bg: "var(--risk-100)", fg: "var(--risk-700)", icon: "⚠" },
  即将到期: { bg: "var(--warn-100)", fg: "var(--warn-700)", icon: "⏰" },
  未到期: { bg: "var(--ok-100)", fg: "var(--ok-700)", icon: "✓" },
};

function PayableLedgerTable({ rows }: { rows: PayableRow[] }) {
  const total = rows.reduce((acc, r) => acc + parseInt(r.amount.replace(/[¥,]/g, ""), 10), 0);
  const overdue = rows.filter((r) => r.aging === "已超期");
  const soon = rows.filter((r) => r.aging === "即将到期");
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* AI 提醒条 */}
      <div
        style={{
          padding: "10px 16px",
          background: "var(--ai-100)",
          borderBottom: "1px solid #bddff3",
          fontSize: 11.5,
          color: "var(--ink-800)",
          lineHeight: 1.55,
          display: "flex",
          gap: 14,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <span style={{ fontWeight: 700, color: "var(--ai-700)", fontSize: 10.5, letterSpacing: "0.05em" }}>
          {I.spark(11)} AI 账期提醒
        </span>
        <span>
          本月应付合计 <strong>¥{total.toLocaleString()}</strong>　·
          <span style={{ color: "var(--risk-700)", fontWeight: 700 }}>
            已超期 {overdue.length} 笔
          </span>
          　·
          <span style={{ color: "var(--warn-700)", fontWeight: 700 }}>
            30 天内到期 {soon.length} 笔
          </span>
        </span>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 11.5,
            fontFamily: "var(--font)",
          }}
        >
          <thead>
            <tr style={{ background: "var(--surface-2)" }}>
              <SLTh>供应商</SLTh>
              <SLTh>来源单据</SLTh>
              <SLTh align="right">应付金额</SLTh>
              <SLTh>到期日</SLTh>
              <SLTh align="right">距到期</SLTh>
              <SLTh>账龄</SLTh>
              <SLTh>录入方式</SLTh>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const aging = AGING_META[r.aging];
              return (
                <tr key={r.supplier + r.invoiceDate} style={{ borderTop: "1px solid var(--ink-50)" }}>
                  <SLTd bold>{r.supplier}</SLTd>
                  <SLTd>{r.source}</SLTd>
                  <SLTd align="right" mono bold>
                    {r.amount}
                  </SLTd>
                  <SLTd mono>{r.dueDate}</SLTd>
                  <SLTd
                    align="right"
                    mono
                    style={{
                      color:
                        r.daysToDue < 0
                          ? "var(--risk-700)"
                          : r.daysToDue < 30
                          ? "var(--warn-700)"
                          : "var(--ink-700)",
                      fontWeight: 700,
                    }}
                  >
                    {r.daysToDue < 0 ? `超 ${-r.daysToDue} 天` : `${r.daysToDue} 天`}
                  </SLTd>
                  <SLTd>
                    <span
                      className="pill"
                      style={{
                        background: aging.bg,
                        color: aging.fg,
                        fontSize: 10.5,
                        fontWeight: 700,
                      }}
                    >
                      {aging.icon} {r.aging}
                    </span>
                  </SLTd>
                  <SLTd>
                    <DataSourceTag source={r.dataSource} />
                  </SLTd>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SectionHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink-900)" }}>{title}</div>
      <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 3, lineHeight: 1.55 }}>
        {sub}
      </div>
    </div>
  );
}

/* ---------------- Section 1: 采购订单表 ---------------- */

function PurchaseOrderTable({ orders }: { orders: PurchaseOrder[] }) {
  const isDesktop = useIsDesktop();
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* AI 草稿提示条 */}
      <div
        style={{
          padding: "10px 16px",
          background: "var(--ai-100)",
          borderBottom: "1px solid #bddff3",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          fontSize: 11.5,
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontWeight: 700,
            color: "var(--ai-700)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            fontSize: 10.5,
          }}
        >
          {I.spark(11)} AI 草稿
        </span>
        <span style={{ color: "var(--ink-700)" }}>
          智通 AI 已从 6 封邮件合同 / 3 张纸质订单中自动抽取建单
        </span>
        <span
          style={{
            color: "var(--ok-700)",
            fontWeight: 600,
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
          }}
        >
          {/* iter 14：锦泰绿确认 dot */}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 4,
              background: "var(--jintai-green)",
              flexShrink: 0,
            }}
          />
          ✓ 采购 · 张主管 · 2026-05-17 09:42 复核确认
        </span>
      </div>

      {isDesktop ? (
        <DesktopTable orders={orders} />
      ) : (
        <MobileList orders={orders} />
      )}
    </div>
  );
}

function DesktopTable({ orders }: { orders: PurchaseOrder[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          fontFamily: "var(--font)",
        }}
      >
        <thead>
          <tr style={{ background: "var(--surface-2)" }}>
            <Th>订单号</Th>
            <Th>供应商</Th>
            <Th>物料</Th>
            <Th>规格</Th>
            <Th align="right">数量</Th>
            <Th align="right">金额</Th>
            <Th>交货</Th>
            <Th>状态</Th>
            <Th>录入方式</Th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.poNo} style={{ borderTop: "1px solid var(--ink-100)" }}>
              <Td mono>
                {o.poNo}
                {o.fromPrNo && (
                  <div style={{ fontSize: 10, color: "var(--ink-500)", marginTop: 2 }}>
                    ← {o.fromPrNo}
                  </div>
                )}
              </Td>
              <Td>{o.supplier}</Td>
              <Td bold>{o.material}</Td>
              <Td mono>{o.spec}</Td>
              <Td align="right" mono>{o.qty}</Td>
              <Td align="right" mono bold>{o.amount}</Td>
              <Td mono>{o.deliveryDate}</Td>
              <Td>
                <JintaiStatusBadge status={o.status} />
              </Td>
              <Td>
                <DataSourceTag source={o.dataSource} />
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MobileList({ orders }: { orders: PurchaseOrder[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {orders.map((o) => (
        <div
          key={o.poNo}
          style={{
            padding: 14,
            borderTop: "1px solid var(--ink-100)",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink-900)" }}>
              {o.material}
            </span>
            <JintaiStatusBadge status={o.status} />
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
            <span style={{ fontFamily: "ui-monospace, monospace" }}>{o.poNo}</span> · {o.supplier}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--ink-700)", marginTop: 2 }}>
            {o.qty} · {o.unitPrice} · <strong>{o.amount}</strong> · 交 {o.deliveryDate}
          </div>
          <div style={{ marginTop: 4 }}>
            <DataSourceTag source={o.dataSource} />
          </div>
        </div>
      ))}
    </div>
  );
}

function Th({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "right";
}) {
  return (
    <th
      style={{
        padding: "10px 14px",
        textAlign: align ?? "left",
        fontSize: 10.5,
        fontWeight: 700,
        color: "var(--ink-500)",
        letterSpacing: "0.04em",
        textTransform: "uppercase",
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  align,
  mono,
  bold,
}: {
  children: React.ReactNode;
  align?: "right";
  mono?: boolean;
  bold?: boolean;
}) {
  return (
    <td
      style={{
        padding: "10px 14px",
        textAlign: align ?? "left",
        color: bold ? "var(--ink-900)" : "var(--ink-800)",
        fontFamily: mono ? "ui-monospace, monospace" : "var(--font)",
        fontWeight: bold ? 700 : 500,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {children}
    </td>
  );
}

/* ---------------- Section 2: 供应商卡片 ---------------- */

function SupplierCard({ supplier }: { supplier: Supplier }) {
  return (
    <div className="card-flat" style={{ padding: 14, borderRadius: 12 }}>
      <div
        style={{
          fontSize: 13.5,
          fontWeight: 700,
          color: "var(--ink-900)",
          marginBottom: 3,
        }}
      >
        {supplier.shortName}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-500)", marginBottom: 10 }}>
        {supplier.fullName}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 4,
          fontSize: 12,
          color: "var(--ink-700)",
        }}
      >
        <Row k="主要品类" v={supplier.category} />
        <Row k="月均采购" v={supplier.monthlySpend} bold />
        <Row k="账期" v={supplier.paymentTerm} />
      </div>
      <div
        style={{
          marginTop: 10,
          paddingTop: 10,
          borderTop: "1px dashed var(--ink-100)",
          fontSize: 11,
          color: "var(--ai-700)",
          lineHeight: 1.55,
        }}
      >
        <span style={{ fontWeight: 700, marginRight: 4 }}>AI 备注：</span>
        {supplier.trustNote}
      </div>
    </div>
  );
}

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
      <span style={{ color: "var(--ink-500)" }}>{k}</span>
      <span
        style={{
          color: "var(--ink-900)",
          fontWeight: bold ? 700 : 500,
          textAlign: "right",
        }}
      >
        {v}
      </span>
    </div>
  );
}

/* ---------------- Section 3: AI 采购收件箱卡片 ---------------- */

const KIND_META: Record<
  PurchaseInboxCard["kind"],
  { bg: string; fg: string; icon: string }
> = {
  采购发票: { bg: "var(--ai-100)", fg: "var(--ai-700)", icon: "🧾" },
  采购合同: { bg: "var(--brand-100)", fg: "var(--brand-700)", icon: "📄" },
  字段缺失: { bg: "var(--warn-100)", fg: "var(--warn-700)", icon: "⚠️" },
};

function PurchaseInboxCardView({ card }: { card: PurchaseInboxCard }) {
  const meta = KIND_META[card.kind];
  const isMissing = card.kind === "字段缺失";
  return (
    <div
      className="card"
      style={{
        padding: 16,
        borderLeft: `3px solid ${isMissing ? "var(--warn-500)" : "var(--ai-500)"}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <span
          className="pill"
          style={{
            background: meta.bg,
            color: meta.fg,
            fontSize: 11,
            fontWeight: 600,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span>{meta.icon}</span> {card.kind}
        </span>
        <span style={{ fontSize: 11.5, color: "var(--ink-800)", fontWeight: 600 }}>
          {card.source}
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-400)", marginLeft: "auto" }}>
          {card.uploadedAt}
        </span>
      </div>

      <div
        style={{
          fontSize: 12.5,
          color: "var(--ink-700)",
          lineHeight: 1.55,
          marginBottom: 12,
        }}
      >
        {card.aiSummary}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 6,
          marginBottom: 12,
        }}
      >
        {card.fields.map((f) => {
          const missing = f.value.includes("未识别");
          return (
            <div
              key={f.key}
              style={{
                padding: "8px 10px",
                borderRadius: 8,
                background: missing ? "var(--warn-100)" : "var(--surface-2)",
                border: missing ? "1px solid #f1d4a6" : "1px solid var(--ink-100)",
                fontSize: 11.5,
                lineHeight: 1.4,
              }}
            >
              <div style={{ fontSize: 10.5, color: "var(--ink-500)", fontWeight: 600 }}>
                {f.key}
              </div>
              <div
                style={{
                  color: missing ? "var(--warn-700)" : "var(--ink-900)",
                  fontWeight: 600,
                  marginTop: 2,
                  fontFamily:
                    /\d/.test(f.value) && !f.key.includes("货物") && !f.key.includes("供应商")
                      ? "ui-monospace, monospace"
                      : undefined,
                }}
              >
                {f.value}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          padding: "10px 12px",
          borderRadius: 8,
          background: isMissing ? "var(--warn-100)" : "var(--ai-100)",
          border: isMissing ? "1px solid #f1d4a6" : "1px solid #bddff3",
          fontSize: 12,
          color: isMissing ? "var(--warn-700)" : "var(--ai-700)",
          lineHeight: 1.55,
          marginBottom: 10,
        }}
      >
        <span style={{ fontWeight: 700 }}>建议动作：</span>
        {card.suggestedAction.replace(/^建议[：:]\s?/, "")}
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <button
          className="pill"
          style={{
            background: "var(--brand-500)",
            color: "#fff",
            border: "none",
            padding: "6px 14px",
            fontSize: 11.5,
            fontWeight: 600,
            cursor: "pointer",
            borderRadius: 6,
          }}
        >
          {isMissing ? "补充字段" : "确认入账"}
        </button>
        <button
          className="pill"
          style={{
            background: "var(--surface-2)",
            color: "var(--ink-700)",
            border: "1px solid var(--ink-200)",
            padding: "6px 14px",
            fontSize: 11.5,
            fontWeight: 500,
            cursor: "pointer",
            borderRadius: 6,
          }}
        >
          驳回
        </button>
        <JintaiSourceCitation source={{ kind: "合同", label: card.source }} />
      </div>
    </div>
  );
}
