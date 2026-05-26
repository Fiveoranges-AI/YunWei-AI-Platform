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
import {
  createIssueVoucher,
  ensureDemoSeed,
  getBriefingKpi,
  getHealth,
  JintaiBackendError,
  postApprovePr,
  postIssueAndConfirm,
  postReceivePo,
  type BriefingKpiOut,
  type HealthOut,
} from "../../../api/jintai-backend";

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

/* ---------- 引导式 Tour 状态 (iter 23) ---------- */
export type ProductionSubtab = "A" | "D" | "B" | "C";
/** tourStep: 0 = 未启动 / 1-N = 步骤中 / N+1 = 总结 */

/* ---------- Round 4: backend-mode 状态 ---------- */
export type BackendMode = "mock" | "backend";

/** 后端落库的真实 ID,backend mode 用 (mock 模式忽略). */
export type BackendIds = {
  supplierId?: string;
  materialId?: string;
  voucherId?: string;
  prId?: string;
  poId?: string;
};

export type BackendStatus = {
  health?: HealthOut;
  lastError?: string;
  seeding?: boolean;
  lastSyncedAt?: number;
};

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
  /** iter 23: 引导式演示 */
  tourStep: number;
  tourPlaying: boolean;
  /** iter 23: 受 tour 控制的子 tab (生产 D/A/B/C) */
  productionSubtab: ProductionSubtab;
  /** iter 23: tour 滚动锚点 (panel 监听后 scrollIntoView) */
  scrollAnchor: string | null;
  /** round 4: 当前 demo 模式 */
  mode: BackendMode;
  /** round 4: 后端落库的真实 ID,用于串起 4 个 mutation API 调用 */
  backendIds: BackendIds;
  /** round 4: 来自 GET /briefing/kpi 的最新快照 (持久化证明) */
  backendKpi: BriefingKpiOut | null;
  /** round 4: 后端连通性 + 最近错误 */
  backendStatus: BackendStatus;
};

