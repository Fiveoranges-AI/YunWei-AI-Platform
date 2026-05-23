import type {
  AIBlock,
  ExtractionCard,
  FlowCard,
  FlowStep,
  ProcessParameter,
  Risk,
  SourceRef,
} from "../screens/jintai/data";

const API_BASE = "/api/jintai";

export class JintaiApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

type RawExtractionItem = {
  queue_no: string;
  source_document_name?: string | null;
  extraction_type: string;
  target_table?: string | null;
  extracted_data?: Record<string, unknown> | null;
  confidence?: number | null;
  created_at?: string | null;
  status: string;
};

type RawAskResponse = {
  answer: string;
  data: Array<Record<string, unknown>>;
  citations: Array<{ table: string; id: string }>;
};

type RawOverview = {
  kpis: {
    total_flow_cards: number;
    delayed_flow_cards: number;
    sintering_flow_cards: number;
    quantity_exception_flow_cards: number;
    completed_flow_cards: number;
    created_flow_cards: number;
  };
  queue: {
    pending_review: number;
    confirmed: number;
    rejected: number;
  };
  products: {
    total_products: number;
    high_risk_products: number;
  };
};

type RawFlowCardSummary = {
  flow_card_no: string;
  planned_quantity: string | number;
  completed_quantity?: string | number | null;
  defective_quantity?: string | number | null;
  unit?: string | null;
  current_step_code?: string | null;
  priority?: string | null;
  due_at?: string | null;
  status: string;
  order_no: string;
  customer_name: string;
  product_sku: string;
  product_name: string;
  quality_risk_level?: string | null;
};

type RawFlowCardDetail = {
  flow_card: RawFlowCardSummary & {
    order_date?: string | null;
    promised_delivery_date?: string | null;
  };
  step_records: Array<{
    step_code: string;
    step_name: string;
    step_sequence: number;
    input_quantity?: string | number | null;
    output_quantity?: string | number | null;
    defective_quantity?: string | number | null;
    equipment_code?: string | null;
    qc_result?: Record<string, unknown> | null;
    status: string;
    operator_name?: string | null;
  }>;
};

type RawProcessParameter = {
  product_sku: string;
  product_name: string;
  route_code: string;
  route_name: string;
  version: string;
  step_code: string;
  step_name: string;
  step_sequence: number;
  workstation?: string | null;
  standard_hours?: string | number | null;
  required_role_code?: string | null;
  qc_points?: Record<string, unknown> | null;
  status: string;
};

type RawBriefing = {
  briefing_date: string;
  counters: {
    delayed_flow_cards: number;
    sintering_flow_cards: number;
    quantity_exception_flow_cards: number;
    created_flow_cards: number;
  };
  risk_flow_cards: Array<{
    flow_card_no: string;
    status: string;
    current_step_code?: string | null;
    due_at?: string | null;
    delay_reason?: string | null;
    quantity_variance_reason?: string | null;
    customer_name: string;
    product_sku: string;
    product_name: string;
  }>;
  high_defect_products: Array<{
    sku: string;
    name: string;
    defective_quantity: string | number;
    defect_rate?: string | number | null;
  }>;
  pending_ai_queue: RawExtractionItem[];
  recommendations: string[];
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    throw new JintaiApiError(`Jintai API ${path} failed`, res.status);
  }
  return (await res.json()) as T;
}

export async function getJintaiKpis(): Promise<Array<{
  label: string;
  value: number;
  hint: string;
  suffix?: string;
}>> {
  const overview = await requestJson<RawOverview>("/overview");
  const queueTotal =
    overview.queue.pending_review + overview.queue.confirmed + overview.queue.rejected;
  const inProgress =
    overview.kpis.total_flow_cards -
    overview.kpis.completed_flow_cards -
    overview.kpis.created_flow_cards;
  return [
    { label: "AI 队列记录", value: queueTotal, hint: "来自 ai_extraction_queue，先复核再入库" },
    { label: "待确认草稿", value: overview.queue.pending_review, hint: "等待老板 / 生产经理人工确认" },
    { label: "进行中生产单", value: inProgress, hint: "成型 / 烧结 / 检包中的流转单" },
    { label: "延期风险订单", value: overview.kpis.delayed_flow_cards, hint: "已标记 delayed 的生产流转单" },
    { label: "数量异常单", value: overview.kpis.quantity_exception_flow_cards, hint: "需人工复核后再决定补产或入库" },
    { label: "来源可追溯率", value: 100, hint: "当前 MVP 数据全部带来源映射或队列记录", suffix: "%" },
  ];
}

