# 光天耐火 AI 库存管家 Demo · 迭代日志

> 客户：宜兴光天耐火材料有限公司（http://www.gtnckj.com/product.asp）
> 分支：feat/guangtian-demo（基于 feat/jintai-demo HEAD）
> 演示口号：用 AI 把 1,000+ SKU 管清楚 · 实时记录出入库 · 提前 3 天发现缺货风险
>
> 设计原则继承自 Jintai demo iter 7（简洁）/ iter 14（品牌 accent）/ iter 16（icon 分组配色）。

---

## Iter G1 — 项目骨架 + URail 入口 + Hero
**Commit:** 7abe9cc

- 从 feat/jintai-demo 分出 feat/guangtian-demo
- 新建 `apps/win-web/src/screens/guangtian/` 目录
- App.tsx 注册 `guangtian` ScreenName / TabName，对应 GuangtianDemoPage
- AppShell.VIEW_META 加 `guangtian: { title: "宜兴光天耐火材料 · AI 库存管家", sub: "1,000+ SKU 实时记录..." }`
- URail 加 "光天试点" 入口（icon `I.pkg`，紧邻"锦泰试点"）
- tokens.css 加品牌色：
  - `--guangtian-red: #D92020`（logo 文字红，主 accent）
  - `--guangtian-blue: #1A3F8E`（logo 副标深蓝，数据 tab）
  - 库存状态色 `--stock-low / --stock-out / --stock-ok / --stock-dead`
- `public/guangtian-logo.png` 复制就位（用户上传的光天科技红蓝圆形 logo）
- **GuangtianHero**：顶部红 50% / 蓝 50% 双段装饰条 + logo + "宜兴光天耐火材料 · **AI 库存管家**"（红字 accent）+ 副标 + 3 CTA（红"模拟入库" / 灰"SKU 档案" / 蓝"问问 AI"）

## Iter G2 — 9 个 tab 骨架
**Commit:** 7abe9cc（与 G1 合并提交）

- GuangtianDemoPage 顶层容器，9 tab horizontal nav（沿用 Jintai 的 `<div hidden>` 切换保 state）
- hash ↔ tab 同步（`#dashboard`、`#sku`、`#inbound`、`#outbound`、`#ledger`、`#shortage`、`#replenish`、`#ask`、`#report`）
- 每 tab 头：breadcrumb（"光天试点 / xxx"）+ title + 1 句副标
- 9 个 tab icon + 颜色：
  - 工作台（grid, brand-500）/ SKU 档案（pkg, brand-500）
  - 入库（inbox, guangtian-blue）/ 出库（upload, guangtian-blue）/ 流水（clock, guangtian-blue）
  - 缺货预警（warn, guangtian-red）
  - AI 补产建议（factory, ai-purple）/ 问问 AI（chat, ai-purple）
  - AI 库存日报（calendar, brand-700）
- footer：Powered by 智通 AI + 光天 logo + "v2026.05 演示版本（纯前端 mock）"

## Iter G3 — Tab 1 工作台 Dashboard
**Commit:** 14676a1

- 价值主张 banner：紫底 + 闪光 icon + "用 AI 把 1,000+ SKU 管清楚..."
- 7 KPI 卡片网格（desktop 7 列 / mobile 2 列），左色条按风险等级：
  - SKU 总数 1,286（brand 蓝）/ 今日入库 18（brand 蓝）/ 今日出库 23（guangtian 蓝）
  - 低库存 46（stock-low 橙）/ 订单缺货 7（guangtian-red 红）
  - 异常 12（warn-600）/ 呆滞 31（stock-dead 灰）
- 双栏布局：
  - 左 1.65fr：今日库存风险提醒 5 条（2 红 + 2 黄 + 1 灰），每条独立 tag badge + 详情 + CTA（"查看缺货预警" / "去 AI 补产建议"）跳对应 tab
  - 右 1fr：问问 AI 助手 sidecard（紫边）+ 6 快捷问题 + 1 AI 示例回答 + 数据来源 footer

## Iter G4 — Tab 2 SKU 产品档案
**Commit:** a8377fe

