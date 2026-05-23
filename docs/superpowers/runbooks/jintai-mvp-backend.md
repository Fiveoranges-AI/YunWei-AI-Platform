# 锦泰耐火材料 MVP 后端 Runbook

本 runbook 覆盖当前后端交付范围：数据库 schema、seed data、只读生产流转查询、AI 待确认队列。它不包含前端页面开发、不连接真实用友库、不写回客户正式业务系统。

## 当前边界

- 数据在平台库的 `jintai_mvp` schema 中，避免改动现有 `public.users`、`public.tenants`、`yunwei_win` 每企业业务库。
- `/api/jintai/*` 走现有 `app_session` 登录态和企业 membership 鉴权。
- 默认只允许 `enterprise_id` 为 `jintai-demo` 或 `jintai` 的企业成员访问；可用 `JINTAI_MVP_ENTERPRISE_IDS` 逗号分隔覆盖。
- 普通成员可读；`owner/admin` 才能创建或审核 AI 队列项。
- AI/OCR/Excel 结果必须先进入 `jintai_mvp.ai_extraction_queue`。
- `/review` 只确认或驳回队列项，不直接改生产流转单、订单、产品等业务表。

## 文件

- Migration: `services/platform-api/migrations/012_jintai_production_mvp.sql`
- Seed: `services/platform-api/seeds/001_jintai_mvp_seed.sql`
- API: `services/platform-api/platform_app/jintai_api.py`
- Tests: `services/platform-api/tests/test_jintai_api.py`
- 用友占位: `src/integrations/yonyou/`

## 初始化数据

后端启动时会自动执行 `services/platform-api/migrations/*.sql`。也可以直接运行脚本，它会先重放幂等 migration，再写入 seed：

```bash
./scripts/seed-jintai-mvp.sh
```

验收 seed 计数：

```bash
./scripts/check-jintai-mvp.sh
```

也可以手动执行：

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f services/platform-api/seeds/001_jintai_mvp_seed.sql
```

## 本地启动

```bash
cd services/platform-api
uv sync
./.venv/bin/uvicorn platform_app.main:app --reload --port 8000
```

如果 8000 已被其他服务占用，可改用 8001：

```bash
DATABASE_URL="postgresql://postgres:test@127.0.0.1:5433/test" \
REDIS_URL="redis://127.0.0.1:6380" \
COOKIE_SECRET="test-cookie-secret-32-bytes-padding=" \
JINTAI_MVP_ENTERPRISE_IDS="jintai-demo,jintai" \
./.venv/bin/uvicorn platform_app.main:app --host 127.0.0.1 --port 8001
```

前端开发服务器可代理到该后端并直达锦泰页：

```bash
cd apps/win-web
JINTAI_API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5176
# http://127.0.0.1:5176/win/?tab=jintai
```

本地演示账号可按测试库需要创建为 `jintai_owner / jintai-demo-pass`，企业 ID 为 `jintai-demo`，角色为 `owner`：

```bash
./scripts/bootstrap-jintai-demo-user.sh
```

如果当前登录账号不属于 `jintai-demo` 或 `jintai` 企业，需要先创建企业并授权，或在本地 `.env` 里设置：

```bash
JINTAI_MVP_ENTERPRISE_IDS=yinhu,jintai-demo,jintai
```

## API 快速检查

以下请求需要已登录浏览器的 `app_session` cookie，或用测试客户端带 cookie 调用。

```bash
curl -b "app_session=$APP_SESSION" http://localhost:8000/api/jintai/overview
curl -b "app_session=$APP_SESSION" http://localhost:8000/api/jintai/customers
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/flow-cards?status=delayed"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/flow-cards?current_step_code=sintering"
curl -b "app_session=$APP_SESSION" http://localhost:8000/api/jintai/flow-cards/FC-JT-202605-005
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/orders?status=delayed"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/process-routes?product_sku=JT-AM-SP-001"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/process-parameters?product_sku=JT-AM-SP-001"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/source-mappings?local_table=products"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/briefing?briefing_date=2026-05-17"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/ai-extraction-queue?status=pending_review"
curl -b "app_session=$APP_SESSION" "http://localhost:8000/api/jintai/extractions?status=pending"
```

创建队列项：

```bash
curl -X POST -b "app_session=$APP_SESSION" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/jintai/ai-extraction-queue \
  -d '{
    "source_document_name": "manual-flow-card.jpg",
    "extraction_type": "ocr_flow_card",
    "target_table": "production_flow_cards",
    "payload": {"source": "manual_test"},
    "extracted_data": {"flow_card_no": "FC-JT-MANUAL-001"},
    "confidence": 0.88
  }'
```

创建 ingest 占位记录。该接口只创建 `attachments` 和 `ai_extraction_queue`，不执行 OCR，不连接用友，不写业务表：

```bash
curl -X POST -b "app_session=$APP_SESSION" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/jintai/ingest \
  -d '{
    "source_document_name": "flow-card-placeholder.jpg",
    "mime_type": "image/jpeg",
    "extraction_type": "ocr_flow_card",
    "target_table": "production_flow_cards",
    "payload": {"source": "manual_test"},
    "extracted_data": {"flow_card_no": "FC-JT-PLACEHOLDER"},
    "confidence": 0.75
  }'
```

人工审核队列项：

```bash
curl -X POST -b "app_session=$APP_SESSION" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/jintai/ai-extraction-queue/AIQ-JT-202605-001/review \
  -d '{
    "action": "confirm",
    "reviewer_role_code": "production_manager",
    "note": "人工确认 OCR 结果属实"
  }'
```

兼容 demo 挂接点的确认别名：

```bash
curl -X POST -b "app_session=$APP_SESSION" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/jintai/extractions/AIQ-JT-202605-001/confirm \
  -d '{"reviewer_role_code": "production_manager"}'
```

规则型问答。当前不调用外部 LLM，只查库、返回引用，并写 `ai_query_logs`：

```bash
curl -X POST -b "app_session=$APP_SESSION" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/jintai/ask \
  -d '{"query_text": "今天哪些生产单延期？"}'
```

## Seed 数据验收点

- 5 个业务用户角色：老板、生产经理、成型操作员、烧结操作员、检包操作员。
- 5 个客户。
- 8 个产品，偏锦泰窑炉耐火窑具/技术陶瓷业务线。
- 每个产品 1 条默认工艺路线，每条路线包含成型、烧结、检包。
- 15 张生产流转单，每张 3 条工序执行记录。
- 覆盖 3 张延期、4 张卡在烧结、2 张数量异常、2 个高风险产品、2 张已完成、2 张刚创建未开始。

## 后续建议

1. 前端只接现有 `/win/` 的锦泰 demo，不新增页面；先读 `overview`、`flow-cards`、`ai-extraction-queue`。
2. 再做“确认后写业务表”的受控 confirm handler：必须按 `target_table` allowlist、字段 allowlist、事务、审计日志实现。
3. 用友仍从离线 Excel/CSV 或只读中间库导入，不连接客户生产库。
4. 如果要进入真实试点，先把 `JINTAI_MVP_ENTERPRISE_IDS` 改成客户独立企业 ID，再接前端。
