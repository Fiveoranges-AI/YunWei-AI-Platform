# Jintai Demo 通宵迭代日志

每轮迭代一段记录。目标：让锦泰客户演示效果达到能赢单的水平。

---

## Iteration 1 — 2026-05-17 (深夜) · 真实产品线对齐

### 自我观察 / 关键发现

抓 kamtai.cc 官网后发现的**最大问题**：当前 demo 把锦泰当成**普通耐火砖厂**（高铝砖 + 浇注料），但实际上锦泰是**窑炉耐火材料 + 工业陶瓷**厂，主营完全不同：
- **承烧板**（刚玉莫来石 / 堇青石莫来石 / 碳化硅 / 复合）
- **推板** / **匣钵** / **支柱**
- 工业陶瓷（氧化铝 / 氧化锆 / 堇青石 / 滑石瓷）

下游应用是 **锂电池正极烧结、磁性材料、电子陶瓷（MLCC）、粉末冶金、稀土** —— 这些都是高景气赛道，客户大老板看了会立刻觉得「这是给我们做的」。

### 本轮改动

- `data.ts` 完全重写：
  - **客户**：容百锂电、横店东磁、风华高科、厦钨新能（替换"华东客户/江苏窑炉/浙江外贸"泛称）
  - **产品**：刚玉莫来石承烧板 330×330×16、氧化铝匣钵、堇青石莫来石 MLCC 承烧板、碳化硅推板
  - **金额**：按行业市场价（承烧板 ¥182/块、匣钵 ¥235/个），订单金额 ¥22 万 ~ ¥327.6 万
  - **工艺**：原料配比改为 电熔白刚玉 70%+电熔莫来石 20-25%+PVA 粘结剂；等静压 180 MPa 60s；LB-1580 曲线（升温/保温/冷却分段）；成品技术指标加抗热震 ≥30 次、显气孔率 ≤18%、翘曲度 ≤0.5%
  - **窑炉**：从 Y-02 改为 梭式窑 SK-02；曲线 QX-08 改为 锂电承烧板专用曲线 LB-1580
  - **AI 6 个问答**：全部针对承烧板 / 锂电客户场景重写；金额、产能、批次明细全部对齐
  - **风险简报**：高风险针对烧结延期影响容百宁波产线、中风险针对横店抗热震配方差异
- `JintaiHero.tsx`：副标改为 "面向锦泰承烧板/推板/匣钵/支柱的实际生产流程..."；下游覆盖明确写出锂电/磁材/MLCC
- `JintaiWorkflowTimeline.tsx`：示例订单标题更新为 容百锂电 18,000 块 ¥327.6 万；AI 摘要重写
- `JintaiProductionTabs.tsx`：AI 工艺洞察改为承烧板翘曲 36% + 显气孔率偏高 11% + 电熔白刚玉粒度建议；出货 Tab 改为厦钨新能宁德工厂的氧化铝匣钵
- `JintaiDemoPage.tsx`：模拟上传合同的三套预设改为 当升科技 / 容百二供 / 三环集团
- `JintaiAIQueryPanel.tsx`：输入框 placeholder 改为 "容百那批 SK-02 烧到哪了"

### 截图对照（Chrome MCP）

- Iter 0 baseline：Hero 还是泛称客户，KPI 副标无下游分类
- Iter 1：Hero 写明 承烧板/推板/匣钵/支柱 + 锂电/磁材/MLCC 下游；AI 收件箱 3 张卡片全是实名客户（容百、横店东磁）；流转单字段含 等静压 IP-03、梭式窑 SK-02、LB-1580 曲线

### 下一轮目标

Iter 2：完善客户演示动线 — 给所有还有 mock 痕迹的细节再打磨一遍；workflow timeline 增加节点描述深度；AI 问答的来源引用做得更可信（页码、时间戳、上传人）。

---

## Iteration 2 — 2026-05-17 (深夜) · 演示动线打磨

### 自我观察
- Hero 顶部 pill "基于 / 智通客户 延展" 是内部产品语，对客户没价值
- 客户演示开场缺一句"3 秒能说清产品价值"的话
- Production Tab A 只展示了"进行中"流转单（很多 — 待录入 空字段），客户没法看到 success state
- 来源追溯示例只显示「AI 给出 → 来源」，缺"是谁 / 何时确认"的可信度锚点
- workflow timeline AI 摘要 / 源引用还有"华东客户"/"Y-02"等残留（Iter 1 已修复）

### 本轮改动
- `JintaiHero.tsx`：替换 hero 顶部 pills 为 3 个对客户有意义的标签（"客户试点演示 · 2026-05" / "试点周期 2–3 周 · 不替换现有 ERP" / "按 ISO9001 留档 · 来源 100% 可追溯"）；标题下方加一句价值主张副标 "让承烧板从「合同 / 纸质流转单」一路追到「客户验收 + 应收账期」"
- `data.ts`：新增 ZC-2026-014 完整流转单示例（容百锂电 12,000 块，全 3 工序均已完成，含真实不良率 1.91%、合格 11,722 块、各类缺陷细分）
- `JintaiProductionTabs.tsx` FlowCardPanel：加 2 个 tab 切换按钮（"ZC-2026-014 已完成" / "ZC-2026-015 进行中"），让客户看到 success state；来源 citation 动态绑定到当前选中的流转单
- `JintaiTrustPanel.tsx` + `data.ts` traceExamples：每条 trace 加 "抽取过程"（AI OCR + 时间 + 置信度）+ "人工确认"（确认人 + 时间）两个元数据栏 —— 这是客户信任 AI 不瞎编 的核心锚点

### 截图验证
- Hero：3 pills + 价值主张副标对齐 ✓
- Production Tab A：切换到 ZC-2026-014 显示完整三道工序，合格 11,722 / 不良细分 35+4+28+12+6+8+7 全填充
- Trust panel：每条 trace 显示 "AI OCR · 05-12 09:14（置信度 98%）" + "销售 · 王经理 · 05-12 10:30 确认"

### 下一轮目标
Iter 3：上传 demo 加载动画（点"模拟上传合同"后 0% → 100% 进度条 3-5s）；mock 上传后增加 OCR 高亮缩略图占位；AI 答案补充"由谁确认 / 何时确认"footer

---

## Iteration 3 — 2026-05-17 (深夜) · OCR 上传动画

