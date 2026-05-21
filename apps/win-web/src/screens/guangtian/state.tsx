import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  recentInbounds as seedInbounds,
  recentOutbounds as seedOutbounds,
  ledgerRows as seedLedger,
  skuRows,
} from "./data";

// ============================================================================
// iter G10: lifted state — toast + 数字联动
// ============================================================================

export type ToastLevel = "ok" | "warn" | "err" | "info" | "ai";
export type Toast = { id: string; message: string; level: ToastLevel };

export type InboundEntry = {
  time: string;
  sku: string;
  name: string;
  qty: string;
  unit: string;
  batch: string;
  location: string;
  op: string;
  source: string;
};
export type OutboundEntry = {
  time: string;
  sku: string;
  name: string;
  qty: string;
  customer: string;
  order: string;
  status: string;
  op: string;
};
export type LedgerEntry = {
  time: string;
  op: string;
  sku: string;
  name: string;
  delta: string;
  before: number;
  after: number;
  ref: string;
  user: string;
  note: string;
  confidence?: number; // iter G11: AI 识别置信度 0-100
  confirmed?: boolean; // iter G11: 是否已确认（true=已确认 / false=待确认）
};

type AddInboundInput = {
  sku: string;
  name: string;
  qty: number;
  unit: string;
  batch: string;
  location: string;
  op: string;
  source: string;
};

type AddOutboundInput = {
  sku: string;
  name: string;
  qty: number;
  unit: string;
  customer: string;
  order: string;
  op: string;
};

type GTContextValue = {
  // toast
  toasts: Toast[];
  showToast: (message: string, level?: ToastLevel) => void;
  dismissToast: (id: string) => void;

  // 数字联动
  skuStocks: Record<string, number>;
  inboundRecords: InboundEntry[];
  outboundRecords: OutboundEntry[];
  ledgerEntries: LedgerEntry[];
  todayInboundCount: number;
  todayOutboundCount: number;

  addInbound: (entry: AddInboundInput) => void;
  addOutbound: (entry: AddOutboundInput) => boolean; // false 表示库存不足拒绝
  // iter G11: 流水"待确认 → 已确认"操作
  confirmLedger: (time: string, sku: string) => void;

  // 跨 tab 联动：Dashboard / Shortage 把问题推到 AskInventory
  pendingAsk: string | null;
  setPendingAsk: (q: string | null) => void;

  // iter G12-B: 一键演示模式
  demoStep: number; // 0 = 未启动 / 1-6 = 步骤中 / 7 = 总结
  demoPlaying: boolean; // 自动播放中
  startDemo: () => void;
  pauseDemo: () => void;
  resumeDemo: () => void;
  exitDemo: () => void;
  nextDemoStep: () => void;
  highlightSku: string | null; // demo 时高亮某个 SKU
  highlightOrder: string | null; // demo 时高亮某个订单
};

const GuangtianContext = createContext<GTContextValue | null>(null);

export function useGT(): GTContextValue {
  const ctx = useContext(GuangtianContext);
  if (!ctx) throw new Error("useGT must be used inside <GuangtianProvider>");
  return ctx;
}

function nowStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function GuangtianProvider({ children }: { children: ReactNode }) {
  // toast
  const [toasts, setToasts] = useState<Toast[]>([]);
  const showToast = useCallback((message: string, level: ToastLevel = "ok") => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { id, message, level }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);
  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // 数字联动 — initial from data.ts seed
  const [skuStocks, setSkuStocks] = useState<Record<string, number>>(() =>
    Object.fromEntries(skuRows.map((r) => [r.code, r.stock])),
  );
  const [inboundRecords, setInboundRecords] = useState<InboundEntry[]>(seedInbounds);
  const [outboundRecords, setOutboundRecords] = useState<OutboundEntry[]>(seedOutbounds);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>(seedLedger);
  const [todayInboundCount, setTodayInboundCount] = useState(18);
  const [todayOutboundCount, setTodayOutboundCount] = useState(23);
  const [pendingAsk, setPendingAsk] = useState<string | null>(null);

  // iter G12-B: 演示模式
  const [demoStep, setDemoStep] = useState(0);
  const [demoPlaying, setDemoPlaying] = useState(false);
  const [highlightSku, setHighlightSku] = useState<string | null>(null);
  const [highlightOrder, setHighlightOrder] = useState<string | null>(null);
  const demoTimerRef = useRef<number | null>(null);

  // iter G13: 单向 6 步高亮映射
  // step 1 inbound · 2 ledger · 3 shortage(SO-003) · 4 replenish(AL90) · 5 ask · 6 report
  useEffect(() => {
    if (demoStep === 3) {
      setHighlightSku(null);
      setHighlightOrder("SO-20260519-003"); // 缺货预警高亮 003
    } else if (demoStep === 4) {
      setHighlightSku("JT-GZB-AL90"); // 补产建议高亮 AL90 行 + auto assign
      setHighlightOrder(null);
    } else if (demoStep === 0) {
      setHighlightSku(null);
      setHighlightOrder(null);
    } else {
      // step 1 / 2 / 5 / 6 不需要 highlight，clear 掉避免遗留
      setHighlightSku(null);
      setHighlightOrder(null);
    }
  }, [demoStep]);

  // 自动播放推进：每步 2800ms
  useEffect(() => {
    if (!demoPlaying || demoStep === 0 || demoStep >= 7) return;
    demoTimerRef.current = window.setTimeout(() => {
      setDemoStep((s) => s + 1);
    }, 2800);
    return () => {
      if (demoTimerRef.current) {
        window.clearTimeout(demoTimerRef.current);
        demoTimerRef.current = null;
      }
    };
  }, [demoPlaying, demoStep]);

  const startDemo = useCallback(() => {
    setDemoStep(1);
    setDemoPlaying(true);
  }, []);
  const pauseDemo = useCallback(() => setDemoPlaying(false), []);
  const resumeDemo = useCallback(() => setDemoPlaying(true), []);
  const exitDemo = useCallback(() => {
    setDemoStep(0);
    setDemoPlaying(false);
    setHighlightSku(null);
    setHighlightOrder(null);
    if (demoTimerRef.current) {
      window.clearTimeout(demoTimerRef.current);
      demoTimerRef.current = null;
    }
  }, []);
  const nextDemoStep = useCallback(() => {
    setDemoStep((s) => (s >= 7 ? s : s + 1));
  }, []);

  const confirmLedger = useCallback(
    (time: string, sku: string) => {
      setLedgerEntries((prev) =>
        prev.map((r) => (r.time === time && r.sku === sku ? { ...r, confirmed: true } : r)),
      );
      showToast("✓ 已确认 · 流水状态变为 已确认", "ok");
    },
    [showToast],
  );

  const addInbound = useCallback(
    (entry: AddInboundInput) => {
      const time = nowStamp();
      setSkuStocks((prev) => {
        const before = prev[entry.sku] ?? 0;
        const after = before + entry.qty;
        // ledger 必须用最新前后值
        setLedgerEntries((rows) => [
          {
            time,
            op: "入库",
            sku: entry.sku,
            name: entry.name,
            delta: `+${entry.qty}`,
            before,
            after,
            ref: entry.source,
            user: entry.op,
            note: `${entry.batch} 批次`,
            confidence: 96 + Math.floor(Math.random() * 4), // 96-99 入库手工录入高置信
            confirmed: true,
          },
          ...rows,
        ]);
        setInboundRecords((rs) => [
          {
            time,
            sku: entry.sku,
            name: entry.name,
            qty: `+${entry.qty.toLocaleString()}`,
            unit: entry.unit,
            batch: entry.batch,
            location: entry.location,
            op: entry.op,
            source: entry.source,
          },
          ...rs,
        ]);
        showToast(
          `✓ 入库成功 · ${entry.name} +${entry.qty} ${entry.unit} · 库存 ${before.toLocaleString()} → ${after.toLocaleString()}`,
          "ok",
        );
        return { ...prev, [entry.sku]: after };
      });
      setTodayInboundCount((c) => c + 1);
    },
    [showToast],
  );

  const addOutbound = useCallback(
    (entry: AddOutboundInput): boolean => {
      const time = nowStamp();
      let ok = false;
      setSkuStocks((prev) => {
        const before = prev[entry.sku] ?? 0;
        if (before < entry.qty) {
          showToast(
            `✗ 库存不足 · ${entry.name} 需 ${entry.qty}，仅余 ${before.toLocaleString()}`,
            "err",
          );
          return prev;
        }
        const after = before - entry.qty;
        ok = true;
        setLedgerEntries((rows) => [
          {
            time,
            op: "出库",
            sku: entry.sku,
            name: entry.name,
            delta: `-${entry.qty}`,
            before,
            after,
            ref: `${entry.order} · ${entry.customer}`,
            user: entry.op,
            note: "",
            confidence: 96 + Math.floor(Math.random() * 4),
            confirmed: true,
          },
          ...rows,
        ]);
        setOutboundRecords((rs) => [
          {
            time,
            sku: entry.sku,
            name: entry.name,
            qty: `-${entry.qty.toLocaleString()}`,
            customer: entry.customer,
            order: entry.order,
            status: "已出库",
            op: entry.op,
          },
          ...rs,
        ]);
        showToast(
          `✓ 出库成功 · ${entry.name} -${entry.qty} ${entry.unit} · 库存 ${before.toLocaleString()} → ${after.toLocaleString()}`,
          "ok",
        );
        return { ...prev, [entry.sku]: after };
      });
      if (ok) setTodayOutboundCount((c) => c + 1);
      return ok;
    },
    [showToast],
  );

  const value = useMemo<GTContextValue>(
    () => ({
      toasts,
      showToast,
      dismissToast,
      skuStocks,
      inboundRecords,
      outboundRecords,
      ledgerEntries,
      todayInboundCount,
      todayOutboundCount,
      addInbound,
      addOutbound,
      confirmLedger,
      pendingAsk,
      setPendingAsk,
      demoStep,
      demoPlaying,
      startDemo,
      pauseDemo,
      resumeDemo,
      exitDemo,
      nextDemoStep,
      highlightSku,
      highlightOrder,
    }),
    [
      toasts,
      showToast,
      dismissToast,
      skuStocks,
      inboundRecords,
      outboundRecords,
      ledgerEntries,
      todayInboundCount,
      todayOutboundCount,
      addInbound,
      addOutbound,
      confirmLedger,
      pendingAsk,
      demoStep,
      demoPlaying,
      startDemo,
      pauseDemo,
      resumeDemo,
      exitDemo,
      nextDemoStep,
      highlightSku,
      highlightOrder,
    ],
  );

  return <GuangtianContext.Provider value={value}>{children}</GuangtianContext.Provider>;
}
