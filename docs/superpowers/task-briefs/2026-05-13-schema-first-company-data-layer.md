# Task Brief: Schema-First Company Data Layer Rebuild

你是接手 `/Users/eason/agent-platform` 的 coding agent。请实现 Win ingest 的 V2 重做：上传文件后经过 OCR、schema route、extractor 抽取，生成基于 tenant 公司全局 schema 的表格化 ReviewDraft；用户在表格里审核、补空字段、确认后，才写入 tenant 公司的业务数据库。

## 必读上下文

先读这三个文件：

1. `/Users/eason/agent-platform/coding-principle.md`
2. `/Users/eason/agent-platform/docs/superpowers/specs/2026-05-13-schema-first-company-data-layer-design.md`
3. `/Users/eason/agent-platform/docs/superpowers/plans/2026-05-13-schema-first-company-data-layer.md`

参考 repo 已 clone 到：

`/private/tmp/yinhu-brain-ref`

重点参考这些设计，不要照搬路径：

- `/private/tmp/yinhu-brain-ref/backend/app/models/document_extraction.py`
- `/private/tmp/yinhu-brain-ref/backend/app/models/field_provenance.py`
- `/private/tmp/yinhu-brain-ref/backend/app/services/ingest/schemas.py`
- `/private/tmp/yinhu-brain-ref/backend/app/services/customer_intelligence/inbox_confirm.py`
- `/private/tmp/yinhu-brain-ref/backend/app/services/customer_intelligence/inbox_apply.py`

## 当前问题

现在 OCR 和 schema 路由/抽取能拿到很多内容，但 Review 页的 “AI 提取结论” 只显示少量信息。根因不是 LLM 一定没抽到，而是当前接口和 UI 合约错误：

- 后端 `/win/api/ingest/jobs` 把合并后的 `UnifiedDraft` 存进 `IngestJob.result_json`。
- `normalize_pipeline_results()` 只把 `identity`、`contract_order`、`commitment_task_risk` 映射进 `UnifiedDraft`。
- `finance`、`logistics`、`manufacturing_requirement` 多数停留在 raw `pipeline_results`。
- 前端 `Review.tsx -> jobToBatch() -> batchToReview()` 只渲染若干固定 draft path，不按 schema table 渲染。
- 所以 schema summary 很丰富，但最终 review 只显示幸存到 `UnifiedDraft` 的少量字段。

不要继续给 `batchToReview()` 打补丁。要建立新的 schema-first contract。

## 目标行为

流程必须变成：

1. 用户上传文件或粘贴文本。
2. 后端 OCR 转文字并持久化 `documents`。
3. 后端 schema router 选择相关 pipeline/table。
4. extractor 抽字段。
5. 后端根据 tenant 公司全局 schema catalog 生成 `ReviewDraft`。
6. 前端按表格展示 `ReviewDraft.tables`。
7. 对于被选中的表，所有 schema 字段都要显示；没有抽到的字段显示为空/missing，用户可以手动填。
8. 用户确认后，后端将 reviewed cells 写入 tenant 业务表，并写 `field_provenance`。

关键验收例子：

订单表 `orders` 有 6 个字段。AI 只抽到 4 个。Review UI 必须显示 6 个 cell：4 个有值，2 个空白 `missing`，用户可编辑后确认。

## 架构决策

- tenant 公司 schema 是公司全局数据库 schema，是 AI 和人共同访问、维护的数据底座。
- schema catalog 存在 tenant DB 内，不是前端 hard-code。
- AI 可以写 `document_extractions`、`field_provenance`、`schema_change_proposals`。
- AI 不直接写业务主表；业务表只在用户确认后写入。
- 保留现有 V1 `/win/api/ingest/jobs` 和 `/win/api/ingest/auto`，新增 V2 `/win/api/ingest/v2/*`，验证通过后让 Upload/Review 走 V2。

## 需要新增的核心后端模块

按 plan 实现这些文件：

