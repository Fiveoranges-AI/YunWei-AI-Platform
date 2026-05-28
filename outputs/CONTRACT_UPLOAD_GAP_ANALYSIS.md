# 锦泰合同上传 — Discovery + Gap Analysis (Round 13)

**生成**: 2026-05-28 凌晨 · **来源**: 实地 grep + 文件 read across 4 worktrees (main / jintai-backend-mainline / jintai-finance-reports / jintai-frontend-mode)
**结论 (一句话)**: 现状比 brief 估计的好 — **schema / API / parse adapter / confirm_writer 全 ✅ 已有**, 真正缺的是 (a) DemoMockProvider 的 Contract 分支 (b) 前端 jintai 合同库 overlay (c) V2 PII redaction *根本没有这个模块*

---

## 调查范围

逐项扫:
1. Contract entity 模型
2. parse_pipeline contract 路径 (PDF → 候选 JSON)
3. V2 安全栈 (PII redaction / sensitive_entities)
4. UI 入口 (智通客户主 app + 锦泰 demo)
5. 测试覆盖

---

## 1. 合同实体 model — ✅ 已经很完整

### 表 `contracts` (yunwei_win/models/contract.py)

完整 schema, 所有 mixins (Timestamp + RowProvenance + HumanVerification + RowAudit + Ownership + SoftDelete):

| 字段 | 类型 | 备注 |
|------|------|------|
| `id` | UUID | PK |
| `customer_id` | UUID | FK → customers.id (RESTRICT) |
| `order_id` | UUID nullable | FK → orders.id (CASCADE), 老路径保留 |
| `contract_no_external` | str | 索引,对方合同号 |
| `contract_no_internal` | str | 我方内部编号 |
| `amount_total` | Numeric(18, 4) | 合同总额 |
| `amount_currency` | str(8) | CNY/USD/... |
| `payment_milestones` | JSON (list) | 老路径,新写走子表 |
| `delivery_terms` | text | 交付条款 |
| `penalty_terms` | text | 违约条款 |
| `effective_date` / `expiry_date` / `signing_date` | Date | |
| `payment_terms` | text | 账期文本 ("月结30天" 等) |
| `confidence_overall` | float | 文档级抽取置信度 (legacy column) |
| `status` | str(32) | |

### 表 `contract_payment_milestones` (yunwei_win/models/company_data.py:125)

| 字段 | 类型 | 备注 |
|------|------|------|
| `id` | UUID | PK |
| `contract_id` | UUID | FK |
| `name` | str(128) | 节点名 (首付 / 验收 / 尾款) |
| `ratio` | Numeric(8,4) | 0.3 = 30% |
| `amount` | Numeric(18,4) | 绝对额 |
| `trigger_event` | str(128) | "签约后" / "验收通过后" |
| `trigger_offset_days` | int | +N 天 |
| `due_date` | Date | 计算后 |
| `raw_text` | text | 原文 |
| `sort_order` | int | |

**结论**: schema 完美, 不需要改。

---

## 2. parse_pipeline 合同路径 — ⚠ 全有但 DemoMock 出错实体

### contract adapter — ✅ 完整 (228 行, `services/parse_pipeline/adapters/contract.py`)

流程:
1. PDF text-extractable (pdfplumber): 直接拿 markdown, 跳 OCR
2. 否则当图: base64 → provider (Claude vision)
3. 推 ExtractionPayload → provider → ProviderResult
4. shape → CandidateJSON, stamp source_span / penalise no-provenance / 计算 overall_confidence

### Contract entity ontology field aliases — ✅ (ontology.py:140-149)

`contract_no_external`, `contract_no_internal`, `amount_total`, `amount_currency`, `signing_date`, `effective_date`, `expiry_date`, `payment_terms` 全有中文 + 英文 aliases。

### `/api/win/parse/upload` PDF 路由 — ✅

`_EXT_TO_SOURCE_TYPE` (parse_upload.py:62-69): `.pdf → "contract"`。

### **❌ DemoMockProvider 合同分支错** (providers/demo.py:65)

```python
if any(k in payload.filename for k in ("合同", "采购")):
    entities = [_gen_purchase_requisition(rng, payload.filename)]   # ← 错!
```

