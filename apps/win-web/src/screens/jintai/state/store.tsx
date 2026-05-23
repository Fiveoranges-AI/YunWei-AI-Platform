/**
 * iter 22: 锦泰 demo 共享 store
 *
 * 设计原则:
 *  - 所有跨模块联动的 mock data 从 const 升级成 state,由 reducer 推进。
 *  - 主线 5 步剧本: 车间领料 → 仓管确认扣库存 → 触发预警+申购草稿
 *                   → 张主管批准转 PO → 模拟入库回补 + 应付新增。
 *  - 每步反馈 = toast (右上角 3s) + flash 高亮 (改变的行 2s 飘黄)。
 *  - 无新依赖: React Context + useReducer + setTimeout。
 *
 * 不动:三表数字 (财务核心展示) / 工艺单 / 概览 trustItems 等纯展示数据。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";
import {
  initialExtractionCards,
  payableLedger as seedPayable,
  purchaseOrders as seedPOs,
  purchaseRequisitions as seedPRs,
  stockLedgers as seedStock,
} from "../data";
import type {
  ExtractionCard,
  PayableRow,
  PurchaseOrder,
  PurchaseRequisition,
  StockLedger,
} from "../data";

/* ---------- Toast ---------- */
export type Toast = {
  id: string;
  level: "info" | "success" | "warn" | "risk";
  title: string;
  body?: string;
};

/* ---------- Flash 高亮 (按 entity key 记录最近改动时间) ---------- */
export type FlashMap = Record<string, number>; // key -> timestamp (ms)
const FLASH_DURATION = 2200;

/* ---------- 主线步骤进度 ---------- */
export type DemoStep =
  | "idle"
  | "shipment-pending" // 1. 领料单待确认 (inbox 有草稿)
  | "stock-low" // 2. 库存已扣 + 预警
  | "pr-pending" // 3. 申购草稿待审批
  | "po-pending" // 4. PO 已转 待入库
  | "complete"; // 5. 入库回补完成

/* ---------- 主线锁定的数据 (硬编码故事) ---------- */
const PIVOT_MATERIAL = "α 氧化铝粉"; // 主线材料 (主库存里 healthy → 扣减后跌破 safety)
const ISSUE_QTY = 800; // 领料数量 (kg)
const PR_REORDER_QTY = 4000; // 申购数量 (kg)
const PR_UNIT_PRICE = 24.0; // ¥/kg (山东中铝)
const PR_AMOUNT = PR_REORDER_QTY * PR_UNIT_PRICE; // 96,000
const NEW_PR_NO = "PR-2026-017";
const NEW_PO_NO = "PO-2026-009";
const NEW_INBOX_ID = "demo-line-issue-001";

/* ---------- State ---------- */
export type JintaiState = {
  stockLedgers: StockLedger[];
  purchaseOrders: PurchaseOrder[];
  purchaseRequisitions: PurchaseRequisition[];
  payableLedger: PayableRow[];
  inboxCards: ExtractionCard[];
  toasts: Toast[];
  flash: FlashMap;
  step: DemoStep;
};

const initialState: JintaiState = {
  stockLedgers: seedStock,
  purchaseOrders: seedPOs,
  purchaseRequisitions: seedPRs,
  payableLedger: seedPayable,
  inboxCards: initialExtractionCards,
  toasts: [],
  flash: {},
  step: "idle",
};

/* ---------- Actions ---------- */
type Action =
  | { type: "SIMULATE_RAW_ISSUE" }
  | { type: "CONFIRM_INBOX"; cardId: string }
  | { type: "REJECT_INBOX"; cardId: string }
  | { type: "APPROVE_PR"; prNo: string }
  | { type: "REJECT_PR"; prNo: string }
  | { type: "RECEIVE_PO"; poNo: string }
  | { type: "DISMISS_TOAST"; id: string }
  | { type: "CLEAR_FLASH"; key: string }
  | { type: "RESET" };

