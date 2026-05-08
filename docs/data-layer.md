# Platform Data Layer — Lakehouse Ingestion

> **Status**: draft, 2026-05-05
> **Counterpart**: kernel side defined in `/Users/eason/Documents/eason/five-oranges/YunWei-AI-Kernel/docs/superpowers/specs/2026-05-05-meta-harness-kernel-pivot-design.md`
> **Scope**: producer side of the lakehouse (who writes bronze, who runs bronze→silver). Consumer side (silver schema, agent queries, Meta-Harness loop) lives in the kernel spec — this doc just imports the contract.

---

## 1. 为什么 platform 拥有数据层

YunWei-AI 体系三方分工:

| 系统 | 职责 |
|---|---|
| YunWei-AI-Kernel | 生成 customer agent 代码 + Meta-Harness 优化循环;**只读 silver** |
| **YunWei-AI-Platform**(本 repo) | 多租户 runtime + 用户/ACL + HMAC 反代 + **数据管理(本 spec)** + 部署 customer agent |
| 未来 import-agent(独立 repo) | 多源 bronze→silver 翻译;只懂数据,不懂业务 |

数据管理落 platform 的理由:
- platform 已有 user / tenant / session / HMAC 全套基础设施
- 数据 UI 与 agent 反代天然同域(`app.fiveoranges.ai/data` vs `/c/<client>/<agent>/`)
- kernel 是无状态 generator,不该承担运行时数据管理
- import-agent 还没建,platform 先承接最朴素的几条路径(文件上传 + 人工录入)

---

## 2. Lakehouse 物理布局(per tenant)

沿用 platform v2.0 客户级容器隔离约定 → 每个客户一个数据卷:

```
data/tenants/<client_id>/
├─ bronze/                         # 原始落地,1:1 镜像源,不做转换
│  ├─ erp_kingdee/<YYYY-MM-DD>/<table>_raw.parquet + _meta.json
│  ├─ erp_yongyou/<YYYY-MM-DD>/...
│  ├─ file_excel/<YYYY-MM-DD>/<filename>.parquet + _meta.json
│  ├─ file_pdf/<YYYY-MM-DD>/<filename>.parquet + _meta.json
│  └─ manual_ui/<YYYY-MM-DD>/<form_name>.parquet + _meta.json
├─ silver-live.duckdb              # 客户 agent 只读挂载;此 spec 的核心产出
└─ silver-snapshot-<YYYY-MM-DD>.duckdb  # kernel evaluator 用的冻结快照
```

`_meta.json` 每文件一份,内容:
```json
{
  "source_type": "file_excel",
  "tenant": "yinhu",
  "ingested_at": "2026-05-04T10:23:01Z",
  "ingested_by": "user:eason",
  "uploader_ip": "...",
  "original_filename": "sales-q1.xlsx",
  "sheet_name": "Sheet1",
  "row_count": 4203,
  "checksum_sha256": "..."
}
```

Silver 文件路径由 platform 决定;**kernel 通过环境变量 `YUNWEI_SILVER_DB_PATH` 拿到**,不硬编码。

---

## 3. UI 总体形态 — 数据中心 + 导入助手

### 3.1 用户画像与设计取舍

目标用户是 SME 运营/财务/老板,**不是** data engineer / analyst。明确**不做** Databricks 风格的 SQL workspace / Notebook / Catalog 三层导航 — 那是分析师工具,对运营是负担。设计原则:

- 用户不写 SQL,不看 schema 树
- 用户的核心问题只有三个:"我数据齐了吗?"、"这条对不对?"、"再来一份这样的数据怎么导?"
- 所有数据通路收敛到**一个**控制台:`app.fiveoranges.ai/data`(下称"数据中心"),不再分散到独立页面

### 3.2 控制台主区(三层堆叠,只读优先)

