// iter G12-A: 3 个手写 inline SVG 图表，0 依赖
import { useIsDesktop } from "../../../lib/breakpoints";

// ============================================================================
// 1. 库存趋势折线图 — 高铝砖 + 莫来石 近 30 天
// ============================================================================
// mock 30 天数据（5/01 → 5/30）
const TREND_DAYS = 30;
const TREND_HLZ = [3200, 3450, 3600, 3850, 3500, 3300, 3450, 3700, 4100, 4300, 4150, 4000, 3900, 3850, 3750, 3600, 3500, 3400, 3300, 3550, 3800, 4100, 4500, 4800, 5100, 5300, 5080, 4800, 4500, 4280];
const TREND_MLS = [950, 920, 880, 850, 800, 760, 700, 650, 620, 600, 580, 560, 540, 500, 470, 440, 420, 400, 380, 360, 340, 330, 320, 310, 320, 320, 320, 320, 320, 320];
const SAFETY_HLZ = 2000;
const SAFETY_MLS = 800;

export function StockTrendChart() {
  const w = 560;
  const h = 200;
  const pad = { t: 20, r: 16, b: 24, l: 38 };
  const cw = w - pad.l - pad.r;
  const ch = h - pad.t - pad.b;
  const maxY = 5500;

  const x = (i: number) => pad.l + (i / (TREND_DAYS - 1)) * cw;
  const y = (v: number) => pad.t + (1 - v / maxY) * ch;

  const path = (data: number[]) =>
    data.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const fillPath = (data: number[]) =>
    `${path(data)} L ${x(TREND_DAYS - 1).toFixed(1)} ${y(0).toFixed(1)} L ${x(0).toFixed(1)} ${y(0).toFixed(1)} Z`;

  const yTicks = [0, 1000, 2000, 3000, 4000, 5000];
  const xTicks = [0, 5, 10, 15, 20, 25, 29];
  const xLabel = (i: number) => `5/${String(i + 1).padStart(2, "0")}`;

  return (
    <ChartCard title="库存趋势 · 近 30 天" subtitle="高铝砖 + 莫来石砖 / 安全线虚线参考">
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label="库存趋势折线图">
        <defs>
          <linearGradient id="gt-hlz-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--brand-500)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--brand-500)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="gt-mls-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--guangtian-blue)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--guangtian-blue)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Y 网格 */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={pad.l}
              x2={w - pad.r}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--ink-100)"
              strokeWidth="1"
              strokeDasharray={v === 0 ? "0" : "2 4"}
            />
            <text x={pad.l - 6} y={y(v) + 3} fontSize="9" fill="var(--ink-400)" textAnchor="end">
              {v.toLocaleString()}
            </text>
          </g>
        ))}

        {/* X 标签 */}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={h - pad.b + 14} fontSize="9" fill="var(--ink-400)" textAnchor="middle">
            {xLabel(i)}
          </text>
        ))}

        {/* 安全线 */}
        <line
          x1={pad.l}
          x2={w - pad.r}
          y1={y(SAFETY_HLZ)}
          y2={y(SAFETY_HLZ)}
          stroke="var(--brand-500)"
          strokeWidth="1"
          strokeDasharray="3 3"
          opacity="0.4"
        />
        <text x={w - pad.r - 2} y={y(SAFETY_HLZ) - 3} fontSize="8" fill="var(--brand-700)" textAnchor="end" opacity="0.7">
          高铝安全线 2,000
        </text>
        <line
          x1={pad.l}
          x2={w - pad.r}
          y1={y(SAFETY_MLS)}
          y2={y(SAFETY_MLS)}
          stroke="var(--guangtian-red)"
          strokeWidth="1"
          strokeDasharray="3 3"
          opacity="0.4"
        />
        <text x={w - pad.r - 2} y={y(SAFETY_MLS) - 3} fontSize="8" fill="var(--guangtian-red)" textAnchor="end" opacity="0.7">
          莫来石安全线 800
        </text>

        {/* fill 区 */}
        <path d={fillPath(TREND_HLZ)} fill="url(#gt-hlz-fill)" />
        <path d={fillPath(TREND_MLS)} fill="url(#gt-mls-fill)" />

        {/* 折线 */}
        <path d={path(TREND_HLZ)} fill="none" stroke="var(--brand-500)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
        <path d={path(TREND_MLS)} fill="none" stroke="var(--guangtian-blue)" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />

        {/* 末端 dot */}
        <circle cx={x(TREND_DAYS - 1)} cy={y(TREND_HLZ[TREND_DAYS - 1])} r="3" fill="var(--brand-500)" />
        <circle cx={x(TREND_DAYS - 1)} cy={y(TREND_MLS[TREND_DAYS - 1])} r="3" fill="var(--guangtian-blue)" />
      </svg>

      {/* legend */}
      <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 11, color: "var(--ink-600)" }}>
        <Legend color="var(--brand-500)" label="高铝砖 (4,280 块)" />
        <Legend color="var(--guangtian-blue)" label="莫来石砖 (320 块)" />
      </div>
    </ChartCard>
  );
}

// ============================================================================
// 2. 库存状态分布环形图
// ============================================================================
const DIST = [
  { label: "正常",     value: 1167, color: "var(--stock-ok)"          },
  { label: "低库存",   value: 46,   color: "var(--stock-low)"         },
  { label: "缺货",     value: 7,    color: "var(--stock-out)"         },
  { label: "数据异常", value: 12,   color: "var(--ai-purple-deep)"    },
  { label: "呆滞",     value: 54,   color: "var(--stock-dead)"        },
];

