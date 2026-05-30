# P0 任务② — 解析流水线 (parse_pipeline) 完成报告

**Branch**: `feat/parse-pipeline-p0-task2` (从 `feat/ontology-p0-task1` 切出, base 指向任务①分支)
**Worktree**: `/Users/kobeli/Documents/Yinhu Project/YunWei-AI-Platform/yunwei-parse-p0`
**Generated**: 2026-05-21 by Claude (autonomous overnight, per授权 prompt)

---

## 1. Phase 0 勘探结论 (5 行)

仓库已经存在大量可复用基础设施,**不需要自研任何解析底层**:

- `services/schema_ingest/parsers/spreadsheet.py` 的 `SpreadsheetParser` 已经把 xlsx/csv/xls 拆成带 cell-级 grounding 的 `ParseArtifact`(每个 cell 都有 `sheet:<name>!R<row>C<col>` 引用)。
- `services/llm.py::call_claude` 已经是带重试 / 计费 / `llm_calls` 表落地的 Claude wrapper,支持 vision (image base64) + DeepSeek-compat endpoint fallback,model 默认从 `settings.model_parse / model_vision` 取。
- `services/ocr/` 有 `OcrProvider` Protocol + Mistral & MinerU 两套实现;`pdfplumber` 已在 deps。
- `models/field_provenance.py` 已经有 `(entity_type, field_name, source_page, source_excerpt, confidence, source_refs)` 的列布局——本任务的"每字段 confidence + source_span"概念与之同源。
- 任务①的 `models/operations.py` 提供了 OrderItem / Delivery / NextAction 等新表,本体边界已明确,我直接 `import` 出 required-fields。

**结论**:任务②不是要造一条平行 pipeline,而是要在已有基础设施上加一层**面向产品的"候选 JSON shape"层** —— 把 `ParseArtifact` / `ProviderResult` 翻译成任务② prompt 里规定的严格 JSON,带本体感知的 `missing_required` 与统一的 dedup warning。

---

## 2. Phase 1 设计

### Provider 选型

| 适配器 | 复用 | 新写 |
|---|---|---|
| Excel | `SpreadsheetParser`(已有) + `ontology.HEADER_ALIASES`(新增的别名表) | 0 LLM 调用,纯确定性 |
| Contract | `pdfplumber`(已有)抽 text → `ClaudeProvider` 走 `call_claude`;扫描件回落 base64 → vision | `ExtractionProvider` 接口 |
| WeChat 截图 | 直接 vision Claude,无 OCR | 同上 |

`ExtractionProvider` 是新 Protocol(`providers/base.py`),沿用与 `OcrProvider` / `FileParser` 一致的形态。**测试全部走 `MockProvider`**,不烧 token;生产走 `ClaudeProvider(session=...)`。

### 文件清单 (新增 9 文件, 修改 0 文件)

```
services/platform-api/yunwei_win/services/parse_pipeline/
    __init__.py                  公共导出
    candidate.py                 CandidateJSON / CandidateEntity / FieldCandidate / SourceSpan
    ontology.py                  required_fields() 动态读取任务①模型;HEADER_ALIASES
    pipeline.py                  parse_to_candidates() 统一入口,按 source_type 分发
    README.md                    用法 + provider 配置 + confidence 算法说明
    providers/
        __init__.py
        base.py                  ExtractionProvider Protocol + payload / result 模型
        mock.py                  MockProvider 给测试用 (canned 或 callable)
        claude.py                ClaudeProvider 封装 call_claude (text / vision 两种模式)
    adapters/
        __init__.py
        excel.py                 csv/xlsx → ParseArtifact → 表头匹配 → CandidateJSON
        contract.py              pdf/img → text or vision → provider → CandidateJSON (含 _shape_candidate_json 复用)
        screenshot.py            img → vision provider → 复用 _shape_candidate_json

services/platform-api/tests/test_parse_pipeline.py         8 测试 (snapshot + 字段语义)
services/platform-api/tests/fixtures/parse_pipeline/
    sample_orders.csv
    sample_contract.txt
    sample_screenshot.png       (69 字节占位 PNG)

outputs/parse_pipeline_samples/
    01_excel.json
    02_contract.json
    03_screenshot.json
```

