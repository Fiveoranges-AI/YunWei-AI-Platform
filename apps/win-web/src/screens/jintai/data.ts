// 锦泰耐火材料 AI 生产流转试点 — Mock data (frontend-only)
// All values are for demo only; no real customer / order / pricing data.

export type Risk = "high" | "medium" | "low";

export type Customer = {
  id: string;
  name: string;
  shortName: string;
  owner: string;
};

export type Order = {
  orderNo: string;
  customer: string;
  product: string;
  specification: string;
  quantity: number;
  deliveryDate: string;
  status: string;
  risk: Risk;
};

export type FlowStep = {
  name: "成型" | "烧结" | "检包";
  status: "已完成" | "进行中" | "未开始";
  plannedDate: string;
  // 成型字段
  machineNo?: string;
  moldNo?: string;
  flowCardNo?: string;
  materialNo?: string;
  materialQty?: number | null;
  remainingMaterialQty?: number | null;
  completedQty?: number | null;
  wasteBlankQty?: number | null;
  // 烧结字段
  receivedQty?: number | null;
  kilnNo?: string;
  curveNo?: string;
  loadingDate?: string;
  burningStartTime?: string;
  kilnLoadingQty?: number | null;
  kilnOutputQty?: number | null;
  defectQty?: number | null;
  // 检包字段
  qualifiedQty?: number | null;
  repairableQty?: number | null;
  minorDamageQty?: number | null;
  blackSpotQty?: number | null;
  smallChipQty?: number | null;
  largeChipQty?: number | null;
  crackQty?: number | null;
  severeDamageQty?: number | null;
  blackMaterialQty?: number | null;
  scrapQty?: number | null;
  operator?: string | null;
  remark?: string;
};

export type FlowCard = {
  flowCardNo: string;
  planNo: string;
  orderNo: string;
  customer: string;
  product: string;
  specification: string;
  plannedQty: number;
  deliveryDate: string;
  currentStep: "成型" | "烧结" | "检包" | "完成";
  status: "进行中" | "完成" | "待开始";
  risk: Risk;
  steps: FlowStep[];
};

export type ProcessParameter = {
  product: string;
  version: string;
  route: string;
  groups: { title: string; rows: { key: string; value: string }[] }[];
};

export type ExtractionCard = {
  id: string;
  kind: "合同" | "生产流转单" | "出货单" | "Excel 订单";
  source: string;
  uploadedAt: string;
  status: "待确认" | "订单已生成" | "流转单已生成" | "出货已记录";
  confidence: number;
  fields: { key: string; value: string; confidence?: number }[];
  toBeGenerated: string;
};

export type SourceRef = {
  kind: "合同" | "生产流转单" | "Excel" | "微信" | "出货单" | "工艺单" | "入库单";
  label: string;
};

export type AIBlock = {
  question: string;
  verdict: string;
  details: { key: string; value: string }[];
  evidence: SourceRef[];
  next: string[];
};

export const customers: Customer[] = [
  { id: "C001", name: "华东某耐材客户", shortName: "华东客户", owner: "销售A" },
  { id: "C002", name: "江苏某窑炉工程公司", shortName: "江苏窑炉", owner: "销售B" },
  { id: "C003", name: "浙江某外贸客户", shortName: "浙江外贸", owner: "销售C" },
];

export const orders: Order[] = [
  {
    orderNo: "SO-2026-001",
    customer: "华东客户",
    product: "高铝耐火砖",
    specification: "230×114×65",
    quantity: 12000,
    deliveryDate: "2026-06-20",
    status: "烧结中",
    risk: "high",
  },
  {
    orderNo: "SO-2026-002",
    customer: "江苏窑炉",
    product: "耐火浇注料",
    specification: "50kg/袋",
    quantity: 500,
    deliveryDate: "2026-06-25",
    status: "成型中",
    risk: "medium",
  },
  {
    orderNo: "SO-2026-003",
    customer: "浙江外贸",
    product: "莫来石砖",
    specification: "定制规格",
    quantity: 8000,
    deliveryDate: "2026-07-05",
    status: "待生产",
    risk: "low",
  },
];