合同文件名应该生成 **Contract** 实体, 不是 PurchaseRequisition。锦泰 demo 客户/老板上传 `采购合同.pdf` 看到的是 PR 字段 (申购号 / 部门 / 申请人), 不是合同字段 (合同号 / 对方 / 金额 / 到期日)。

**修法**: 写 `_gen_contract()`, "合同" 关键字路由到它; "采购" 关键字仍走 PR。这是 round 13 必修项 #1。

### `_run_demo_provider` 跳 adapter — ⚠ 设计意图

`parse_upload.py:_run_demo_provider` 传 `markdown=""` (绕过 pdfplumber 读真实文本)。这是 round 5 故意决定 — DemoMockProvider 不读内容,只看 filename+size hash, 所以 adapter 跑不跑都一样。

**没问题**, 只是说明 demo path 跟真 LLM path 走不同分支:
- Claude path: `parse_to_candidates()` → adapter (pdfplumber 抽真文本) → provider (vision)
- demo path: 跳过 adapter, 直接 `_run_demo_provider()` → 出 deterministic mock

---

## 3. V2 PII redaction — ❌ **该模块不存在**

Brief 假设有 "Phase 2 PII redaction" 模块。**实地确认: 没有。**

- `git grep -l 'redact_document\|class Sensitive\|sensitive_entities\|document_chunks' origin/main` → **空**
- 同样扫 4 个 jintai/p0 branches → 空
- `services/platform-api/yunwei_win/services/` 唯一 PII/redact/sanitize 命中: `llm.py:_sanitize_request()` — 是把 base64 blob 替换成 size marker 防日志爆炸, 跟 PII redaction 无关
- `find . -iname 'SECURITY*'` → 无文件

**这是 brief 估计错误**。V2 安全栈 (RLS, audit) 在 win-vnext-tenant-schema 里有 (review_lock_api 等), 但 PII redaction 模块没人写过。

**Round 13 决策**: 按用户红线 — "**如果中途发现需要修改 V2 安全核心,停下来记 SELF_AUDIT, 不要硬上**". 我不会在通宵 round 临时造一个 PII redaction 模块 (会用错 regex / 漏挂 ingest pipeline / 没人 review)。**留为 P3 backlog**, 在 SELF_AUDIT + GAP_ANALYSIS doc 里写明。

如果一定要立刻 ship 一个最弱版本: 在 `/parse/upload` 返回里加 warnings 标 "合同含敏感信息(金额/对方/电话), 请审核后再外传", 不写入 sensitive_entities 表 (该表不存在)。这是文案警告, 不是真 redaction。可选, 不在 round 13 主线。

---

## 4. UI 入口 — ⚠ 后端有 list/detail, 前端 jintai 没 contract overlay

### 后端 API — ✅ 完整 (read.py:428-509)

- `GET /api/win/contracts?limit=50` 列表 (sorted by created_at desc)
- `GET /api/win/contracts/{id}` 详情 — 返回 contract + order + customer + **FieldProvenance** 行 (provenance 是 confirm_writer 写入时落的字段级证据 — 真正的 "AI 先填、人确认" 审计链)
- `_contract_dict` 序列化全字段 (amount_total / currency / payment_milestones / delivery_terms / penalty_terms / effective_date / expiry_date / signing_date / payment_terms / confidence_overall / status / soft-delete 标志)

### 智通客户主 app — N/A

那是另一个 app (win-customer-profile), 这一轮不动。

### 锦泰 demo 前端 — ❌ 没合同 overlay

`JintaiBackendOverlays.tsx` 当前 4 个 overlay:
- Finance (会企三表)
- Briefing (经营日报 KPI)
- Purchase (PR/PO/Payable)
- Production BOM

**缺**: Contract overlay (合同库列表)。客户上传合同采纳后, 没有地方能在 demo UI 里看到 "刚入库的合同"。

`JintaiRealUploadPanel.tsx` (round 5) 接 PDF mime → 上传 → confirm 流可以走通, **但是当前 accept 流只对 IssueVoucher 触发主线 (扣库存 → 缺料 → auto-draft PR)**, 对 Contract 实体只是 `已写入 Contract (id=xxx...)`, 然后就没下文了。客户看不到这个 contract 入哪。