export function StockDistributionDonut() {
  const total = DIST.reduce((s, d) => s + d.value, 0);
  const size = 180;
  const r = 65;
  const cx = size / 2;
  const cy = size / 2;
  const stroke = 18;
  const circ = 2 * Math.PI * r;

  let acc = 0;
  const segs = DIST.map((d) => {
    const len = (d.value / total) * circ;
    const offset = -acc;
    acc += len;
    return { ...d, len, offset, gap: circ - len };
  });

  return (
    <ChartCard title="SKU 状态分布" subtitle={`${total.toLocaleString()} 个 SKU 总览`}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "4px 0 2px" }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }} role="img" aria-label="状态分布环形图">
          {/* 背景圈 */}
          <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--ink-50)" strokeWidth={stroke} />
          {/* 段 */}
          {segs.map((s, i) => (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={stroke}
              strokeDasharray={`${s.len} ${s.gap}`}
              strokeDashoffset={s.offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              strokeLinecap="butt"
            />
          ))}
          {/* 中心数字 */}
          <text x={cx} y={cy - 4} fontSize="22" fontWeight="800" textAnchor="middle" fill="var(--ink-900)" fontFamily="var(--font-display)">
            {total.toLocaleString()}
          </text>
          <text x={cx} y={cy + 14} fontSize="10" textAnchor="middle" fill="var(--ink-500)">
            SKU
          </text>
        </svg>
        {/* iter G14: 每项两行 — 状态名 nowrap 不折断 + 第 2 行小灰字 数量·百分比 */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 9 }}>
          {DIST.map((d) => {
            const pct = ((d.value / total) * 100).toFixed(1);
            return (
              <div key={d.label} style={{ display: "flex", alignItems: "flex-start", gap: 8, minWidth: 0 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: d.color,
                    flexShrink: 0,
                    marginTop: 5,
                  }}
                />
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0, lineHeight: 1.25 }}>
                  <span style={{ fontSize: 13, color: "var(--ink-800)", fontWeight: 600, whiteSpace: "nowrap" }}>
                    {d.label}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: "var(--ink-500)",
                      fontFamily: "var(--font-mono, var(--font))",
                      marginTop: 2,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {d.value.toLocaleString()} · {pct}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </ChartCard>
  );
}

// ============================================================================
// 3. Top 出库 SKU 水平柱状图
// ============================================================================
const TOP_OUT = [
  { sku: "JT-HLZ-230-114-65", name: "高铝砖（标准型）", qty: 4800, unit: "块" },
  { sku: "JT-JZL-JC18-LR",    name: "低水泥浇注料",     qty: 320,  unit: "袋" },
  { sku: "JT-MLS-M70",        name: "莫来石砖 M70",     qty: 280,  unit: "块" },
  { sku: "JT-HLZ-T3-150",     name: "高铝砖 T3 异型",   qty: 220,  unit: "块" },
  { sku: "JT-GZB-AL80",       name: "刚玉砖 AL80",      qty: 180,  unit: "块" },
];

export function TopOutboundBars() {
  const max = Math.max(...TOP_OUT.map((t) => t.qty));
  return (
    <ChartCard title="出库 TOP 5 · 近 7 天" subtitle="按出货数量排序">
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
        {TOP_OUT.map((t, i) => {
          const pct = (t.qty / max) * 100;
          return (
            <div key={t.sku}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 3 }}>
                <span style={{ fontSize: 11, color: "var(--ink-700)", fontWeight: 600 }}>
                  <span style={{
                    display: "inline-block",
                    width: 16,
                    fontSize: 10,
                    color: i === 0 ? "var(--guangtian-red)" : "var(--ink-400)",
                    fontWeight: 800,
                    textAlign: "center",
                    marginRight: 4,
                  }}>#{i + 1}</span>
                  {t.name}
                </span>
                <span style={{ fontSize: 11.5, color: "var(--ink-900)", fontWeight: 700, fontFamily: "var(--font-mono, var(--font))" }}>
                  {t.qty.toLocaleString()} <span style={{ color: "var(--ink-400)", fontWeight: 400, fontSize: 10 }}>{t.unit}</span>
                </span>
              </div>
              <div style={{ height: 8, background: "var(--ink-50)", borderRadius: 3, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, var(--brand-500) 0%, var(--brand-600) 100%)`,
                    borderRadius: 3,
                    transition: "width 0.4s ease",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </ChartCard>
  );
}

// ============================================================================
// 公共 wrapper
// ============================================================================
function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: "16px 18px", minWidth: 0 }}>
      <header style={{ marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--ink-900)" }}>{title}</h3>
        <div style={{ fontSize: 11, color: "var(--ink-500)", marginTop: 2 }}>{subtitle}</div>
      </header>
      {children}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 14, height: 3, background: color, borderRadius: 2 }} />
      {label}
    </span>
  );
}

// 顶层容器（在 DashboardPanel 中嵌入用）
export function DashboardChartsGrid() {
  const isDesktop = useIsDesktop();
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: isDesktop ? "1.4fr 0.9fr 1fr" : "1fr",
        gap: 14,
        marginBottom: 24,
      }}
    >
      <StockTrendChart />
      <StockDistributionDonut />
      <TopOutboundBars />
    </section>
  );
}