- `platform/yinhu_brain/models/company_schema.py`
- `platform/yinhu_brain/models/company_data.py`
- `platform/yinhu_brain/models/document_extraction.py`
- `platform/yinhu_brain/services/company_schema/default_catalog.py`
- `platform/yinhu_brain/services/company_schema/catalog.py`
- `platform/yinhu_brain/services/ingest_v2/schemas.py`
- `platform/yinhu_brain/services/ingest_v2/review_draft.py`
- `platform/yinhu_brain/services/ingest_v2/auto.py`
- `platform/yinhu_brain/services/ingest_v2/confirm.py`
- `platform/yinhu_brain/api/company_schema.py`
- `platform/yinhu_brain/api/ingest_v2.py`

也要修改：

- `platform/yinhu_brain/models/__init__.py`
- `platform/yinhu_brain/models/field_provenance.py`
- `platform/yinhu_brain/models/ingest_job.py`
- `platform/yinhu_brain/db.py`
- `platform/yinhu_brain/workers/ingest_rq.py`
- `platform/yinhu_brain/__init__.py`

## 需要新增的核心前端模块

- `platform/app-win/src/api/ingestV2.ts`
- `platform/app-win/src/components/review/ReviewTableWorkspace.tsx`
- `platform/app-win/src/components/review/ReviewCellEditor.tsx`

也要修改：

- `platform/app-win/src/data/types.ts`
- `platform/app-win/src/screens/Upload.tsx`
- `platform/app-win/src/screens/Review.tsx`

## ReviewDraft 合约

后端 V2 返回的核心结构必须是表格化的：

```json
{
  "extraction_id": "uuid",
  "document_id": "uuid",
  "schema_version": 1,
  "status": "pending_review",
  "document": {
    "filename": "order.pdf",
    "summary": "客户订单，包含总金额和交付地址"
  },
  "route_plan": {
    "selected_pipelines": [
      { "name": "contract_order", "confidence": 0.92, "reason": "包含订单号、金额、交付条款" }
    ]
  },
  "tables": [
    {
      "table_name": "orders",
      "label": "订单",
      "rows": [
        {
          "client_row_id": "orders:0",
          "operation": "create",
          "cells": [
            {
              "field_name": "amount_total",
              "label": "订单金额",
              "data_type": "decimal",
              "required": false,
              "value": 30000,
              "display_value": "30000",
              "status": "extracted",
              "confidence": 0.91,
              "evidence": { "page": 1, "excerpt": "合同总价人民币叁万元整" },
              "source": "ai"
            },
            {
              "field_name": "delivery_address",
              "label": "交付地址",
              "data_type": "text",
              "required": false,
              "value": null,
              "display_value": "",
              "status": "missing",
              "confidence": null,
              "evidence": null,
              "source": "empty"
            }
          ]
        }
      ]
    }
  ]
}
```

前端 V2 Review 不要再从 `ReviewField[]` 和 `ReviewExtraction[]` 推导展示，直接渲染 `ReviewDraft.tables`。

## 后端实现要求

1. schema catalog:
   - 建 `company_schema_tables`、`company_schema_fields`、`schema_change_proposals`。
   - `GET /win/api/company-schema` 要 idempotently seed 默认 schema 并返回。
   - 默认 schema 至少包含 customers、contacts、products、product_requirements、contracts、contract_payment_milestones、orders、invoices、invoice_items、payments、shipments、shipment_items、customer_journal_items、customer_tasks。

2. company data tables:
   - 保留现有 `customers`、`contacts`、`orders`、`contracts`。
   - 增加 products、requirements、invoice、payment、shipment、journal 等缺失表。
   - `field_provenance.EntityType` 要覆盖新增实体。

3. document extraction:
   - 新增 `document_extractions` 表保存每次抽取的 route plan、raw pipeline results、review draft、status。
   - `IngestJob` 增加 `workflow_version` 和 `extraction_id`。
   - `db.py` 要能给既有 tenant DB 补 V2 表/列。