**Round 13 修法**: 
1. 给 `JintaiBackendOverlays.tsx` 加第 5 个 overlay `JintaiContractsBackendOverlay` (列出 `GET /contracts` 返回值, 展示 contract_no / customer / amount / signing_date / status)
2. 挂到合适的 tab — 可能新建一个 "合同库" tab, 或挂到 "AI 收件箱" tab 下面作为子区
3. JintaiRealUploadPanel accept 后, 如果是 Contract 实体, refresh contract list overlay

### 前端示例 PDF — ✅ 已有

`public/samples/jintai/采购合同.pdf` 已存在 (round 5 准备的)。

---

## 5. 测试覆盖 — ⚠ parse_pipeline 全, jintai 端到端缺

### ✅ 已有

- `tests/test_parse_pipeline.py` 全套 contract 测试 (line 117-228 区间):
  - 用 MockProvider 出 Customer + Contract 双实体 + Customer-has-Contract relationship
  - 验证 provenance 落 source_span / source_page / status field confidence cap
- `tests/test_url_contract.py` — URL 路由 contract (不是数据 contract, 命名冲突)

### ❌ 缺

- `tests/test_jintai_contract_*` — 任何 jintai 端到端 contract 测试
- 跨租户 contract 隔离 (round 9 `test_jintai_cross_tenant.py` 没覆盖 Contract)
- 并发 contract confirm (round 9 `test_jintai_concurrency_audit.py` 只测了 IssueVoucher / PR)
- DemoMockProvider 出 Contract 的单元测试 (因为之前根本不出)

---

## Round 13 实施范围 (基于 gap, **不扩张**)

### A. 后端 (PR #115 stack)

1. **DemoMockProvider 加 `_gen_contract()` 分支** (`providers/demo.py`)
   - 关键字 "合同" → Contract; 仅 "采购" → 仍 PR
   - 字段: contract_no_external / contract_no_internal / amount_total / amount_currency / signing_date / effective_date / expiry_date / payment_terms / status
   - 也给一条 Customer entity + Customer-has-Contract relationship (因为 Contract 需要 customer_id FK, 不然 confirm_writer 写入会留 NULL FK — 可接受但 reviewer 看不出关系)

2. **新 tests** (`tests/test_jintai_contract.py`, ~5 cases):
   - `test_demo_mock_provider_generates_contract_for_合同_filename`
   - `test_parse_upload_contract_pdf_returns_contract_candidate`
   - `test_contract_appears_in_list_after_confirm`
   - 加跨租户 case 到 `test_jintai_cross_tenant.py` (扩展, 不新文件)
   - 加并发 confirm case 到 `test_jintai_concurrency_audit.py` (扩展)

3. **CI workflow** 加新测试 file 到 SQLite job enum

### B. 前端 (PR #116 stack)

4. **`JintaiContractsBackendOverlay` 组件** (`JintaiBackendOverlays.tsx` 加 ~80 行)
   - 列出 `GET /contracts` (limit=20)
   - 表格: 合同号 (内/外) / 客户 / 金额 / 签订日 / 到期日 / 状态 / 置信度
   - 复用 OverlayChrome (已有 loading / error / refetch)
   - 挂哪? **新建 "合同库" tab**, 添加到顶部 nav, mock 模式时显示一个 "demo 数据 — 真实合同需 backend mode" 占位

5. **`useBackendQuery` 调 `listContracts`** (`api/jintai-backend.ts` 加 ~30 行)
   - `ContractListItem` 类型 + `listContracts()` helper

6. **JintaiRealUploadPanel.accept Contract 分支** (~20 行)
   - 写完 Contract 后: refresh contract overlay (dispatch event)
   - 不触发主线 (Contract 不像 IssueVoucher 触发库存 / PR — 单纯 entity 入库)

### C. 文档 + 脚本

7. **`scripts/jintai/contract-demo.sh`** (~60 行):
   - 一行命令: 起 backend → 上传 `采购合同.pdf` → 验证 candidate → confirm → 列表确认能看到
   - 用 curl + jq, 仿 round 7 smoke-clean 风格

8. **一张端到端截图** `round13-contract-upload-e2e.png`:
   - 上传 contract → 字段 + 置信度卡片 → 采纳 → contract overlay 显示新合同

9. **FINAL_REPORT §24** 章节, **SELF_AUDIT 加 round 13 行**, **PR 描述加 7 段速读**

### **D. 不做** (留 backlog)