const _readInitialMode = (): BackendMode => {
  if (typeof window === "undefined") return "mock";
  const qp = new URLSearchParams(window.location.search);
  const q = qp.get("mode");
  if (q === "backend") return "backend";
  if (q === "mock") return "mock";
  try {
    const ls = window.localStorage.getItem("jintai.mode");
    if (ls === "backend") return "backend";
  } catch { /* ignore */ }
  return "mock";
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
  tourStep: 0,
  tourPlaying: false,
  productionSubtab: "A",
  scrollAnchor: null,
  mode: _readInitialMode(),
  backendIds: {},
  backendKpi: null,
  backendStatus: {},
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
  | { type: "FLASH_KEYS"; keys: string[] }
  | { type: "SET_PRODUCTION_SUBTAB"; subtab: ProductionSubtab }
  | { type: "SET_SCROLL_ANCHOR"; anchor: string | null }
  | { type: "TOUR_START" }
  | { type: "TOUR_SET_STEP"; step: number }
  | { type: "TOUR_PAUSE" }
  | { type: "TOUR_RESUME" }
  | { type: "TOUR_EXIT" }
  | { type: "RESET" }
  /* round 4: backend-mode 状态机 */
  | { type: "SET_MODE"; mode: BackendMode }
  | { type: "SET_BACKEND_IDS"; ids: Partial<BackendIds> }
  | { type: "SET_BACKEND_KPI"; kpi: BriefingKpiOut | null }
  | { type: "SET_BACKEND_STATUS"; status: Partial<BackendStatus> };

/* ---------- 引导式 Tour 剧本 (10 步 + 总结) ---------- */

export type TourStep = {
  id: number;
  tab: "briefing" | "inbox" | "purchase" | "production" | "finance" | "ask" | "trust";
  subtab?: ProductionSubtab;
  scrollAnchor?: string;
  title: string;
  narration: string;
  badge?: string;
  /** 进入此步触发的 action (副作用动作: 模拟领料 / 确认 / 批准 / 入库) */
  action?: Exclude<Action, { type: "DISMISS_TOAST" } | { type: "CLEAR_FLASH" } | { type: "FLASH_KEYS" } | { type: "SET_PRODUCTION_SUBTAB" } | { type: "SET_SCROLL_ANCHOR" } | { type: "TOUR_START" } | { type: "TOUR_SET_STEP" } | { type: "TOUR_PAUSE" } | { type: "TOUR_RESUME" } | { type: "TOUR_EXIT" } | { type: "RESET" }>;
  /** 重新激活的 flash 高亮 key (让 4s 之后切回来还能看到飘黄) */
  flashKeys?: string[];
  /** 本步停留时长 (ms) */
  durationMs: number;
};

export const TOUR_STEPS: TourStep[] = [
  {
    id: 1,
    tab: "briefing",
    title: "陈总打开经营日报",
    narration:
      "早上 7:55 · AI 7 大 KPI 已就绪。今日要事 6 条跨 5 模块,陈总醒后 5 分钟扫一眼最该关注的事:容百烧结晚 2 天 / 5 月三表已生成 / α 氧化铝粉涨价。",
    badge: "📅 经营日报 · 老板视角",
    durationMs: 6000,
  },
  {
    id: 2,
    tab: "inbox",
    title: "AI 收到 1 张车间领料单",
    narration:
      "9:18 成型车间张师傅扫码领 α 氧化铝粉 800 kg 投料 BL-2026-018。手写单子拍照传上来,AI 立即识别 7 个字段(车间/领用人/物料/数量/用途/日期),整体置信度 91%。",
    badge: "✨ AI 抽取 · 待王仓管确认",
    action: { type: "SIMULATE_RAW_ISSUE" },
    flashKeys: ["inbox:demo-line-issue-001"],
    durationMs: 8000,
  },
  {
    id: 3,
    tab: "inbox",
    title: "王仓管 ✓ 确认入账",
    narration:
      'AI 不直接动库存 — 王仓管点这一下确认才算数。这是"AI 先填、人确认"的核心:AI 把字段填好,人最终拍板。',
    badge: "✓ 王仓管 已确认",
    action: { type: "CONFIRM_INBOX", cardId: "demo-line-issue-001" },
    durationMs: 8000,
  },
  {
    id: 4,
    tab: "purchase",
    scrollAnchor: "stock-ledger",
    title: "库存台账 α 氧化铝粉 自动扣减",
    narration:
      "跨模块联动:α 氧化铝粉 期末 1,880 → 1,080 kg,跌破安全线 1,500,余量条立即飘红 ⚠ 低库存。整笔扣减来自王仓管刚才那一下确认,不是 AI 直接动。",
    badge: "⚠ 1,880 → 1,080 kg",
    flashKeys: ["stock:α 氧化铝粉"],
    durationMs: 8000,
  },
  {
    id: 5,
    tab: "production",
    subtab: "D",
    title: "配料单 D · 缺料预警",
    narration:
      "另一边:配料单 BL-2026-015 容百锂电承烧板 本批需 α 氧化铝粉 4,000 kg vs 现存 1,080 kg,缺 2,920 kg 自动飘红。AI 警告生产组别开新批次。",
    badge: "⚠ 配料缺 2,920 kg",
    durationMs: 7000,
  },
  {
    id: 6,
    tab: "purchase",
    scrollAnchor: "requisition",
    title: "AI 自动生成申购草稿 PR-2026-017",
    narration:
      "同步:AI 检测到 α 氧化铝粉 跌破安全线,按近 3 月平均用量自动出申购草稿。山东中铝 / 4,000 kg / 单价 ¥24.00 / 总价 ¥96,000。AI 先填、张主管确认。",
    badge: "✨ PR-2026-017 · 张主管待审批",
    flashKeys: ["pr:PR-2026-017"],
    durationMs: 8000,
  },
  {
    id: 7,
    tab: "purchase",
    scrollAnchor: "requisition",
    title: "张主管 批准 → 转采购订单",
    narration:
      "采购张主管复核后批准。系统自动:① 申购单 待审批 → 已转订单;② 采购订单顶部新增 PO-2026-009 山东中铝 ¥96,000。",
    badge: "✓ PR → PO-2026-009",
    action: { type: "APPROVE_PR", prNo: "PR-2026-017" },
    flashKeys: ["po:PO-2026-009", "pr:PR-2026-017"],
    durationMs: 8000,
  },
  {
    id: 8,
    tab: "purchase",
    scrollAnchor: "purchase-orders",
    title: "4 天后山东中铝送到 · 仓管入库 +4,000 kg",
    narration:
      "货到厂区,仓管确认入库。系统联动:库存 α 氧化铝粉 1,080 → 5,080 kg 回到健康,余量条变绿;应付台账自动新增一笔 ¥96,000,60 天账期到期 2026-07-24。",
    badge: "✓ PO-2026-009 已入库 · 应付 +¥96,000",
    action: { type: "RECEIVE_PO", poNo: "PO-2026-009" },
    flashKeys: ["stock:α 氧化铝粉", "po:PO-2026-009"],
    durationMs: 9000,
  },
  {
    id: 9,
    tab: "purchase",
    scrollAnchor: "payable",
    title: "应付台账 KPI 联动",
    narration:
      "本月应付从 ¥327,000 → ¥423,000(主线新增 ¥96,000 · 共 7 笔)。3 段彩色账龄条立即重新分布:已超期 / 30 天内 / 未到期 三段比例随新笔即时刷新。",
    badge: "¥327,000 → ¥423,000",
    durationMs: 7000,
  },
  {
    id: 10,
    tab: "briefing",
    title: "陈总扫一眼:本月应付 KPI 实时反映",
    narration:
      "回到经营日报。本月应付 KPI 从 ¥327,000 涨到 ¥423,000,副标 \"主线新增 +¥96,000 · 共 7 笔\"。全链 AI识别→王仓管→库存预警→AI草稿→张主管→入库→应付,90 秒走完,每步都签过字。",
    badge: "✓ 全程闭环",
    durationMs: 8000,
  },
];

export const TOUR_TOTAL = TOUR_STEPS.length;

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

    case "FLASH_KEYS":
      return flashKeys(state, action.keys);

    case "SET_PRODUCTION_SUBTAB":
      return { ...state, productionSubtab: action.subtab };

    case "SET_SCROLL_ANCHOR":
      return { ...state, scrollAnchor: action.anchor };

    case "TOUR_START":
      // Round 4: preserve mode + backend bookkeeping so a tour run in backend
      // mode keeps the seeded supplier/material IDs and continues to fire
      // real API calls. Tour resets ONLY the demo display state.
      return {
        ...initialState,
        mode: state.mode,
        backendIds: state.backendIds,
        backendKpi: state.backendKpi,
        backendStatus: state.backendStatus,
        tourStep: 1,
        tourPlaying: true,
      };

    case "TOUR_SET_STEP":
      return { ...state, tourStep: action.step };

    case "TOUR_PAUSE":
      return { ...state, tourPlaying: false };

    case "TOUR_RESUME":
      return { ...state, tourPlaying: true };

    case "TOUR_EXIT":
      return { ...state, tourStep: 0, tourPlaying: false, scrollAnchor: null };

    case "RESET":
      // Preserve mode across reset; reset everything else.
      return {
        ...initialState,
        mode: state.mode,
        toasts: [{ id: "reset", level: "info", title: "已重置到 demo 初始状态" }],
      };

    case "SET_MODE": {
      if (typeof window !== "undefined") {
        try { window.localStorage.setItem("jintai.mode", action.mode); } catch { /* ignore */ }
      }
      return {
        ...state,
        mode: action.mode,
        // 切 mode 同时重置后端 IDs (避免老 ID 串扰)
        backendIds: action.mode === "mock" ? {} : state.backendIds,
      };
    }
    case "SET_BACKEND_IDS":
      return { ...state, backendIds: { ...state.backendIds, ...action.ids } };
    case "SET_BACKEND_KPI":
      return { ...state, backendKpi: action.kpi };
    case "SET_BACKEND_STATUS":
      return {
        ...state,
        backendStatus: { ...state.backendStatus, ...action.status, lastSyncedAt: Date.now() },
      };

    default:
      return state;
  }
}