export async function listJintaiFlowCards(limit = 6): Promise<FlowCard[]> {
  const payload = await requestJson<{ flow_cards: RawFlowCardSummary[] }>(
    `/flow-cards?limit=${encodeURIComponent(String(limit))}`,
  );
  const selected = payload.flow_cards.slice(0, limit);
  const details = await Promise.all(
    selected.map((card) =>
      requestJson<RawFlowCardDetail>(`/flow-cards/${encodeURIComponent(card.flow_card_no)}`),
    ),
  );
  return details.map(toFlowCard);
}

export async function getJintaiProcessParameter(productSku = "JT-AM-SP-001"): Promise<ProcessParameter> {
  const payload = await requestJson<{ process_parameters: RawProcessParameter[] }>(
    `/process-parameters?product_sku=${encodeURIComponent(productSku)}`,
  );
  if (payload.process_parameters.length === 0) {
    throw new JintaiApiError("No process parameters", 404);
  }
  return toProcessParameter(payload.process_parameters);
}

export async function getJintaiBriefing(): Promise<{
  briefingDate: string;
  metrics: Array<{ label: string; value: number | string; sub: string }>;
  risks: Array<{
    severity: Risk;
    title: string;
    detail: string;
    suggestion: string;
    sources: SourceRef[];
  }>;
}> {
  const payload = await requestJson<RawBriefing>("/briefing");
  return {
    briefingDate: payload.briefing_date,
    metrics: [
      { label: "延期生产单", value: payload.counters.delayed_flow_cards, sub: "状态为 delayed" },
      { label: "卡在烧结", value: payload.counters.sintering_flow_cards, sub: "current_step_code = sintering" },
      { label: "数量异常", value: payload.counters.quantity_exception_flow_cards, sub: "等待人工复核" },
      { label: "刚创建", value: payload.counters.created_flow_cards, sub: "尚未开始生产" },
      { label: "AI 待确认", value: payload.pending_ai_queue.length, sub: "抽取结果不直接写业务表" },
      { label: "高不良产品", value: payload.high_defect_products.length, sub: "按工序记录聚合" },
    ],
    risks: toBriefingRisks(payload),
  };
}

export async function listJintaiExtractions(status = "pending"): Promise<ExtractionCard[]> {
  const payload = await requestJson<{ items: RawExtractionItem[] }>(
    `/extractions?status=${encodeURIComponent(status)}`,
  );
  return payload.items.map(toExtractionCard);
}

export async function createJintaiIngestPlaceholder(
  kind: ExtractionCard["kind"],
  fileName: string,
  extractedData: Record<string, string> = {},
): Promise<ExtractionCard> {
  const payload = await requestJson<{ item: RawExtractionItem }>("/ingest", {
    method: "POST",
    body: JSON.stringify({
      source_document_name: fileName,
      extraction_type: kindToExtractionType(kind),
      target_table: kindToTargetTable(kind),
      payload: { source: "win_web_demo" },
      extracted_data: extractedData,
    }),
  });
  return toExtractionCard(payload.item);
}

export async function confirmJintaiExtraction(queueNo: string): Promise<void> {
  await requestJson(`/extractions/${encodeURIComponent(queueNo)}/confirm`, {
    method: "POST",
    body: JSON.stringify({ reviewer_role_code: "production_manager" }),
  });
}

export async function askJintai(question: string): Promise<AIBlock> {
  const payload = await requestJson<RawAskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ query_text: question }),
  });
  return {
    question,
    verdict: payload.answer,
    details: payload.data.slice(0, 6).flatMap(recordToDetails),
    evidence: payload.citations.slice(0, 6).map(toSourceRef),
    next: [
      "查看来源记录后再做生产或交付调整。",
      "涉及数量异常时，先走人工复核，不让 AI 直接修改业务数据。",
    ],
  };
}

function toExtractionCard(item: RawExtractionItem): ExtractionCard {
  const extracted = item.extracted_data ?? {};
  return {
    id: item.queue_no,
    kind: extractionTypeToKind(item.extraction_type),
    source: item.source_document_name || item.queue_no,
    uploadedAt: item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "刚刚",
    status: queueStatusToCardStatus(item.status, item.extraction_type),
    confidence: item.confidence ?? 0.8,
    fields: Object.entries(extracted).slice(0, 8).map(([key, value]) => ({
      key,
      value: formatValue(value),
    })),
    toBeGenerated: targetTableLabel(item.target_table),
  };
}

