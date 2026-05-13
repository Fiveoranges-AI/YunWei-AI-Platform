import type { AskSeed, CustomerDetail, Review } from "./types";

export const MOCK_CUSTOMERS: CustomerDetail[] = [
  {
    id: "wh",
    name: "万华化学",
    monogram: "万华",
    color: "#1f6c8a",
    tag: "重点客户",
    updated: "2 小时前",
    aiSummary:
      "该客户聚焦设备项目交付，10 月底前需确认终验方案；尾款 ¥322,000 待回款。建议本周联系王总确认资金安排。",
    metrics: { contractTotal: 3220000, receivable: 322000, contracts: 2, tasks: 3, contacts: 4 },
    risk: { level: "med", label: "中风险", note: "收款周期延长 18 天" },
    timeline: [
      { kind: "upload", title: "上传新合同草案", when: "今天 10:30", by: "李欣 · 销售助理", src: "终验补充协议_v2.pdf" },
      { kind: "meet", title: "完成第一次需求沟通会议", when: "昨天 14:00", by: "王总 · 万华化学", src: "语音 12′45″" },
      { kind: "wechat", title: "王总确认月底前回款", when: "昨天 09:12", by: "微信 · 王志强", src: "微信截图 3 张" },
      { kind: "invoice", title: "开具增值税发票 ¥150,000", when: "5 月 6 日", by: "财务 · 张华", src: "INV-20260506-018" },
    ],
    commitments: [
      { id: "c1", text: "客户承诺 10 月 31 日前完成尾款支付", source: "微信 · 王总 · 昨天", confidence: "high" },
      { id: "c2", text: "我方承诺 10 月 25 日前完成终验文件交付", source: "终验补充协议_v2.pdf · §4.2", confidence: "high" },
    ],
    tasks: [
      { id: "t1", text: "本周内致电王总确认尾款进度", due: "本周内", owner: "李欣" },
      { id: "t2", text: "准备终验现场设备清单", due: "10 月 22 日", owner: "陈工" },
      { id: "t3", text: "同步法务部备案备用催收方案", due: "本月内", owner: "张律师" },
    ],
    risks: [
      {
        id: "r1",
        level: "med",
        title: "收款周期延长预警",
        detail: "客户内部审批节奏放缓，对比上次合同延后 18 天。",
        sources: ["微信记录 王总 · 昨天", "上次合同付款记录"],
      },
    ],
    contacts: [
      { id: "p1", name: "王志强", role: "采购总监", initial: "王", phone: "138****8888", last: "昨天 09:12" },
      { id: "p2", name: "张华", role: "财务经理", initial: "张", phone: "139****0021", last: "5 月 6 日" },
      { id: "p3", name: "陈立", role: "工程师", initial: "陈", phone: "136****2401", last: "上周三" },
    ],
    docs: [
      { id: "d1", name: "终验补充协议_v2.pdf", kind: "合同", date: "今天" },
      { id: "d2", name: "微信记录_王总_2026-05", kind: "聊天", date: "昨天" },
      { id: "d3", name: "设备采购合同_2026Q1.pdf", kind: "合同", date: "4 月 12 日" },
      { id: "d4", name: "送货单_SH-20260308.jpg", kind: "送货单", date: "3 月 8 日" },
    ],
  },
  {
    id: "tx",
    name: "腾鑫精密机械",
    monogram: "TX",
    color: "#3a6ea5",
    tag: "常规",
    updated: "昨天",
    aiSummary: "近 30 天无新动态，存在 1 张未到期发票。建议安排回访。",
    metrics: { contractTotal: 880000, receivable: 0, contracts: 1, tasks: 1, contacts: 2 },
    risk: { level: "low", label: "低风险", note: "回访间隔较长" },
  },
  {
    id: "hd",
    name: "海德新材料",
    monogram: "HD",
    color: "#5a7d8c",
    tag: "潜在",
    updated: "3 天前",
    aiSummary: "处于报价阶段，已发出第二轮报价单。客户对交期和返修条款敏感。",
    metrics: { contractTotal: 0, receivable: 0, contracts: 0, tasks: 2, contacts: 2 },
    risk: { level: "low", label: "低风险", note: "尚未签约" },
  },
  {
    id: "jh",
    name: "巨华机电设备",
    monogram: "JH",
    color: "#8a5a3a",
    tag: "老客户",
    updated: "5 天前",
    aiSummary: "上批货物已交付完毕，客户对外发了感谢信。下一年度框架协议可启动续约谈判。",
    metrics: { contractTotal: 1280000, receivable: 0, contracts: 3, tasks: 1, contacts: 3 },
    risk: { level: "low", label: "低风险", note: "续约期临近" },
  },
  {
    id: "sf",
    name: "盛丰汽配",
    monogram: "SF",
    color: "#7a3a3a",
    tag: "注意",
    updated: "4 天前",
    aiSummary: "客户两次延期付款，且本月有第三方投诉提及账期问题。建议谨慎扩大授信。",
    metrics: { contractTotal: 660000, receivable: 198000, contracts: 1, tasks: 4, contacts: 2 },
    risk: { level: "high", label: "高风险", note: "账期连续延期 2 次" },
  },
];