- 顶部筛选条：类别（全/高铝砖/莫来石/浇注料/刚玉砖）+ 状态（5 种）+ 搜索框 + "AI 帮我整理 SKU 命名"按钮
- 10 列表格：SKU 编码 / 产品 / 规格 / 类别 / 单位 / 库位 / 当前库存 / 安全库存 / 状态 / 操作
- 8 条耐火材料 mock：JT-HLZ-230-114-65 高铝砖 / JT-MLS-M70 莫来石 / JT-JZL-JC16 浇注料 / JT-GZB-AL80 刚玉砖 / JT-HLZ-T3-150 高铝砖异型 / JT-MLS-MS65 莫来石轻质 / JT-JZL-JC18-LR 低水泥浇注料 / JT-GZB-AL90 高纯刚玉砖
- 5 状态 badge：
  - 正常（绿）/ 低库存（橙）/ 缺货风险（红淡）/ 已缺货（深红）/ 呆滞（灰）
- AI 命名规则弹窗：4 段编码格式 `JT-HLZ-230-114-65` 配色拆解 + 8 个品类代码对照表 + "AI 生成迁移映射表"按钮

## Iter G5 — Tab 3+4 入库 / 出库登记
**Commit:** 29ab010

**入库**：
- 9 字段表单（双列网格）：SKU + 数量 + 单位 / 入库类型 / 批次 / 库位 / 关联生产单 / 操作人 / 附件
- "确认入库"按钮 → toast "入库登记成功 · 已写入流水 + 触发 AI 校验"
- 最近入库记录表 5 条（生产入库 + 采购入库，颜色绿正向）
- 右侧 AI 校验 sidecard（紫边 sticky）：批次重号 ⚠ 警告 + 库位匹配 ✓ + AI 小贴士（批次号规范 + 关联生产单 + OCR）

**出库**：
- 8 字段表单：客户订单 / 出库类型 / SKU / 数量（绑 state，>库存触发红框）/ 库位 / 批次 / 物流 / 操作人
- 库存不足（默认 200 vs 0）触发红色警告框：标题 + AI 三建议 + 3 操作按钮（分批 / 触发补产 / 联系客户）
- 提交按钮 disabled
- 最近出库记录表 4 条（已出库 / 部分出库 / 库存不足 3 种状态徽章）
- 右侧 AI 出货风险 sidecard（红边 sticky）：高风险 + 关注

## Iter G6 — Tab 5+6+7 流水 / 缺货 / 补产
**Commit:** be81d21

**库存流水追溯**：
- 筛选条：操作类型 pill（全/入/出/调拨/盘点/报废/退货）+ SKU 搜索 + 日期范围 + 导出 Excel 按钮
- 10 列表格：时间 / 操作 / SKU / 产品 / 变动（+绿/-红）/ 操作前 / 操作后 / 关联单据 / 操作人 / 备注
- 6 类操作徽章配色：入库绿 / 出库蓝 / 调拨紫 / 盘点橙 / 报废红 / 退货灰
- 8 条 mock（含调拨方向异常 + 盘点偏差 +12 + 部分出库未跟进）
- AI 异常识别 3 卡片网格（紫边）：盘点偏差 / 调拨异常 / 部分出库未跟进，"定位流水 →"按钮

**订单缺货预警**：
- 顶部摘要 pill 行：本周 3 笔 / 🔴 高 2 / 🟡 中 0 / 🟢 可发 1 + "AI 已 10:18 完成最新核对"
- 3 个订单卡片（左色边按风险）：
  - SO-20260519-001 江苏宏泰 高风险 ¥38,600 — 默认展开
  - SO-20260519-002 江苏宏泰 可发 ¥6,200 — 折叠
  - SO-20260519-003 常州新材 高风险 ¥62,400 — 折叠
- 展开内容：左 SKU 明细表（5 列含 缺口字段）+ 右 AI 处理建议（拆单 / 补产 / 调整交期 + 3 行动按钮）