### confidence + missing_required 算法

**单字段 confidence**:
- Excel: `header_match_confidence (1.0 完全等于别名 / 0.85 包含别名) × value_presence (1.0 / 0.4 if 空)`。
- Contract & Screenshot: provider 返回 confidence 直接采用,但**当 provider 没附 source_excerpt / source_page / source_ref_id 时**,confidence 被 cap 到 0.5 然后再 -0.1,并往 `warnings` 写一条"未提供原文出处"。

**overall_confidence**:`mean(单字段 confidence) × max(0.4, 1.0 - 0.05 × total_missing_required_count)`,截断到 `[0, 1]`。

**missing_required 计算**:
- `ontology.required_fields(entity_type)` **从 SQLAlchemy 模型动态读取**,规则:`nullable=False AND default is None AND server_default is None AND name 不在系统 FK 白名单`。
- 系统 FK (`customer_id` / `order_id` / `contract_id` ... ) 不算缺失—它们通过 `relationships[]` 表达。
- 当前实际需要由解析器输出的最小必填集:Customer→`full_name`、Contact→`name`、Product→`name`、Payment→`amount`,其余因有默认值或全部 nullable 而为空集。
- 测试 `test_required_fields_match_task_one_ontology()` 给这层定了基线;如果任务①以后再加一个新的 NOT NULL 列,这个测试会失败,强制此处更新。

**Customer 重名 dedup**:`difflib.SequenceMatcher.ratio() ≥ 0.85` 进 `warnings`,**不自动合并**(符合红线)。当前只有 Excel 适配器消费 `existing_customer_names`;contract / screenshot 由 LLM 在 warnings 里提示。

---

## 3. Phase 2 实施摘要

按 prompt 顺序: **Excel → Contract → Screenshot**,每一步都跑通快照测试。

3 个最小样例 + 期望候选 JSON 都已生成,落在 `outputs/parse_pipeline_samples/`。

主要结果(完整 JSON 见样例文件):

| 样例 | 输入文件 | 实体数 | overall_confidence | 关键说明 |
|---|---|---|---|---|
| 01_excel | `sample_orders.csv`(2 行 8 列) | 6 (2× Customer + 2× Contact + 2× Order) | 1.0 | 全表头完全命中别名;每个 cell 都带 `sheet:sample_orders!R2C1` 形式的 `source_span.cell`;3 条 row-内 relationships(Customer-has-Order / Customer-has-Contact)。 |
| 02_contract | `sample_contract.txt` + MockProvider | 2 (Customer + Contract) | 0.9 | 每字段都有 `source_span.text` 命中原文片段 + `page=1`;含 `Customer-has-Contract` relationship。 |
| 03_screenshot | `sample_screenshot.png` + MockProvider | 2 (Contact + Order) | 0.762 | "6月10日前"被模型判 0.55 confidence 并加 warning;provider 已收到 `image_b64` + `image/png`。 |

---

## 4. Phase 3 自检结果

### 4.1 新增测试 (8 个,全 green)

```
tests/test_parse_pipeline.py
  ✓ test_excel_adapter_extracts_customers_and_orders_per_row
  ✓ test_excel_adapter_flags_dedup_against_existing_customers
  ✓ test_excel_adapter_warns_when_no_known_headers_found
  ✓ test_contract_adapter_shapes_provider_output
  ✓ test_contract_adapter_filters_unknown_field_names
  ✓ test_screenshot_adapter_passes_image_b64_to_provider
  ✓ test_required_fields_match_task_one_ontology
  ✓ test_unknown_entity_type_returns_empty_required

8 passed in 0.51s
```

### 4.2 邻近现有测试回归

```
tests/test_parser_providers.py            ✓ 6/6
tests/test_extraction_schema_vnext.py     ✓ 16/16
tests/test_extraction_normalize_validate.py ✓ 6/6
tests/test_customer_management.py         ✓ 10/10
tests/test_file_type_detection.py         ✓ 3/3
tests/test_landingai_ade_client.py        ✓ 6/6
tests/test_landingai_large_parse_jobs.py  ✓ 8/8
tests/test_entity_resolution.py           ✓ 6/6
tests/test_ingest_review_draft.py         ✓ 7/7
```