```
┌─────────────────────────────────────────────────────────┐
│  Health Panel                                            │
│  silver 5 张表的健康卡片:行数、最近更新、来源分布饼图   │
├─────────────────────────────────────────────────────────┤
│  Table Browser                                           │
│  选 silver 表 → 看行(分页 / 过滤 / 全文搜索)            │
│  不暴露 SQL,不暴露 join                                 │
├─────────────────────────────────────────────────────────┤
│  Bronze Files                                            │
│  bronze 落地清单:source_type、上传人、时间、行数、回滚 │
└─────────────────────────────────────────────────────────┘
```

主区**不放**"上传按钮""新增按钮"这类入口 — 所有写操作统一通过 §3.3 侧栏 assistant 发起,避免心智分裂。

### 3.3 侧边栏:导入助手(chat-style agent)

固定停靠右侧,是 platform-side 内置 agent。系统提示词包含 silver-canonical schema 摘要 + 当前租户 bronze/silver 状态。承担四件事,把原本要分到三个页面的流程串成一段对话:

1. **拖文件给我** — 用户把 Excel/CSV/PDF 拖进 chat;assistant 落 bronze + 在 chat 里渲染 sheet 列表 + 50 行预览(对应 §4.2 / §4.3 后端路径)
2. **建映射** — assistant 自动猜 bronze 列 → silver 列;用户在 chat 里点确认或文字纠正(如"customer_name 应该映射到 customer.display_name");无需独立映射页(对应 §5.1)
3. **手填一条** — 引导式问答:"录哪张表?" → 渲染该表必填字段的小表单 → 提交即双写 bronze + silver(对应 §4.4)
4. **回答"我数据齐了吗"** — 读 health panel + bronze 清单,回报"客户表 OK,订单表本月缺 3 周",降低用户认知负担

assistant 调用的工具就是 §4 / §5 中描述的后端 API,**不新增数据通路** — 这一节只是 UI 包装层。

### 3.4 路由 / 入口收敛

| 早期设想(已废弃) | 现行 |
|---|---|
| `/data/upload` | 数据中心 → 侧栏 assistant "拖文件给我" |
| `/data/entry/<table>` | 数据中心 → 侧栏 assistant "手填一条" |
| `/data/mapping/<file>` | 数据中心 → 侧栏 assistant "建映射" |

API 路径见 §4、§5,不受 UI 收敛影响。

---

## 4. 四类 bronze 写入路径

### 4.1 ERP API(`source_type=erp_*`)

未来 import-agent 干。本 spec 不实现,只锁定:

- import-agent 启动时,platform 给它注入 `client_id` + 该客户的 ERP credentials(从 platform.db 已有的 `tenants` 表扩列)
- 输出位置:`data/tenants/<client_id>/bronze/erp_<vendor>/<date>/`
- 每次抓取必须写 `_meta.json`,字段如 §2

### 4.2 Excel / CSV 上传(`source_type=file_excel`)

后端端点:`POST /api/data/upload`(multipart)。前端入口为 §3.3 侧栏 assistant,**没有**独立上传页。

- 鉴权:复用现有 session + CSRF
- 处理:
  1. 接收文件 → 存原文件到 `data/tenants/<client_id>/_uploads/<uuid>.xlsx`(留底,用于 audit)
  2. 用 pandas/openpyxl 读取每个 sheet → 转 parquet(列名保留 sheet 原文,不做语义映射)
  3. 写 `bronze/file_excel/<date>/<original_filename>__<sheet>.parquet` + `_meta.json`
  4. 在 platform.db 写一条 `bronze_files` 记录(供数据中心主区列出 / 回滚)
- 失败处理:任何错误回滚 — 已写入文件 rm,db 行 rollback
- 响应:返回 sheet 列表 + 前 50 行预览的 JSON,assistant 直接渲染到 chat

### 4.3 PDF(`source_type=file_pdf`)

复用 §4.2 同一端点 + 入口,但解析步骤不同:

- 接收 → 调用外部 OCR/extraction(Claude API + vision,或 pdfplumber for born-digital)
- 提取出表格化数据 → 转 parquet
- **解析失败不算 bronze 完成**:assistant 在 chat 里提示"这份 PDF 没识别出表格,要不要用 Excel 模板手填?"