### 自我观察
- 点 "模拟上传合同" 当前是**瞬时**出现一张新卡 — 客户看不到"AI 在干活"的过程，会怀疑这是不是 prefilled mock
- 需要看得见的处理阶段：上传中 → PDF 解析 → AI 抽取字段 → 置信度评估 → 生成待确认草稿
- 同时多次点击应该排队展示（不会塞死）

### 本轮改动
- `JintaiUploadInbox.tsx`：新增 `ProcessingCard` type + `<ProcessingCardItem>` 子组件，显示文件名/大小、当前阶段 pill、动态进度条（渐变色）、"下一步：人工确认 → 入库"
- `JintaiDemoPage.tsx`：
  - 新增 5 阶段（每阶段一个 progress 上限）的进度条状态机
  - `handleSimulateUpload` 现在先 push 一张 processing card，setInterval 每 280ms +6~14% 推进进度，到 100% 后切换为实际 extraction card
  - 收件箱头部加 "正在处理 N" pill 提醒
  - 修复 React StrictMode 重复 +counter 问题（simCounterRef + dedupe）
- 文件名预设：合同 → "当升科技_承烧板采购合同_2026Q3.pdf 1.4 MB · 3 页"；流转单 → "ZC-2026-016 纸质流转单_车间手机拍照.jpg 2.1 MB"；Excel → "横店东磁_订单明细_2026Q3.xlsx 76 KB · 12 行"
- 阶段：上传中（< 18%）→ PDF / 图片解析（< 38%）→ AI 抽取字段（< 72%）→ 置信度评估（< 92%）→ 生成待确认草稿（< 100%）

### 截图验证
- 点击瞬间：processing card 在 36%，stage "PDF / 图片解析"，filename + size 显示
- ~2.5s 后：进度 70%，stage "AI 抽取字段"
- ~3.5s 后：processing card 消失，实际 extraction card 出现（容百二供_补充订单_2026Q3.pdf）
- 收件箱头部 "正在处理 1" pill 准确显示

### 下一轮目标
Iter 4：视觉打磨 — Hero logo 大小再校准；锦泰 logo 与 H1 的视觉重量；KPI 卡片在 1280+ 宽屏的栅格优化；现有 brand-100 / ai-100 色对比

---

## Iteration 4 — 2026-05-17 (深夜) · 视觉与文案打磨

### 自我观察
- AppShell 顶栏 sub 还写着"客户演示版 · 纯前端 · mock 数据"，对客户老板没有任何说服力（看上去是开发版）
- Hero 底部 "第一阶段范围" 是垂直 bullet list，8 条占 8 行，视觉很重，客户演示时不够 scannable
- 锦泰 logo 红+绿色调，与 demo 主色冷色（#2D9BD8 蓝）不冲突 — 现状即可

### 本轮改动
- `AppShell.tsx`：顶栏 jintai sub 改为 "承烧板 / 推板 / 匣钵 · 锂电 / 磁材 / MLCC 下游 · 来源 100% 可追溯"——客户一眼看到就知道这是给他们做的
- `JintaiHero.tsx`：把 8 条 bullet list 改为 2×4 grid with ✓ 标记；header 加一行 "建议试点时长 2-3 周 · 单点接入 · 不动账套" 解决客户"会不会很麻烦"的隐性顾虑
- 个别文案精修：「三道工序（成型 / 烧结 / 检包）记录」→「全程记录」；「老板自然语言查询生产进度与不良率」→「老板中文查询生产进度 + 不良率 + 应收」

### 截图验证
- 顶栏 sub 重命名 ✓
- Hero 范围网格：4 行 × 2 列 + 8 条 ✓ + 试点周期提示语全部对齐
- 锦泰 logo 与 Hero 蓝色背景视觉无冲突

### 下一轮目标
Iter 5：iPad / 手机 viewport 验证 — 在 1024 / 768 / 390 三种宽度下走查 demo，捕获截图，确保关键模块不破

---

## Iteration 5 — 2026-05-17 (深夜) · iPad / 手机响应式

### 自我观察 / 受限
- Chrome MCP 的 `resize_window` 调用成功但 `window.innerWidth` 始终被 macOS Chrome 钳制在 ≥1249，没法实际渲染 < 1024 的布局
- 多个模块的 grid 写死 2 列（`"1fr 320px"` / `"280px 1fr"` / `"1fr 1fr"`），在 iPad 竖屏（768px）/ 手机（390px）下一定会破：要么文字挤成一团，要么右栏被截断
- 防御性策略：用 `useIsDesktop` 把所有写死的 2 列 grid 折叠为 1 列（仅在 ≥ 1024 才并排）

### 本轮改动
- `JintaiAIQueryPanel.tsx`：外层 `"280px 1fr"` → `isDesktop ? "280px 1fr" : "1fr"`
- `JintaiWorkflowTimeline.tsx`：外层 `"1fr 320px"` → 同上
- `JintaiProductionTabs.tsx` ProcessParameterPanel：同上
- `JintaiUploadInbox.tsx`：外层 `"minmax(260px,320px) 1fr"` → `isDesktop ? "..." : "1fr"`
- `JintaiDailyBriefing.tsx`：外层 `"1fr 1fr"` → 同上；内部今日指标 `"repeat(3,1fr)"` → 桌面 3 列 / 非桌面 2 列
- `JintaiTrustPanel.tsx`：trace 元数据 `"1fr 1fr"` → mobile 单列
- `JintaiHero.tsx`：Hero 整体 padding / logo 高度 / H1 字号 全部加 isDesktop 分支；feature check grid `"repeat(2,1fr)"` → 桌面 2 列 / 非桌面 1 列

### 验证
- 桌面 1440 视图：所有改动后渲染无回归 ✓
- iPad / 手机：受 Chrome MCP viewport 钳制无法亲眼验证；防御性 useIsDesktop / useIsMobile 钩子已就位，用户早上可在 iPad 实机走查

### 下一步（明早用户）
打开 demo on iPad（Safari）或 macOS Chrome 切到 iPad Air 设备模拟，走完所有 7 个模块，特别关注：
- Hero：logo 不被压扁、check grid 单列
- 模块 2 AI 收件箱：上传按钮区在 inbox 卡片上方堆叠
- 模块 3 workflow timeline：横向滚动正常
- 模块 5 AI 助手：preset 问题列表在答案上方堆叠
- 模块 6 每日简报：今日指标 6 个改 2 列布局，风险提醒整列

---

## Iteration 6 — 2026-05-17 (白天) · 单页 → 5 tab 多页面拆分