export const flowCards: FlowCard[] = [
  {
    flowCardNo: "ZC-2026-015",
    planNo: "SC-2026-015",
    orderNo: "SO-2026-001",
    customer: "华东客户",
    product: "高铝耐火砖",
    specification: "230×114×65",
    plannedQty: 12000,
    deliveryDate: "2026-06-20",
    currentStep: "烧结",
    status: "进行中",
    risk: "high",
    steps: [
      {
        name: "成型",
        status: "已完成",
        plannedDate: "2026-06-12",
        machineNo: "A-03",
        moldNo: "MJ-230-01",
        flowCardNo: "LC-230-01",
        materialNo: "L-2026-061",
        materialQty: 12500,
        remainingMaterialQty: 300,
        completedQty: 12100,
        wasteBlankQty: 100,
        operator: "张三",
      },
      {
        name: "烧结",
        status: "进行中",
        plannedDate: "2026-06-16",
        receivedQty: 12000,
        kilnNo: "Y-02",
        curveNo: "QX-08",
        loadingDate: "2026-06-14",
        burningStartTime: "08:30",
        kilnLoadingQty: 12000,
        kilnOutputQty: null,
        defectQty: null,
        operator: "李四",
      },
      {
        name: "检包",
        status: "未开始",
        plannedDate: "2026-06-18",
        receivedQty: null,
        qualifiedQty: null,
        repairableQty: null,
        minorDamageQty: null,
        blackSpotQty: null,
        smallChipQty: null,
        largeChipQty: null,
        crackQty: null,
        severeDamageQty: null,
        blackMaterialQty: null,
        scrapQty: null,
        operator: null,
      },
    ],
  },
];

export const processParameter: ProcessParameter = {
  product: "高铝耐火砖（230×114×65）",
  version: "v2.3 · 2026-04 启用",
  route: "原料配比 → 混炼 → 压制成型 → 干燥 → 烧结 → 检包",
  groups: [
    {
      title: "原料配比",
      rows: [
        { key: "高铝矾土", value: "≥ 78%" },
        { key: "粘结剂", value: "5–6%" },
        { key: "添加剂", value: "1.5%" },
      ],
    },
    {
      title: "压制成型",
      rows: [
        { key: "成型压力", value: "120 MPa" },
        { key: "保压时间", value: "8 s" },
        { key: "目标坯体密度", value: "2.78 g/cm³" },
      ],
    },
    {
      title: "烧结曲线（QX-08）",
      rows: [
        { key: "升温速率", value: "60 ℃/h（≤ 800 ℃）" },
        { key: "最高温度", value: "1450 ℃" },
        { key: "保温时间", value: "6 h" },
        { key: "冷却方式", value: "随炉冷却至 200 ℃" },
      ],
    },
    {
      title: "检包标准",
      rows: [
        { key: "外观判定", value: "无裂纹 / 黑斑 / 大坍块" },
        { key: "尺寸公差", value: "±1.5 mm" },
        { key: "抽检比例", value: "5%" },
      ],
    },
  ],
};

export const initialExtractionCards: ExtractionCard[] = [
  {
    id: "ex-001",
    kind: "合同",
    source: "华东客户_设备采购合同_2026Q2.pdf",
    uploadedAt: "今天 09:12",
    status: "待确认",
    confidence: 0.94,
    fields: [
      { key: "客户名称", value: "华东某耐材客户", confidence: 0.98 },
      { key: "产品", value: "高铝耐火砖", confidence: 0.97 },
      { key: "规格", value: "230×114×65", confidence: 0.99 },
      { key: "数量", value: "12,000 块", confidence: 0.96 },
      { key: "交付日期", value: "2026-06-20", confidence: 0.93 },
      { key: "付款方式", value: "30/60/10，验收后 90 天结清", confidence: 0.86 },
    ],
    toBeGenerated: "销售订单 SO-2026-001",
  },
  {
    id: "ex-002",
    kind: "生产流转单",
    source: "ZC-2026-015 纸质流转单（手机拍照）",
    uploadedAt: "今天 10:48",
    status: "待确认",
    confidence: 0.88,
    fields: [
      { key: "计划单号", value: "SC-2026-015", confidence: 0.97 },
      { key: "产品", value: "高铝耐火砖", confidence: 0.95 },
      { key: "规格", value: "230×114×65", confidence: 0.97 },
      { key: "数量", value: "12,000", confidence: 0.94 },
      { key: "计划交期", value: "2026-06-20", confidence: 0.9 },
      { key: "成型机台", value: "A-03", confidence: 0.86 },
      { key: "成型操作人", value: "张三", confidence: 0.78 },
    ],
    toBeGenerated: "生产流转单 ZC-2026-015 + 三个工序卡（成型/烧结/检包）",
  },
  {
    id: "ex-003",
    kind: "Excel 订单",
    source: "江苏窑炉_订单明细_2026Q2.xlsx",
    uploadedAt: "今天 11:30",
    status: "待确认",
    confidence: 0.91,
    fields: [
      { key: "客户名称", value: "江苏某窑炉工程公司", confidence: 0.96 },
      { key: "产品", value: "耐火浇注料", confidence: 0.94 },
      { key: "规格", value: "50kg/袋", confidence: 0.95 },
      { key: "数量", value: "500 袋", confidence: 0.93 },
      { key: "交付日期", value: "2026-06-25", confidence: 0.89 },
    ],
    toBeGenerated: "销售订单 SO-2026-002",
  },
];