PDF 是 best-effort,不保证所有 PDF 都能落 bronze。早期可以只支持发票 / 送货单等结构化模板。

### 4.4 人工录入(`source_type=manual_ui`)

无数据租户的首选路径。入口为 §3.3 侧栏 assistant 的 "手填一条" 流程,后端端点:`POST /api/data/manual/<table>`,table ∈ silver canonical 5 表。

- 表单字段直接对应 silver 列(从 kernel 的 `silver-canonical.yaml` 渲染)
- 提交时:**双写** — 写入 `bronze/manual_ui/` 一份(留 audit) + 直接 upsert 到 `silver-live.duckdb`(因为人工录入不需要再做语义转换)
- 编辑/删除:沿用 platform.db 的 `bronze_files` 索引找回原 bronze 行,改动同时反映 silver

这是 **bronze 不再是必经之路**的唯一例外 — 人工录入路径可以"短路"直接进 silver,但 bronze 必须留底。

---

## 5. bronze → silver 转换

### 5.1 谁负责

- 文件类(file_excel / file_pdf):**§3.3 assistant 承接半自动映射** — 用户在 chat 里确认或纠正 assistant 猜出的列对应关系,映射规则存 platform.db `silver_mappings`,后续同模板自动跑
- ERP 类(erp_*):**未来 import-agent**(每个 ERP vendor 一套规则)
- 人工录入:跳过转换,§4.4 双写

### 5.2 触发时机

- 文件上传完成 + 映射建好 → 自动触发一次转换
- ERP 增量同步完成 → import-agent 自己触发
- 任何转换都是 idempotent — 重跑结果一致(用 source_lineage 主键去重)

### 5.3 silver schema 来源

silver canonical schema 由 **kernel** 维护,文件:
`yunwei-kernel/lakehouse/silver-canonical.yaml`(v1 锁 5 表 + 必含 `source_type` + `source_lineage`)。

platform 通过 git submodule 或定期 sync 拿到这份 yaml,作为校验、手填表单渲染、assistant 系统提示词的依据。schema 升级走 kernel 的 spec/plan 流程,platform 跟随。

---

## 6. 与 kernel 的协作点

| 协作点 | 谁先动 | 接口 |
|---|---|---|
| silver 文件位置 | platform 决定 | 环境变量 `YUNWEI_SILVER_DB_PATH` 注入 customer agent 容器 |
| silver schema 演进 | kernel 主导 | `silver-canonical.yaml` 文件 |
| Meta-Harness 评估快照 | kernel 触发,platform 配合 | platform 暴露 `POST /api/data/snapshot/<client_id>` 让 kernel 复制冻结 |
| 上线新 candidate(promote) | kernel 触发 | platform `POST /api/admin/redeploy` 改容器 mount |
| Langfuse trace 回流 | platform 接 OTLP,kernel 拉 | OTLP endpoint 由 platform 配置;kernel 用 Langfuse SDK 读 |

---

## 7. Out-of-scope(本 spec 不做)

- ❌ ERP API 抓取本身(future import-agent)
- ❌ silver schema 设计/演进(kernel 主导)
- ❌ Meta-Harness 优化循环逻辑(kernel)
- ❌ 高级数据质量校验 / 主数据管理 / 审批工作流(可视为 v2)
- ❌ 跨租户数据共享(违反 v2.0 容器隔离原则)
- ❌ 实时流式数据(本期只批量)
- ❌ 多源 conflict resolution(同客户既有金蝶又有 Excel,先简单 last-write-wins)
- ❌ SQL workspace / Notebook / Catalog 浏览器(用户画像不需要,见 §3.1)

---

## 8. 实施分层

### M1: Foundation
- `data/tenants/<client>/` 目录约定 + 创建脚本
- platform.db 加 `bronze_files` 表 + `silver_mappings` 表
- 引入 `silver-canonical.yaml` sync(从 kernel repo)
- DuckDB 单元测试夹具