**AI 补产建议**：
- 顶部紫边卡片：紫圆 factory icon + "AI 已推荐本周补产 3 个 SKU" + "✓ 生成本周补产计划"主 CTA
- 3 个补产 SKU 卡片，按优先级 #1 / #2 / #3：
  - #1 JC-16 浇注料 400 袋（高优先 红）
  - #2 M70 莫来石砖 600 块（高优先 红）
  - #3 AL90 刚玉砖 250 块（中优先 橙）
- 每卡片 5 列：优先级标 / SKU 名 / 库存进度条 / 建议补产数（大字 + 出炉日期）/ AI 理由（多句）+ 2 按钮（挂工艺组 / 调整数量）
- "生成补产计划"弹窗：AI 总结 paragraph + 编号列表 + 发送给工艺组按钮

## Iter G7 — Tab 8+9 问问 AI / 库存日报
**Commit:** 0db783e

**问问 AI 库存管家**：
- 左 1.7fr 对话区（min-height 540）：
  - Header 紫圆 chat icon + 标题 + "● 实时连接"徽章
  - 对话流：1 预装 mock 问答："今天哪些订单可能发不出去？" → AI 高/中/低分类回答 + 3 项数据来源 footer
  - 用户消息右蓝气泡 / AI 左白带紫边 + spark icon
  - 输入框 + 发送按钮（按输入有内容启用紫色）
  - 4 底部快捷（生成日报 / 缺货清单 / 补产建议 / 导出 SKU 表）
- 右 1fr sidebar（sticky）：
  - 8 预设问题（按 spec：今天哪些订单可能发不出去 / JT-HLZ-230-114-65 这周可以再出多少 / 哪些 SKU 应该补产 / 近 30 天哪些 SKU 没动销 / C-01 库位现在有什么货 / JC-16 浇注料过去半年的出货趋势 / 本月低库存预警有多少 / 给我生成今天的库存日报）
  - "AI 能干什么？" 说明 card（紫边）：查库存 / 查订单 / 给建议 / 找异常 / 写日报 + 免责声明（AI 不直接改库存数据）

**AI 库存日报**：
- 顶部 AI 自动生成提示条（紫边）："AI 已于 2026-05-19 18:30 自动生成" + "✓ 数据完整"绿徽章
- 主日报卡片（max-width 880 居中）：
  - 报头：YIXING GUANGTIAN REFRACTORY 英文小标 + 中文 H1（红字 accent）+ 日期 + 周二 + "陈总 / 仓库主管 · 内部参阅"
  - 红色 2px 底线
  - 摘要段（灰底卡）："今日入库 18 笔，出库 23 笔..."
  - 8 大块正文（每块蓝边小标 + 圆点列表）：
    1. 今日入出库（3 行）
    2. 缺货 & 风险（3 行 🔴/🟡）
    3. AI 补产建议（4 行）
    4. 库存异常（3 行）
    5. 呆滞 SKU 提醒（3 行）
    6. 库位使用情况（3 行 A/B/C 区）
    7. 下游订单展望（3 行 7 日窗口）
    8. 操作绩效（3 行 王主管/张仓管/李师傅）
  - 报尾：版本号 + 生成时间
- 底部分发栏（max-width 880 卡）：
  - 📋 复制全文（红）/ 📄 导出 PDF（蓝）/ 💬 发给陈总（绿）/ 💬 发给王主管（绿）/ 修改模板（灰）

## Iter G8 — 自审 + 截图 + 报告
**Commit:** be81d21 之后（无单独 commit，文档归集到 G9）

- 9 tab 截图全通过 Chrome MCP 1440×900 desktop 实拍验证
- 整体配色检验通过，沿用 Jintai iter 7 简洁原则
- 写本 iteration log

## Iter G9 — Logo 放大 + 全 9 tab 视觉减负
**Commit:** 9e9af51

### 用户反馈
"页面信息有点多 + busy + 光天 logo 太小不够醒目"。

### 光天 Hero
- logo **84px → 120px**（视觉权重 +40%）
- h1 **22px → 30px**，weight 800，红字 accent 加粗
- 副标 2 行长句 → 1 句"用 AI 把 1,000+ SKU 管清楚，提前 3 天发现缺货风险。"

