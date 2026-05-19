// 锦泰耐火材料 AI 生产流转试点 — Mock data (frontend-only)
// 客户：宜兴市锦泰耐火材料有限公司（成立 2006，丁蜀镇大港村）
// 主营：窑炉耐火材料制品（承烧板/推板/支柱/匣钵）+ 工业陶瓷
// 下游：锂电池正极烧结、磁性材料、电子陶瓷（MLCC）、粉末冶金、稀土
// 所有客户名、订单号、金额均为演示用半真实数据，未对应任何实盘交易。

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
  status: "待确认" | "已确认" | "已驳回" | "订单已生成" | "流转单已生成" | "出货已记录";
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
  { id: "C001", name: "容百新能源科技股份有限公司", shortName: "容百锂电", owner: "销售 · 王经理" },
  { id: "C002", name: "横店集团东磁股份有限公司", shortName: "横店东磁", owner: "销售 · 周经理" },
  { id: "C003", name: "广东风华高新科技股份有限公司", shortName: "风华高科", owner: "销售 · 林经理" },
  { id: "C004", name: "厦钨新能源材料股份有限公司", shortName: "厦钨新能", owner: "销售 · 王经理" },
];

export const orders: Order[] = [
  {
    orderNo: "SO-2026-001",
    customer: "容百锂电",
    product: "刚玉莫来石承烧板",
    specification: "330×330×16 mm",
    quantity: 18000,
    deliveryDate: "2026-06-20",
    status: "烧结中",
    risk: "high",
  },
  {
    orderNo: "SO-2026-002",
    customer: "横店东磁",
    product: "氧化铝匣钵",
    specification: "300×220×100 mm",
    quantity: 4500,
    deliveryDate: "2026-06-25",
    status: "成型中",
    risk: "medium",
  },
  {
    orderNo: "SO-2026-003",
    customer: "风华高科",
    product: "堇青石莫来石承烧板",
    specification: "260×260×10 mm（MLCC 专用）",
    quantity: 22000,
    deliveryDate: "2026-07-05",
    status: "待生产",
    risk: "low",
  },
  {
    orderNo: "SO-2026-004",
    customer: "厦钨新能",
    product: "碳化硅推板",
    specification: "300×300×20 mm",
    quantity: 2400,
    deliveryDate: "2026-07-12",
    status: "排产中",
    risk: "low",
  },
];