4. review draft materializer:
   - 由 `route_plan.selected_pipelines` 决定展示哪些 table。
   - 每个被展示的 table 必须遍历 catalog active fields，生成完整 cells。
   - 没值就是 `missing`，有 default 就 source=`default`。
   - array tables 没抽到时也要给一条空 row，方便用户填写。

5. V2 worker/API:
   - `POST /win/api/ingest/v2/jobs` 创建 `workflow_version="v2"` 的 jobs。
   - RQ worker 按 `workflow_version` 分发到 `auto_ingest_v2()`。
   - V2 job extracted 后 `result_json` 存 `ReviewDraft`。
   - 提供 extraction get/patch/confirm/ignore endpoints。

6. confirm:
   - 校验 required/data_type。
   - 按父子顺序写业务表。
   - 写 `FieldProvenance`。
   - 标记 `DocumentExtraction`、`Document`、相关 V2 `IngestJob` 为 confirmed。

## 前端实现要求

1. `ingestV2.ts`:
   - 定义 V2 types。
   - 提供 create/list/get job、get/patch/confirm/ignore extraction、get company schema API。

2. `Upload.tsx`:
   - 新上传走 V2 jobs。
   - 不删 V1 历史逻辑，避免破坏旧数据。

3. `Review.tsx`:
   - 如果 job 是 V2 或 `result_json.tables` 存在，渲染 `ReviewTableWorkspace`。
   - V1 继续走当前 legacy path。

4. `ReviewTableWorkspace`:
   - 按 table 展示。
   - 每个 schema field 一列或一项，不能隐藏 missing。
   - 支持编辑 cell、reject cell、为 array table 加 row。
   - confirm 时发送 patches。

## 必须写的测试

后端：

- `platform/tests/test_company_schema_catalog.py`
  - model registered
  - default schema seed idempotent
  - `GET /win/api/company-schema` returns ordered schema
  - approve `add_field` proposal works

- `platform/tests/test_ingest_v2_review_draft.py`
  - `orders` 6 fields but extraction only 4 values -> output exactly 6 cells
  - missing cells status is `missing`
  - array table with no extracted items creates one empty row

- `platform/tests/test_ingest_v2_api.py`
  - create V2 job
  - get V2 job
  - get extraction
  - patch review draft
  - ignore extraction idempotently

- `platform/tests/test_ingest_v2_confirm.py`
  - confirm writes business rows
  - user-filled missing cells persist
  - provenance rows are created
  - missing required cell returns 400 and does not confirm

- Update `platform/tests/test_ingest_rq_worker.py`
  - V2 worker dispatch test
  - existing V1 worker tests still pass

前端：

- At minimum run TypeScript check.
- If existing frontend test harness is absent, keep logic typed and pure where possible.

## 验证命令

Backend:

```bash
cd platform && ./.venv/bin/pytest tests/test_company_schema_catalog.py tests/test_ingest_v2_review_draft.py tests/test_ingest_v2_api.py tests/test_ingest_v2_confirm.py tests/test_ingest_rq_worker.py tests/test_ingest_jobs.py -q
```

Frontend:

```bash
cd platform/app-win && npm run check
```

Manual:

1. 上传一个订单/合同类文件。
2. 等待 job extracted。
3. Review 页面展示 schema tables。
4. 验证 `orders` 所有字段都出现，没抽到的是空白 missing cell。
5. 手动填写 missing cell。
6. confirm 后检查业务表和 `field_provenance`。

## 非目标

- 不重写 OCR provider。
- 不重写 LandingAI/DeepSeek provider。
- 不删除 V1 ingest/auto endpoints。
- 不做完整 schema 管理后台 UI；本轮只要求 schema catalog API 和 proposal API 可用。
- 不做复杂 fuzzy merge。V2 confirm 先按 `entity_id` 更新，否则创建。

## 交付标准

- 每个 task 小步提交，避免一个大 commit。
- 不提交无关 `.gitignore` 或 dist/build 文件。
- 保持旧 V1 测试通过。
- 最终回答要说明改了哪些文件、跑了哪些测试、是否有未完成风险。
