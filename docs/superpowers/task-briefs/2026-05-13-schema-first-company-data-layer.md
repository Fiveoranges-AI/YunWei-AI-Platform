# Task Brief: Schema-First Win Ingest V2

你是 coding agent，在仓库 `/Users/eason/agent-platform` 工作。

任务：
实现 Win ingest V2：上传/OCR/schema route/extractor 后生成基于 tenant 公司全局 schema 的表格化 `ReviewDraft`，用户 review/补 missing cells 后确认写入 tenant 公司数据表。

必读：

- `/Users/eason/agent-platform/coding-principle.md`
- `/Users/eason/agent-platform/docs/superpowers/specs/2026-05-13-schema-first-company-data-layer-design.md`
- `/Users/eason/agent-platform/docs/superpowers/plans/2026-05-13-schema-first-company-data-layer.md`

当前 repo 结构：

- Backend service: `services/platform-api/`
- Win backend package: `services/platform-api/yunwei_win/`
- Win frontend app: `apps/win-web/`
- Canonical API prefix: `/api/win/*`
- Browser SPA route: `/win/`

禁止使用旧路径：

- `platform/yinhu_brain/*`
- `platform/app-win/*`
- `/win/api/*`

背景：

- 当前 V1 后端 `pipeline_results` 很丰富，但 `UnifiedDraft` 和前端 `batchToReview()` 只展示固定字段。
- 因此 schema route / 抽取摘要丰富，而 “AI 提取结论” 稀疏。
- 不要继续给 `batchToReview()` 补字段。V2 必须直接渲染 schema table/cell。

目标行为：

- `orders` schema 有 6 个 active fields，AI 只抽到 4 个时，Review UI 仍显示 6 个 cells。
- 未抽到的字段显示 `status="missing"` 且可编辑。
- 用户确认后，reviewed cells 写入 tenant DB business tables，并写 `field_provenance`。

推荐派工：

- Agent A: schema catalog
  - 只改 `services/platform-api/yunwei_win/models/company_schema.py`
  - 只改 `services/platform-api/yunwei_win/services/company_schema/*`
  - 只改 `services/platform-api/yunwei_win/api/company_schema.py`
  - 只改 `services/platform-api/yunwei_win/models/__init__.py`
  - 只改 `services/platform-api/yunwei_win/routes.py`
  - 只改 `services/platform-api/tests/test_company_schema_catalog.py`

- Agent B: ReviewDraft materializer
  - 只改 `services/platform-api/yunwei_win/models/document_extraction.py`
  - 只改 `services/platform-api/yunwei_win/services/ingest_v2/*`
  - 只改 `services/platform-api/yunwei_win/models/__init__.py`
  - 只改 `services/platform-api/tests/test_ingest_v2_review_draft.py`

- Agent C: V2 API/worker/confirm
  - 只改 `services/platform-api/yunwei_win/api/ingest_v2.py`
  - 只改 `services/platform-api/yunwei_win/services/ingest_v2/auto.py`
  - 只改 `services/platform-api/yunwei_win/services/ingest_v2/confirm.py`
  - 只改 `services/platform-api/yunwei_win/models/ingest_job.py`
  - 只改 `services/platform-api/yunwei_win/db.py`
  - 只改 `services/platform-api/yunwei_win/routes.py`
  - 只改 `services/platform-api/yunwei_win/workers/ingest_rq.py`
  - 只改 `services/platform-api/tests/test_ingest_v2_api.py`
  - 只改 `services/platform-api/tests/test_ingest_v2_confirm.py`
  - 只改 `services/platform-api/tests/test_ingest_rq_worker.py`

- Agent D: frontend V2 client/UI
  - 只改 `apps/win-web/src/api/ingestV2.ts`
  - 只改 `apps/win-web/src/data/types.ts`
  - 只改 `apps/win-web/src/components/review/*`
  - 只改 `apps/win-web/src/screens/Review.tsx`
  - 只改 `apps/win-web/src/screens/Upload.tsx`

测试：

Backend:

```bash
cd services/platform-api
./.venv/bin/pytest \
  tests/test_company_schema_catalog.py \
  tests/test_ingest_v2_review_draft.py \
  tests/test_ingest_v2_api.py \
  tests/test_ingest_v2_confirm.py \
  tests/test_ingest_rq_worker.py \
  tests/test_ingest_jobs.py \
  -q
```

Frontend:

```bash
cd apps/win-web
npm run check
```

交付标准：

- 不回滚用户或其他 agent 的改动。
- 不引入旧 `/win/api` alias。
- V1 ingest 路由保留。
- 输出改动文件、测试结果、剩余风险。