- **V2 PII redaction**: 不存在的模块。任何此方向的 work 都要 CTO 决策 + 设计 review。GAP_ANALYSIS §3 已写清。
- **语义检索 / 合同 RAG**: brief 说 "advanced features 留下一轮"。
- **Contract 修订历史 / 版本**: 表里没字段, 不在 scope。

---

## 设计决策与风险

### 决策 1: 给 demo PDF 加 Customer + Customer-has-Contract relationship
**为何**: Contract 表 `customer_id` 可空, 但 demo 真实场景一定关联客户。confirm_writer 已支持 `Customer-has-Contract`。给 demo provider 加 1 个 Customer 实体让 reviewer 看到完整 relationship 链。
**风险**: Customer 表唯一性约束 (full_name unique?) 多次 demo 重复上传会冲突。**缓解**: 每次 seed 用 filename hash 后缀加到客户名 (e.g. "锦泰锂电客户-a3f4"), 避免重复。

### 决策 2: 新建 "合同库" tab 而非塞到现有 tab
**为何**: 现有 tabs 都有专属语义 (经营日报/财务/采购/生产/AI 收件箱/问 AI/可信 AI)。合同库是独立 entity 类别, 单独 tab 更清晰。
**风险**: tab 列表已经 7 个, 加第 8 个会挤。**缓解**: 截图测一下宽度, 必要时改图标或缩短文案。

### 决策 3: 不接 V2 PII redaction
**为何**: 模块不存在; 通宵临时造一个 high-risk (regex 漏 / ingest 没全挂 / 没人 review)。**用户红线明确**说过这个场景。
**替代**: 在合同详情 overlay 顶部加一行小字 "💡 合同含敏感信息(金额/对方/电话), 外发前请确认权限"。是文案提醒, 不是真打码。

### 决策 4: 不动 V2 vnext (RLS / review_lock / audit)
**为何**: 这些是 #107 PR 范围, 锦泰栈 base 在 #110-#113 之上, 不跨过去改。

---

## 估时 + 顺序

| 阶段 | 内容 | 估时 |
|------|------|------|
| B-1 | DemoMockProvider _gen_contract + Customer + relationship | 20 min |
| B-2 | 新测 file + 跨租户 + 并发 case | 35 min |
| B-3 | CI workflow yaml 加新 file | 2 min |
| B-4 | 后端 commit + push + CI 等绿 | 5 min wall + 等 4 min |
| C-1 | api/jintai-backend.ts 加 listContracts | 10 min |
| C-2 | JintaiContractsBackendOverlay (~80 lines) | 30 min |
| C-3 | JintaiRealUploadPanel Contract 分支 + refresh dispatch | 20 min |
| C-4 | tab 加 "合同库" + 路由 (有 mock placeholder) | 25 min |
| C-5 | 前端 commit + push + CI 等绿 | 5 min + 2 min |
| D-1 | contract-demo.sh | 15 min |
| D-2 | 端到端截图 (起 backend + frontend + headless Chrome 自驱) | 15 min |
| D-3 | FINAL_REPORT §24 + SELF_AUDIT + PR description | 25 min |

**总估**: ~3.5 小时实施 + ~10 分钟 CI 等 + 余量。 老板 8 小时可睡, 我有大量余量自我审查 + 修问题。

---

## 复盘验证清单 (做完跑一遍)

- [ ] DemoMockProvider 上传 `采购合同.pdf` (无 ANTHROPIC_API_KEY) 返回 Contract 实体 + 完整 8 个字段
- [ ] `/parse/upload` → `/confirm/entities` → `GET /contracts` 链跑通 (curl 验证)
- [ ] 前端 mock mode 默认不会进 backend (round 13 hotfix 之后), URL 默认零红色
- [ ] 前端 backend mode + backend 跑 → 合同库 overlay 显示真实数字
- [ ] 跨租户隔离 (tenant_a 的 contract 在 tenant_b 看不到)
- [ ] 双 confirm 同 Contract 不出 2 行 (用 ingestion_id idempotency 保护? 或者认了)
- [ ] CI: SQLite 93+N / PG 511+N / smoke / frontend typecheck+build 全绿
- [ ] 截图能跑能看
- [ ] FINAL_REPORT §24 + SELF_AUDIT + PR description 同步

---

**生成于**: round 13 discovery, 2026-05-28 02:50 / **下一步**: 实施 → 测试 → CI → 文档 → 老板早上看