/* ---------- Context ---------- */
type Ctx = {
  state: JintaiState;
  dispatch: React.Dispatch<Action>;
  /** iter 23: 引导式 90 秒演示 */
  startTour: () => void;
  pauseTour: () => void;
  resumeTour: () => void;
  exitTour: () => void;
  nextTourStep: () => void;
  /** 当前步配置(便于 Tour bar 显示) */
  currentTourStep: TourStep | null;
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
  /** round 4: backend-mode 切换 + 副作用 */
  setMode: (mode: BackendMode) => void;
  refreshBackendKpi: () => Promise<void>;
  /** round 4: 包装 dispatch — backend mode 下先发 API,失败 fallback 到 mock */
  dispatchWithBackend: (action: Action) => Promise<void>;
};

const JintaiContext = createContext<Ctx | null>(null);

export function JintaiProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const tourTimerRef = useRef<number | null>(null);
  const tourEnteredRef = useRef<number>(0);

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

  /* ---------- round 4 screenshot helper: ?jumpToEnd=1 直接到 demo-complete ---------- */
  const jumpedRef = useRef(false);
  useEffect(() => {
    if (jumpedRef.current) return;
    if (typeof window === "undefined") return;
    const qp = new URLSearchParams(window.location.search);
    if (qp.get("jumpToEnd") === "1") {
      jumpedRef.current = true;
      dispatch({ type: "TOUR_SET_STEP", step: TOUR_TOTAL + 1 });
    }
  }, []);

  /* ---------- iter 23: 引导式 Tour 引擎 ---------- */
  // 进入每一步:① 派发 step.action ② 重新激活 flashKeys ③ 设置子 tab + scroll
  useEffect(() => {
    if (state.tourStep === 0 || state.tourStep > TOUR_TOTAL) return;
    // 防止 React StrictMode 二次触发同一 step 的副作用
    if (tourEnteredRef.current === state.tourStep) return;
    tourEnteredRef.current = state.tourStep;
    const step = TOUR_STEPS[state.tourStep - 1];
    if (step.action) {
      // Round 4: backend mode 走 dispatchWithBackend (失败 fallback 到 mock)
      void dispatchWithBackend(step.action);
    }
    if (step.flashKeys && step.flashKeys.length > 0) {
      // 延迟 200ms 给 action 落地后再 flash (action 自己也会 flash 一次)
      window.setTimeout(() => dispatch({ type: "FLASH_KEYS", keys: step.flashKeys! }), 200);
    }
    if (step.subtab) dispatch({ type: "SET_PRODUCTION_SUBTAB", subtab: step.subtab });
    if (step.scrollAnchor !== undefined) {
      dispatch({ type: "SET_SCROLL_ANCHOR", anchor: step.scrollAnchor ?? null });
    } else {
      dispatch({ type: "SET_SCROLL_ANCHOR", anchor: null });
    }
  }, [state.tourStep]);

  // 自动推进: 当前步停留 durationMs 后切下一步
  useEffect(() => {
    if (!state.tourPlaying || state.tourStep === 0 || state.tourStep > TOUR_TOTAL) return;
    const step = TOUR_STEPS[state.tourStep - 1];
    tourTimerRef.current = window.setTimeout(() => {
      dispatch({ type: "TOUR_SET_STEP", step: state.tourStep + 1 });
    }, step.durationMs);
    return () => {
      if (tourTimerRef.current) {
        window.clearTimeout(tourTimerRef.current);
        tourTimerRef.current = null;
      }
    };
  }, [state.tourPlaying, state.tourStep]);

  /* ---------- round 4: backend-mode 引擎 ---------- */

  const refreshBackendKpi = useCallback(async () => {
    try {
      const kpi = await getBriefingKpi();
      dispatch({ type: "SET_BACKEND_KPI", kpi });
      dispatch({ type: "SET_BACKEND_STATUS", status: { lastError: undefined } });
    } catch (e) {
      const msg = e instanceof JintaiBackendError ? `${e.message}: ${JSON.stringify(e.detail)}` : String(e);
      dispatch({ type: "SET_BACKEND_STATUS", status: { lastError: msg } });
    }
  }, []);

  /** 进入 backend mode 时:health check + seed supplier+material (如未有) + 拉首次 KPI */
  const ensureSeedRef = useRef<Promise<void> | null>(null);
  const ensureBackendSeed = useCallback(async () => {
    if (ensureSeedRef.current) return ensureSeedRef.current;
    const run = (async () => {
      dispatch({ type: "SET_BACKEND_STATUS", status: { seeding: true, lastError: undefined } });
      try {
        const health = await getHealth();
        dispatch({ type: "SET_BACKEND_STATUS", status: { health } });
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        dispatch({
          type: "SET_BACKEND_STATUS",
          status: { seeding: false, lastError: `health: ${msg}` },
        });
        throw e;
      }
      // 已经 seed 过 (state 有 ids) 就 skip,不重复 seed
      if (state.backendIds.supplierId && state.backendIds.materialId) {
        dispatch({ type: "SET_BACKEND_STATUS", status: { seeding: false } });
        await refreshBackendKpi();
        return;
      }
      try {
        const ids = await ensureDemoSeed({
          supplierName: `${PIVOT_MATERIAL} demo 供应商 ${new Date().toISOString().slice(0, 16)}`,
          paymentTermsDays: 60,
          materialCode: `RM-AL2O3-DEMO-${Date.now()}`,
          materialName: PIVOT_MATERIAL,
          unit: "kg",
          safetyStock: 1500,
          initialBalance: 1880,
        });
        dispatch({ type: "SET_BACKEND_IDS", ids });
        dispatch({ type: "SET_BACKEND_STATUS", status: { seeding: false } });
        await refreshBackendKpi();
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        dispatch({ type: "SET_BACKEND_STATUS", status: { seeding: false, lastError: msg } });
      }
    })();
    ensureSeedRef.current = run;
    return run;
  }, [state.backendIds.supplierId, state.backendIds.materialId, refreshBackendKpi]);

  const setMode = useCallback((mode: BackendMode) => {
    ensureSeedRef.current = null; // allow re-seed on next backend entry
    dispatch({ type: "SET_MODE", mode });
    if (mode === "backend") {
      // fire and forget
      void ensureBackendSeed();
    }
  }, [ensureBackendSeed]);

  // 初次 mount 时如 mode=backend 触发 seed
  const initialSeedDoneRef = useRef(false);
  useEffect(() => {
    if (initialSeedDoneRef.current) return;
    initialSeedDoneRef.current = true;
    if (state.mode === "backend") void ensureBackendSeed();
  }, [state.mode, ensureBackendSeed]);

  /**
   * 包装 dispatch:
   *  - mock mode:  原样 dispatch
   *  - backend mode: 对主线 4 个 action 先打 API → 成功 → dispatch + refresh KPI;
   *                  失败 → toast + 仍 dispatch 以保 demo 不挂 (fallback)
   *  - 其它 action: 直接 dispatch
   */
  const dispatchWithBackend = useCallback(
    async (action: Action) => {
      if (state.mode === "mock") {
        dispatch(action);
        return;
      }
      // backend mode
      try {
        if (action.type === "SIMULATE_RAW_ISSUE") {
          await ensureBackendSeed();
          const ids = state.backendIds;
          // Re-read after ensureBackendSeed (above sets via dispatch — state may be stale).
          // Use refs would be cleaner; for safety we tolerate ids being undefined and 再 dispatch + fallback.
          if (!ids.materialId) {
            // seed in progress / failed — dispatch mock fallback
            dispatch(action);
            return;
          }
          const voucherId = await createIssueVoucher({
            materialId: ids.materialId,
            voucherNo: `BL-DEMO-${Date.now()}`,
            workshop: "成型车间",
            applicant: "张师傅",
            quantity: ISSUE_QTY,
            unit: "kg",
            purpose: "demo backend mode 一键演示",
          });
          dispatch({ type: "SET_BACKEND_IDS", ids: { voucherId } });
        } else if (action.type === "CONFIRM_INBOX" && action.cardId === NEW_INBOX_ID) {
          const vid = state.backendIds.voucherId;
          if (vid) {
            const resp = await postIssueAndConfirm(vid);
            dispatch({
              type: "SET_BACKEND_IDS",
              ids: { prId: resp.auto_drafted_pr_id ?? undefined },
            });
          }
        } else if (action.type === "APPROVE_PR" && action.prNo === NEW_PR_NO) {
          const pid = state.backendIds.prId;
          const sid = state.backendIds.supplierId;
          if (pid && sid) {
            // fetch PR items to get unit price target
            const { listRequisitions } = await import("../../../api/jintai-backend");
            const prs = await listRequisitions();
            const pr = prs.find((p) => p.id === pid);
            const unitPrices: Record<string, string> = {};
            for (const it of pr?.items || []) {
              unitPrices[it.id] = String(PR_UNIT_PRICE.toFixed(2));
            }
            const resp = await postApprovePr(pid, { supplier_id: sid, unit_prices: unitPrices });
            dispatch({ type: "SET_BACKEND_IDS", ids: { poId: resp.po_id } });
          }
        } else if (action.type === "RECEIVE_PO" && action.poNo === NEW_PO_NO) {
          const po = state.backendIds.poId;
          if (po) {
            await postReceivePo(po, { warehouse: "原料库 A-02" });
          }
        }
        dispatch(action);
        // refresh KPI after each mutation (mainline actions)
        if (["SIMULATE_RAW_ISSUE", "CONFIRM_INBOX", "APPROVE_PR", "RECEIVE_PO"].includes(action.type)) {
          await refreshBackendKpi();
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        dispatch({
          type: "SET_BACKEND_STATUS",
          status: { lastError: `${action.type}: ${msg}` },
        });
        // fallback 到 mock 行为,demo 不挂
        dispatch(action);
      }
    },
    [
      state.mode,
      state.backendIds,
      ensureBackendSeed,
      refreshBackendKpi,
    ],
  );

  const startTour = useCallback(() => {
    tourEnteredRef.current = 0;
    dispatch({ type: "TOUR_START" });
  }, []);
  const pauseTour = useCallback(() => dispatch({ type: "TOUR_PAUSE" }), []);
  const resumeTour = useCallback(() => dispatch({ type: "TOUR_RESUME" }), []);
  const exitTour = useCallback(() => {
    tourEnteredRef.current = 0;
    dispatch({ type: "TOUR_EXIT" });
  }, []);
  const nextTourStep = useCallback(() => {
    dispatch({ type: "TOUR_SET_STEP", step: Math.min(state.tourStep + 1, TOUR_TOTAL + 1) });
  }, [state.tourStep]);

  const currentTourStep =
    state.tourStep >= 1 && state.tourStep <= TOUR_TOTAL ? TOUR_STEPS[state.tourStep - 1] : null;

  const value = useMemo<Ctx>(
    () => ({
      state,
      dispatch,
      startTour,
      pauseTour,
      resumeTour,
      exitTour,
      nextTourStep,
      currentTourStep,
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
      setMode,
      refreshBackendKpi,
      dispatchWithBackend,
    }),
    [
      state, startTour, pauseTour, resumeTour, exitTour, nextTourStep,
      currentTourStep, isFlashing, setMode, refreshBackendKpi, dispatchWithBackend,
    ],
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