function extractionTypeToKind(type: string): ExtractionCard["kind"] {
  if (type === "excel_sales_order") return "Excel 订单";
  if (type === "ocr_flow_card") return "生产流转单";
  if (type === "quality_exception") return "生产流转单";
  return "合同";
}

function kindToExtractionType(kind: ExtractionCard["kind"]): string {
  if (kind === "Excel 订单") return "excel_sales_order";
  if (kind === "生产流转单") return "ocr_flow_card";
  if (kind === "出货单") return "manual_note";
  return "manual_note";
}

function kindToTargetTable(kind: ExtractionCard["kind"]): string {
  if (kind === "合同" || kind === "Excel 订单") return "sales_orders";
  if (kind === "生产流转单") return "production_flow_cards";
  return "production_step_records";
}

function generatedStatus(type: string): ExtractionCard["status"] {
  if (type === "excel_sales_order") return "订单已生成";
  if (type === "ocr_flow_card" || type === "quality_exception") return "流转单已生成";
  return "出货已记录";
}

function queueStatusToCardStatus(status: string, type: string): ExtractionCard["status"] {
  if (status === "pending_review") return "待确认";
  if (status === "confirmed") return "已确认";
  if (status === "rejected") return "已驳回";
  return generatedStatus(type);
}

function targetTableLabel(table?: string | null): string {
  if (table === "sales_orders") return "销售订单草稿";
  if (table === "production_flow_cards") return "生产流转单草稿";
  if (table === "production_step_records") return "工序记录草稿";
  if (table === "customers") return "客户资料草稿";
  if (table === "products") return "产品资料草稿";
  return "待确认草稿";
}

function recordToDetails(record: Record<string, unknown>): { key: string; value: string }[] {
  return Object.entries(record)
    .filter(([key]) => !key.endsWith("_id") && key !== "id")
    .slice(0, 4)
    .map(([key, value]) => ({ key, value: formatValue(value) }));
}

function toSourceRef(citation: { table: string; id: string }): SourceRef {
  const kind: SourceRef["kind"] =
    citation.table === "products"
      ? "工艺单"
      : citation.table === "sales_orders"
        ? "合同"
        : "生产流转单";
  return { kind, label: `${citation.table}:${citation.id.slice(0, 8)}` };
}

function toFlowCard(detail: RawFlowCardDetail): FlowCard {
  const card = detail.flow_card;
  const currentStep = currentStepLabel(card.current_step_code, card.status);
  return {
    flowCardNo: card.flow_card_no,
    planNo: card.flow_card_no.replace("FC-JT", "SC-JT"),
    orderNo: card.order_no,
    customer: card.customer_name,
    product: card.product_name,
    specification: card.product_sku,
    plannedQty: numberValue(card.planned_quantity),
    deliveryDate: formatDate(card.due_at),
    currentStep,
    status: card.status === "completed" ? "完成" : card.status === "created" ? "待开始" : "进行中",
    risk: flowRisk(card),
    steps: detail.step_records.map(toFlowStep),
  };
}

function toFlowStep(record: RawFlowCardDetail["step_records"][number]): FlowStep {
  const status: FlowStep["status"] =
    record.status === "completed"
      ? "已完成"
      : record.status === "queued"
        ? "未开始"
        : "进行中";
  const input = maybeNumber(record.input_quantity);
  const output = maybeNumber(record.output_quantity);
  const defective = maybeNumber(record.defective_quantity);
  const operator = record.operator_name ?? null;
  const common = {
    name: stepNameFromCode(record.step_code),
    status,
    plannedDate: record.status === "queued" ? "待排程" : "已排程",
    operator,
    remark: record.qc_result ? formatValue(record.qc_result) : undefined,
  };
  if (record.step_code === "forming") {
    return {
      ...common,
      machineNo: record.equipment_code ?? undefined,
      materialQty: input,
      completedQty: output,
      wasteBlankQty: defective,
    };
  }
  if (record.step_code === "sintering") {
    return {
      ...common,
      receivedQty: input,
      kilnNo: record.equipment_code ?? undefined,
      curveNo: stringFromObject(record.qc_result, "temperature_curve"),
      kilnLoadingQty: input,
      kilnOutputQty: output,
      defectQty: defective,
    };
  }
  return {
    ...common,
    receivedQty: input,
    qualifiedQty: output,
    scrapQty: defective,
  };
}