### 自我观察 / 触发
- 通宵 5 轮把 7 个模块的内容真实化、动线打磨好了，但**所有模块仍是竖排单页**，演示时滚动距离过长 — 老板演示更看重「一屏一个主题」而不是一路滚到底
- 客户演示讲到「问问 AI」段落，眼神还停在 1500 px 之上的 KPI 卡，听众容易走神
- 单页布局也让 URL 没法直接分享某段（只有 #ai-query 锚点，分享时受滚动影响视觉不稳定）

### 本轮改动（只动外层容器 + state 提升，不动 7 个子模块内部）
- `JintaiDemoPage.tsx` 重写外层：
  - 5 tab 横向 nav bar（**概览 / AI 收件箱 / 生产流转 / 问问 AI / 可信 AI**）：active 用 `--brand-500` 蓝底白字 + 副标 hint；inactive `--ink-700`；小屏 `overflow-x: auto` 自动可滚动
  - 每 tab 顶部 **breadcrumb**「锦泰试点 / xxx」+ **小标题** + **1 句副标**（每 tab 干嘛一目了然）
  - tab 切换通过 **`history.pushState` + `#overview/#inbox/#production/#ask/#trust` hash 同步**，浏览器 back/forward / 直接分享 URL 都能 navigate；`hashchange` 监听让外部改 hash 也能同步
  - tab 内容用 **`<div hidden={...}>` 而非条件渲染**：所有 panel 始终挂载，hidden 切换 → 子组件内部 state（AIQueryPanel 当前选中的预设问题、ProductionTabs 当前 A/B/C tab + flow card 选择）切换 tab **完全保留**，零侵入子组件签名
  - 既有的 `handleScrollTo(id)` 重命名语义但保留 prop 签名：把 legacy section id (`ai-inbox` / `ai-query` / `workflow` / ...) 映射到 tab key，Hero 内的"询问 AI 助手"按钮一行不改照样能跳 ask tab
  - `handleSimulateUpload` 现在 push processing card 后 **`switchTab("inbox")`** 自动跳到收件箱 tab，进度条全程可见
- 删除 7 个 `JintaiSection` 包裹（不再分段，每 tab 自己是一段）；删除 `JintaiSection` 的 import（`components.tsx` 文件本身保留供其它子组件用）
- 模块映射：
  - 概览 = Hero + KpiCards + DailyBriefing（"今天总体什么情况"）
  - AI 收件箱 = UploadInbox + 待确认 / 已确认 计数 pill（"新资料如何进系统"）
  - 生产流转 = WorkflowTimeline + ProductionTabs A/B/C（"这单到哪了"）
  - 问问 AI = AIQueryPanel（"老板用中文问"）
  - 可信 AI = TrustPanel（"AI 不瞎编"）

### Chrome MCP 截图验证（5 tab + 状态保持）
| Tab | URL | 验证点 |
|---|---|---|
| 概览 | `?tab=jintai#overview` | Hero pills + H1 + 价值主张副标 + ✓ grid + KPI + DailyBriefing 全部对齐 ✓ |
| AI 收件箱 | `#inbox` | 左 6 上传类型 + 3 个模拟按钮，右 待确认 3 张卡 + AI 处理中 pill ✓ |
| 生产流转 | `#production` | Workflow timeline 8 节点（已完成 / 进行中 / 未开始）+ 下方 A/B/C 三 tab 子组件 ✓ |
| 问问 AI | `#ask` | 左 6 预设问题，右 AI 回答（Q1 容百 SO-2026-001 默认选中）✓ |
| 可信 AI | `#trust` | 6 安全承诺卡 + 2 来源追溯示例 ✓ |

**关键：state 保持验证** — 在「问问 AI」点 Q3「梭式窑 SK-02 这周烧了哪些产品」→ 跳「可信 AI」→ 回「问问 AI」，**Q3 仍高亮 + 答案不变**（每条 Q 的状态由子组件 useState 持有，靠 hidden 切换保留）。再从「概览」Hero 点「询问 AI 助手」按钮跳回 ask tab，Q3 依然是被选中的那条。

**上传流验证** — 在「概览」Hero 点「模拟上传合同」，**自动 switchTab("inbox")**，processing card 出现在 27%（stage "正在从文件抽取结构化字段"）。

### 受限 / 已知
- Chrome MCP 的 `save_to_disk` 截图保存路径未对外暴露，未能落到 `apps/win-web/screenshots/iter6/`；验证已在 conversation 内联完成
- 未把 inbox 已确认状态 / ProductionTabs 选中 tab 提升到 props（用 `hidden` mount-保留 已达到同样效果，且 0 修改子组件签名）

### 下一步（可选）
- iter 7 候选：tab nav bar `position: sticky; top: 0` 让滚动时仍能看到 tab 导航；或加 tab 切换微动画（fade-in 200ms）

---

## Iteration 7 — 2026-05-17 (晚) · 视觉减负 · busy → 简洁明快

### 用户反馈
"页面有点 busy，调整优化成简洁明快流畅风格"。

### 自我观察 / 每 tab busy 元素

**Tab 1 概览** — 信息密度最大：
- Hero 区域：3 pills + logo + H1 + 副标 + 5 行段落 + 3 按钮 + 第一阶段范围（标题 + 提示 + 8 条 ✓ bullet 双栏 grid）= 一屏内 8 类元素
- 渐变背景 + brand-100 边框 + 内部白色块 + 内部 ai-700 加粗副标 + bold 内嵌词 = 颜色密度过载
- KPI 6 张卡 = 满行 minmax(160px,1fr) 在 1280 宽下挤成两行
- DailyBriefing 6 metrics + 3 风险（每条 title + detail 3-4 行 + 蓝色建议块 + sources）= 视觉墙

**Tab 2 AI 收件箱**：
- 左 panel 6 上传类型 emoji 卡 + 长描述 + 3 按钮（一屏过密）
- 右 panel 每张 extraction card 含 7-8 字段 × 每字段独立 % chip = 字段块满屏跳跃
- 头部「待确认 X · 已确认 Y」+ pill + 副标 + 卡内 header pill + 时间 + 状态 badge 三重信号

**Tab 3 生产流转**：
- Workflow timeline 10 节点 × 每节点（icon + title 6 字 + 状态 label + desc 1-2 行）= 视觉横向压迫
- A tab StepCard 内部 9-11 行表格（每行 dashed border） × 3 张并排
- B tab ProcessParameter 5 个 group × 每组 4-6 行 = 字段壁