export const MOCK_REVIEW: Review = {
  customer: { name: "万华化学", isExisting: true, confidence: 0.96 },
  channel: "微信沟通",
  docType: "聊天截图 + 语音",
  contact: { name: "王志强", role: "采购总监", initial: "王" },
  confidence: 0.92,
  fields: [
    { key: "客户名称", value: "万华化学", conf: "high" },
    { key: "沟通渠道", value: "微信", conf: "high" },
    { key: "联系人", value: "王志强（采购总监）", conf: "high" },
    { key: "沟通时间", value: "2026-05-07 14:00", conf: "med" },
  ],
  extractions: [
    {
      kind: "commitment",
      title: "承诺事项",
      text: "客户承诺 10 月 31 日前付款",
      source: { type: "微信", label: "微信截图第 2 条" },
      conf: "high",
    },
    {
      kind: "task",
      title: "待办事项",
      text: "提前 7 天提醒客户付款节点",
      source: { type: "微信", label: "微信截图第 2 条" },
      conf: "high",
    },
    {
      kind: "risk",
      title: "风险线索",
      text: "客户提及内部审批延长，建议提前确认资金",
      source: { type: "语音", label: "语音 02:15 处" },
      conf: "med",
    },
    {
      kind: "contact",
      title: "联系人",
      text: "新增联系人：陈立（工程师 · 136****2401）",
      source: { type: "微信", label: "微信名片" },
      conf: "high",
    },
  ],
  missing: ["合同金额", "合同编号"],
  evidence: [
    { id: "e1", type: "微信截图", label: "微信截图 #2", preview: "WeChat · 2026-05-07" },
    { id: "e2", type: "语音转写", label: "语音 02:15", preview: '02:15 · "我们这边大概月底之前能给…"' },
    { id: "e3", type: "语音转写", label: "语音 04:38", preview: '04:38 · "审批可能会比上次慢一点点"' },
  ],
};

export const MOCK_ASK_SEED: AskSeed = {
  customerId: "wh",
  messages: [
    { role: "user", text: "这个客户现在有什么风险？", when: "今天 14:30" },
    {
      role: "ai",
      blocks: {
        verdict:
          "存在中等风险：客户尾款 ¥322,000 仍未到账，且其内部审批节奏明显放缓。建议本周联系并提前备案。",
        evidence: [
          { id: "e1", type: "微信", label: "微信记录 · 王总 · 昨天" },
          { id: "e2", type: "合同", label: "终验补充协议_v2.pdf · §4.2" },
          { id: "e3", type: "语音", label: "语音 02:15 · 02:15 处" },
        ],
        next: [
          "本周内联系王总确认资金安排；同步财务陈姐准备催收预案。",
          "把催收备用方案同步法务备案。",
          '为客户标记"重点跟进"，10 月 25 日自动提醒。',
        ],
        related: [
          { kind: "合同", label: "设备采购合同_2026Q1.pdf" },
          { kind: "联系人", label: "王志强 · 采购总监" },
        ],
      },
    },
  ],
  suggestions: [
    "还有多少钱没收？",
    "最近一次沟通说了什么？",
    "下一步应该做什么？",
    "谁是关键联系人？",
  ],
};
