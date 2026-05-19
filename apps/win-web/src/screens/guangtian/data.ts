// 光天耐火材料 AI 库存管家 — 行业 mock 数据
// 真实感：高铝砖 / 莫来石砖 / 浇注料 / 刚玉砖 等耐火材料行业 SKU
// 客户：江苏 / 浙江 长三角钢厂 + 玻璃厂 + 水泥厂下游
// 时间：2026-05-19 (今日)

export type StockStatus = "正常" | "低库存" | "缺货风险" | "已缺货" | "呆滞";

export type SkuRow = {
  code: string;
  name: string;
  spec: string;
  category: string;
  unit: string;
  location: string;
  stock: number;
  safety: number;
  status: StockStatus;
  lastIn?: string;
  lastOut?: string;
};

export const skuRows: SkuRow[] = [
  {
    code: "JT-HLZ-230-114-65",
    name: "高铝砖（标准型）",
    spec: "230×114×65 mm",
    category: "高铝砖",
    unit: "块",
    location: "A-03",
    stock: 4280,
    safety: 2000,
    status: "正常",
    lastIn: "2026-05-17",
    lastOut: "2026-05-19",
  },
  {
    code: "JT-MLS-M70",
    name: "莫来石砖",
    spec: "M70 等级 230×114×65",
    category: "莫来石砖",
    unit: "块",
    location: "A-05",
    stock: 320,
    safety: 800,
    status: "低库存",
    lastIn: "2026-05-10",
    lastOut: "2026-05-19",
  },
  {
    code: "JT-JZL-JC16",
    name: "浇注料",
    spec: "JC-16 标准型 25kg/袋",
    category: "浇注料",
    unit: "袋",
    location: "B-02",
    stock: 0,
    safety: 200,
    status: "已缺货",
    lastIn: "2026-04-28",
    lastOut: "2026-05-18",
  },
  {
    code: "JT-GZB-AL80",
    name: "刚玉砖",
    spec: "AL80 等级 230×114×65",
    category: "刚玉砖",
    unit: "块",
    location: "C-01",
    stock: 1850,
    safety: 1500,
    status: "缺货风险",
    lastIn: "2026-05-05",
    lastOut: "2026-05-19",
  },
  {
    code: "JT-HLZ-T3-150",
    name: "高铝砖（T3 异型）",
    spec: "T3 异型 150×75 mm",
    category: "高铝砖",
    unit: "块",
    location: "A-04",
    stock: 6800,
    safety: 1500,
    status: "正常",
    lastIn: "2026-05-15",
    lastOut: "2026-05-17",
  },
  {
    code: "JT-MLS-MS65",
    name: "莫来石轻质砖",
    spec: "MS-65 轻质保温",
    category: "莫来石砖",
    unit: "块",
    location: "A-06",
    stock: 95,
    safety: 0,
    status: "呆滞",
    lastIn: "2025-11-20",
    lastOut: "2025-12-15",
  },
  {
    code: "JT-JZL-JC18-LR",
    name: "低水泥浇注料",
    spec: "JC-18 低水泥 25kg/袋",
    category: "浇注料",
    unit: "袋",
    location: "B-03",
    stock: 540,
    safety: 300,
    status: "正常",
    lastIn: "2026-05-12",
    lastOut: "2026-05-19",
  },
  {
    code: "JT-GZB-AL90",
    name: "高纯刚玉砖",
    spec: "AL90 等级 230×114×65",
    category: "刚玉砖",
    unit: "块",
    location: "C-02",
    stock: 78,
    safety: 200,
    status: "低库存",
    lastIn: "2026-05-03",
    lastOut: "2026-05-18",
  },
];

// ---- 工作台风险提醒 ----
export type RiskAlert = {
  level: "high" | "medium" | "low";
  title: string;
  body: string;
  cta?: string;
};

export const dashboardAlerts: RiskAlert[] = [
  {
    level: "high",
    title: "JT-JZL-JC16 浇注料 已缺货 14 天",
    body: "客户江苏宏泰工程 SO-20260519-001 订单已下，原计划本周五出货，目前库存 0 袋 · 需补产 200 袋。",
    cta: "查看缺货预警",
  },
  {
    level: "high",
    title: "JT-MLS-M70 莫来石砖 低于安全线",
    body: "当前 320 块 / 安全 800 块 · 按近 30 天均日出货 28 块/天计，约 11 天耗尽 · 下游订单常州新材 5 月底交付。",
    cta: "去 AI 补产建议",
  },
  {
    level: "medium",
    title: "JT-GZB-AL80 刚玉砖 缺货风险",
    body: "本周 5 笔订单合计需出 2,400 块，现库存 1,850 块 · 缺口 550 块 · 建议拆单或申请加单。",
  },
  {
    level: "medium",
    title: "C-01 库位 库存盘点偏差 +12 块",
    body: "5 月 17 日盘点 vs 系统账实差 +12 块 · 张仓管已标注待复核 · AI 建议核对 2026-05-15 入库批次 P20260515-03。",
  },
  {
    level: "low",
    title: "31 个 SKU 90 天无动销（呆滞）",
    body: "占总 SKU 2.4%，合计占用库位 8 个 · AI 建议下次盘点时归集 B-05 呆滞专区。",
  },
];

