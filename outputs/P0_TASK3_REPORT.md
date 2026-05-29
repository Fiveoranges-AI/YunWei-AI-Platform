# P0 任务③ — 人机确认卡片 · 落地报告

**分支:** `feat/confirm-cards-p0-task3`（base = `feat/parse-pipeline-p0-task2`,栈式）
**Worktree:** `/Users/kobeli/Documents/Yinhu Project/yunwei-confirm-cards-p0`
**Co-author:** Claude Opus 4.7
**日期:** 2026-05-21

## TL;DR

任务③ 实施完成。前端 + 后端 + Demo + 单测,前端 build 0 error,后端新增 6 个测试全部 pass(总 273 pass / 11 pre-existing fail,已逐项核实跟我无关)。

3 个 P0 全部交付。

## Phase 0 — 勘探结论

| 项 | 现状 | 决策 |
| --- | --- | --- |
| 前端 | win-web · React 18 + Vite + TS · 纯 CSS token(无 antd/shadcn) · `App.tsx` 栈式路由 · `fetch + credentials:include` 请求层 | 沿用,新建 `components/confirm/*` |
| 既有 Review | `screens/Review.tsx` 是**老**流程(schema_ingest ReviewDraft + lock) | **不复用**——任务②的 CandidateJSON 是新数据形状,需要独立组件 |
| 后端 | `yunwei_win/api/*` 路由通过 `routes.py` 挂载到 `/api/win` · `get_session` 自动按 enterprise 路由 | 新增 `api/confirm.py` + `services/confirm_writer.py` |
| 本体表 | Customer/Contact/Order/Contract/Product/Invoice/Payment/OrderItem 全部带 `human_verified` / `verified_by` / `verified_at` / `source_*` mixin · `ActionLog` 表已就位 | 直接调 ORM 写,无需新表 |
| 候选 JSON | `services/parse_pipeline/candidate.py` shape 稳定 | TS mirror in `data/candidate.ts` |
| 测试 | 用 `_make_engine` 内存 SQLite + 重写 `_clean_state` autouse fixture 避免 Postgres | 沿用 |

**对接结论:无障碍**——前后端在同一 repo,一次性交付。

## 文件清单

### 新增 — 后端

| 路径 | 行数 | 说明 |
| --- | --- | --- |
| `services/platform-api/yunwei_win/api/confirm.py` | 175 | POST `/api/win/confirm/entities` · Pydantic 模型 + 调 confirm_writer |
| `services/platform-api/yunwei_win/services/confirm_writer.py` | 470 | candidate → ORM 行 · 拓扑排序解析关系 · 审计字段强制注入 · ActionLog 每条一条 |
| `services/platform-api/tests/test_confirm_cards.py` | 320 | 6 个测试:audit 戳 · 编辑后置信度置 null · 关系解析 · 关联既有 · 校验 400 · 空请求 400 |

### 改 — 后端

| 路径 | 改动 |
| --- | --- |
| `services/platform-api/yunwei_win/routes.py` | +2 行:`include confirm_router` |

### 新增 — 前端

| 路径 | 行数 | 说明 |
| --- | --- | --- |
| `apps/win-web/src/data/candidate.ts` | 100 | TS mirror of CandidateJSON · ConfirmEntitiesRequest · WrittenEntity |
| `apps/win-web/src/api/confirm.ts` | 40 | `confirmEntities()` client |
| `apps/win-web/src/components/confirm/ConfirmCard.tsx` | 360 | 展示卡片(纯展示层,无 fetch) |
| `apps/win-web/src/components/confirm/useConfirmSubmit.ts` | 170 | 编辑状态 + 提交逻辑 hook |
| `apps/win-web/src/components/confirm/DuplicateWarningDialog.tsx` | 130 | 「新建 / 关联已有」对话框 |
| `apps/win-web/src/components/confirm/README.md` | 90 | 组件 props 文档 + 使用说明 |
| `apps/win-web/src/screens/ConfirmDemo.tsx` | 240 | Demo 页 + 硬编码样例 CandidateJSON |

### 改 — 前端