### 工作台 Dashboard
- KPI **7 → 4** 张关键（SKU 总数 / 低库存 / 订单缺货 / 异常）
- KPI 字号 22 → 28，padding 14 → 18
- 价值主张 banner 删除（被 Hero 副标涵盖）
- 风险提醒 **5 → 3** (Top 3)
- AI 快捷问题 **6 → 4**

### SKU 档案
- 顶部筛选折叠成"高级筛选 ▸"按钮，默认只显示 search + AI CTA
- 表格列 **10 → 8**（单位合并入库存；操作列去掉）
- 状态色 **5 档 → 3 档**（缺货风险+已缺货 合并为"缺货"；呆滞独立灰）

### 入库 / 出库登记
- 字段折叠：入库 9 → 5 + 折叠 / 出库 8 → 4 + 折叠
- 备注移入折叠区
- AI 校验 sidecard **2 → 1** 条最严重
- 删除"AI 入库小贴士" footer
- 最近记录 **5/4 → 3** 笔
- 入库表格列 8 → 7（操作人入来源列）

### 库存流水
- 表格列 **10 → 7**（合并 操作前+后 为 "前→后"；操作人+备注 入关联单据）
- AI 异常识别 **3 → 1** 最严重

### 订单缺货预警
- 3 订单卡片**默认全折叠**（不再默认展开 001）
- 行内 1 句 AI 建议摘要（高风险订单）

### AI 补产建议
- AI 理由长文本 → 1 句概要

### 问问 AI
- 预设 **8 → 4** 最有故事性
- "AI 能干什么？" 5 行 → 3 行

### 库存日报
- **8 大块 → 5 块**（合并入出库为流水；合并缺货+异常+呆滞为风险/库位概况）
- 摘要 80 字 → 60 字

### 全局
- 卡片 gap 14-18 → 20-24
- 卡片 padding 16-18 → 20-22

### 数字总览
| Tab | 元素 | Before | After | 减幅 |
|---|---|---:|---:|---:|
| 工作台 | KPI | 7 | 4 | -43% |
| 工作台 | 风险列表 | 5 | 3 | -40% |
| 工作台 | 快捷问题 | 6 | 4 | -33% |
| SKU 档案 | 表格列 | 10 | 8 | -20% |
| SKU 档案 | 状态色 | 5 | 3 | -40% |
| 入库登记 | 默认字段 | 9 | 5 | -44% |
| 入库登记 | AI 校验 | 2 | 1 | -50% |
| 入库登记 | 最近记录 | 5 | 3 | -40% |
| 出库登记 | 默认字段 | 8 | 4 | -50% |
| 出库登记 | AI 风险 | 2 | 1 | -50% |
| 库存流水 | 表格列 | 10 | 7 | -30% |
| 库存流水 | AI 异常 | 3 | 1 | -67% |
| 缺货预警 | 默认展开数 | 1 | 0 | 全折叠 |
| 问问 AI | 预设 | 8 | 4 | -50% |
| 库存日报 | 大块数 | 8 | 5 | -38% |
| Hero | logo size | 84px | 120px | +43% |
| Hero | h1 size | 22px | 30px | +36% |

## Iter G10 — 全面交互激活 + Toast + 数字联动
**Commit:** 4a8e50a

### 用户反馈
"让更多按钮可实际操作 + 增强真实感可用性 + 全面优化 UI。客户演示时点哪都有反应，像真能用的系统不是静态展示。"

### 基础设施（新文件 2 个）

#### `state.tsx` (Context Provider)
- 提升 4 大状态到 GuangtianProvider 全局：
  - `skuStocks: Record<string, number>` — 实时库存 map
  - `inboundRecords / outboundRecords / ledgerEntries` — 流水列表
  - `todayInboundCount / todayOutboundCount` — KPI 计数
- `addInbound(entry)` — 一次提交联动 3 件事：库存 +N + 入库表 prepend + ledger prepend + toast
- `addOutbound(entry)` — 同上反向 + 库存不足拒绝 + 错误 toast
- `pendingAsk` + `setPendingAsk` — Dashboard 推送问题给 Ask tab