### M2: 数据中心控制台(只读骨架)
- 单页 `/data` + 三层主区:health panel / table browser / bronze files
- 全部从 silver-live.duckdb + platform.db 直接渲染,只读
- 侧栏 assistant 占位(UI 在,工具尚未接通)

### M3: assistant 接通文件上传 + 自动映射
- `POST /api/data/upload` + Excel → bronze parquet pipeline
- assistant "拖文件给我" + "建映射" 两个流程串通
- silver 增量 upsert(走 §5.1 映射规则)
- 验收点:assistant 一次会话从拖文件到 silver 落库闭环

### M4: assistant 接通手填 + PDF best-effort
- `POST /api/data/manual/<table>` + 5 张 silver 表的表单 schema 自动从 yaml 渲染
- assistant "手填一条" 引导式流程
- PDF 解析路径 best-effort 接入 §4.3
- 给 future import-agent 留好 ERP credentials 注入面 + bronze 落地约定

每 M 一份独立 plan;不要并行,按顺序来。

---

## 9. Acceptance Criteria

| ID | 标准 |
|---|---|
| AC-D1 | 通过侧栏 assistant 上传一份 Excel,bronze parquet + `_meta.json` 落盘,chat 里返回前 50 行预览 |
| AC-D2 | 同一份 Excel 上传两次,bronze 不重复写(checksum 去重),assistant 提示"已存在" |
| AC-D3 | 在 assistant 里确认 sheet→silver 列映射后,silver-live.duckdb 行数 = bronze parquet 行数 |
| AC-D4 | 通过 assistant "手填一条" 录入一条 customer 记录,silver 立刻可查,bronze/manual_ui/ 也有副本;主区 health panel 行数 +1 |
| AC-D5 | kernel 的 evaluator 用 `silver-snapshot.duckdb` 跑 search-set,与 silver-live 完全独立(物理副本) |
| AC-D6 | 数据中心主区 Bronze Files 面板能列出某 tenant 全部 bronze 文件,按 source_type 过滤 |
| AC-D7 | 在主区 Bronze Files 删除一份 bronze 文件 → silver 中对应 source_lineage 行同步删除(级联) |
| AC-D8 | 不存在 `/data/upload`、`/data/entry/<table>`、`/data/mapping` 等独立页面;所有写路径只能从 `/data` 控制台 + 侧栏 assistant 发起 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Excel 列名漂移(同模板下次列名变了) | 映射存 platform.db,识别到列名漂移时阻塞自动转换、assistant 主动提示用户重映射 |
| 人工录入 typo 污染 silver | 双写 bronze 留 audit;主区 Table Browser 支持撤回 / 编辑历史 |
| PDF 解析准确率低 | 不强求,失败让用户转 Excel;不在 silver 落不准的数据 |
| 大 Excel 内存爆 | 流式解析(pandas chunked / pyarrow),限制单文件 < 100MB |
| silver schema 变更破坏现有 mapping | 每次 schema 升级跑 mapping migration,失败的 mapping 标 deprecated 留人工修 |
| bronze 文件无限增长 | 留存策略 v2 再做(本期不做,SME 数据量小)|
| assistant 误猜映射污染 silver | 映射 commit 前必须用户在 chat 里确认;首次未确认前自动转换不跑 |

---

## 11. 开放问题(留 plan 阶段决)

1. silver-canonical.yaml 走 git submodule 还是 sync 脚本?(submodule 准但更新慢)
2. assistant 优先支持哪几张 silver 表的"手填一条"?(全 5 张 vs 先做最高频的 customers + orders)
3. PDF OCR 优先用 Claude API vision 还是 pdfplumber + 启发式?
4. silver-snapshot 创建时机:on-demand(kernel 通过 API 触发)vs 定时(每天凌晨)?
5. ~~assistant 用 platform 自家 LLM client 直接调,还是复用 kernel agent runtime?~~ **已决:platform 自家 Anthropic Python SDK**(kernel 是 stateless generator,不为长会话设计;assistant 跨租户共享逻辑,不需要 Meta-Harness 优化)