// ---- KPI ----
export const kpiCards = [
  { label: "SKU 总数", value: "1,286", trend: "+12", trendLabel: "本月新增", color: "var(--brand-500)" },
  { label: "今日入库", value: "18", trend: "笔", trendLabel: "5 个 SKU", color: "var(--brand-500)" },
  { label: "今日出库", value: "23", trend: "笔", trendLabel: "9 个 SKU", color: "var(--guangtian-blue)" },
  { label: "低库存预警", value: "46", trend: "SKU", trendLabel: "占 3.6%", color: "var(--stock-low)" },
  { label: "订单缺货风险", value: "7", trend: "单", trendLabel: "本周交付", color: "var(--guangtian-red)" },
  { label: "异常记录", value: "12", trend: "条", trendLabel: "盘点偏差 / 错位", color: "var(--warn-600)" },
  { label: "呆滞 SKU", value: "31", trend: "项", trendLabel: ">90 天无动销", color: "var(--stock-dead)" },
];

// ---- Dashboard 6 快捷问题 + 1 AI 示例回答 ----
export const dashboardQuickAsks = [
  "今天哪些 SKU 库存低于安全线？",
  "哪些订单可能这周发不出去？",
  "JT-HLZ-230-114-65 这周还能出多少？",
  "近 30 天哪些 SKU 没动销？",
  "B-02 库位上有什么 SKU？",
  "AI 给我个本周补产建议",
];

export const dashboardAiSample = {
  q: "今天哪些 SKU 库存低于安全线？",
  a: "今天有 46 个 SKU 低于安全库存，其中 3 个最紧迫：\n\n1. JT-JZL-JC16 浇注料 — 已缺货 14 天 · 客户江苏宏泰工程订单待发\n2. JT-MLS-M70 莫来石砖 — 库存 320 / 安全 800 · 约 11 天耗尽\n3. JT-GZB-AL90 高纯刚玉砖 — 库存 78 / 安全 200 · 高端订单常用\n\n建议今日先排 JT-JZL-JC16 补产，AI 已草拟 200 袋补产单 (B-02 库位)，要不要看一下？",
  sources: [
    "SKU 档案 · 2026-05-19 09:30 库存快照",
    "近 30 天出货流水 · 1,247 条",
    "下游订单 SO-20260519-001 / 002",
  ],
};