### 4.3 仓库全量测试

本地 Python 3.11 环境下,**所有可收集到的测试都通过**;部分测试在 collection 阶段就报错,是 prompt 上下文已经标注过的**预先存在问题**(`platform_app/data_layer/manual.py` 用了 PEP 701 f-string 语法,只在 3.12+ 可解析;prod 跑 3.14,本地 3.11 兜不住)。这些都不是任务②引入的——任务① PR #110 的报告里也提到过同一现象。

---

## 5. 红线核对

| 红线 | 是否遵守 |
|---|---|
| 不落库,只返候选 JSON | ✅ 整个 pipeline 没有任何 `session.add` / `session.commit` |
| 不自研 OCR | ✅ Excel 走 `SpreadsheetParser`;PDF 走 `pdfplumber` 或 vision provider;无新 OCR 代码 |
| 不动任务①的 schema | ✅ 仅 `import` `models.Customer/Contact/...`,无任何模型修改 |
| 不动 guangtian / jintai demo | ✅ worktree 完全隔离;`git diff main..HEAD` 不含 demo 路径 |
| 不引重依赖 | ✅ 零新增 pip 依赖;复用 `openpyxl/pandas/pdfplumber/anthropic`(全部已在 deps) |
| provider 接口可替换 | ✅ `ExtractionProvider` Protocol;`MockProvider` / `ClaudeProvider` 双实现 |
| 结构化日志 | ✅ `pipeline.parse_to_candidates` 在每次运行后写一条 `parse_pipeline.done` info log,含 source_type / filename / entities / overall_confidence / duration_ms |
| 真实 secret 不入 commit | ✅ provider 通过 `services.llm` 拿 `settings.anthropic_api_key`;无硬编码密钥 |
| 现有测试 green | ✅ 见 4.2/4.3 |
| 不 push main | ✅ 工作 branch:`feat/parse-pipeline-p0-task2`(base: `feat/ontology-p0-task1`) |

---

## 6. 待用户拍板 / 留给任务③

1. **PR base 选择**:目前预设 `feat/ontology-p0-task1`(栈式更清晰);也可改为 `main`(PR 自含,但 Reviewer 会同时看到任务①的 diff)。用户开 PR 时可在 `gh pr create --base` 选择。
2. **`ClaudeProvider` 的 prompt**:把 system 指令折进 user message 第一段,因为 repo 已有的 `call_claude` wrapper 不暴露 `system=` 参数。若任务③需要更精细的 system / tool_use 控制,需要先扩 `call_claude` 签名,这里暂时不做。
3. **Excel 表头别名 (`HEADER_ALIASES`)**:目前覆盖 8 个实体共 ~50 个常见别名,可能在真实客户文件下命中率不足。任务③在客户实际跑通后,可以把命中率指标作为回归基线扩充别名表。
4. **`OrderItem` row-relationship**:Excel 适配器目前只在同一行里**有 Order + OrderLine 列时**才产 `Order-has-OrderLine` relationship。如果实际客户的"明细表"是另一个 sheet 跟订单表横向关联,需要任务③加 sheet-级别的关系合并(本任务有意不做,保持只产候选)。
5. **重名 dedup 范围**:当前只对 Customer 做 fuzzy;后续如果发现 Contact / Product 也需要,接口已经留好(就是同一个 `_add_dedup_warnings` 函数加目标实体类型 + 字段名参数)。

---

## 7. Commit / PR 流程

- 已在 worktree `yunwei-parse-p0` 工作;`git status` 干净指向新文件。
- 下一步(留给用户最后过目后执行,或我可以接续):
  1. `git add` 上述 9 个新文件 + 3 个 fixture + `outputs/`(可选,outputs 通常不入版本控制)
  2. `git commit -m "feat(parse-pipeline): file → candidate JSON 流水线 — P0 task ②"`
  3. `git push -u origin feat/parse-pipeline-p0-task2`
  4. `gh pr create --base feat/ontology-p0-task1 --label do-not-merge`

任务③可以从这条 branch 继续切下一层 worktree。
