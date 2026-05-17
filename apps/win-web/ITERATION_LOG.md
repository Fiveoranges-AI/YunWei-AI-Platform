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

## 总结

跑了 5 轮 + 5 个 commit（在 baseline commit `720fd50` 之上）：
- 0569199 iter 1 真实产品线对齐
- (iter 2) Hero polish + completed flow card + trace metadata
- (iter 3) OCR upload progress animation
- (iter 4) 顶栏 sub + Hero feature grid 视觉打磨
- (iter 5) iPad / 手机响应式 防御性 collapse

全部 local 未 push，等用户早上 review 后再决定是否 push。