#### `Toast.tsx` (Toast 系统)
- 右上角固定 + 滑入动画 (220ms)
- 5 种 level：ok 绿 / warn 黄 / err 红 / info 蓝 / ai 紫
- 自动 3.5s 消失 / 点击立即关闭
- icon: ✓ ⚠ ✗ ℹ ✦
- 顺便提供 `<Spinner>` 组件给 loading 状态

### 激活的交互（25+）

**Dashboard**
- 4 KPI 卡片 click → 跳对应 tab + info toast（低库存→SKU 等）
- KPI hover translateY -2px + shadow lift
- 4 AI 快捷问题 click → setPendingAsk + 跳 ask tab 自动 send
- 风险列表 CTA "查看缺货预警" → 跳转 + toast
- KPI 数值 live 派生（低库存 count 用 skuStocks 算）

**SKU 档案**
- 8 SKU 库存数字 live （入库后跳来这里看 +N）
- 状态色重算（live stock 决定 正常/低库存/缺货/呆滞）
- 行 hover 浅灰 + click → toast 显示库存详情
- "让 AI 生成迁移映射表" → toast + 关闭弹窗

**入库登记**
- 9 字段全受控 state
- SKU 切换 → 单位 + 库位自动同步
- 数量行 live 预览 "提交后库存 X → Y"
- 提交 → 0.7s spinner "AI 校验中…" → toast + 表格加行 + 库存 +N

**出库登记**
- 8 字段全受控 + SKU/订单联动
- 数量 > 库存 → 红框 + 红警告 + 提交 disabled
- 数量 ≤ 库存 → live 显示 "出库后剩 Y"
- "分批出库（先出 X）" → 自动填入 currentStock
- "触发补产单" / "联系客户" → toast
- 提交 → 0.7s spinner → toast + 表格加行 + 库存 -N

**库存流水**
- ledgerEntries 全部 context 派生（入出库后自动 prepend）
- "导出 Excel" → info toast (显示导出条数)

**缺货预警**
- 3 订单的 "采纳建议 / 联系客户 / 查看历史" 全 toast

**AI 补产建议**
- "生成本周补产计划" → 1.2s spinner → 弹窗
- 每行 "挂到工艺组" → toast + 按钮变绿 "✓ 已挂"
- 弹窗 "发送给工艺组" → 微信发送 toast

**问问 AI**
- 4 预设 mock 答案库（PRESET_ANSWERS）含数据来源
- pendingAsk 自动 send
- 输入框真响应 + 1s thinking spinner
- 4 快捷按钮 → 对应回答或 toast
- 600px 固定高 + 双 rAF 自动滚底

**AI 库存日报**
- "复制全文" → navigator.clipboard 真复制 + toast
- "PDF / 微信发陈总 / 微信发王主管 / 修改模板" → toast

### 验证截图

通过 Chrome MCP 实测（1440×721 desktop）：
- 入库提交 ID `ss_8981j4t26` — Toast "✓ 入库成功 · 高铝砖 +800 块 · 库存 4,280 → 5,080" 弹出 + SKU 下拉同步 + 表格 prepend
- SKU 档案 `ss_6483whoan` — 跳到这里看库存数字已变 5,080
- Dashboard KPI 点击 `ss_45632gas2` — 自动跳缺货预警 + info toast
- 问问 AI 预设 `ss_04487bl2t` — JC-16 趋势 mock 答案 + 数据来源 1,842 条出货

### 三大演示亮点

1. **「录一笔库存全变」**：入库 tab 提交 → toast 弹 → SKU 档案库存数字立即同步 → 库存流水首行就是这笔
2. **「KPI 是入口而非数字」**：工作台 4 个 KPI 都能直接点跳到对应明细 tab
3. **「问问 AI 真像 AI」**：预设点击 → 用户气泡 → 1s spinner "AI 正在查询" → 答案带数据来源 + 滚到底部

### Bug 修复
- SKU 状态阈值：原逻辑 `< safety * 0.5 → 已缺货` 误判 M70 320/800 为缺货。修正为 0 → 已缺货 / 0<stock<safety → 低库存。