export const flowCards: FlowCard[] = [
  {
    flowCardNo: "ZC-2026-014",
    planNo: "SC-2026-014",
    orderNo: "SO-2026-014",
    customer: "容百锂电",
    product: "刚玉莫来石承烧板",
    specification: "330×330×16 mm",
    plannedQty: 12000,
    deliveryDate: "2026-05-10",
    currentStep: "完成",
    status: "完成",
    risk: "low",
    steps: [
      {
        name: "成型",
        status: "已完成",
        plannedDate: "2026-04-25",
        machineNo: "等静压 IP-03",
        moldNo: "MJ-330-NCM",
        flowCardNo: "LC-2026-014-A",
        materialNo: "GM78-2026-051",
        materialQty: 12500,
        remainingMaterialQty: 280,
        completedQty: 12100,
        wasteBlankQty: 120,
        operator: "成型组 · 张师傅",
      },
      {
        name: "烧结",
        status: "已完成",
        plannedDate: "2026-04-30",
        receivedQty: 12100,
        kilnNo: "梭式窑 SK-02",
        curveNo: "LB-1580",
        loadingDate: "2026-04-28",
        burningStartTime: "07:50",
        kilnLoadingQty: 12080,
        kilnOutputQty: 11950,
        defectQty: 130,
        operator: "烧成组 · 李师傅",
      },
      {
        name: "检包",
        status: "已完成",
        plannedDate: "2026-05-04",
        receivedQty: 11950,
        qualifiedQty: 11722,
        repairableQty: 86,
        minorDamageQty: 42,
        smallChipQty: 35,
        largeChipQty: 4,
        blackSpotQty: 28,
        crackQty: 12,
        severeDamageQty: 6,
        blackMaterialQty: 8,
        scrapQty: 7,
        operator: "检包组 · 周师傅",
        remark: "整体不良率 1.91% · 合格品全部 5% 抽检通过 · 已交容百宁波",
      },
    ],
  },
  {
    flowCardNo: "ZC-2026-015",
    planNo: "SC-2026-015",
    orderNo: "SO-2026-001",
    customer: "容百锂电",
    product: "刚玉莫来石承烧板",
    specification: "330×330×16 mm（NCM811 高镍专用）",
    plannedQty: 18000,
    deliveryDate: "2026-06-20",
    currentStep: "烧结",
    status: "进行中",
    risk: "high",
    steps: [
      {
        name: "成型",
        status: "已完成",
        plannedDate: "2026-06-12",
        machineNo: "等静压 IP-03",
        moldNo: "MJ-330-NCM",
        flowCardNo: "LC-2026-015-A",
        materialNo: "GM78-2026-061",
        materialQty: 18800,
        remainingMaterialQty: 320,
        completedQty: 18420,
        wasteBlankQty: 60,
        operator: "成型组 · 张师傅",
      },
      {
        name: "烧结",
        status: "进行中",
        plannedDate: "2026-06-16",
        receivedQty: 18420,
        kilnNo: "梭式窑 SK-02",
        curveNo: "LB-1580（锂电承烧板专用曲线）",
        loadingDate: "2026-06-14",
        burningStartTime: "08:30",
        kilnLoadingQty: 18400,
        kilnOutputQty: null,
        defectQty: null,
        operator: "烧成组 · 李师傅",
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
  product: "刚玉莫来石承烧板（330×330×16 mm · 锂电正极 NCM 烧结专用）",
  version: "v2.3 · 2026-04 启用",
  route: "原料配比 → 球磨混炼 → 等静压成型 → 110 ℃ 干燥 → 高温烧结（LB-1580）→ 精磨 → 检包",
  groups: [
    {
      title: "原料配比",
      rows: [
        { key: "电熔白刚玉（α-Al₂O₃）", value: "≥ 70%" },
        { key: "电熔莫来石（3Al₂O₃·2SiO₂）", value: "20–25%" },
        { key: "粘结剂（PVA + 糊精）", value: "4–5%" },
        { key: "成孔剂", value: "1.5%" },
      ],
    },
    {
      title: "等静压成型",
      rows: [
        { key: "成型压力", value: "180 MPa" },
        { key: "保压时间", value: "60 s" },
        { key: "目标坯体密度", value: "2.78 g/cm³" },
        { key: "尺寸公差（坯）", value: "±0.8 mm" },
      ],
    },
    {
      title: "高温烧结 · 曲线 LB-1580",
      rows: [
        { key: "升温速率（≤ 800 ℃）", value: "60 ℃/h" },
        { key: "升温速率（800–1580 ℃）", value: "35 ℃/h" },
        { key: "最高烧成温度", value: "1580 ℃" },
        { key: "保温时间", value: "6 h" },
        { key: "降温方式", value: "随炉冷却至 200 ℃" },
        { key: "总周期", value: "约 72 h" },
      ],
    },
    {
      title: "成品技术指标",
      rows: [
        { key: "体积密度", value: "≥ 2.72 g/cm³" },
        { key: "显气孔率", value: "≤ 18%" },
        { key: "常温抗折强度", value: "≥ 45 MPa" },
        { key: "抗热震性（1100 ℃ ⇌ 室温）", value: "≥ 30 次不裂" },
        { key: "尺寸公差（成品）", value: "±0.3 mm" },
        { key: "翘曲度", value: "≤ 0.5%" },
      ],
    },
    {
      title: "检包标准",
      rows: [
        { key: "外观判定", value: "无裂纹 / 黑斑 / 边角缺损 / 翘曲超差" },
        { key: "抽检比例", value: "首批 100%，量产 5%" },
        { key: "客户验收", value: "容百二供 SIP-Li-04 标准" },
      ],
    },
  ],
};

export const initialExtractionCards: ExtractionCard[] = [
  {
    id: "ex-001",
    kind: "合同",
    source: "容百锂电_承烧板采购合同_2026Q2.pdf",
    uploadedAt: "今天 09:12",
    status: "待确认",
    confidence: 0.94,
    fields: [
      { key: "客户名称", value: "容百新能源科技股份有限公司", confidence: 0.98 },
      { key: "产品", value: "刚玉莫来石承烧板", confidence: 0.97 },
      { key: "规格", value: "330×330×16 mm", confidence: 0.99 },
      { key: "数量", value: "18,000 块", confidence: 0.96 },
      { key: "单价", value: "¥182 / 块（含税）", confidence: 0.94 },
      { key: "交付日期", value: "2026-06-20", confidence: 0.93 },
      { key: "付款方式", value: "30/60/10，验收后 90 天结清", confidence: 0.86 },
      { key: "技术标准", value: "容百二供 SIP-Li-04（NCM811 高镍兼容）", confidence: 0.78 },
    ],
    toBeGenerated: "销售订单 SO-2026-001 · ¥327.6 万",
  },
  {
    id: "ex-002",
    kind: "生产流转单",
    source: "ZC-2026-015 纸质流转单（车间手机拍照）",
    uploadedAt: "今天 10:48",
    status: "待确认",
    confidence: 0.88,
    fields: [
      { key: "计划单号", value: "SC-2026-015", confidence: 0.97 },
      { key: "产品", value: "刚玉莫来石承烧板", confidence: 0.95 },
      { key: "规格", value: "330×330×16 mm", confidence: 0.97 },
      { key: "数量", value: "18,000", confidence: 0.94 },
      { key: "计划交期", value: "2026-06-20", confidence: 0.9 },
      { key: "成型机台", value: "等静压 IP-03", confidence: 0.86 },
      { key: "烧结窑炉", value: "梭式窑 SK-02", confidence: 0.83 },
      { key: "烧成曲线", value: "LB-1580", confidence: 0.84 },
      { key: "成型操作人", value: "张师傅", confidence: 0.74 },
    ],
    toBeGenerated: "生产流转单 ZC-2026-015 + 三个工序卡（成型/烧结/检包）",
  },
  {
    id: "ex-003",
    kind: "Excel 订单",
    source: "横店东磁_磁材烧结匣钵_订单明细_2026Q2.xlsx",
    uploadedAt: "今天 11:30",
    status: "待确认",
    confidence: 0.91,
    fields: [
      { key: "客户名称", value: "横店集团东磁股份有限公司", confidence: 0.96 },
      { key: "产品", value: "氧化铝匣钵", confidence: 0.94 },
      { key: "规格", value: "300×220×100 mm", confidence: 0.95 },
      { key: "数量", value: "4,500 个", confidence: 0.93 },
      { key: "单价", value: "¥235 / 个", confidence: 0.91 },
      { key: "交付日期", value: "2026-06-25", confidence: 0.89 },
      { key: "应用工序", value: "永磁铁氧体二次烧结", confidence: 0.82 },
    ],
    toBeGenerated: "销售订单 SO-2026-002 · ¥105.75 万",
  },
];

export const kpis = [
  { label: "已识别资料", value: 24, hint: "近 7 天，AI 自动识别合同 / 流转单 / Excel" },
  { label: "待确认草稿", value: 6, hint: "等待销售 / 生产人工确认入库" },
  { label: "进行中生产单", value: 12, hint: "成型 / 烧结 / 检包" },
  { label: "延期风险订单", value: 3, hint: "AI 预测交期偏离，覆盖锂电 / 磁材 / MLCC" },
  { label: "今日待出货", value: 2, hint: "成品入库 → 出货单" },
  { label: "来源可追溯率", value: 100, hint: "每条字段均可点击回溯原件", suffix: "%" },
];

export const workflowNodes = [
  { id: "crm", title: "CRM / 客户", desc: "容百锂电已建档", status: "done" as const },
  { id: "order", title: "订单", desc: "SO-2026-001 已生成", status: "done" as const },
  { id: "wo", title: "工单", desc: "WO-2026-015", status: "done" as const },
  { id: "plan", title: "计划单", desc: "SC-2026-015 · 18,000 块", status: "done" as const },
  { id: "flow", title: "生产流转", desc: "ZC-2026-015 进行中", status: "current" as const },
  { id: "molding", title: "成型", desc: "已完成 · IP-03 等静压", status: "done" as const },
  { id: "sinter", title: "烧结", desc: "进行中 · SK-02 · LB-1580 曲线", status: "current" as const },
  { id: "pack", title: "检包", desc: "未开始", status: "pending" as const },
  { id: "stock", title: "成品入库", desc: "未开始", status: "pending" as const },
  { id: "ship", title: "出货", desc: "未开始 · 容百宁波厂", status: "pending" as const },
];

export const dailyBriefingMetrics = [
  { label: "新增订单", value: 1, sub: "SO-2026-002 横店东磁 已确认" },
  { label: "新增生产单", value: 2, sub: "成型 1 · 待开始 1" },
  { label: "延期风险", value: 1, sub: "ZC-2026-015 锂电承烧板烧结" },
  { label: "今日已检包", value: 0, sub: "等待 SK-02 出窑" },
  { label: "今日入库", value: 1, sub: "氧化铝匣钵 · 1,500 个" },
  { label: "今日出货", value: 0, sub: "暂无安排" },
];

export const dailyRisks = [
  {
    severity: "high" as Risk,
    title: "ZC-2026-015 锂电承烧板烧结预计延期 1 天",
    detail:
      "梭式窑 SK-02 当前烧成曲线 LB-1580 在 1450–1580 ℃ 段温升偏慢约 8 ℃/h，AI 预测出窑时间将晚于计划 24 小时。客户容百锂电合同交期 06-20，下一站精磨 + 检包窗口被压缩；这批承烧板将进入容百宁波正极线 NCM811 高镍二烧工位，客户对到货延期敏感。",
    suggestion:
      "建议生产部今日内决策：① 切换备用梭式窑 SK-03（同曲线已校验）；② 或与容百仓储经理预先报备交期可能偏移 1 天，避免触发客户产线 PPM 罚则。",
    sources: [
      { kind: "生产流转单" as const, label: "ZC-2026-015 · 烧结段实时温升记录" },
      { kind: "工艺单" as const, label: "LB-1580 烧结曲线 v2.3" },
      { kind: "合同" as const, label: "容百锂电_承烧板采购合同_2026Q2.pdf · §5 交付条款" },
    ],
  },
  {
    severity: "medium" as Risk,
    title: "SO-2026-002 氧化铝匣钵 工艺参数与上批不一致",
    detail:
      "横店东磁本次订购的氧化铝匣钵在合同技术附录中明确「永磁铁氧体二烧最高温度 1320 ℃，要求 ≥ 50 次抗热震不裂」，而锦泰工艺单 v2.3 的氧化铝匣钵抗热震指标为 ≥ 30 次。AI 已比对历史 5 批同客户订单，未发现工艺单更新。",
    suggestion:
      "请技术负责人在排产前确认是否采用 v2.4 临时配方（提高电熔莫来石占比、降低 Al₂O₃ 含量），并补录工艺变更记录归档。",
    sources: [
      { kind: "合同" as const, label: "横店东磁_2026Q2.pdf · §技术附录 4.2 抗热震指标" },
      { kind: "工艺单" as const, label: "氧化铝匣钵 v2.3" },
    ],
  },
  {
    severity: "low" as Risk,
    title: "SO-2026-003 风华高科 MLCC 承烧板客户图纸尚未确认",
    detail:
      "风华高科 MLCC 用堇青石莫来石承烧板为定制规格（260×260×10 mm，要求开 12×12 通气孔阵列），订单录入已 3 天，但客户最新版图纸（含通气孔分布坐标）尚未在系统中归档，存在排产返工风险。",
    suggestion:
      "建议销售今日跟进风华高科 张工 确认最新图纸 PDF，确认后挂载到订单 SO-2026-003。",
    sources: [{ kind: "微信" as const, label: "风华高科 · 张工 · 昨天 16:42" }],
  },
];

export const presetQuestions: AIBlock[] = [
  {
    question: "容百锂电 SO-2026-001 这批承烧板现在做到哪了？还能按时交吗？",
    verdict:
      "订单 SO-2026-001（容百锂电 · 刚玉莫来石承烧板 330×330×16 · 18,000 块 · ¥327.6 万）成型已完成 18,420 块（含 60 块废坯），目前在梭式窑 SK-02 烧结中，曲线 LB-1580 已运行 38 小时。AI 预测出窑 06-17 晚、精磨检包 06-18、入库 06-19、发货 06-19 夜。最终交付 06-20 上午到容百宁波，按时交付概率 78%，存在 1 天延期可能。",
    details: [
      { key: "成型", value: "已完成 18,420 块 · 废坯 60 块 · 张师傅 06-12 完成" },
      { key: "烧结", value: "进行中 · SK-02 · LB-1580 曲线 · 06-14 08:30 装窑 · 李师傅" },
      { key: "检包", value: "未开始 · 计划 06-18 · 抽检 5%" },
      { key: "出货", value: "目的地：容百锂电宁波厂 · 顺丰物流" },
      { key: "AI 预测", value: "按时交付概率 78%，存在 1 天延期可能" },
      { key: "金额", value: "¥327.6 万（已收首付 ¥98.28 万）" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015 · 三道工序" },
      { kind: "合同", label: "容百锂电_承烧板采购合同_2026Q2.pdf" },
      { kind: "工艺单", label: "LB-1580 烧结曲线 v2.3" },
    ],
    next: [
      "确认 SK-02 窑炉今晚温升曲线是否回到 35 ℃/h 正常区间。",
      "若仍偏慢，今日内决策是否切换备用梭式窑 SK-03（同曲线已校验）。",
      "通知销售王经理提前告知容百仓储经理交期可能偏移 1 天。",
    ],
  },
  {
    question: "本月哪些订单存在延期风险？影响多少金额？",
    verdict:
      "当前 3 单存在延期风险，影响金额合计约 ¥456 万。其中 1 单高风险（容百 SO-2026-001 烧结紧张 ¥327.6 万），1 单中风险（横店东磁 SO-2026-002 工艺参数待确认 ¥105.75 万），1 单低风险（风华高科 SO-2026-003 客户图纸未到 ¥22 万）。",
    details: [
      { key: "高风险", value: "SO-2026-001 · 容百锂电 · 承烧板 · 06-20 交期 · 烧结紧张 · ¥327.6 万" },
      { key: "中风险", value: "SO-2026-002 · 横店东磁 · 氧化铝匣钵 · 工艺参数待确认 · ¥105.75 万" },
      { key: "低风险", value: "SO-2026-003 · 风华高科 · MLCC 承烧板 · 客户图纸未到 · ¥22 万" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015" },
      { kind: "合同", label: "SO-2026-001 / 002 / 003" },
      { kind: "微信", label: "风华高科 · 张工 · 昨天" },
    ],
    next: [
      "优先处理 SO-2026-001 烧结进度，今日内确认是否切换备用窑。",
      "技术与销售对齐 SO-2026-002 抗热震配方变更（v2.3 → v2.4）。",
      "今日跟进 SO-2026-003 风华高科客户图纸归档。",
    ],
  },
  {
    question: "梭式窑 SK-02 这周烧了哪些产品？不良率多少？",
    verdict:
      "近 7 天梭式窑 SK-02 共完成 5 批次烧结（LB-1580 / LB-1620 两类曲线），合计 64,200 块/个产品，平均不良率 2.1%。其中 1 批次（容百锂电 ZC-2026-011）出现轻微翘曲超差 4 件，已闭环挑选。本周窑炉利用率 92%。",
    details: [
      { key: "批次 1", value: "ZC-2026-010 · 容百锂电承烧板 · LB-1580 · 不良率 1.8%" },
      { key: "批次 2", value: "ZC-2026-011 · 容百锂电承烧板 · LB-1580 · 不良率 2.4%（翘曲 4 件）" },
      { key: "批次 3", value: "ZC-2026-012 · 厦钨新能匣钵 · LB-1620 · 不良率 2.0%" },
      { key: "批次 4", value: "ZC-2026-013 · 横店东磁匣钵 · LB-1620 · 不良率 2.3%" },
      { key: "批次 5", value: "ZC-2026-014 · 容百锂电承烧板 · LB-1580 · 不良率 1.9%" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-010 ~ 014" },
      { kind: "工艺单", label: "LB-1580 / LB-1620 曲线" },
    ],
    next: [
      "查看 ZC-2026-011 翘曲偏高原因（4 件均位于窑车上层，怀疑温场不均）。",
      "下周排产时关注 LB-1580 装窑数量是否偏多，建议每车 ≤ 380 块。",
    ],
  },
  {
    question: "刚玉莫来石承烧板近 30 天不良率怎么样？",
    verdict:
      "近 30 天刚玉莫来石承烧板（330×330×16 容百规格）累计生产 4 批共 72,400 块，整体不良率 2.06%，较上月（2.45%）下降 0.39 个百分点。主要不良项：翘曲超差 36%、边角小掉块 27%、黑斑 18%、显气孔率偏高 11%。",
    details: [
      { key: "总产", value: "72,400 块 / 4 批次" },
      { key: "整体不良率", value: "2.06%（上月 2.45%）" },
      { key: "翘曲超差", value: "占不良的 36%" },
      { key: "边角小掉块", value: "占不良的 27%" },
      { key: "黑斑", value: "占不良的 18%" },
      { key: "显气孔率偏高", value: "占不良的 11%（疑似坯体密度不稳）" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-010 ~ 014" },
      { kind: "工艺单", label: "刚玉莫来石承烧板 v2.3" },
    ],
    next: [
      "检查近 30 天电熔白刚玉供应商批次（怀疑 0521 批粒度分布偏粗，影响坯体密度）。",
      "翘曲超差集中在窑车上层，建议下批次调整装窑高度限制至 380 块/车。",
    ],
  },
  {
    question: "容百锂电今年下了多少单？还有没付的吗？",
    verdict:
      "容百锂电 2026 年 1–5 月共下 5 单刚玉莫来石承烧板，合计 ¥1,418 万。已付 ¥1,063.5 万（4 单结清 + SO-2026-001 首付 30%），剩余 ¥354.5 万：SO-2026-001 尾款按 60/10 分两笔，发货 60 天后 ¥196.56 万、验收 90 天后 ¥32.76 万。",
    details: [
      { key: "订单数", value: "5 单 · 全部为 330×330×16 承烧板" },
      { key: "合同金额", value: "¥1,418 万（年化估计 ¥3,400+ 万）" },
      { key: "已收款", value: "¥1,063.5 万（4 单已结清）" },
      { key: "在途订单", value: "SO-2026-001 ¥327.6 万（首付已收）" },
      { key: "下一笔账期", value: "2026-08-19（发货 60 天后）¥196.56 万" },
    ],
    evidence: [
      { kind: "合同", label: "容百锂电_承烧板采购合同_2026Q2.pdf" },
      { kind: "合同", label: "容百锂电_历史订单 4 份" },
    ],
    next: [
      "销售王经理跟进 SO-2026-001 发货前的客户验收节奏，确认 60 天账期起算日。",
      "本周内联系容百 SQE 王工，确认 Q3 是否追加 25,000 块订单（电话中已口头提及）。",
    ],
  },
  {
    question: "本周要给哪几个客户主动汇报进度？",
    verdict:
      "建议本周优先向 3 个客户主动报进度：容百锂电（SO-2026-001 烧结进度 + 交期预警）、横店东磁（SO-2026-002 抗热震配方变更确认）、风华高科（SO-2026-003 MLCC 承烧板图纸催复）。",
    details: [
      { key: "容百锂电", value: "06-20 交期 · 烧结进度同步 · 预警可能晚 1 天" },
      { key: "横店东磁", value: "请客户确认是否接受 v2.4 抗热震配方变更" },
      { key: "风华高科", value: "请客户尽快提交 MLCC 承烧板最新版图纸（含通气孔坐标）" },
    ],
    evidence: [
      { kind: "生产流转单", label: "ZC-2026-015" },
      { kind: "合同", label: "横店东磁 / 风华高科 订单" },
    ],
    next: ["销售今日内分别发出 3 条客户进度通知（建议附 1 张烧结实时照片给容百）。"],
  },
  /* ---- 财务 + 采购预设问题 (Iter 8/9) ---- */
  {
    question: "本月利润多少？毛利率怎么样？",
    verdict:
      "2026-05 月营业收入 6,800,000 元，净利润 1,189,000 元，毛利率 35.0%（环比 +0.2 个点）。锂电承烧板（容百 3,200,000 + 风华 950,000）占收入 61%，是利润主引擎；横店东磁匣钵单价小幅下行，拉低毛利 0.4 个点。",
    details: [
      { key: "营业收入", value: "6,800,000 元（环比 +8.6%）" },
      { key: "营业成本", value: "4,420,000 元" },
      { key: "毛利率", value: "35.0%（行业上限 35–40%）" },
      { key: "期间费用", value: "795,000 元（销 280 + 管 350 + 财 45 + 研 120）" },
      { key: "净利润", value: "1,189,000 元" },
      { key: "来源", value: "损益表 2026-05 · 王会计 05-17 09:31 确认" },
    ],
    evidence: [
      { kind: "Excel", label: "2026-05 损益表 · AI 草稿已确认" },
      { kind: "合同", label: "本月 3 张销售合同（容百 / 横店 / 风华）" },
    ],
    next: [
      "横店东磁匣钵单价压力建议 Q3 谈判提示成本上行（电熔白刚玉 +6.7%）。",
      "下月排产时优先调度容百高毛利单，减少横店低价单的产能占用。",
    ],
  },
  {
    question: "本周回款情况？哪几笔到账？",
    verdict:
      "本周（05-12 ~ 05-17）已收回款 ¥2,150 K：容百锂电 SO-2026-001 首付 ¥1,200,000（合同 30% 首款，05-14 到账）+ 横店东磁 ZC-022 验收尾款 ¥800,000（05-15 到账）+ 其他小额 ¥150,000。本周应收净增加 ¥520,000（容百 + 厦钨新单发货确认应收）。",
    details: [
      { key: "容百锂电", value: "¥1,200,000 · 05-14 招行到账 · 首付 30%" },
      { key: "横店东磁", value: "¥800,000 · 05-15 工行到账 · 验收尾款" },
      { key: "其他", value: "¥150,000 · 风华 + 三环零碎尾款" },
      { key: "本周入金合计", value: "¥2,150,000" },
      { key: "下周预计回款", value: "¥1,800,000（容百 SO-2026-001 60 天账期到期一笔）" },
    ],
    evidence: [
      { kind: "Excel", label: "招行 + 工行流水 05-12~05-17 · 银行已对账" },
      { kind: "合同", label: "容百 / 横店 销售合同（付款节奏条款）" },
    ],
    next: [
      "提醒销售王经理：容百 SO-2026-001 下周到期账款 ¥1,800,000 提前 3 天去催对账。",
      "厦钨新能本月发货 1 笔尚未确认收货，建议本周内通知物流催签。",
    ],
  },
  /* ---- 采购预设问题 (Iter 9) ---- */
  {
    question: "α 氧化铝粉这批多少钱进的？跟上批比涨跌？",
    verdict:
      "PO-2026-008 山东中铝物资 α 氧化铝粉 CT3000SG · 4,000 kg · 单价 ¥24.00 / kg · 总价 ¥96,000，已到货待入库。对比上批 PO-2026-002（02-15 入库）¥22.50 / kg，本次涨价 +6.7%。山东中铝近 3 月质量稳定，但价格随大宗微涨，建议关注后续季度行情。",
    details: [
      { key: "本批单价", value: "¥24.00 / kg" },
      { key: "上批单价", value: "¥22.50 / kg（02-15 PO-2026-002）" },
      { key: "涨幅", value: "+6.7% · 与同期国内电池级氧化铝大宗价吻合" },
      { key: "数量 / 总价", value: "4,000 kg · ¥96,000" },
      { key: "账期", value: "60 天 · 应付到期 2026-07-24" },
      { key: "建议替代", value: "宜兴蓝海 W18 电熔白刚玉部分场景可替代 · 价差 ¥10/kg" },
    ],
    evidence: [
      { kind: "合同", label: "山东中铝物资 增值税专票 20260517-A001.pdf" },
      { kind: "入库单", label: "采购订单 PO-2026-008（待入库）" },
    ],
    next: [
      "询价万华化学水玻璃，作为部分配方的替代结合剂方案。",
      "Q3 锁价：与山东中铝洽谈 5 吨级框架协议，争取年内回到 ¥22.5 价位。",
    ],
  },
  {
    question: "哪个供应商最近账期最紧？该优先付？",
    verdict:
      "5 大供应商中，山东中铝物资账期最长（60 天）但金额最大（月均 ¥85,000 + 本月新增 ¥96,000），下一笔应付到期日 2026-07-24 ¥96,000，是最值得跟踪的对象。建议本周内优先回款客户应收（容百 ¥1,800,000 到期一笔）来对冲。",
    details: [
      { key: "山东中铝", value: "60 天 · 应付 ¥96,000 · 到期 2026-07-24" },
      { key: "萍乡耐材", value: "45 天 · 应付 ¥76,000 · 到期 2026-07-06" },
      { key: "宜兴蓝海", value: "30 天 · 应付 ¥84,000 · 到期 2026-06-11" },
      { key: "焦作高纯石墨", value: "30 天 · 应付 ¥27,000 · 到期 2026-06-18" },
      { key: "上海博凯化工", value: "30 天 · 应付 ¥13,600 · 到期 2026-06-14" },
    ],
    evidence: [
      { kind: "Excel", label: "应付账款明细表 2026-05 · 财务王会计已确认" },
      { kind: "合同", label: "5 张采购合同（账期条款）" },
    ],
    next: [
      "本周内对账容百到期回款 ¥1,800,000，到账即可优先付山东中铝。",
      "宜兴蓝海距离近、关系长，可提前 3 天主动结清以维护应急加急通道。",
    ],
  },
  /* ---- 经营日报预设问题 (Iter 11) ---- */
  {
    question: "今日经营日报怎么写的？哪些重点？",
    verdict:
      "2026-05-18（周一）经营日报 AI 07:55 已自动生成，标记 1 红 / 2 黄 / 4 行动。最该关注 3 件事：① 容百 SC-2026-016 烧结晚 2 天影响 06-20 交期（高风险） ② 王会计 5 月三表 1,189,000 净利润已生成等您看一眼 ③ α 氧化铝粉本批涨价 6.7%（中风险）。完整版在「📅 经营日报」tab。",
    details: [
      { key: "今日要事", value: "销售 1 / 财务 1 / 生产 2 / 采购 1 / 风险 1" },
      { key: "财务", value: "今日回款 ¥1,200,000 · 月累计 ¥4,800,000 · 货币资金 ¥8,200,000" },
      { key: "生产", value: "进行中 12 张 · 今日完成 2 张 · 延期风险 1 单" },
      { key: "采购", value: "今日入库 α 氧化铝粉 ¥96,000 · 在途莫来石 5-22 到 · 1 笔账期超期" },
      { key: "客户", value: "跟进容百王主管 · 新询盘宁波锂电 12,000 件 · 风华 -15%" },
      { key: "AI 建议", value: "4 个行动 · 上午 9:00 优先电话容百车间确认 SC-2026-016 进度" },
    ],
    evidence: [
      { kind: "Excel", label: "经营日报 2026-05-18 · AI 草稿" },
      { kind: "生产流转单", label: "SC-2026-015 / 016 / 017" },
      { kind: "合同", label: "容百 + 横店 + 风华 5 月订单合计" },
    ],
    next: [
      "上午 9:00 给容百锂电王主管去电（高风险跟进）",
      "上午 10:30 和王会计 review 5 月三表（财务一签）",
      "下午 14:00 对采购小李，山东中铝 6 月行情 + 锁价决策",
    ],
  },
];

export const trustItems = [
  {
    title: "数据来源 100% 可追溯",
    body: "每个 AI 生成的字段都可以点击查看原始来源（合同第几页、Excel 哪一行、微信哪一段、流转单照片高亮位置）。",
  },
  {
    title: "AI 不直接写入业务数据",
    body: "AI 抽取后先生成「待确认草稿」，必须由对应业务人员（销售 / 生产 / 检验）审核后才会进入正式订单 / 生产流转单。",
  },
  {
    title: "财务三表绝不被 AI 修改",
    body: "资产负债表 / 损益表 / 现金流量表 全程 AI 只生成草稿，财务总监 + 王会计双签确认后才入账，不接管任何凭证修改权限。",
  },
  {
    title: "财务级双签 · 银行级加密",
    body: "采购付款、应收冲账、报表确认 全部要求双人复核 + AES-256 端到端加密 + 操作日志可导出审计。",
  },
  {
    title: "每条字段都有置信度",
    body: "置信度低于 85% 的字段会高亮提示（如手写操作人姓名 / 印章遮挡的税率），提醒人工重点检查。",
  },
  {
    title: "原始资料原样保存",
    body: "合同 PDF、纸质流转单照片、Excel 原件、微信截图都按客户 / 订单挂载留档，便于追溯与 ISO9001 审计。",
  },
  {
    title: "权限可控",
    body: "销售、成型、烧成、检包、老板分别看到自己关心的视图；老板视图默认只读，避免误操作。",
  },
  {
    title: "工艺参数沉淀为可问数据",
    body: "工艺单录入后，老板可以用中文查询历史配方、烧成曲线、不良率，不再翻 Excel 找 LB-1580 上次哪批最稳。",
  },
];

export const traceExamples: Array<{
  aiFact: string;
  source: SourceRef;
  extractedBy: string;
  confirmedBy: string;
}> = [
  {
    aiFact: "SO-2026-001 计划交期 2026-06-20，金额 ¥327.6 万",
    source: {
      kind: "合同",
      label: "容百锂电_承烧板采购合同_2026Q2.pdf · 第 3 页 §4 交付条款",
    },
    extractedBy: "AI OCR · 2026-05-12 09:14（置信度 98%）",
    confirmedBy: "销售 · 王经理 · 05-12 10:30 确认",
  },
  {
    aiFact: "成型环节已完成 18,420 块 · 废坯 60 块",
    source: {
      kind: "生产流转单",
      label: "ZC-2026-015 · 一、成型段 · 张师傅 · 06-12 17:42 拍照上传",
    },
    extractedBy: "AI 手写体识别 · 06-12 17:45（成品数置信度 94% · 操作人 74%）",
    confirmedBy: "成型组长 · 张师傅 · 06-12 17:50 当场确认",
  },
  {
    aiFact: "近 30 天承烧板平均不良率 2.06%",
    source: {
      kind: "生产流转单",
      label: "ZC-2026-010 ~ 014 · 检包段 5 批次汇总",
    },
    extractedBy: "AI 聚合计算 · 数据基于 5 张已确认入库的检包单",
    confirmedBy: "原始 5 张检包单分别由 周师傅 / 检包组长 确认",
  },
  {
    aiFact: "2026-05 月净利润 1,189,000 元（毛利率 35.0%）",
    source: {
      kind: "Excel",
      label: "Kingdee 月度损益表 2026-05 · AI 草稿",
    },
    extractedBy: "AI 自三方账套（Kingdee + 支付宝 + 银行流水）聚合 · 不修改原凭证",
    confirmedBy: "财务 · 王会计 · 2026-05-17 09:31 复核确认 + 财务总监二签",
  },
  {
    aiFact: "2026-05-18 经营日报由 AI 07:55 自动生成（1 红 / 2 黄 / 4 行动）",
    source: {
      kind: "Excel",
      label: "经营日报 2026-05-18 · AI 草稿 · 已推送陈总微信",
    },
    extractedBy: "AI 跨 5 模块聚合（财务 + 生产 + 采购 + 客户 + 风险）· 07:55 触发",
    confirmedBy: "陈总 · 2026-05-18 08:02 在手机端打开 · 1 条已标「已处理」",
  },
];

/* ===========================================================================
 *  财务模块 (Iter 8)
 *
 *  设计原则：
 * - 数字单位统一元 (¥)，演示时显示完整千位分隔金额
 *  - 资产负债表 + 损益表 + 现金流量表 内部数字呼应：
 *      · 资产负债表 货币资金 8,200  ↔ 现金流量表 期末余额 8,200
 *      · 损益表 销售收入 6,800     ↔ 现金流量表 销售商品收到现金 5,500（差额计入应收）
 *      · 损益表 净利润 1,189       ↔ 资产负债表 留存收益本期增加
 *  - 月份口径：2026-05；资产负债表为 2026-05-31 时点
 * ========================================================================= */

export type FinanceRow = {
  key: string;
  value: string;
  bold?: boolean; // 小计 / 合计加粗
  indent?: number; // 0 = 顶级科目，1 = 子科目
};

export type FinanceReport = {
  id: "balance" | "income" | "cashflow";
  label: string;
  sub: string;
  period: string; // 报表期间文字
  aiDraft: string; // 顶部 "AI 已自动生成" 草稿提示
  confirmedBy: string; // 人工确认锚点
  sections: { title: string; rows: FinanceRow[]; subtotal?: FinanceRow }[];
  bottomLine: FinanceRow; // 资产合计 / 净利润 / 现金净增加
};

export const financeReports: FinanceReport[] = [
  {
    id: "balance",
    label: "资产负债表",
    sub: "Balance Sheet · 2026-05-31",
    period: "2026-05-31 月末",
    aiDraft:
      "智通 AI 已根据本月 12 张凭证、5 张采购入库单、3 张销售出库单自动汇总科目余额，生成草稿。",
    confirmedBy: "财务 · 王会计 · 2026-05-17 09:24 复核确认",
    sections: [
      {
        title: "流动资产",
        rows: [
          { key: "货币资金", value: "8,200" },
          { key: "应收账款", value: "12,500" },
          { key: "存货", value: "6,800" },
          { key: "预付账款", value: "1,500" },
        ],
        subtotal: { key: "流动资产小计", value: "29,000", bold: true },
      },
      {
        title: "非流动资产",
        rows: [
          { key: "固定资产 (账面净额)", value: "18,000" },
          { key: "长期股权投资", value: "0" },
        ],
        subtotal: { key: "非流动资产小计", value: "18,000", bold: true },
      },
      {
        title: "流动负债",
        rows: [
          { key: "短期借款", value: "5,000" },
          { key: "应付账款", value: "7,800" },
          { key: "应交税费", value: "1,200" },
        ],
        subtotal: { key: "流动负债小计", value: "14,000", bold: true },
      },
      {
        title: "非流动负债 + 所有者权益",
        rows: [
          { key: "长期借款", value: "3,000" },
          { key: "实收资本", value: "10,000" },
          { key: "留存收益", value: "19,300", indent: 0 },
          { key: "  本期净利润已结转 +1,189", value: "—", indent: 1 },
        ],
        subtotal: { key: "权益 + 长借小计", value: "32,300", bold: true },
      },
    ],
    bottomLine: { key: "资产总计 = 负债 + 所有者权益", value: "47,000", bold: true },
  },
  {
    id: "income",
    label: "损益表",
    sub: "Income Statement · 2026-05",
    period: "2026-05-01 ~ 05-31",
    aiDraft:
      "智通 AI 已根据本月 3 张销售出库单、5 张采购入库单、12 张费用凭证自动归集收入与成本，生成草稿。",
    confirmedBy: "财务 · 王会计 · 2026-05-17 09:31 复核确认",
    sections: [
      {
        title: "营业收入",
        rows: [
          { key: "容百锂电 · 承烧板", value: "3,200", indent: 1 },
          { key: "横店东磁 · 匣钵", value: "1,800", indent: 1 },
          { key: "风华高科 · MLCC 承烧板", value: "950", indent: 1 },
          { key: "其他客户合计", value: "850", indent: 1 },
        ],
        subtotal: { key: "营业收入合计", value: "6,800", bold: true },
      },
      {
        title: "营业成本与毛利",
        rows: [
          { key: "营业成本", value: "4,420" },
          { key: "毛利 (毛利率 35.0%)", value: "2,380", bold: true },
        ],
      },
      {
        title: "期间费用",
        rows: [
          { key: "销售费用", value: "280" },
          { key: "管理费用", value: "350" },
          { key: "财务费用", value: "45" },
          { key: "研发费用", value: "120" },
        ],
        subtotal: { key: "期间费用合计", value: "795", bold: true },
      },
      {
        title: "利润与所得税",
        rows: [
          { key: "营业利润", value: "1,585" },
          { key: "利润总额", value: "1,585" },
          { key: "所得税 (25%)", value: "396" },
        ],
      },
    ],
    bottomLine: { key: "本月净利润", value: "1,189", bold: true },
  },
  {
    id: "cashflow",
    label: "现金流量表",
    sub: "Cash Flow · 2026-05",
    period: "2026-05-01 ~ 05-31",
    aiDraft:
      "智通 AI 已根据本月 8 张银行流水、支付宝 入账、5 张采购付款单自动归集三类现金流，生成草稿。",
    confirmedBy: "财务 · 王会计 · 2026-05-17 09:38 复核确认",
    sections: [
      {
        title: "经营活动现金流",
        rows: [
          { key: "销售商品收到现金", value: "5,500", indent: 1 },
          { key: "购买商品支付现金", value: "−3,800", indent: 1 },
          { key: "支付职工工资", value: "−650", indent: 1 },
          { key: "支付各项税费", value: "−180", indent: 1 },
        ],
        subtotal: { key: "经营活动净现金流", value: "+870", bold: true },
      },
      {
        title: "投资活动现金流",
        rows: [
          { key: "购置生产设备 (等静压辅机)", value: "−200", indent: 1 },
        ],
        subtotal: { key: "投资活动净现金流", value: "−200", bold: true },
      },
      {
        title: "筹资活动现金流",
        rows: [
          { key: "偿还短期借款本金", value: "−500", indent: 1 },
        ],
        subtotal: { key: "筹资活动净现金流", value: "−500", bold: true },
      },
      {
        title: "现金余额",
        rows: [
          { key: "期初货币资金余额", value: "8,030" },
          { key: "本期现金净增加", value: "+170", bold: true },
        ],
      },
    ],
    bottomLine: { key: "期末货币资金余额 (与资产负债表一致)", value: "8,200", bold: true },
  },
];

/* ===========================================================================
 *  采购模块 (Iter 9)
 *
 *  - 物料按宜兴锦泰耐火材料真实原料结构：
 *      α 氧化铝粉 / 莫来石骨料 / 刚玉骨料 / 石墨电极粉 / 硅微粉 / 磷酸二氢铝
 *  - 采购金额量级与损益表 营业成本 4,420,000 自洽（本月约 ¥327,000 原料入库）
 * ========================================================================= */

export type PurchaseOrder = {
  poNo: string;
  supplier: string;
  material: string;
  spec: string;
  qty: string;
  unitPrice: string;
  amount: string; // ¥
  deliveryDate: string;
  status: "已入库" | "已到货待入库" | "在途";
  warehouse?: string;
};

export const purchaseOrders: PurchaseOrder[] = [
  {
    poNo: "PO-2026-008",
    supplier: "山东中铝物资",
    material: "α 氧化铝粉",
    spec: "CT3000SG · 5N 级",
    qty: "4,000 kg",
    unitPrice: "¥24.00 / kg",
    amount: "¥96,000",
    deliveryDate: "2026-05-25",
    status: "已到货待入库",
  },
  {
    poNo: "PO-2026-007",
    supplier: "萍乡耐材原料",
    material: "莫来石骨料",
    spec: "3–5 mm · M70",
    qty: "8,000 kg",
    unitPrice: "¥9.50 / kg",
    amount: "¥76,000",
    deliveryDate: "2026-05-22",
    status: "已入库",
    warehouse: "原料库 A-03",
  },
  {
    poNo: "PO-2026-006",
    supplier: "焦作高纯石墨",
    material: "石墨电极粉",
    spec: "200 目 · C ≥ 99.9%",
    qty: "1,500 kg",
    unitPrice: "¥18.00 / kg",
    amount: "¥27,000",
    deliveryDate: "2026-05-19",
    status: "已入库",
    warehouse: "原料库 B-02",
  },
  {
    poNo: "PO-2026-005",
    supplier: "上海博凯化工",
    material: "硅微粉",
    spec: "SF965 · D50 ≈ 1.5 μm",
    qty: "2,000 kg",
    unitPrice: "¥6.80 / kg",
    amount: "¥13,600",
    deliveryDate: "2026-05-15",
    status: "已入库",
    warehouse: "原料库 C-01",
  },
  {
    poNo: "PO-2026-004",
    supplier: "宜兴蓝海耐火",
    material: "刚玉骨料",
    spec: "W18 · 电熔白刚玉",
    qty: "6,000 kg",
    unitPrice: "¥14.00 / kg",
    amount: "¥84,000",
    deliveryDate: "2026-05-12",
    status: "已入库",
    warehouse: "原料库 A-01",
  },
  {
    poNo: "PO-2026-003",
    supplier: "杭州瑞晟化工",
    material: "磷酸二氢铝 (结合剂)",
    spec: "工业级 ≥ 99%",
    qty: "800 kg",
    unitPrice: "¥38.00 / kg",
    amount: "¥30,400",
    deliveryDate: "2026-05-08",
    status: "已入库",
    warehouse: "原料库 D-01",
  },
];

export type Supplier = {
  shortName: string;
  fullName: string;
  category: string;
  monthlySpend: string;
  paymentTerm: string;
  trustNote: string;
};

export const suppliers: Supplier[] = [
  {
    shortName: "山东中铝物资",
    fullName: "山东中铝物资贸易有限公司",
    category: "α 氧化铝粉 / 高纯氧化铝",
    monthlySpend: "¥85,000 / 月",
    paymentTerm: "账期 60 天",
    trustNote: "近 3 月质量稳定 · 价格随大宗微涨 6.7%",
  },
  {
    shortName: "萍乡耐材原料",
    fullName: "萍乡市耐火材料原料有限公司",
    category: "莫来石 + 刚玉骨料",
    monthlySpend: "¥160,000 / 月",
    paymentTerm: "账期 45 天",
    trustNote: "本地长期合作 · 物流稳定",
  },
  {
    shortName: "焦作高纯石墨",
    fullName: "焦作市高纯石墨制品有限公司",
    category: "石墨电极粉 / 石墨匣钵料",
    monthlySpend: "¥30,000 / 月",
    paymentTerm: "账期 30 天",
    trustNote: "供货周期 7 天 · 小批量灵活",
  },
  {
    shortName: "上海博凯化工",
    fullName: "上海博凯精细化工有限公司",
    category: "硅微粉 / 化工辅料",
    monthlySpend: "¥40,000 / 月",
    paymentTerm: "账期 30 天",
    trustNote: "技术支持响应快 · 配方咨询免费",
  },
  {
    shortName: "宜兴蓝海耐火",
    fullName: "宜兴市蓝海耐火材料有限公司",
    category: "电熔白刚玉 W18 / 本地原料",
    monthlySpend: "¥90,000 / 月",
    paymentTerm: "账期 30 天",
    trustNote: "本地 · 半小时车程到厂 · 应急加急可优先",
  },
];

export type PurchaseInboxCard = {
  id: string;
  kind: "采购发票" | "采购合同" | "字段缺失";
  source: string;
  uploadedAt: string;
  aiSummary: string;
  fields: { key: string; value: string }[];
  suggestedAction: string;
};

export const purchaseInboxCards: PurchaseInboxCard[] = [
  {
    id: "PIN-2026-014",
    kind: "采购发票",
    source: "山东中铝物资_增值税专票_20260517-A001.pdf",
    uploadedAt: "2026-05-17 09:12",
    aiSummary:
      "已抽取到金额、税率、货物、数量；与 PO-2026-008 自动匹配，建议确认后自动入库 + 生成应付账款凭证。",
    fields: [
      { key: "发票号", value: "20260517-A001" },
      { key: "供应商", value: "山东中铝物资" },
      { key: "金额 (含税)", value: "¥96,000" },
      { key: "税率", value: "13%" },
      { key: "货物", value: "α 氧化铝粉 CT3000SG" },
      { key: "数量", value: "4,000 kg" },
      { key: "匹配订单", value: "PO-2026-008" },
    ],
    suggestedAction: "建议：确认 → 自动入库到 A-02 → 生成应付账款 ¥96,000 · 账期至 2026-07-24",
  },
  {
    id: "PIN-2026-013",
    kind: "采购合同",
    source: "万华化学_水玻璃采购合同_2026Q3.pdf",
    uploadedAt: "2026-05-17 08:48",
    aiSummary:
      "新供应商，已抽出合同金额、货物、数量、首单交期；建议生成新的采购订单 PO-2026-009 并建档供应商。",
    fields: [
      { key: "供应商", value: "万华化学集团股份有限公司" },
      { key: "货物", value: "钠水玻璃 (Na₂SiO₃ · 模数 3.3)" },
      { key: "数量", value: "5 吨" },
      { key: "合同金额", value: "¥120,000" },
      { key: "账期", value: "60 天" },
      { key: "首单交期", value: "2026-06-15" },
    ],
    suggestedAction: "建议：生成 PO-2026-009 + 新建「万华化学」供应商档案 + 提示采购经理预付定金 30%",
  },
  {
    id: "PIN-2026-012",
    kind: "字段缺失",
    source: "上海博凯化工_发票_20260515-B003.pdf",
    uploadedAt: "2026-05-17 08:21",
    aiSummary:
      "AI 已抽出发票主要信息，但「税率」字段缺失（票面被印章遮挡），无法自动生成应付凭证。",
    fields: [
      { key: "发票号", value: "20260515-B003" },
      { key: "供应商", value: "上海博凯化工" },
      { key: "金额 (含税)", value: "¥13,600" },
      { key: "税率", value: "— 未识别" },
      { key: "货物", value: "硅微粉 SF965" },
      { key: "匹配订单", value: "PO-2026-005" },
    ],
    suggestedAction: "建议：人工补充税率（推测 13%）→ 重新生成应付凭证；或退回供应商重开发票",
  },
];

/* ===========================================================================
 *  📅 经营日报 (Iter 11)
 *
 *  老板早上 8 点打开手机看的 5 分钟摘要。
 *  跨 tab 聚合：财务 / 生产 / 采购 / 客户 / 风险 / AI 今日行动建议
 *  数字 100% 自洽于其它 tab：
 *    - 货币资金 8,200 ↔ 资产负债表
 *    - 容百回款 1,200,000 ↔ Ask AI 本周回款 Q6
 *    - α 氧化铝粉涨价 6.7% ↔ Ask AI Q7
 *    - 进行中流转 12 张 ↔ 概览 KPI
 *    - 5 月净利润 1,189,000 ↔ 损益表
 * ========================================================================= */

export type DailyBriefBlock = {
  icon: string;
  category: "财务" | "生产" | "采购" | "客户";
  bullets: string[]; // 每条 ≤ 60 字，数字用 「」包裹
  aiHint: string;
};

export type DailyBriefRisk = {
  level: "high" | "medium" | "low";
  title: string;
  recommendation: string;
};

export type DailyBriefAction = {
  time: string; // "上午 9:00"
  action: string;
  category: "财务" | "生产" | "采购" | "销售";
};

export type DailyBriefHistory = {
  date: string;
  status: "已读" | "未读";
  red: number;
  yellow: number;
  actions: number;
};

export const dailyBrief = {
  date: "2026-05-18",
  weekday: "周一",
  generatedAt: "2026-05-18 07:55",
  counts: { sales: 1, finance: 1, production: 2, purchase: 1, risk: 1 },
  aiSummary:
    "今天最该关注 3 件事：① 容百锂电 SC-2026-016 烧结进度比计划晚 2 天，影响 06-20 交期；② 王会计 5 月三表（净利润 1,189,000 · 毛利率 35.0%）已生成，等您看一眼； ③ α 氧化铝粉本批 PO-2026-008 比上批涨价 6.7%，下批采购前建议先问行情。",
  blocks: [
    {
      icon: "💰",
      category: "财务",
      bullets: [
        "今日回款「¥1,200,000」(容百锂电 SO-2026-001 首付) · 本月累计回款「¥4,800,000」/ 应收「¥5,200,000」",
        "货币资金余额「¥8,200,000」(月初 ¥8,030,000 · +¥170,000)",
        "下月初有 3 张原料采购付款合计「¥327,000」到期，建议预留备用金",
      ],
      aiHint: "5 月利润「¥1,189,000」已交财务总监二签，您可直接在「💰 财务」tab 看三表草稿。",
    },
    {
      icon: "🏭",
      category: "生产",
      bullets: [
        "进行中流转单「12 张」· 今日完成「2 张」(容百 SC-2026-015 烧结 / 横店东磁 SC-2026-017 检包)",
        "延期风险「1 单」: 容百 SC-2026-016 烧结进度比计划晚「2 天」",
        "今日待出货「2 单」合计「¥315,000」(容百宁波 + 厦钨宁德)",
      ],
      aiHint: "建议上午 9:00 给容百锂电王主管去电，提前告知交期可能偏移 1-2 天。",
    },
    {
      icon: "📦",
      category: "采购",
      bullets: [
        "今日入库: 山东中铝 α 氧化铝粉 「4,000 kg / ¥96,000」(PO-2026-008)",
        "在途: 萍乡耐材 莫来石骨料预计「05-22」到货 (PO-2026-007 已发运)",
        "异常: 杭州瑞晟 磷酸二氢铝供应商账期约定「30 天」，本笔已「45 天」未付",
      ],
      aiHint: "α 氧化铝粉本批 ¥24/kg 比上批涨「+6.7%」，建议下批采购前问行情。",
    },
    {
      icon: "🤝",
      category: "客户",
      bullets: [
        "今日跟进: 容百锂电王主管，确认 5 月 SC-2026-016 排产 + 6 月计划",
        "新询盘: 宁波某锂电厂询 莫来石承烧板「12,000 件」(销售已应答)",
        "异常: 风华高科本月订单同比「-15%」，需主动拜访",
      ],
      aiHint: "已为您起草 1 条客户跟进短信（容百王主管），「问问 AI」一键查看。",
    },
  ] as DailyBriefBlock[],
  risks: [
    {
      level: "high",
      title: "容百 SC-2026-016 烧结进度晚 2 天，可能影响 06-20 交期",
      recommendation: "立即跟进车间主管 + 提前告知容百仓储经理交期偏移",
    },
    {
      level: "medium",
      title: "α 氧化铝粉本批涨价「+6.7%」(¥22.5 → ¥24 / kg)",
      recommendation: "下批采购前问行情；可考虑 Q3 与山东中铝洽谈 5 吨锁价框架协议",
    },
    {
      level: "medium",
      title: "风华高科本月订单同比「-15%」",
      recommendation: "销售小张本周内主动拜访，了解需求变化原因",
    },
  ] as DailyBriefRisk[],
  actions: [
    { time: "上午 9:00", category: "生产", action: "电话容百锂电王主管，确认 SC-2026-016 是否可接受 06-22 交付（原 06-20）" },
    { time: "上午 10:30", category: "财务", action: "和王会计 review 5 月三表，重点看销售费用环比 ↑ 12% 是否合理" },
    { time: "下午 14:00", category: "采购", action: "和采购小李对 山东中铝 6 月行情，决策是否提前锁价 5 吨" },
    { time: "下午 16:00", category: "销售", action: "给销售小张派任务：本月二次拜访风华高科（订单 -15%）" },
  ] as DailyBriefAction[],
  history: [
    { date: "2026-05-17 周日", status: "已读", red: 1, yellow: 2, actions: 6 },
    { date: "2026-05-16 周六", status: "已读", red: 0, yellow: 3, actions: 4 },
    { date: "2026-05-15 周五", status: "已读", red: 2, yellow: 1, actions: 5 },
    { date: "2026-05-14 周四", status: "已读", red: 0, yellow: 2, actions: 3 },
    { date: "2026-05-13 周三", status: "已读", red: 1, yellow: 1, actions: 4 },
  ] as DailyBriefHistory[],
};