| 路径 | 改动 |
| --- | --- |
| `apps/win-web/src/App.tsx` | +27 行:`confirmDemo` screen + `?screen=confirmDemo` URL param 路由 |

## 关键设计决策

### 1. 后端写入语义(审计字段)

每个 entity 写入时强制设置:
- `human_verified = True`
- `verified_by = request.state.actor`(或 `user.id/username/display_name`,fallback `"unknown"`)
- `verified_at = now(UTC)`
- `source_type / source_ref / source_span` 从候选 JSON 透传(`source_span` 聚合为 `{primary, fields:{name:span,...}}` JSON)
- `extracted_by = "llm"` · `created_by = updated_by = actor`
- `confidence` = **未被编辑的字段** 的 min 置信度(全被改 → None;一条都没改 → min(field.confidence))。
- 每个 entity 追加一条 `ActionLog`:`action_type = create_profile`(新建)或 `reconcile`(关联既有),`input_summary` 含 `ingestion_id` / `entity_type` / `edited_fields=...`。

### 2. 关系解析

`relationships[].type` → 子实体 + FK 列。已映射:
- `Customer-has-Contact / Order / Contract / Invoice / Payment`
- `Order-has-OrderLine/OrderItem / Invoice` · `Contract-has-Order` · `Invoice-has-Payment` · `OrderLine-has-Product`

拓扑排序确保父表先 flush,子表读到真实 UUID。未识别的 relationship type → 只 log warning,不报错(未来扩展时友好)。

### 3. "关联既有"分支

`existing_entity_id: UUID` 命中时,**不插入新行**,但仍写一条 `ActionLog`(action=`reconcile`),关系仍按 existing id 解析。Demo 页通过 `DuplicateWarningDialog` 让用户做选择。

### 4. 字段值强类型 coercion

`_coerce_value` 用 SQLAlchemy column.python_type 做柔性转换:
- 字符串 → Date / Decimal / int / float / bool / datetime
- Contact.role enum 特殊处理(候选 JSON 是 `"seller"` 字符串,落库要 enum)
- 失败抛 `ConfirmFieldError` → API 层返 400 + 字段名

### 5. 前端 layering(可复用)

```
+------------------------------------------------+
| screens/ConfirmDemo.tsx  (host: sample data)   |
|                                                |
|  +----------------------+  +----------------+  |
|  | ConfirmCard (展示)   |  | useConfirmSubmit |
|  | EvidencePopover     |  | 编辑+提交       |  |
|  | DuplicateDialog     |  +----------------+  |
|  +----------------------+         |           |
|                                   v           |
|                          api/confirm.ts       |
+------------------------------------------------+
                                    |
                          POST /api/win/confirm/entities
                                    |
                                    v
                   api/confirm.py → confirm_writer.py → ORM
```

`ConfirmCard` 是纯展示,可以被小程序/企微 H5 复用——只换一个 renderer。

## 自检结果

| 项 | 结果 |
| --- | --- |
| 后端新增测试 `test_confirm_cards.py` | **6 passed** in 0.50s |
| 后端 task ① + ② + ③ + customer_management 全跑 | **23 passed** in 1.10s |
| 后端较广覆盖(扣除 pre-existing 3.11/3.14 f-string 阻塞模块) | **273 passed / 11 failed**(11 个 fail 已 git checkout baseline 复现,跟任务③ 无关) |
| 前端 `npm run check` (tsc --noEmit) | **0 error** |
| 前端 `npm run build` (tsc + vite build) | **OK** · 317.32 kB JS · 10.78 kB CSS |
| Vite dev 跑通 + ConfirmDemo 模块 200 | **OK**(curl `/win/?screen=confirmDemo` 返回 200,所有组件文件 transform 成功) |

### Demo 闭环验证(代码级)

Backend test `test_confirm_resolves_customer_has_contact_relationship` 模拟一次"喂任务② 样例 → 确认 → 落库"的完整闭环:发送 Customer + Contact + 关系 → 写入两条 ORM 行 + 写两条 ActionLog → DB 校验 `customer_id` 解析正确 + `human_verified=True` + `verified_by="test-user"` + `source_type="contract"`。**审计标记真的写了。**