/* ---------- helpers ---------- */
function withToast(state: JintaiState, t: Omit<Toast, "id">): JintaiState {
  const id = `t-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  return { ...state, toasts: [...state.toasts, { id, ...t }] };
}

function flashKeys(state: JintaiState, keys: string[]): JintaiState {
  const now = Date.now();
  const next = { ...state.flash };
  keys.forEach((k) => (next[k] = now));
  return { ...state, flash: next };
}

function mutateStockRow(
  ledgers: StockLedger[],
  materialName: string,
  delta: number, // kg 加减 (出库为负, 入库为正)
): { ledgers: StockLedger[]; newBalance: number; safetyStock: number } {
  let newBalance = 0;
  let safetyStock = 0;
  const next = ledgers.map((l) => {
    if (l.kind !== "原材料") return l;
    return {
      ...l,
      rows: l.rows.map((r) => {
        if (r.name !== materialName) return r;
        const oldBal = parseInt(r.balance.replace(/,/g, ""), 10) || 0;
        const oldOut = parseInt((r.outQty || "0").replace(/,/g, ""), 10) || 0;
        const oldIn = parseInt((r.inQty || "0").replace(/,/g, ""), 10) || 0;
        const next = oldBal + delta;
        newBalance = next;
        safetyStock = parseInt((r.safetyStock || "0").replace(/,/g, ""), 10) || 0;
        const lowAfter = safetyStock > 0 && next < safetyStock;
        const updated: typeof r = {
          ...r,
          outQty: delta < 0 ? (oldOut + -delta).toLocaleString() : r.outQty,
          inQty: delta > 0 ? (oldIn + delta).toLocaleString() : r.inQty,
          balance: next.toLocaleString(),
          warning: lowAfter ? "low" : "ok",
        };
        return updated;
      }),
    };
  });
  return { ledgers: next, newBalance, safetyStock };
}

/* ---------- Reducer ---------- */
function reducer(state: JintaiState, action: Action): JintaiState {
  switch (action.type) {
    /* ---- Step 1: 领料单上传 (AI 收件箱新增草稿) ---- */
    case "SIMULATE_RAW_ISSUE": {
      const exists = state.inboxCards.some((c) => c.id === NEW_INBOX_ID);
      if (exists) {
        return withToast(state, {
          level: "info",
          title: "领料单已在收件箱",
          body: "请先在收件箱确认或驳回。",
        });
      }
      const newCard: ExtractionCard = {
        id: NEW_INBOX_ID,
        kind: "出货单", // 复用现有 kind (作为"领料单",视觉一致)
        source: "成型车间_领料单_BL-2026-018_张师傅手写.jpg",
        uploadedAt: `刚刚 · ${new Date().toLocaleTimeString("zh-CN", {
          hour: "2-digit",
          minute: "2-digit",
        })}`,
        status: "待确认",
        confidence: 0.91,
        fields: [
          { key: "单据类型", value: "车间领料单", confidence: 0.96 },
          { key: "申请车间", value: "成型车间", confidence: 0.97 },
          { key: "领用人", value: "张师傅", confidence: 0.93 },
          { key: "物料", value: PIVOT_MATERIAL, confidence: 0.95 },
          { key: "数量", value: `${ISSUE_QTY.toLocaleString()} kg`, confidence: 0.94 },
          { key: "用途", value: "BL-2026-018 容百二供 NCM 高镍配料", confidence: 0.87 },
          { key: "日期", value: "今天", confidence: 0.92 },
        ],
        toBeGenerated: `库存出库 ${ISSUE_QTY.toLocaleString()} kg · 触发库存联动`,
      };
      const next = { ...state, inboxCards: [newCard, ...state.inboxCards], step: "shipment-pending" as DemoStep };
      return withToast(flashKeys(next, [`inbox:${NEW_INBOX_ID}`]), {
        level: "info",
        title: "AI 收到 1 张车间领料单",
        body: `张师傅领 ${PIVOT_MATERIAL} ${ISSUE_QTY} kg · 请王仓管确认`,
      });
    }

    /* ---- Step 2: 仓管确认 → 库存扣减 → 跌破安全线 → 自动生成申购草稿 ---- */
    case "CONFIRM_INBOX": {
      const card = state.inboxCards.find((c) => c.id === action.cardId);
      if (!card) return state;
      // 标记为已确认 (但保留在列表 + 状态改变)
      const updatedCards = state.inboxCards.map((c) =>
        c.id === action.cardId ? { ...c, status: "已确认" as const } : c,
      );

      let next: JintaiState = { ...state, inboxCards: updatedCards };

      // 如果是主线领料单 → 触发扣库存 + 申购草稿
      if (action.cardId === NEW_INBOX_ID) {
        const { ledgers, newBalance, safetyStock } = mutateStockRow(
          state.stockLedgers,
          PIVOT_MATERIAL,
          -ISSUE_QTY,
        );
        next = { ...next, stockLedgers: ledgers };

        const lowAfter = newBalance < safetyStock;
        next = flashKeys(next, [`stock:${PIVOT_MATERIAL}`]);
        next = withToast(next, {
          level: "success",
          title: `✓ 库存已扣减 ${ISSUE_QTY} kg`,
          body: `${PIVOT_MATERIAL} 余量 ${newBalance.toLocaleString()} kg${
            lowAfter ? ` · ⚠ 跌破安全线 ${safetyStock.toLocaleString()}` : ""
          }`,
        });

        if (lowAfter) {
          // 自动生成申购草稿
          const exists = state.purchaseRequisitions.some((pr) => pr.prNo === NEW_PR_NO);
          if (!exists) {
            const newPR: PurchaseRequisition = {
              prNo: NEW_PR_NO,
              dept: "成型车间",
              applicant: "成型组 · 张师傅",
              applyDate: "今天",
              supplier: "山东中铝物资",
              status: "待审批",
              source: "AI 抽取",
              sourceNote: `AI 检测到 ${PIVOT_MATERIAL} 跌破安全线 → 自动按近 3 月平均用量生成申购草稿`,
              items: [
                {
                  name: PIVOT_MATERIAL,
                  spec: "CT3000SG · 5N 级",
                  unit: "kg",
                  qty: PR_REORDER_QTY.toLocaleString(),
                  arriveDate: "2026-06-05",
                  note: "锁定 山东中铝 · 单价 ¥24.00 · 总价 ¥96,000",
                },
              ],
            };
            next = {
              ...next,
              purchaseRequisitions: [newPR, ...state.purchaseRequisitions],
              step: "pr-pending" as DemoStep,
            };
            next = flashKeys(next, [`pr:${NEW_PR_NO}`]);
            next = withToast(next, {
              level: "risk",
              title: `⚠ AI 自动生成申购草稿 ${NEW_PR_NO}`,
              body: `山东中铝 / ${PIVOT_MATERIAL} ${PR_REORDER_QTY.toLocaleString()} kg / ¥${PR_AMOUNT.toLocaleString()} · 张主管待审批`,
            });
          } else {
            next = { ...next, step: "stock-low" as DemoStep };
          }
        }
      } else {
        next = withToast(next, {
          level: "success",
          title: "✓ 已确认入账",
          body: card.toBeGenerated,
        });
      }
      return next;
    }

    case "REJECT_INBOX": {
      const card = state.inboxCards.find((c) => c.id === action.cardId);
      if (!card) return state;
      const updated = state.inboxCards.map((c) =>
        c.id === action.cardId ? { ...c, status: "已驳回" as const } : c,
      );
      return withToast(
        { ...state, inboxCards: updated },
        { level: "warn", title: "已驳回", body: card.source },
      );
    }

    /* ---- Step 3: 申购批准 → 自动转 PO ---- */
    case "APPROVE_PR": {
      const pr = state.purchaseRequisitions.find((p) => p.prNo === action.prNo);
      if (!pr || pr.status !== "待审批") return state;
      const stamp = new Date().toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
      const newPONo = action.prNo === NEW_PR_NO ? NEW_PO_NO : `PO-${pr.prNo.replace("PR-", "")}`;
      const updatedPRs = state.purchaseRequisitions.map((p) =>
        p.prNo === action.prNo
          ? {
              ...p,
              status: "已转订单" as const,
              approver: "采购 · 张主管",
              approvedAt: stamp,
              poRef: newPONo,
            }
          : p,
      );

      // 自动生成对应 PO (在 list 顶部)
      const newPO: PurchaseOrder = {
        poNo: newPONo,
        supplier: pr.supplier ?? pr.items[0]?.note?.match(/锁定 (\S+)/)?.[1] ?? "—",
        material: pr.items[0]?.name ?? "—",
        spec: pr.items[0]?.spec ?? "—",
        qty: `${pr.items[0]?.qty ?? ""} ${pr.items[0]?.unit ?? ""}`.trim(),
        unitPrice: `¥${PR_UNIT_PRICE.toFixed(2)} / kg`,
        amount: `¥${PR_AMOUNT.toLocaleString()}`,
        deliveryDate: pr.items[0]?.arriveDate ?? "—",
        status: "在途",
        dataSource: "AI · 微信群",
        fromPrNo: pr.prNo,
      };
      let next: JintaiState = {
        ...state,
        purchaseRequisitions: updatedPRs,
        purchaseOrders: [newPO, ...state.purchaseOrders],
        step: action.prNo === NEW_PR_NO ? ("po-pending" as DemoStep) : state.step,
      };
      next = flashKeys(next, [`pr:${action.prNo}`, `po:${newPONo}`]);
      return withToast(next, {
        level: "success",
        title: `✓ 申购 ${action.prNo} 已批准 → 转单 ${newPONo}`,
        body: `${newPO.supplier} · ${newPO.material} · ${newPO.amount}`,
      });
    }

    case "REJECT_PR": {
      const pr = state.purchaseRequisitions.find((p) => p.prNo === action.prNo);
      if (!pr || pr.status !== "待审批") return state;
      const updated = state.purchaseRequisitions.map((p) =>
        p.prNo === action.prNo ? { ...p, status: "已驳回" as const } : p,
      );
      return withToast(
        { ...state, purchaseRequisitions: updated },
        { level: "warn", title: `${action.prNo} 已驳回` },
      );
    }

    /* ---- Step 4: 模拟到货入库 → 库存回补 + 应付新增 ---- */
    case "RECEIVE_PO": {
      const po = state.purchaseOrders.find((p) => p.poNo === action.poNo);
      if (!po || po.status === "已入库") return state;
      const qty = parseInt(po.qty.replace(/[^\d]/g, ""), 10) || 0;
      const { ledgers, newBalance } = mutateStockRow(state.stockLedgers, po.material, qty);
      const updatedPOs = state.purchaseOrders.map((p) =>
        p.poNo === action.poNo ? { ...p, status: "已入库" as const, warehouse: "原料库 A-02" } : p,
      );
      // 应付新增一笔
      const exists = state.payableLedger.some((pp) => pp.source.includes(action.poNo));
      let nextPayable = state.payableLedger;
      if (!exists) {
        const newPayable: PayableRow = {
          supplier: po.supplier,
          source: `${action.poNo} 入库单 + 发票`,
          amount: po.amount,
          invoiceDate: new Date().toISOString().slice(0, 10),
          dueDate: "2026-07-24",
          aging: "未到期",
          daysToDue: 60,
          dataSource: "AI · 发票 OCR",
        };
        nextPayable = [newPayable, ...state.payableLedger];
      }
      let next: JintaiState = {
        ...state,
        stockLedgers: ledgers,
        purchaseOrders: updatedPOs,
        payableLedger: nextPayable,
        step: action.poNo === NEW_PO_NO ? ("complete" as DemoStep) : state.step,
      };
      next = flashKeys(next, [`po:${action.poNo}`, `stock:${po.material}`, `payable:${action.poNo}`]);
      return withToast(next, {
        level: "success",
        title: `✓ ${action.poNo} 入库 ${qty.toLocaleString()} kg`,
        body: `${po.material} 余量回到 ${newBalance.toLocaleString()} kg · 应付新增 ${po.amount} 待付`,
      });
    }

    case "DISMISS_TOAST":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };

    case "CLEAR_FLASH": {
      const next = { ...state.flash };
      delete next[action.key];
      return { ...state, flash: next };
    }

    case "RESET":
      return { ...initialState, toasts: [{ id: "reset", level: "info", title: "已重置到 demo 初始状态" }] };

    default:
      return state;
  }
}

/* ---------- Context ---------- */
type Ctx = {
  state: JintaiState;
  dispatch: React.Dispatch<Action>;
  /** 一键演示主线 — 1.5s 间隔顺序触发 5 步 */
  playAll: () => void;
  /** 高亮判断 */
  isFlashing: (key: string) => boolean;
  /** Demo 锁定常量, 给按钮显示用 */
  consts: {
    pivotMaterial: string;
    issueQty: number;
    newPrNo: string;
    newPoNo: string;
    newInboxId: string;
    prAmount: number;
    prReorderQty: number;
  };
};

const JintaiContext = createContext<Ctx | null>(null);

export function JintaiProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const playingRef = useRef(false);

  // 自动 dismiss toast (3s)
  useEffect(() => {
    if (state.toasts.length === 0) return;
    const id = state.toasts[state.toasts.length - 1].id;
    const t = window.setTimeout(() => dispatch({ type: "DISMISS_TOAST", id }), 3200);
    return () => window.clearTimeout(t);
  }, [state.toasts]);

  // 自动 clear flash (2.2s 后) — 简单方案: 触发 rerender 时检查每个 key
  useEffect(() => {
    const keys = Object.keys(state.flash);
    if (keys.length === 0) return;
    const now = Date.now();
    const timers = keys.map((k) => {
      const ts = state.flash[k];
      const remain = Math.max(0, FLASH_DURATION - (now - ts));
      return window.setTimeout(() => dispatch({ type: "CLEAR_FLASH", key: k }), remain + 100);
    });
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [state.flash]);

  const isFlashing = useCallback(
    (key: string) => {
      const ts = state.flash[key];
      return ts !== undefined && Date.now() - ts < FLASH_DURATION;
    },
    [state.flash],
  );

  const playAll = useCallback(() => {
    if (playingRef.current) return;
    playingRef.current = true;
    dispatch({ type: "RESET" });
    const steps: Array<() => void> = [
      () => dispatch({ type: "SIMULATE_RAW_ISSUE" }),
      () => dispatch({ type: "CONFIRM_INBOX", cardId: NEW_INBOX_ID }),
      () => dispatch({ type: "APPROVE_PR", prNo: NEW_PR_NO }),
      () => dispatch({ type: "RECEIVE_PO", poNo: NEW_PO_NO }),
    ];
    steps.forEach((s, i) => window.setTimeout(s, 600 + i * 1800));
    window.setTimeout(() => (playingRef.current = false), 600 + steps.length * 1800);
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      state,
      dispatch,
      playAll,
      isFlashing,
      consts: {
        pivotMaterial: PIVOT_MATERIAL,
        issueQty: ISSUE_QTY,
        newPrNo: NEW_PR_NO,
        newPoNo: NEW_PO_NO,
        newInboxId: NEW_INBOX_ID,
        prAmount: PR_AMOUNT,
        prReorderQty: PR_REORDER_QTY,
      },
    }),
    [state, playAll, isFlashing],
  );

  return (
    <JintaiContext.Provider value={value}>
      {children}
      <ToastStack toasts={state.toasts} onDismiss={(id) => dispatch({ type: "DISMISS_TOAST", id })} />
    </JintaiContext.Provider>
  );
}

export function useJintai(): Ctx {
  const c = useContext(JintaiContext);
  if (!c) throw new Error("useJintai must be used inside <JintaiProvider>");
  return c;
}

/* ---------- Toast 浮动栈 (右上角) ---------- */
const TOAST_COLORS: Record<Toast["level"], { bg: string; fg: string; border: string }> = {
  info: { bg: "var(--brand-100)", fg: "var(--brand-700)", border: "#bddff3" },
  success: { bg: "var(--ok-100)", fg: "var(--ok-700)", border: "#c7e4d2" },
  warn: { bg: "var(--warn-100)", fg: "var(--warn-700)", border: "#f1d4a6" },
  risk: { bg: "var(--risk-100)", fg: "var(--risk-700)", border: "#f2c7c4" },
};

function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        pointerEvents: "none",
        maxWidth: 380,
      }}
    >
      {toasts.slice(-4).map((t) => {
        const c = TOAST_COLORS[t.level];
        return (
          <div
            key={t.id}
            onClick={() => onDismiss(t.id)}
            style={{
              pointerEvents: "auto",
              padding: "10px 14px",
              borderRadius: 10,
              background: c.bg,
              border: `1px solid ${c.border}`,
              borderLeft: `3px solid ${c.fg}`,
              boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
              cursor: "pointer",
              animation: "jintai-toast-in 0.3s ease",
            }}
          >
            <div style={{ fontSize: 12.5, fontWeight: 700, color: c.fg, lineHeight: 1.45 }}>
              {t.title}
            </div>
            {t.body && (
              <div style={{ fontSize: 11, color: "var(--ink-700)", marginTop: 3, lineHeight: 1.5 }}>
                {t.body}
              </div>
            )}
          </div>
        );
      })}
      <style>{`@keyframes jintai-toast-in { from { transform: translateX(20px); opacity: 0 } to { transform: none; opacity: 1 } }`}</style>
    </div>
  );
}

/* ---------- 共享 flash 样式 ---------- */
export function flashStyle(active: boolean): React.CSSProperties {
  if (!active) return {};
  return {
    boxShadow: "0 0 0 2px var(--warn-500), 0 0 12px rgba(245,158,11,0.45)",
    transition: "box-shadow 0.3s ease",
  };
}