export const kpis = [
  { label: "已识别资料", value: 18, hint: "近 7 天，AI 自动识别" },
  { label: "待确认草稿", value: 6, hint: "等待人工确认入库" },
  { label: "进行中生产单", value: 12, hint: "成型 / 烧结 / 检包" },
  { label: "延期风险订单", value: 4, hint: "AI 预测交期偏离" },
  { label: "今日待出货", value: 2, hint: "成品入库 → 出货单" },
  { label: "来源可追溯率", value: 100, hint: "每条字段均可点击回溯", suffix: "%" },
];

export const workflowNodes = [
  { id: "crm", title: "CRM / 客户", desc: "华东客户已建档", status: "done" as const },
  { id: "order", title: "订单", desc: "SO-2026-001 已生成", status: "done" as const },
  { id: "wo", title: "工单", desc: "WO-2026-015", status: "done" as const },
  { id: "plan", title: "计划单", desc: "SC-2026-015", status: "done" as const },
  { id: "flow", title: "生产流转", desc: "ZC-2026-015 进行中", status: "current" as const },
  { id: "molding", title: "成型", desc: "已完成 · A-03 机台", status: "done" as const },
  { id: "sinter", title: "烧结", desc: "进行中 · Y-02 窑", status: "current" as const },
  { id: "pack", title: "检包", desc: "未开始", status: "pending" as const },
  { id: "stock", title: "成品入库", desc: "未开始", status: "pending" as const },
  { id: "ship", title: "出货", desc: "未开始", status: "pending" as const },
];

export const dailyBriefingMetrics = [
  { label: "新增订单", value: 1, sub: "SO-2026-002 已确认" },
  { label: "新增生产单", value: 2, sub: "成型 1 · 待开始 1" },
  { label: "延期风险", value: 1, sub: "ZC-2026-015 烧结" },
  { label: "今日已检包", value: 0, sub: "等待烧结出窑" },
  { label: "今日入库", value: 1, sub: "莫来石砖 · 1500 块" },
  { label: "今日出货", value: 0, sub: "暂无安排" },
];

export const dailyRisks = [
  {
    severity: "high" as Risk,
    title: "ZC-2026-015 烧结预计延期 1 天",
    detail:
      "Y-02 窑炉曲线 QX-08 当前实测温升较慢，AI 预测出窑时间将晚于计划 24 小时。客户华东已签合同，交期 06-20，下一站检包窗口被压缩。",
    suggestion: "建议生产协调今日内确认是否切换备用窑炉 Y-03，或与客户预先报备交期偏移 1 天。",
    sources: [
      { kind: "生产流转单" as const, label: "ZC-2026-015 · 烧结段" },
      { kind: "工艺单" as const, label: "QX-08 烧结曲线 v2.3" },
    ],
  },
  {
    severity: "medium" as Risk,
    title: "SO-2026-002 工艺参数与历史不一致",
    detail:
      "江苏窑炉本次订购的耐火浇注料粘结剂比例较上次配方下调 0.5%，AI 在合同中识别到客户增加了「冬季抗裂」要求，但工艺单 v2.3 未对应更新。",
    suggestion: "请技术负责人在排产前确认是否需要使用 v2.4 临时配方，并补录工艺变更记录。",
    sources: [
      { kind: "合同" as const, label: "江苏窑炉_2026Q2.pdf · §技术附录" },
      { kind: "工艺单" as const, label: "耐火浇注料 v2.3" },
    ],
  },
  {
    severity: "low" as Risk,
    title: "SO-2026-003 客户图纸尚未确认",
    detail:
      "浙江外贸客户莫来石砖为定制规格，订单录入已 3 天，但客户最新版图纸尚未在系统中归档，存在排产返工风险。",
    suggestion: "建议销售今日跟进客户最新版图纸 PDF，确认后挂载到订单 SO-2026-003。",
    sources: [{ kind: "微信" as const, label: "浙江外贸 · 林经理 · 昨天" }],
  },
];