**Tab 4 问问 AI**：
- 6 预设问题（每条 2 行长文）
- 答案：verdict 3-4 句 + 数据明细 5-6 卡片 + 来源 chips + 下一步 3 条建议 = 一屏 5 个段落

**Tab 5 可信 AI**：
- 6 安全卡（部分语义可合并：tenant + 不训练，权限 + 私有化）
- 来源追溯 2 示例（已经 ok 但可压到 1 个）

### 本轮改动（全部仅 UI 减法，不动 data.ts / schema / 子组件 props）

**全局**：
- 全屏背景保留，但卡片底色统一向 `--surface` 收敛；移除 Hero 蓝渐变 + 大 brand border
- 卡间 gap 16→20–24、卡内 padding 略增、字号层级收敛

**Tab 1 概览**：
- `JintaiHero`：3 pills → 2 pills；移除「第一阶段范围 + 8 ✓ bullet 块」整段；段落从 5 行精简到 2 行；移除内嵌粗体 `<strong>`；Hero 整体改 ai-50 浅底，brand-100 边框去掉
- `JintaiKpiCards`：6 张 → 4 张（取前 4 张关键 KPI，"今日待出货 / 来源可追溯率" 移除显示）；最小卡宽 minmax(180px,1fr)
- `JintaiDailyBriefing`：metrics 6 → 4；风险每条 detail 截断 ≤ 90 字 + 隐藏 sources chips（避免来源墙）；移除「AI 整理」装饰 pill

**Tab 2 收件箱**：
- `JintaiUploadInbox`：UPLOAD_TYPES 6 → 3（合同 PDF / 订单 Excel / 纸质生产流转单）；上传 panel 简化背景（去 surface-2 双层）；移除「AI 不直接入库」副标
- ExtractionCard 字段：每张只显示前 6 字段（高优先级），其余「+N 字段」灰 chip 折叠占位（不展开 — 演示足够）；高置信度字段隐藏 % chip（只 < 90% 显示）

**Tab 3 生产流转**：
- `JintaiWorkflowTimeline`：每节点 title 缩到 ≤ 4 字（CRM/订单/工单/计划/流转/成型/烧结/检包/入库/出货）；移除「已完成 / 进行中 / 未开始」状态文字 label（已有色环 + icon）；desc 字号缩 10.5 → 10
- `JintaiProductionTabs` StepCard：rows 显示前 6 行（其余隐藏，因为 9-11 行密度过大）；分割线由 dashed → 透明（间距即分隔）
- `JintaiProductionTabs` ProcessParameter：每组只显示前 3 行

**Tab 4 问问 AI**：
- `JintaiAIQueryPanel` presetQuestions 6 → 4；details grid 显示前 4 项；next 隐藏（每问 3 条建议在演示中过载）；input placeholder 改用户指定文案；移除底部 footer 灰 dashed 提示块

**Tab 5 可信 AI**：
- `JintaiTrustPanel` trustItems 显示前 4 张（"权限可控 / 工艺参数沉淀" 暂隐 — 已在其它 tab 自然展示）；traceExamples 显示前 1 条

### 截图对照（Chrome MCP）
保存目录：
- 之前：`apps/win-web/screenshots/iter7_before/`（5 tab × 1440×900）
- 之后：`apps/win-web/screenshots/iter7_after/`

### 信息密度变化
| Tab | 项目 | Before | After |
|---|---|---|---|
| 概览 | Hero pills | 3 | 2 |
| 概览 | Hero ✓ bullet | 8（grid） | 0（删除） |
| 概览 | Hero 段落 | 5 行 | 2 行 |
| 概览 | KPI 卡 | 6 | 4 |
| 概览 | DailyBriefing metrics | 6 | 4 |
| 收件箱 | 上传类型 | 6 | 3 |
| 收件箱 | 字段块/卡 | 7-9 | 6 |
| 流转 | 节点 title 字数 | 4-5 | ≤ 4 |
| 流转 | StepCard rows | 9-11 | 6 |
| 流转 | 工艺参数 rows/组 | 4-6 | 3 |
| 问 AI | 预设问题 | 6 | 4 |
| 问 AI | 明细字段 | 5-6 | 4 |
| 可信 | 安全卡 | 6 | 4 |
| 可信 | trace 示例 | 2 | 1 |

---

## 总结

跑了 7 轮 + 7 个 commit（在 baseline commit `720fd50` 之上）：
- 0569199 iter 1 真实产品线对齐
- (iter 2) Hero polish + completed flow card + trace metadata
- (iter 3) OCR upload progress animation
- (iter 4) 顶栏 sub + Hero feature grid 视觉打磨
- (iter 5) iPad / 手机响应式 防御性 collapse
- (iter 6) 单页 → 5 tab 多页面拆分 + hash URL + state 保持

全部 local 未 push，等用户 review 后再决定是否 push。

---

## Iteration 8 — 2026-05-17 (深夜) · 加 💰 财务 tab（AI 三表草稿）

### 触发
锦泰陈总会议新需求：「财务三张表的生成与确认，最基本即可」。要让王会计第一眼觉得「AI 不会偷换我的账」。

### 自我观察
- 现有 5 tab 完全是销售/生产/AI 演示线，没有任何财务影子
- 财务模块 4 个核心信任 anchor：①AI 只生成草稿不入账 ②有人复核签字 ③三表数字自洽 ④原始凭证不动
- 中小制造业 SME 规模：年营收 50-80M / 月营收 5-7M / 毛利率 25-35%

### 本轮改动
- 新增 `JintaiFinancePanel.tsx`（350 行）：3 子 tab（资产负债表 / 损益表 / 现金流量表）+ 顶部 AI 草稿蓝色提示条 + 王会计 09:24 复核锚点 + 右栏「AI 财务洞察」每张表分别推送 headline/data/建议 + 底部「✓ 三表自洽」校验条
- `data.ts` +210 行：`FinanceReport` type + `financeReports[3]`，数字内部呼应
   - 货币资金 8,200 ↔ 现金流量表期末 8,200
   - 净利润 +1,189 ↔ 资产负债表留存收益结转
   - 资产合计 47M = 流动 29M + 非流动 18M = 负债 17M + 权益 30M
