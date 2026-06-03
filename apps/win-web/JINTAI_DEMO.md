# 锦泰耐火材料 · AI 生产流转试点 Demo

客户演示用的纯前端 wireframe / clickable demo，基于现有 `apps/win-web`（智通客户 / `/win/`）UI 延展。

> ⚠️ **当前版本为前端 demo · 纯 mock 数据 · 不接任何后端。** 仅用于客户演示与方案对齐。

## Demo 入口

- 路径：在 `/win/` 应用中切到左侧导航「锦泰试点」标签（`jintai` tab）。
- 代码入口：`src/screens/jintai/JintaiDemoPage.tsx`
- 路由注入：`src/App.tsx` 增加了 `"jintai"` 屏幕和同名 tab，复用现有 `AppShell` + `URail`。

## 本地运行

```bash
cd apps/win-web
npm install
npm run dev
# 浏览器打开 http://localhost:5173（或 vite 输出端口）
# 点击左侧栏「锦泰试点」进入 demo
```

类型与构建：

```bash
npm run check    # tsc --noEmit
npm run build    # tsc + vite build
```

## Demo 目标

向锦泰耐火材料展示：如何在不替换其现有 ERP 的前提下，借助 Five Oranges AI 的「资料抽取 + 待确认收件箱 + AI 问答」能力，让纸质生产流转单、合同、Excel 订单
变成可确认、可追踪、可问答的生产经营数据。

核心叙事一句话：
> AI 不直接写入正式业务数据 —— 先生成待确认草稿，人工确认后入库。

## 页面结构（7 大模块单页 dashboard）

| 模块 | 名称 | 文件 |
| --- | --- | --- |
| 1 | 试点总览（Hero + KPI） | `JintaiHero.tsx` · `JintaiKpiCards.tsx` |
| 2 | AI 资料收件箱 | `JintaiUploadInbox.tsx` |
| 3 | 主业务流程闭环 timeline | `JintaiWorkflowTimeline.tsx` |
| 4 | 生产三张表 A/B/C tabs | `JintaiProductionTabs.tsx` |
| 5 | 老板 AI 查询 | `JintaiAIQueryPanel.tsx` |
| 6 | 每日经营风险简报 | `JintaiDailyBriefing.tsx` |
| 7 | 来源追溯 & 数据安全 | `JintaiTrustPanel.tsx` |

共享小组件 / Badge / Citation 在 `components.tsx`，mock 数据全部在 `data.ts`。

## 复用现有 UI

- `components/AppShell` · `URail` · `UHeader` — 不修改外观，仅注册新 tab
- 设计 token：`var(--brand-*)` · `var(--ai-*)` · `var(--ok|warn|risk-*)` · `--ink-*` · `.card` · `.pill-*` · `.btn-*` · `.ai-surface` · `.sec-h`
- 自制 icon 库 `src/icons.tsx`（`I.spark / I.cloud / I.camera / I.bulb / I.shield / I.check / I.chev / I.layers / I.ask / I.send` 等）

未引入任何新 UI 框架或依赖。

## 可交互项

| 操作 | 结果（state 内） |
| --- | --- |
| 点 Hero「模拟上传合同」/ 模块 2 同名按钮 | 在 AI 收件箱顶部插入一张新合同识别卡 |
| 点「模拟上传生产流转单」 | 插入纸质流转单识别卡 |
| 点「模拟上传出货单」 | 插入出货单识别卡 |
| 点识别卡上的「确认生成订单 / 流转单 / 入库」 | 该卡片状态切换为「订单已生成 / 流转单已生成 / 出货已记录」 |
| 点 Hero「询问 AI 助手」 | 滚动到模块 5 |
| 模块 4 A/B/C tab 切换 | 切换显示流转单 / 工艺单 / 出货入库 |
| 模块 5 预设问题点击 | 显示对应 AI 回答 + 数据明细 + 来源引用 |

刷新页面会重置全部状态。

## 接真实后端时的 7 个挂接点

| # | 当前 mock 位置 | 真实后端 endpoint（建议） |
| --- | --- | --- |
| 1 | 上传按钮 / `makeSimulatedCard` | `POST /api/jintai/ingest` 文件上传 + OCR |
| 2 | `JintaiUploadInbox` 卡片 | `GET /api/jintai/extractions?status=pending` AI 待确认收件箱 |
| 3 | `data.orders` / `JintaiWorkflowTimeline` | `GET /api/jintai/orders` 订单表 |
| 4 | `data.flowCards` / `JintaiProductionTabs` Tab A | `GET /api/jintai/flow-cards/{no}` 生产流转单表 |
| 5 | `data.processParameter` / Tab B | `GET /api/jintai/process-parameters` 工艺参数表 |
| 6 | `data.presetQuestions` / `JintaiAIQueryPanel` | `POST /api/jintai/ask` AI 查询 API（含来源引用） |
| 7 | `JintaiDailyBriefing` | `GET /api/jintai/briefing?date=YYYY-MM-DD` 每日简报 |

确认草稿入库走 `POST /api/jintai/extractions/{id}/confirm`，由后端生成对应订单 / 流转单 / 出货单实体并返回新业务编号。

## 不要做的事（本 demo 范围之外）

- 不做真实登录、真实 DB、真实文件上传、真实 OCR / AI 调用
- 不做完整 ERP / 库存 / 排产 / 支付
- 不做多租户配置或权限管理
- 不动 `services/platform-api`、不动 migration、不动 V2 安全栈

## 验收脚本（演示讲法）

1. 「上传合同 → AI 识别 → 待确认 → 一键生成订单」
2. 「上传纸质流转单照片 → AI 识别 → 生成电子流转单 + 三道工序卡」
3. 「成型 / 烧结 / 检包逐工序记录 → 自动衔接成品入库 / 出货」
4. 「工艺参数沉淀 → AI 分析近 30 天不良率」
5. 「老板用中文问 AI → 答案 + 数据明细 + 来源引用」
6. 「每日生产风险简报 → 高/中/低三档预警」
7. 「来源追溯 → AI 不瞎编，所有事实点回原始资料」