function toProcessParameter(rows: RawProcessParameter[]): ProcessParameter {
  const first = rows[0];
  return {
    product: `${first.product_name}（${first.product_sku}）`,
    version: first.version,
    route: `${first.route_name} · ${first.route_code}`,
    groups: rows
      .slice()
      .sort((a, b) => a.step_sequence - b.step_sequence)
      .map((row) => ({
        title: row.step_name,
        rows: [
          { key: "工位", value: row.workstation || "未配置" },
          { key: "标准工时", value: row.standard_hours ? `${formatValue(row.standard_hours)} 小时` : "未配置" },
          { key: "角色", value: row.required_role_code || "未配置" },
          { key: "质检点", value: formatQcPoints(row.qc_points) },
        ],
      })),
  };
}

function toBriefingRisks(payload: RawBriefing): Array<{
  severity: Risk;
  title: string;
  detail: string;
  suggestion: string;
  sources: SourceRef[];
}> {
  const risks = payload.risk_flow_cards.slice(0, 4).map((card) => ({
    severity: card.status === "delayed" ? "high" as Risk : card.status === "quantity_exception" ? "medium" as Risk : "low" as Risk,
    title: `${card.flow_card_no} · ${card.customer_name} · ${flowStatusLabel(card.status, card.current_step_code)}`,
    detail:
      card.delay_reason ||
      card.quantity_variance_reason ||
      `${card.product_name} 当前在 ${currentStepLabel(card.current_step_code, card.status)}，计划交期 ${formatDate(card.due_at)}。`,
    suggestion: payload.recommendations[0] ?? "先查看来源记录，再由人工决定下一步处理。",
    sources: [
      { kind: "生产流转单" as const, label: card.flow_card_no },
      { kind: "工艺单" as const, label: card.product_sku },
    ],
  }));
  for (const product of payload.high_defect_products.slice(0, 2)) {
    risks.push({
      severity: "medium",
      title: `${product.name} 不良数量偏高`,
      detail: `${product.sku} 当前样例工序记录累计不良 ${formatValue(product.defective_quantity)}，不良率 ${formatPercent(product.defect_rate)}。`,
      suggestion: payload.recommendations[2] ?? "按产品和工序追溯，不让 AI 直接修改生产记录。",
      sources: [{ kind: "工艺单", label: product.sku }],
    });
  }
  return risks.slice(0, 4);
}

function currentStepLabel(code?: string | null, status?: string): FlowCard["currentStep"] {
  if (status === "completed") return "完成";
  if (code === "sintering") return "烧结";
  if (code === "inspection_packaging") return "检包";
  return "成型";
}

function stepNameFromCode(code: string): FlowStep["name"] {
  if (code === "sintering") return "烧结";
  if (code === "inspection_packaging") return "检包";
  return "成型";
}

function flowRisk(card: RawFlowCardSummary): Risk {
  if (card.status === "delayed" || card.priority === "urgent" || card.priority === "high") return "high";
  if (card.status === "quantity_exception" || card.quality_risk_level === "high") return "medium";
  return "low";
}

function flowStatusLabel(status: string, stepCode?: string | null): string {
  if (status === "delayed") return "延期";
  if (status === "quantity_exception") return "数量异常";
  if (status === "created") return "刚创建";
  return `${currentStepLabel(stepCode, status)}中`;
}

function numberValue(value: string | number | null | undefined): number {
  if (typeof value === "number") return value;
  if (!value) return 0;
  return Number(value) || 0;
}

function maybeNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return numberValue(value);
}

function formatDate(value?: string | null): string {
  if (!value) return "待排程";
  return value.slice(0, 10);
}

function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "待统计";
  const n = numberValue(value);
  return `${(n * 100).toFixed(2)}%`;
}

function formatQcPoints(value?: Record<string, unknown> | null): string {
  if (!value || Object.keys(value).length === 0) return "未配置";
  const checks = value.check;
  if (Array.isArray(checks)) return checks.map(String).join(" / ");
  return formatValue(value);
}

function stringFromObject(value: Record<string, unknown> | null | undefined, key: string): string | undefined {
  const raw = value?.[key];
  return typeof raw === "string" ? raw : undefined;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : String(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