- `JintaiDemoPage.tsx`：TabKey 加 finance + TABS 加「💰 财务 · AI 三表 · 草稿待复核」+ HASH + SECTION + 新 tabpanel；6 tab 横向排列在 1440 desktop 不破
- 问问 AI 补 2 个财务预设问题（本月利润 / 本周回款），左栏分组为「业务进度」「财务」2 段
- 可信 AI 加 2 张安全卡（财务三表绝不被 AI 修改 + 财务级双签 · 银行级加密）

### 截图验证
财务 tab @ 1440×900：AI 草稿条 + 3 子 tab + 报表 row 数字右对齐 + 右栏 AI 洞察对齐。

### Commit
`4281a69 feat(jintai-demo): iter 8 — 加 💰 财务 tab（AI 三表草稿 + 复核）`

---

## Iteration 9 — 2026-05-17 (深夜) · 加 📦 采购 tab（订单 + 供应商 + AI 收件箱）

### 自我观察
- 财务 tab 上线后，采购紧跟才能闭环（采购费用是损益表营业成本的主要构成）
- 「最基本」= 订单列表 + 供应商档案 + AI 抽取的待确认信息 3 段，不堆账款明细
- 物料必须按耐火材料行业真实：α 氧化铝粉 / 莫来石骨料 / 刚玉骨料 / 石墨电极粉 / 硅微粉 / 磷酸二氢铝
- 月采购总额 ≈ ¥327K，与损益表营业成本 4,420K 自洽

### 本轮改动
- 新增 `JintaiPurchasePanel.tsx`（400 行）：3 段（订单表 / 供应商档案 / AI 待确认收件箱）
   - 订单表：6 张 PO 全部真实物料，desktop 横向 9 列表 + mobile 单卡列表，顶部 AI 草稿蓝条 + 张主管 09:42 复核锚点
   - 供应商：5 家长期供应商，每张含「主要品类 / 月均采购 / 账期 / AI 备注」
   - AI 收件箱 3 张卡：①发票自动匹配 PO-2026-008 ②新供应商万华化学建档 ③字段缺失（税率印章遮挡）— 第 3 张琥珀色高亮，演示「AI 知道自己不知道」
- `data.ts` +210 行：`PurchaseOrder` / `Supplier` / `PurchaseInboxCard` types + 3 个 const
- `JintaiDemoPage.tsx`：TabKey 加 purchase + TABS + HASH + SECTION + 新 tabpanel，7 tab 横向排列在 1440 desktop 自适应
- 问问 AI 再补 2 个采购预设问题（α 氧化铝粉价格 + 哪个供应商账期最紧），左栏分组「业务进度（4）/ 财务 + 采购（4）」共 8 个

### 截图验证
采购 tab @ 1440×900：表头 AI 草稿条 + 6 PO 行整齐 + 5 张供应商卡 grid + 3 张 AI 收件箱卡（含琥珀色字段缺失卡）。

### Commit
`276566c feat(jintai-demo): iter 9 — 加 📦 采购 tab（订单 + 供应商 + AI 收件箱）`

---

## Iteration 10 — 2026-05-18 (凌晨) · 演示动线 + 来源精度打磨

### 自我观察 / 截图发现的问题
- 7 tab 截图全部走完后发现：
  ①概览 Hero 只有 3 个 CTA（模拟上传合同 / 模拟上传流转单 / 询问 AI 助手），新加的财务/采购 tab 没有 entry point — 老板要先看到 tab nav 才知道有
  ②财务 tab 的 source chips 写死 "2026-05 凭证汇总.xlsx" — 三张报表却共用同一组 source，不真实
  ③可信 AI tab 只有 1 条 trace 示例（生产流转单），新增的财务模块没有对应的 trace 演示

### 本轮改动（全部 UI 加法/调整，不引新依赖）
- `JintaiHero.tsx`：3 主 CTA 下方加副导航行「或直接查看：[💰 财务 AI 三表] [📦 采购订单 + 供应商]」— pill 风格，视觉不抢主 CTA
- `JintaiFinancePanel.tsx`：source chips 拆为 `REPORT_SOURCES` map，按 reportId 动态绑定：
   - 资产负债表 → Kingdee 月末科目余额表 + 5 张入库单 + 银行对账单
   - 损益表 → 销售合同 + 采购入库（计入成本）+ 期间费用凭证
   - 现金流量表 → 银行流水 + 付款凭证 + 客户回款明细
- `data.ts` `traceExamples` 加 1 条「2026-05 净利润 1,189 K¥」财务 trace（财务总监二签）
- `JintaiTrustPanel.tsx`：trace 由 1 → 2，演示「AI 也不动财务三表」

### 截图验证（Chrome MCP · 1440×900）
- 概览：副导航行可见，2 个 pill 在 3 个主 CTA 下方一行 ✓
- 财务（资产负债表）：底部 source chips 显示 "Kingdee 月末科目余额表.xlsx + 入库单 + 招行对账单" ✓
- 可信：trace 区显示 2 条（生产流转单 + 财务三表）✓
- 7 tab nav 在 1440 desktop 横向不破 ✓

### Commit
`89ed141 feat(jintai-demo): iter 10 — 演示动线 + 来源精度打磨`

---

## Iteration 11 — 2026-05-18 (凌晨) · 加 📅 经营日报 tab（老板早 8 点 5 分钟摘要）

### 用户追加需求
"再加一个'经营日报' tab — 独立于现有 7 tab 之外，做成第 8 tab。这是老板早上 8 点打开手机/web 看的 5 分钟摘要，从其他所有 tab 聚合信息。"

### 自我观察
- 财务/采购都是「业务模块」视角，缺一个「老板早会」视角把所有模块串成一句话
- 6 分块（财务/生产/采购/客户 4 个一句话 + 风险 3 条 + AI 行动 4 个），每块 ≤ 80 字 + 数字加粗
- 数字必须跨 tab 自洽（货币资金 8,200 / 容百回款 1,200K / α 氧化铝 +6.7% 等都已在前几 iter 出现）
- 概览 tab 原有 DailyBriefing 与新 tab 重复，应简化为跳转链接