export const presetQuestions: AIBlock[] = [
  {
    question: "SO-2026-001 现在做到哪一步了？还会按时交吗？",
    verdict:
      "订单 SO-2026-001（华东客户 · 高铝耐火砖 12,000 块）已完成成型，正在 Y-02 窑炉烧结，预计 06-17 出窑、06-18 检包、06-19 入库。AI 预测最终交付时间 06-20，与合同交期持平，但烧结环节有 24 小时风险缓冲已用尽。",
    details: [
      { key: "成型", value: "已完成 12,100 块 · 废坯 100 块 · 张三 06-12 完成" },
      { key: "烧结", value: "进行中 · Y-02 · 曲线 QX-08 · 06-14 装窑 · 李四负责" },
      { key: "检包", value: "未开始 · 计划 06-18" },
      { key: "AI 预测", value: "按时交付概率 78%，存在 1 天延期可能" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015" },
      { kind: "合同", label: "华东客户_设备采购合同_2026Q2.pdf" },
      { kind: "工艺单", label: "QX-08 烧结曲线" },
    ],
    next: [
      "确认 Y-02 窑炉今晚温升曲线是否回到正常区间。",
      "通知销售提前告知客户交期可能偏移 1 天。",
    ],
  },
  {
    question: "本月哪些订单存在延期风险？",
    verdict:
      "当前 4 单存在延期风险，影响金额合计约 ¥86 万。其中 1 单高风险（华东 SO-2026-001 烧结紧张），2 单中风险（工艺参数待确认 / 图纸未到），1 单低风险（原料到货延迟 1 天）。",
    details: [
      { key: "高风险", value: "SO-2026-001 · 华东客户 · 06-20 交期 · 烧结紧张" },
      { key: "中风险", value: "SO-2026-002 · 江苏窑炉 · 工艺参数待确认" },
      { key: "中风险", value: "SO-2026-003 · 浙江外贸 · 客户图纸未到" },
      { key: "低风险", value: "SO-2026-004 · 山东客户 · 原料晚到 1 天" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015" },
      { kind: "合同", label: "SO-2026-002 / 003 / 004" },
      { kind: "微信", label: "浙江外贸 · 林经理 · 昨天" },
    ],
    next: [
      "优先处理 SO-2026-001 烧结进度，今日内确认是否切换备用窑。",
      "技术与销售对齐 SO-2026-002 的配方变更。",
      "今日跟进 SO-2026-003 客户图纸归档。",
    ],
  },
  {
    question: "Y-02 窑炉这周烧了哪些产品？不良率多少？",
    verdict:
      "近 7 天 Y-02 窑炉共完成 5 批次烧结，使用曲线 QX-08 / QX-09 两类，平均不良率 2.1%，其中 1 批次出现轻微大坍块，已闭环处理。",
    details: [
      { key: "批次 1", value: "ZC-2026-010 · 高铝耐火砖 · QX-08 · 不良率 1.8%" },
      { key: "批次 2", value: "ZC-2026-011 · 高铝耐火砖 · QX-08 · 不良率 2.4%" },
      { key: "批次 3", value: "ZC-2026-012 · 莫来石砖 · QX-09 · 不良率 2.0%" },
      { key: "批次 4", value: "ZC-2026-013 · 高铝耐火砖 · QX-08 · 不良率 2.3%" },
      { key: "批次 5", value: "ZC-2026-014 · 高铝耐火砖 · QX-08 · 不良率 1.9%" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-010 ~ 014" },
      { kind: "工艺单", label: "QX-08 / QX-09 曲线" },
    ],
    next: [
      "查看 ZC-2026-011 不良率偏高原因（大坍块 2 块、黑斑 7 块）。",
      "下周排产时关注 QX-08 装窑数量是否偏多。",
    ],
  },
  {
    question: "高铝耐火砖近 30 天不良率怎么样？",
    verdict:
      "近 30 天高铝耐火砖（230×114×65）累计生产 4 批共 47,800 块，整体不良率 2.06%，较上月（2.45%）下降 0.39 个百分点。主要不良项：黑斑 38%、轻微坍块 27%、小裂纹 18%。",
    details: [
      { key: "总产", value: "47,800 块 / 4 批次" },
      { key: "整体不良率", value: "2.06%（上月 2.45%）" },
      { key: "黑斑", value: "占不良的 38%" },
      { key: "轻微坍块", value: "占不良的 27%" },
      { key: "小裂纹", value: "占不良的 18%" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-010 ~ 014" },
      { kind: "工艺单", label: "高铝耐火砖 v2.3" },
    ],
    next: ["检查近 30 天原料粘结剂供应商批次，黑斑占比偏高可能与粘结剂含碳有关。"],
  },
  {
    question: "华东客户今年下了多少单？还有没付的吗？",
    verdict:
      "华东客户 2026 年 1–5 月共下 6 单，合计 ¥412 万。已付 ¥298 万（5 单结清），剩余 1 单 SO-2026-001 ¥114 万按 30/60/10 付款，已收首付 ¥34.2 万，尾款待发货后 90 天内结清。",
    details: [
      { key: "订单数", value: "6 单" },
      { key: "合同金额", value: "¥412 万" },
      { key: "已收款", value: "¥298 万" },
      { key: "在途订单", value: "SO-2026-001 ¥114 万" },
      { key: "下一笔账期", value: "2026-06-20 发货后 60 天内 ¥68.4 万" },
    ],
    evidence: [
      { kind: "合同", label: "华东客户_设备采购合同_2026Q2.pdf" },
      { kind: "合同", label: "华东客户_历史订单 5 份" },
    ],
    next: ["销售跟进 SO-2026-001 发货前的首付剩余款项确认。"],
  },
  {
    question: "本周要给哪几个客户主动汇报进度？",
    verdict:
      "建议本周优先向 3 个客户主动报进度：华东客户（SO-2026-001 烧结进度 + 交期预警）、江苏窑炉（配方变更确认）、浙江外贸（图纸催复）。",
    details: [
      { key: "华东客户", value: "06-20 交期 · 烧结进度同步 · 预警可能晚 1 天" },
      { key: "江苏窑炉", value: "请客户确认冬季抗裂配方变更" },
      { key: "浙江外贸", value: "请客户尽快提交最新版图纸" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015" },
      { kind: "合同", label: "江苏窑炉 / 浙江外贸 订单" },
    ],
    next: ["销售今日内分别发出 3 条客户进度通知。"],
  },
];

export const trustItems = [
  {
    title: "数据来源 100% 可追溯",
    body: "每个 AI 生成的字段都可以点击查看原始来源（合同第几页、Excel 哪一行、微信哪一段）。",
  },
  {
    title: "AI 不直接写入业务数据",
    body: "AI 抽取后先生成「待确认草稿」，必须由对应业务人员审核后才会进入正式订单 / 生产流转单。",
  },
  {
    title: "每条字段都有置信度",
    body: "置信度低于 80% 的字段会高亮提示，提醒人工重点检查。",
  },
  {
    title: "原始资料原样保存",
    body: "合同 PDF、纸质流转单照片、Excel 原件都按客户/订单挂载留档，便于追溯与审计。",
  },
  {
    title: "权限可控",
    body: "销售、生产、检验、老板分别看到自己关心的视图；老板视图默认只读，避免误操作。",
  },
  {
    title: "工艺参数沉淀为可问数据",
    body: "工艺单录入后，老板可以用自然语言查询历史配方、曲线、不良率，不再依赖 Excel 翻找。",
  },
];

export const traceExamples = [
  {
    aiFact: "SO-2026-001 计划交期 2026-06-20",
    source: { kind: "合同" as const, label: "华东客户_设备采购合同_2026Q2.pdf · 第 3 页 §4 交付条款" },
  },
  {
    aiFact: "成型环节已完成 12,100 块 · 废坯 100 块",
    source: { kind: "生产流转单" as const, label: "ZC-2026-015 · 一、成型段 · 张三 · 06-12" },
  },
];
