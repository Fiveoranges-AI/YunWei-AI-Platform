// 试点价值算账 —— 推签单关键。Linear/Stripe 风格冷数字,让总经理自己算、自己被说服。
// 全部前端计算,无后端;假设可改,签约后按真实数据校准。
import { useState } from "react";

function fmt(n: number): string {
  return Math.round(n).toLocaleString("zh-CN");
}

export function RoiPanel() {
  // —— 可改假设（合理默认,基于光天 SKU 规模 + 行业平均）——
  const [hoursNow, setHoursNow] = useState(40); // 库管手工维护 Excel 月工时
  const [wage, setWage] = useState(25); // 库管时薪
  const [discrep, setDiscrep] = useState(8); // 月账实不符次数
  const [discrepCost, setDiscrepCost] = useState(3000); // 每次差异平均损失(过期/错发/重复采购)
  const [orders, setOrders] = useState(60); // 月订单数
  const [stockoutRate, setStockoutRate] = useState(4); // 缺货延单率 %
  const [stockoutCost, setStockoutCost] = useState(4000); // 每延误单损失(赶工/加急/客户关系)
  const [fee, setFee] = useState(2500); // AI 库存管家月费(试点价)

  const HOURS_AI = 8; // AI 后库管月工时(只剩确认/异常处理)
  // —— 输出 ——
  const laborSave = Math.max(0, hoursNow - HOURS_AI) * wage;
  const discrepSave = discrep * discrepCost;
  const delayedOrders = orders * (stockoutRate / 100);
  const stockoutSave = delayedOrders * stockoutCost;
  const totalSave = laborSave + discrepSave + stockoutSave;
  const roi = fee > 0 ? totalSave / fee : 0;

  return (
    <div style={{ maxWidth: 940 }}>
      <header style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "var(--ink-900)", letterSpacing: "-0.01em" }}>
          用了 AI 库存管家，光天每月能省多少？
        </h2>
        <p style={{ margin: "6px 0 0", fontSize: 12.5, color: "var(--ink-500)", lineHeight: 1.6 }}>
          下面的假设可以按您的实际情况改。数字会实时算给您看——您自己判断值不值。
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 18 }}>
        {/* 左：可改假设 */}
        <div className="card" style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink-500)", letterSpacing: "0.04em", marginBottom: 12 }}>
            假设（可改）
          </div>
          <Row label="库管手工维护月工时" value={hoursNow} set={setHoursNow} unit="h/月" />
          <Row label="库管时薪" value={wage} set={setWage} unit="元/h" />
          <Row label="月账实不符次数" value={discrep} set={setDiscrep} unit="次/月" />
          <Row label="每次差异平均损失" value={discrepCost} set={setDiscrepCost} unit="元/次" hint="过期 / 错发 / 重复采购" />
          <Row label="月订单数" value={orders} set={setOrders} unit="单/月" />
          <Row label="缺货延单率" value={stockoutRate} set={setStockoutRate} unit="%" />
          <Row label="每延误单损失" value={stockoutCost} set={setStockoutCost} unit="元/单" hint="赶工 / 加急 / 客户关系" />
          <div style={{ height: 1, background: "var(--ink-100)", margin: "10px 0" }} />
          <Row label="AI 库存管家月费（试点价）" value={fee} set={setFee} unit="元/月" />
        </div>

        {/* 右：说人话的结果 */}
        <div className="card" style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 0 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--ink-500)", letterSpacing: "0.04em", marginBottom: 12 }}>
            每月价值
          </div>
          <OutRow
            label="省人工"
            sub={`库管 ${hoursNow}h → ${HOURS_AI}h，省 ${Math.max(0, hoursNow - HOURS_AI)}h`}
            amount={laborSave}
            tone="muted"
          />
          <OutRow
            label="减少账实差异损失"
            sub={`${discrep} 次/月 × ${fmt(discrepCost)} 元`}
            amount={discrepSave}
            tone="strong"
          />
          <OutRow
            label="减少缺货损失"
            sub={`${fmt(delayedOrders)} 延误单/月 × ${fmt(stockoutCost)} 元`}
            amount={stockoutSave}
            tone="strong"
          />
          <div style={{ height: 1, background: "var(--ink-100)", margin: "12px 0" }} />
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13.5, fontWeight: 700, color: "var(--ink-900)" }}>每月总价值</span>
            <span style={{ fontSize: 28, fontWeight: 800, color: "var(--ink-900)", fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>
              ¥{fmt(totalSave)}
            </span>
          </div>
          <div
            style={{
              marginTop: 12,
              padding: "12px 14px",
              borderRadius: 10,
              background: "var(--surface-2)",
              border: "1px solid var(--ink-100)",
              fontSize: 13,
              color: "var(--ink-700)",
              lineHeight: 1.6,
            }}
          >
            月费 <strong style={{ color: "var(--ink-900)" }}>¥{fmt(fee)}</strong> → 每月净省{" "}
            <strong style={{ color: "var(--guangtian-blue)" }}>¥{fmt(totalSave - fee)}</strong>，
            投入产出比 <strong style={{ color: "var(--guangtian-blue)" }}>约 {roi.toFixed(1)} 倍</strong>。
          </div>
          <div style={{ marginTop: 10, fontSize: 10.5, color: "var(--ink-400)", lineHeight: 1.5 }}>
            ⓘ 数字基于行业平均值与光天 SKU 规模估算；省人工是小钱，差异与缺货才是大钱。
            签订试点后按光天真实数据校准。
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({
  label, value, set, unit, hint,
}: { label: string; value: number; set: (n: number) => void; unit: string; hint?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "6px 0" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: "var(--ink-700)" }}>{label}</div>
        {hint && <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 1 }}>{hint}</div>}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 5, flexShrink: 0 }}>
        <input
          type="number"
          value={value}
          onChange={(e) => set(Math.max(0, Number(e.target.value) || 0))}
          style={{
            width: 80,
            padding: "5px 8px",
            fontSize: 12.5,
            textAlign: "right",
            border: "1px solid var(--ink-200)",
            borderRadius: 6,
            background: "#fff",
            fontFamily: "var(--font)",
            outline: "none",
          }}
        />
        <span style={{ fontSize: 11, color: "var(--ink-400)", width: 36 }}>{unit}</span>
      </div>
    </div>
  );
}

function OutRow({
  label, sub, amount, tone,
}: { label: string; sub: string; amount: number; tone: "muted" | "strong" }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10, padding: "7px 0" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: "var(--ink-800)", fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: 10.5, color: "var(--ink-400)", marginTop: 1 }}>{sub}</div>
      </div>
      <span
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: tone === "strong" ? "var(--ink-900)" : "var(--ink-500)",
          fontFamily: "var(--font-display)",
          flexShrink: 0,
        }}
      >
        ¥{fmt(amount)}
      </span>
    </div>
  );
}