### 本轮改动
- 新增 `JintaiDailyBriefPanel.tsx`（450 行）：
   - **顶部摘要条**：AI 草稿 banner（07:55 生成）+ 日期 + 周几 + 5 个 category counts pill（销售 1 / 财务 1 / 生产 2 / 采购 1 / 风险 1，风险 > 0 红色高亮）+ AI 人话摘要（"今天最该关注 3 件事..."）
   - **4 个 category 分块**（财务 / 生产 / 采购 / 客户）desktop 2 列：每块 3 bullets + AI 提示 banner；数字用 `「...」` 包裹自动加粗等宽显示（`BulletText` parser 拆分）
   - **风险线索块**：3 条 高/中/中，颜色 dot + 标题 + AI 建议
   - **AI 建议今日行动块**：4 个 timeslot（上午 9:00 / 10:30 / 下午 14:00 / 16:00），可点 checkbox 标"已处理"，header 实时计数 + 类别 pill + 任务文字
   - **底部日报历史折叠区**：最近 5 天（已读 + 红/黄/行动统计）
- `data.ts` +145 行：`dailyBrief` const + 4 types（Block / Risk / Action / History）+ Ask AI Q9 经营日报预设
- `JintaiDemoPage.tsx`：TabKey 加 briefing，TABS 第 6 位「📅 经营日报 · 老板 5 分钟看完今天」，HASH + SECTION 映射；新增 `BriefingShortcut` 组件（概览 tab 内 1 行 AI-蓝跳转卡 → "今日经营日报 · 2026-05-18 周一 · AI 已于 07:55 生成 · 今日要事 6 · 1 红 / 2 黄 / 4 行动 · 5 分钟可读完"）
- 旧 `JintaiDailyBriefing` 不再 import（保留组件供未来使用）
- `JintaiHero.tsx`：副导航增加第 3 个入口「📅 今日经营日报」（用 AI 蓝色高亮区别于灰色财务/采购按钮，强调最新最重要）
- `JintaiAIQueryPanel.tsx`：predefined questions 8 → 9，左栏增加第 3 个分组「经营日报」
- `JintaiTrustPanel.tsx`：trace 示例 2 → 3，新增「2026-05-18 经营日报 AI 07:55 自动生成（1 红 / 2 黄 / 4 行动）」+ 「许总 08:02 在手机端打开 · 1 条已标"已处理"」双重锚点

### 跨 tab 数字自洽（验证清单）
| 经营日报内 | 自洽于 |
|---|---|
| 货币资金 ¥8,200K | 资产负债表 / 财务 tab |
| 容百回款 ¥1,200K | Ask AI Q6 本周回款 |
| α 氧化铝 +6.7% | Ask AI Q7 / 采购 tab PO-2026-008 |
| 进行中流转 12 张 | 概览 KPI |
| 5 月净利润 1,189K | 损益表 |
| SC-2026-015 / 016 / 017 | 生产流转 tab planNo 系列 |

### 截图验证（Chrome MCP · 1440×900）
- 8 tab nav 全展开无溢出 ✓
- 顶部摘要条：日期 + 5 pill + AI 摘要 ✓
- 4 category 块（财务/生产/采购/客户）2 列 + AI 提示 ✓（数字「」加粗显示）
- 风险 3 条（🔴高 / 🟡中 / 🟡中）+ AI 建议 ✓
- AI 行动 4 个 + checkbox + 类别 pill + 时间 ✓
- 概览 BriefingShortcut 卡可见，蓝色 → 看完整版 按钮 ✓
- Hero 副导航 3 个入口（💰 财务 / 📦 采购 / 📅 经营日报）✓

### Commit
`75f1040 feat(jintai-demo): iter 11 — 加 📅 经营日报 tab（老板早 8 点 5 分钟摘要）`

---

## Iteration 12 — 2026-05-18 (凌晨) · 8 tab 截图全验证 + 经营日报庆祝 state

### 自我观察
- 8 tab 全部走一遍：概览 / 收件箱 / 生产 / 财务 / 采购 / 经营日报 / 问问 AI / 可信 AI — 均在 1440×900 desktop 对齐无破损
- AI 建议今日行动 4 个全勾选后没有终态反馈，「已处理 4/4」太冷淡，加一个庆祝 state 强化老板「我已完成 AI 建议」的成就感

### 本轮改动
- `JintaiDailyBriefPanel.tsx`：actions 全部勾选时
   - 计数文字「已处理 4 / 4 ✓」变绿色加粗
   - 顶部出现绿色庆祝条「🎉 今日 AI 建议 100% 已执行。明早 7:55 AI 会自动准备明日日报。」
   - 已勾选 action 文字 strikethrough + 颜色变浅

### 截图验证
4 个 action 全勾选 → 庆祝条出现 + 删除线 + 计数变绿 ✓

### Commit
`5e2c3ae feat(jintai-demo): iter 12 — 8 tab 全验证 + 经营日报庆祝 state`

---

## Iteration 13 — 2026-05-18 (凌晨) · 统一 8 tab icon 风格

### 用户反馈
"tab 栏 icon 不统一 — 财务/采购/经营日报用了 emoji（💰 📦 📅），但原 5 个 tab 没 icon。需要统一全部 8 个 tab。"

### 自我观察
- iter 8/9/11 新加的 tab 用了 emoji 当 prefix（图省事），但跟原 5 tab 的"纯文字"形成视觉跳跃
- codebase 既有 `I.*` outline icon 库（icons.tsx · 24 viewBox · 1.6 stroke）已被 AppShell 内 nav 和 button 大量使用 — 风格基线已定
- 优先方案：把所有 8 tab 都加上 `I.*` outline icon，emoji 不进 nav 层
- 副导航 + BriefingShortcut 卡片的 emoji 也要跟上，否则演示动线视觉断层

### 本轮改动
- `icons.tsx` 新增 5 个 outline SVG（保持 24 viewBox + 1.6 stroke 风格）：
   - `I.grid` (4 格田字 — 概览)
   - `I.inbox` (信箱托盘 — AI 收件箱)
   - `I.factory` (厂房 + 烟囱 + 围栏 — 生产流转)
   - `I.pkg` (3D 包裹 — 采购，避免与 inbox 混淆)
   - `I.calendar` (日历 + 3 个点 — 经营日报)
- `JintaiDemoPage.tsx`：
   - TABS 结构加 icon 字段，label 移除 emoji 前缀
   - tab 按钮渲染：第 1 行 inline-flex icon(14px) + label，第 2 行 hint 缩进对齐 icon 右侧
   - tab 颜色：active → 白 #fff · inactive → currentColor + 0.75 opacity（细微弱化）
   - tab padding 16 → 14（腾出 icon 宽度，desktop 1440 仍不溢出）
   - `BriefingShortcut` 卡左侧 📅 emoji 换为 AI-蓝色 36×36 方块 + `I.calendar(18)`