// ---- 入库登记 mock ----
export const recentInbounds = [
  { time: "2026-05-19 09:42", sku: "JT-HLZ-230-114-65", name: "高铝砖", qty: "+800", unit: "块", batch: "P20260519-01", location: "A-03", op: "王主管", source: "生产入库 · SC-2026-0521" },
  { time: "2026-05-19 08:15", sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", qty: "+120", unit: "袋", batch: "P20260519-02", location: "B-03", op: "李师傅", source: "生产入库 · SC-2026-0520" },
  { time: "2026-05-18 16:30", sku: "JT-HLZ-T3-150", name: "高铝砖 T3 异型", qty: "+1,200", unit: "块", batch: "P20260518-04", location: "A-04", op: "王主管", source: "生产入库 · SC-2026-0517" },
  { time: "2026-05-18 11:05", sku: "JT-GZB-AL80", name: "刚玉砖", qty: "+300", unit: "块", batch: "P20260518-03", location: "C-01", op: "张仓管", source: "采购入库 · 江苏华峰" },
  { time: "2026-05-17 14:20", sku: "JT-HLZ-230-114-65", name: "高铝砖", qty: "+600", unit: "块", batch: "P20260517-02", location: "A-03", op: "王主管", source: "生产入库 · SC-2026-0515" },
];

export const inboundAiChecks = [
  {
    level: "warn",
    title: "批次号疑似重复",
    body: "P20260519-01 与今日早 7 点入库的 P20260519-01 重号 · 建议改为 P20260519-01B，或核对是否同一批。",
  },
  {
    level: "ok",
    title: "库位匹配产品类别",
    body: "JT-HLZ-230-114-65 应入 A 区高铝砖库位 · A-03 匹配 · ✓",
  },
];

// ---- 出库登记 mock ----
export const recentOutbounds = [
  { time: "2026-05-19 10:18", sku: "JT-HLZ-230-114-65", name: "高铝砖", qty: "-1,500", customer: "宜兴华能材料", order: "SO-20260518-007", status: "已出库", op: "张仓管" },
  { time: "2026-05-19 09:45", sku: "JT-MLS-M70", name: "莫来石砖", qty: "-200", customer: "常州新材", order: "SO-20260517-012", status: "部分出库", op: "李师傅" },
  { time: "2026-05-19 08:50", sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", qty: "-80", customer: "江苏宏泰工程", order: "SO-20260519-002", status: "已出库", op: "张仓管" },
  { time: "2026-05-19 08:00", sku: "JT-JZL-JC16", name: "浇注料 JC-16", qty: "-0", customer: "江苏宏泰工程", order: "SO-20260519-001", status: "库存不足", op: "—" },
];

export const outboundAiAlerts = [
  {
    level: "danger",
    title: "SO-20260519-001 浇注料 JC-16 库存不足",
    body: "订单需 200 袋，当前库存 0 袋 · 建议联系生产排产 (预计 5 月 22 日补产 200 袋出炉)，或与客户协商分批发货。",
  },
  {
    level: "warn",
    title: "JT-MLS-M70 出货 200 块后剩 120 块",
    body: "已低于安全线 800 块 · AI 建议同步触发补产单。",
  },
];

// ---- 库存流水 ----
export const ledgerRows = [
  { time: "2026-05-19 10:18", op: "出库", sku: "JT-HLZ-230-114-65", name: "高铝砖", delta: "-1,500", before: 5780, after: 4280, ref: "SO-20260518-007 · 宜兴华能", user: "张仓管", note: "" },
  { time: "2026-05-19 09:45", op: "出库", sku: "JT-MLS-M70", name: "莫来石砖", delta: "-200", before: 520, after: 320, ref: "SO-20260517-012 · 常州新材", user: "李师傅", note: "部分出库 · 余 50 待补" },
  { time: "2026-05-19 09:42", op: "入库", sku: "JT-HLZ-230-114-65", name: "高铝砖", delta: "+800", before: 4980, after: 5780, ref: "SC-2026-0521 · 生产", user: "王主管", note: "P20260519-01 批次" },
  { time: "2026-05-19 08:50", op: "出库", sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", delta: "-80", before: 620, after: 540, ref: "SO-20260519-002 · 江苏宏泰", user: "张仓管", note: "" },
  { time: "2026-05-19 08:15", op: "入库", sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", delta: "+120", before: 500, after: 620, ref: "SC-2026-0520 · 生产", user: "李师傅", note: "" },
  { time: "2026-05-18 16:30", op: "调拨", sku: "JT-HLZ-T3-150", name: "高铝砖 T3", delta: "—", before: 5600, after: 6800, ref: "B-05 → A-04", user: "张仓管", note: "从呆滞区移回常备区 +1,200" },
  { time: "2026-05-18 14:20", op: "盘点", sku: "JT-GZB-AL80", name: "刚玉砖", delta: "+12", before: 1838, after: 1850, ref: "盘点单 PD-20260518", user: "张仓管", note: "盘点偏差 · 待复核" },
  { time: "2026-05-18 11:05", op: "入库", sku: "JT-GZB-AL80", name: "刚玉砖", delta: "+300", before: 1538, after: 1838, ref: "PO-2026-0089 · 江苏华峰", user: "张仓管", note: "采购入库" },
];

export const ledgerAiAnomalies = [
  {
    title: "盘点偏差 +12 块（JT-GZB-AL80）",
    body: "2026-05-18 盘点账实差 +12 块 · AI 比对 2026-05-15 入库批次 P20260515-03 入库 312 块，疑似漏记 12 块。建议张仓管核对采购入库单 PO-2026-0089 实物清点。",
  },
  {
    title: "调拨方向异常（JT-HLZ-T3-150）",
    body: "本品从 B-05 呆滞区调回 A-04 常备区 1,200 块 · 与 90 天无动销标签矛盾 · AI 建议核对此批是否为新采购错放入呆滞区。",
  },
  {
    title: "JT-MLS-M70 部分出库未跟进",
    body: "SO-20260517-012 余 50 块待补 · 已挂 36 小时无补出库记录 · 建议李师傅今日跟进客户常州新材确认是否继续补发。",
  },
];

// ---- 订单缺货预警 ----
export type ShortageOrder = {
  id: string;
  customer: string;
  deliveryDate: string;
  level: "high" | "medium" | "low";
  totalValue: string;
  items: { sku: string; name: string; needed: number; stock: number; gap: number; unit: string }[];
  aiSuggestion: string;
};

export const shortageOrders: ShortageOrder[] = [
  {
    id: "SO-20260519-001",
    customer: "江苏宏泰工程有限公司",
    deliveryDate: "2026-05-22 (周五)",
    level: "high",
    totalValue: "¥38,600",
    items: [
      { sku: "JT-JZL-JC16", name: "浇注料 JC-16", needed: 200, stock: 0, gap: 200, unit: "袋" },
      { sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", needed: 60, stock: 540, gap: 0, unit: "袋" },
    ],
    aiSuggestion: "JC-16 完全缺货。建议：① 立即排产 200 袋（预计 5 月 21 日出炉，5 月 22 日勉强可发）；② 与江苏宏泰沟通先发 JT-JZL-JC18-LR 60 袋，JC-16 推迟 3 天；③ 长期对策：JC-16 历史月均出库 350 袋，应将安全库存从 200 → 400 袋。",
  },
  {
    id: "SO-20260519-002",
    customer: "江苏宏泰工程有限公司",
    deliveryDate: "2026-05-25 (下周一)",
    level: "low",
    totalValue: "¥6,200",
    items: [
      { sku: "JT-JZL-JC18-LR", name: "低水泥浇注料", needed: 80, stock: 540, gap: 0, unit: "袋" },
    ],
    aiSuggestion: "库存充足，按期可发。建议安排 5 月 23 日发货，赶在客户上午签收。",
  },
  {
    id: "SO-20260519-003",
    customer: "常州新材科技有限公司",
    deliveryDate: "2026-05-28 (下周四)",
    level: "high",
    totalValue: "¥62,400",
    items: [
      { sku: "JT-MLS-M70", name: "莫来石砖 M70", needed: 500, stock: 320, gap: 180, unit: "块" },
      { sku: "JT-GZB-AL80", name: "刚玉砖 AL80", needed: 800, stock: 1850, gap: 0, unit: "块" },
      { sku: "JT-GZB-AL90", name: "高纯刚玉砖 AL90", needed: 150, stock: 78, gap: 72, unit: "块" },
    ],
    aiSuggestion: "两个 SKU 缺货：M70 缺 180、AL90 缺 72。建议：① M70 排产 180 块（4 天工期，5 月 23 日可入库）；② AL90 此型号生产周期 7 天，建议立即排产 + 与常州新材协商分两批发货（5 月 28 日先发库存 + 6 月 2 日补 72 块）。客户为长期 A 类，备注沟通态度温和。",
  },
];

// ---- AI 补产建议 ----
export type ReplenishmentItem = {
  sku: string;
  name: string;
  currentStock: number;
  safety: number;
  suggestQty: number;
  unit: string;
  priority: "高" | "中" | "低";
  reason: string;
  estDate: string;
};

export const replenishmentItems: ReplenishmentItem[] = [
  {
    sku: "JT-JZL-JC16",
    name: "浇注料 JC-16",
    currentStock: 0,
    safety: 200,
    suggestQty: 400,
    unit: "袋",
    priority: "高",
    reason: "已缺货 14 天 · 江苏宏泰订单待发 200 袋 · 历史月均 350 袋 · 建议直接补到 400（含安全库存翻倍）",
    estDate: "2026-05-22",
  },
  {
    sku: "JT-MLS-M70",
    name: "莫来石砖 M70",
    currentStock: 320,
    safety: 800,
    suggestQty: 600,
    unit: "块",
    priority: "高",
    reason: "本周常州新材订单需 500 块 · 当前 320 · 至少补 600 才能既发货又留安全库存",
    estDate: "2026-05-23",
  },
  {
    sku: "JT-GZB-AL90",
    name: "高纯刚玉砖 AL90",
    currentStock: 78,
    safety: 200,
    suggestQty: 250,
    unit: "块",
    priority: "中",
    reason: "高端 SKU · 生产周期 7 天 · 常州新材下周需 150 块 · 建议本周排产",
    estDate: "2026-05-26",
  },
];

// ---- 问问 AI 库存管家 ----
export const askPresets = [
  "今天哪些订单可能发不出去？",
  "JT-HLZ-230-114-65 这周可以再出多少？",
  "哪些 SKU 应该补产？",
  "近 30 天哪些 SKU 没动销？",
  "C-01 库位现在有什么货？",
  "JC-16 浇注料过去半年的出货趋势？",
  "本月低库存预警有多少？",
  "给我生成今天的库存日报",
];

export const askSampleConversation = [
  {
    role: "user" as const,
    text: "今天哪些订单可能发不出去？",
  },
  {
    role: "ai" as const,
    text: "今天有 3 笔订单存在交付风险，其中 1 笔高风险：\n\n🔴 高风险 1 笔\n• SO-20260519-001 · 江苏宏泰工程 · 2026-05-22 交付 · 缺浇注料 JC-16 200 袋（库存 0）\n\n🟡 中等风险 0 笔\n\n🟢 关注 2 笔\n• SO-20260517-012 · 常州新材 · 莫来石 M70 部分出库后剩 50 块未补 — 36 小时无动作\n• SO-20260519-003 · 常州新材 · 下周四交付 · 缺 M70 180 + AL90 72\n\n建议优先处理 SO-20260519-001，AI 已草拟 400 袋 JC-16 补产单（B-02 库位），点这里查看。",
    sources: [
      { label: "下游订单表 · 实时拉取", count: 7 },
      { label: "SKU 库存快照 · 2026-05-19 10:18", count: 1286 },
      { label: "近 7 天出货流水", count: 156 },
    ],
  },
];

// ---- AI 库存日报 ----
export const dailyReport = {
  date: "2026-05-19",
  weekday: "周二",
  generatedAt: "2026-05-19 18:30",
  summary: "今日入库 18 笔（5 个 SKU），出库 23 笔（9 个 SKU）。1 笔订单已确认延期发货（缺 JC-16 浇注料），2 笔订单需关注。库存周转良好，46 个 SKU 低于安全线，AI 建议本周补产 3 个紧迫 SKU。",
  sections: [
    {
      title: "1. 今日入出库",
      items: [
        "入库 18 笔（合计 +2,820 块/袋）— 含生产入库 12 笔 / 采购入库 6 笔",
        "出库 23 笔（合计 -1,780 块/袋）— 含 7 个下游订单",
        "净流入 +1,040 — 库存总量上涨 0.08%",
      ],
    },
    {
      title: "2. 缺货 & 风险",
      items: [
        "🔴 SO-20260519-001 江苏宏泰 浇注料 JC-16 完全缺货（缺 200 袋）— 已草拟补产单",
        "🟡 JT-MLS-M70 莫来石砖 320 块（安全 800）— 11 天耗尽预期",
        "🟡 JT-GZB-AL90 高纯刚玉砖 78 块（安全 200）— 高端订单常用",
      ],
    },
    {
      title: "3. AI 补产建议",
      items: [
        "JC-16 浇注料 400 袋（5 月 22 日出炉）",
        "M70 莫来石砖 600 块（5 月 23 日出炉）",
        "AL90 高纯刚玉砖 250 块（5 月 26 日出炉）",
        "合计补产计划 → 已挂工艺组排程",
      ],
    },
    {
      title: "4. 库存异常",
      items: [
        "C-01 库位盘点差 +12 块（JT-GZB-AL80）— 张仓管标注待复核",
        "B-05 → A-04 调拨 1,200 块异常方向 — 与呆滞标签矛盾",
        "SO-20260517-012 部分出库余 50 块挂 36 小时无跟进",
      ],
    },
    {
      title: "5. 呆滞 SKU 提醒",
      items: [
        "31 个 SKU 90 天无动销 · 占总 2.4%",
        "占用 8 个库位 · 建议下次盘点归集 B-05 专区",
        "其中 JT-MLS-MS65 莫来石轻质砖 占用面积最大",
      ],
    },
    {
      title: "6. 库位使用情况",
      items: [
        "A 区（高铝砖）— 占用 76%（紧张）· 建议腾出 A-07 空位",
        "B 区（浇注料）— 占用 42%（宽裕）",
        "C 区（刚玉砖）— 占用 58%（正常）",
      ],
    },
    {
      title: "7. 下游订单展望（7 日）",
      items: [
        "本周剩余 4 个工作日，待发订单 12 笔（含 SO-20260519-001 高风险）",
        "下周一 SO-20260519-002 江苏宏泰 60 袋 · 可顺利发货",
        "下周四 SO-20260519-003 常州新材 — 需赶补 M70 / AL90",
      ],
    },
    {
      title: "8. 操作绩效（管理参考）",
      items: [
        "王主管（入库主力）— 12 笔入库 · 100% 批次号合规",
        "张仓管 — 8 笔出库 + 1 笔盘点 · 1 笔 +12 块偏差待复核",
        "李师傅 — 6 笔入库 / 3 笔出库 · 1 笔部分出库需跟进",
      ],
    },
  ],
};