## Iter G11 — 对齐光天新 spec
**Commit:** 5d7c1d0

### 用户反馈
新 spec 详细要求列举到字段级，找 G1-G10 已实现的 gap 并精确补缺。

### Gap 清单 → 补齐 8 项

#### 1. SKU 台账列扩展（SkuCatalogPanel）
- 列 8 → 9（产品名+规格合并 / 加 **材质** / 加 **最近入库** / 加 **最近出库**）
- 材质映射：高铝砖→高铝 / 莫来石砖→莫来石 / 浇注料→刚玉 / 刚玉砖→刚玉
- 状态枚举加 **"数据异常"**（紫色 ai-purple-deep）
- AL80 由"缺货风险"→"数据异常"（反映盘点偏差 +12）
- 状态优先级修：数据异常 / 呆滞标签不被库存阈值覆盖

#### 2. 库存流水 AI 置信度 + 已确认（LedgerPanel）
- 列 7 → 9（加 **AI 识别置信度** + **已确认状态**）
- ConfidenceBadge：≥90 绿 / 75-89 橙 / <75 红
- 已确认绿 badge / 待确认橙按钮（点击 `confirmLedger` → toast + 状态变绿）
- `state.tsx` 新增 `confirmLedger(time, sku)` 函数
- 新增入/出库 auto-confirm 96-99%

#### 3. 订单缺货预警 4 级 + 预计可发货状态（ShortageAlertPanel）
- 风险等级 3 → 4 级（加 **"紧急" urgent** 深红 + pulse 动画）
- `gt-pulse-urgent` 1.8s 循环阴影脉冲
- 每订单加 FulfillmentPill：迷你进度条 + "**可全发 / 可部分发 X% / 需补产**"
- SO-20260519-001 由 high → urgent（5/22 仅 2 天后）

#### 4. AI 单据录入三段（InboundPanel）
- 顶部新增 "AI 单据录入 · 上传扫描件 / 拍照" 区
- 2 mock 单据（📄 江苏华峰 PDF / 📷 王主管拍照），1.5s spinner
- 识别后三段网格：
  - **① AI 识别字段**（绿，≥90% 高置信）
  - **② 待确认字段**（橙虚线框，<90% 需复核）
  - **③ 异常提示**（红，AI 发现的逻辑异常如"采购单号系统未找到 / 批次号命名不一致"）
- "采纳 AI 识别" → 一键回填表单 + toast

#### 5. 问问 AI 结构化答案 + 可点击链接（AskInventoryPanel）
- 预设 4 → **5 spec 问题**：库存不够 / 江苏宏泰能发 / 出库最快 / 可能漏记 / 明天优先生产
- AI 答案从纯文本 → **结构化 AnswerBlock**：
  - 结论（whiteSpace pre-line 多段）
  - 风险等级 badge（5 级 urgent/high/medium/low/info）
  - 数据依据（chip 行 + 来源数据条数）
  - 建议动作（有序列表）
  - **可点击明细**按钮（跳 sku/shortage/ledger/replenish/report tab + info toast）
- 旧 sample 走 role: "ai" 保留兼容，新答案走 role: "ai-block"
- GuangtianDemoPage 传 onGoTab prop 给 Ask panel

### 没补的（已经有了或低优）
- SKU 批次列 — 批次是 per-入库非 per-SKU，逻辑上不合适放 SKU 表（保留在流水中）
- 材质 rename — 已通过派生映射展示，无需改 data.ts category 字段
- ❌ 新建 "AI 收件箱" tab — 按红线"不重复造 tab"，融进 InboundPanel 顶部

### 验证截图
- SKU 9 列 + 材质 + 数据异常紫 badge：`ss_5633rljdg`
- 缺货 4 级 + 紧急 pulse + FulfillmentPill：`ss_2621lyo47`
- Ledger 9 列 + AI 置信度 + 已确认/待确认：`ss_2749045qp`
- AI 单据上传三段：`ss_4649rwgop`
- AI 结构化答案 + 跳转按钮：`ss_1237llez5`