- `JintaiHero.tsx`：副导航 3 个入口同步换成 `I.cash` / `I.pkg` / `I.calendar`

### 保留 emoji 的地方
panel 内部装饰性 emoji（`💰 财务一句话` / `🏭 生产一句话` / `🤝 客户一句话` / `⚠️ 风险线索` / `🎯 AI 建议今日行动` / `🎉` 庆祝条 / 🔴 🟡 风险 dot）— 这些是 user 原 spec 要求的内容层标识，不在 nav 层，统一只针对「tab 栏 + 跳转入口」层。

### 截图验证（Chrome MCP）
8 tab 全部 outline icon 一致，无 emoji 突兀；Hero 副导航 3 button + BriefingShortcut 卡都用 I.* 同风格 ✓

### Commit
`ead41c3 style(jintai-demo): iter 13 — 统一 8 tab icon 与 codebase I.* outline 风格`

---

## Iteration 14 — 2026-05-18 (凌晨) · 锦泰品牌 accent 注入

### 用户反馈
"结合锦泰 logo 红绿配色 + kamtai.cc 网站风格，让 demo 看起来是给锦泰定制的，不是套模板。"

### 流程
**Step 1 抓取（Chrome MCP → kamtai.cc）**
- 主红：`#C32629` (rgb 195,38,41) — active nav link / section title「车间环境/新闻资讯」/ 序号 03 红方块 / 多处 emphasis
- 锦泰绿：`#1B7F3A` — logo 草字头叶（user spec 采用）
- 字体：`sans-serif + Microsoft Yahei + Hiragino Sans GB`（system CJK stack，无 web font）
- 圆角：`0px`（工业直角）— demo 维持既有 8-12px，不强行变直角
- Hero：大红底 + 金色山脉 + "锦泰"印章 + "JIN TAI"金英文 → 中国工业品牌经典构成

**Step 2 brand-tokens.md**：写抓取结果 + 注入策略到 `apps/win-web/src/screens/jintai/brand-tokens.md`（仅文档，不入运行时）

**Step 3 不替换主色**：`--brand-*` 蓝（智通客户产品色）全程保留，锦泰红绿只做 accent。

### 本轮改动（6 处 accent）
1. `tokens.css` 新增 `--jintai-red: #C32629` / `--jintai-red-50: #FBE9E9` / `--jintai-green: #1B7F3A`
2. **Hero 顶部 3px 装饰条**：`linear-gradient(90deg, jintai-red 0-38%, transparent 38-62%, jintai-green 62-100%)` — 整个 demo 第一眼信号
3. **Hero 右上角版本号**：`● 锦泰定制版 v2026.05 · 发布 2026-05-17` jintai-green 字 + 同色 5px dot
4. **Hero h1**：3px `jintai-red` 左侧 border + "宜兴市锦泰耐火材料" 800 加粗，后段 `· AI 生产流转试点` 灰 500 弱化对比 — 公司名是主角
5. **财务 AI 草稿条**「✓ 王会计 复核确认」前加 jintai-green 7px dot — 强化"自己人复核"信号
6. **采购 AI 草稿条**「✓ 张主管 复核确认」前同样加 jintai-green dot
7. **footer**：`Powered by 智通 AI · © 2026 Five Oranges AI · 为 [16px 锦泰 logo] 宜兴市锦泰耐火材料 定制 · 演示版本`

### 不做
- 不换 nav 蓝色为红
- 不引锦泰金色（避免色板过载 — demo 已有 AI 蓝 / brand 蓝 / ok 绿 / warn 琥珀 / risk 红）
- panel 内既有 emoji（💰🏭📦🤝⚠️🎯🎉🔴🟡）保留 — 那是 user spec 的内容层装饰
- 不动 mock data / 业务逻辑 / icon 库（iter 13 已统一）

### 截图验证
- Hero 红绿渐变装饰条 + 版本号 jintai-green + h1 红边加粗 ✓
- 财务 / 采购 AI 草稿条 jintai-green dot ✓
- footer DOM 渲染确认（小 16px logo + 锦泰定制字样）

### Commit
`d9178ce feat(jintai-demo): integrate 锦泰 brand color accents + kamtai.cc visual cues (iter 14)`

---

## Iteration 15 — 2026-05-18 (凌晨) · 许总 → 陈总 重命名

### 用户反馈
"陈总是锦泰真实联系人，许总是早期 mock 占位，全部替换。"

### 改动
sed `s/许总/陈总/g` 5 处一次完成：
- `data.ts` L779 traceExamples 经营日报 source.label
- `data.ts` L782 traceExamples confirmedBy
- `JintaiDailyBriefPanel.tsx` L90 AI 草稿 banner subtitle
- `JintaiDemoPage.tsx` L198 briefing tab TAB_HEAD.sub
- `brand-tokens.md` L55 注入策略文档

grep 验证 0 处残留，截图确认 briefing tab "陈总醒后 5 分钟看完" 正确。

### Commit
`b8bae99 style(jintai-demo): 许总 → 陈总 throughout demo (iter 15)`

---

## Iteration 16 — 2026-05-18 (凌晨) · tab icon 加颜色 + 锦泰品牌呼应 + 专业 2-tone

### 用户反馈
"iter 13 让 tab icon 全部 outline 统一了，但 icon 全黑/灰显得单调不够专业。要加颜色（结合锦泰红/绿/kamtai.cc 风格），仍然统一（不是 8 种乱七八糟），更专业（参考 Linear / Notion / Atlassian SaaS icon 风格）。"

### 设计方案：4 业务族分组配色

| Group | Tab | Token | Hex |
|---|---|---|---|
| 蓝（经营管理） | overview | `--brand-500` | #2d9bd8 |
|  | briefing | `--brand-700` | #1f5fa3 |
| 锦泰红（业务核心） | production | `--jintai-red` | #C32629 |
|  | purchase | `--jintai-red-40` (新) | #D85A5D |
| 锦泰绿（资金合规） | finance | `--jintai-green` | #1B7F3A |
|  | trust | `--jintai-green-dark` (新) | #115624 |
| AI 紫（智能能力） | inbox | `--ai-purple` (新) | #7B5CFA |
|  | ask | `--ai-purple-deep` (新) | #5B3FE0 |

⚠ 既有 `--ai-500` 与 `--brand-500` 同值 `#2d9bd8` 不能区分，必须加 AI 紫族 token。