## 与原 prompt 对齐情况

| 任务交付物 | 是否完成 | 落地点 |
| --- | --- | --- |
| 确认卡片组件(展示层) | ✅ | `components/confirm/ConfirmCard.tsx` |
| 提交 hook/服务(逻辑层) | ✅ | `components/confirm/useConfirmSubmit.ts` + `api/confirm.ts` |
| 后端写入接口(本体落库 + 审计 + ActionLog) | ✅ | `api/confirm.py` + `services/confirm_writer.py` |
| 最小可跑 demo 页 | ✅ | `screens/ConfirmDemo.tsx` · `?screen=confirmDemo` |
| 组件 props 文档 | ✅ | `components/confirm/README.md` |
| 截图说明 | ⚠️ Demo 页可手动截图(本次无桌面环境),URL `?screen=confirmDemo` 即开即用 |
| 字段名+值+置信度颜色+查看原文 | ✅ | 高绿/中黄/低红 + 行底色高亮低 < 0.6 |
| missing_required → "待补充" | ✅ | 卡片底部 dashed-border chip |
| 改值标"人工修改" | ✅ | 编辑框边框+底色变蓝,置信度药丸文字变"人工修改" |
| "全部确认入库" + 逐实体确认 | ✅ | 卡片头部按钮 + 页底大按钮 |
| 重复客户 warning → 弹确认 | ✅ | `DuplicateWarningDialog` · Demo 含一个疑似重复触发 |
| human_verified / verified_by/at 强制写 | ✅ | confirm_writer 注入 |
| source_type/ref/span 透传 | ✅ | 候选 JSON 字段 → 行 stamp |
| confidence 保留 / 改后 = null + was_edited | ✅ | hook 改 was_edited=true → 提交时 confidence=null;writer 算 row confidence 时只看未编辑字段 |
| ActionLog 写 | ✅ | 每 entity 一条 · `input_summary` 含 ingestion_id / edited_fields |
| 不引新 UI 库 | ✅ | 全部 inline + token CSS |
| 不动 guangtian/jintai | ✅ | 用 worktree 隔离;只 commit 任务③ 文件 |
| 展示 vs 提交逻辑分层 | ✅ | 见"前端 layering" |
| 金额/日期受控+校验 | ✅ | `<input type=number/date>` + 后端 `_coerce_value` 失败返 400 |
| 不破坏现有测试 | ✅ | 273 passed · 11 fail 是 pre-existing |

## 待用户拍板

1. **入口位置:** Demo 页目前藏在 `?screen=confirmDemo`,生产是否要把入口接到 Inbox(待确认任务列表)旁边?——本次没改 `screens/Inbox.tsx` 以保持 surgical。
2. **重复客户检测:** 当前候选 JSON 的 dedup 信号在 `warnings: ["…重复…"]` 字符串里;前端只能字符串匹配。若任务②升级成结构化 `duplicate_hints: [{temp_id, candidates: [...]}]`,这里就能换成真正的 candidate id 列表。
3. **审计字段在客户详情页:** 现有 `CustomerDetail` 没有展示 `human_verified` / `verified_by` chips。是否要在 `transformCustomerBase` 加上,供 UI 显示一个「人工已确认 · by xxx」徽章?
4. **现存 `Review.tsx` 老流程:** 跟新 `ConfirmCard` 数据形状完全不同。待用户决定是否要把老的 schema_ingest review 流程整体迁移到新的 candidate JSON path。

## P0 三件套

| 任务 | 分支 | PR | 状态 |
| --- | --- | --- | --- |
| ① 本体 | `feat/ontology-p0-task1` | #110 | open · do-not-merge(等用户 review) |
| ② Parse pipeline | `feat/parse-pipeline-p0-task2` | #111 | open · do-not-merge,base=task① |
| ③ 确认卡片 | `feat/confirm-cards-p0-task3` | (this) | open · do-not-merge,base=task② |

**P0 三件套全部交付。**