### Icon 2-tone 升级
8 个 tab icon 全部从单色 outline 改 2-tone：
- 外形：`fill={c} fillOpacity=0.18 + stroke 实色`
- 关键细节实色：cash 内圆币 / shield 对勾 / calendar 3 dots / ask 主星 + dot / pkg 棱线 / factory 烟囱柱
- icon size 14 → 16 px，更易看清

### TABS 渲染
- 加 color 字段，render 时传给 icon
- **active**：tab 背景 = color，icon 白色 + `transform: scale(1.05)` + 底部 2px `rgba(255,255,255,0.6)` indicator
- **inactive**：背景透明，icon 本色 `opacity: 0.6`（点亮但克制）
- transition `0.15s ease` 平滑切换
- gap icon → label `6 → 8 px`，hint paddingLeft `20 → 24`

### 与 iter 14 视觉呼应
- 生产红 tab + 财务绿 tab 与 hero 装饰条（红 38% → 透明 → 绿 38%）同色
- h1 红边 + 生产 tab 红 + 财务确认 dot 绿都来自同一品牌色族
- 整个 demo 颜色语义闭环：财务一律绿、生产一律红、AI 一律紫、经营管理一律蓝

### 截图验证（Chrome MCP · 4 active 状态）
- Overview active：tab 整体 brand 蓝高亮 ✓
- Production active：锦泰红 tab + 白 icon + 底白 indicator ✓
- Finance active：锦泰绿 tab + 白 icon ✓
- Briefing active：深 brand 蓝 tab ✓
- 4 个非 active tab 显示 2-tone 彩色 icon (opacity 0.6)，颜色按分组清晰

### Commit
`a791915 feat(jintai-demo): colorize tab icons w/ 锦泰 brand + ai accents (iter 16)`

---

## Iteration 17 — 2026-05-18 (凌晨) · 财务本地化（PayPal→支付宝 + K元→元）

### 用户反馈
"国内 SME 不用 PayPal；单位千元（k¥）改成元，下面数字直接以元为单位的计数。"

### 改动
1. **PayPal → 支付宝**（3 处 sed `s/PayPal/支付宝/g`）
   - data.ts traceExamples extractedBy "Kingdee + PayPal + 银行流水" → "Kingdee + 支付宝 + 银行流水"
   - data.ts cashflow aiDraft "8 张银行流水、PayPal 入账" → "8 张银行流水、支付宝 入账"
   - JintaiFinancePanel CrossCheckHint footer "Kingdee / PayPal / 银行流水" → "Kingdee / 支付宝 / 银行流水"

2. **K¥/千元 → 元 (¥)**：所有数字 ×1000 完整展开
   - **财务三表（44 个 FinanceRow value）**：通过 display layer helper `expandYuan(v)`：
     `v + ",000"`（"—" / "0" 不变）。mock data 字串保留为千元基数，
     视图层 append ",000"，避免改 44 处字面值
   - **单位 label** "千元 (K¥)" → "元 (¥)"
   - **bottomLine 后缀** " K¥" → " 元"
   - **AI_INSIGHTS** 3 段手动改：balance 用"4,700 万元 / 1,250 万元"自然中文；
     income/cashflow 用千位分隔"1,189,000 元 / 6,800,000 元 / +870,000 元"
   - **CrossCheckHint 三表自洽** "8,200 = 8,200 / +1,189" → "8,200,000 元 = 8,200,000 元 / +1,189,000 元"
   - **Ask AI 9 预设 verdict/details/next** Python 脚本扫 38 行 K patterns：
     `¥1,200K → ¥1,200,000` / `¥85K → ¥85,000` / `¥13.6K → ¥13,600` (decimal) /
     `6,800 K¥ → 6,800,000 元` / `"容百 3,200K + 风华 950K" → "3,200,000 + 950,000"`
   - **daily brief 财务/生产/采购一句话 + aiHint + aiSummary** 同覆盖
   - **suppliers monthlySpend** ¥85K/月 → ¥85,000/月（5 处）
   - **JintaiPurchasePanel section header** 总金额 ¥327K/¥405K → ¥327,000/¥405,000
   - 注释 "单位千元 (K¥)" → "单位元 (¥)，演示时显示完整千位分隔"

### 截图验证（Chrome MCP · 1440×900）
- 资产负债表：货币资金 **8,200,000** / 应收 **12,500,000** / 流动资产小计 **29,000,000** / 资产总计 **47,000,000 元** ✓
- 损益表：营业收入 **6,800,000** / 净利润 **1,189,000 元** / 期间费用 **795,000** ✓
- 现金流量表：销售收到 **5,500,000** / 经营净 **+870,000 元** / "**支付宝** 入账" 字样 ✓
- 全部数字带千位分隔符，单位 label "元 (¥)"，负数 −3,800,000 红色显示，无 PayPal 字样

### Commit
`859f1c4 style(jintai-demo): localize 财务 — PayPal→支付宝 + k元→元 (iter 17)`

---

## 通宵总结（iter 8 / 9 / 10 / 11 / 12 / 13 / 14 / 15 / 16 / 17）

10 commit 全部 local 落地：
- **4281a69** iter 8 加 💰 财务 tab（AI 三表草稿 + 复核）
- **276566c** iter 9 加 📦 采购 tab（订单 + 供应商 + AI 收件箱）
- **89ed141** iter 10 演示动线 + 来源精度打磨
- **75f1040** iter 11 加 📅 经营日报 tab（老板早 8 点 5 分钟摘要）
- **5e2c3ae** iter 12 8 tab 全验证 + AI 行动庆祝 state
- **ead41c3** iter 13 统一 8 tab icon 与 codebase I.* outline 风格
- **d9178ce** iter 14 锦泰品牌 accent 注入（红绿条 + 版本号 + h1 红边 + 确认绿 dot + footer）
- **b8bae99** iter 15 许总 → 陈总 重命名（5 处）
- **a791915** iter 16 tab icon 加颜色 + 锦泰品牌呼应 + 2-tone 专业 SaaS 风格
- **859f1c4** iter 17 财务本地化 PayPal→支付宝 + K元→元 (×1000 展开)

**5 tab → 8 tab**：概览 / AI 收件箱 / 生产流转 / **财务** / **采购** / **经营日报** / 问问 AI / 可信 AI。所有既有 5 tab 0 业务改动；iter 13 / 14 / 16 / 17 都仅装饰层 / 单位层 / 本地化，「不破坏现有」红线达成。

**待 push**：local 未 push，等用户 review。
