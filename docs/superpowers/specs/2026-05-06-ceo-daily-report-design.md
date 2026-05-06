# CEO 日报推送 — 设计文档（v0）

> 起草：2026-05-06 · 状态：待用户 review · 后继：写 implementation plan
>
> 范围：给银湖 CEO 推送每日"知己知彼"经营日报；MVP 仅服务银湖一人，但代码骨架按"任意客户 CEO 可开通"设计。dashboard 入口与"超级小陈"并列，不放进小陈对话内。

---

## 1. 问题与目标

许总（银湖董事长）每天需要一份**早间快报**回答两类问题：

- **知己**：昨天公司销售/生产/出货怎么样？群里出了什么客户投诉或紧急事？
- **知彼**：重点客户今天有什么新闻？（招投标、人事变动、负面舆情）

现状：这些信息分散在金蝶 ERP、钉钉若干工作群、新闻互联网，许总每天靠人工拼凑。

**MVP 目标**：每个工作日 07:30 之前在钉钉收到一份结构化 markdown 卡片，点开能跳到 dashboard 看完整版+追问。

**非目标（明确排除）**：
- 不做微信群消息源（无官方 API，TOS 风险）
- 不做应收/现金流板块（金蝶星辰 REST 不暴露，已在 backlog/D-2026-05-02-01）— 但代码留 collector 接口
- 不做行业/政策/招标爬取（v2）
- 不做订阅管理 UI（MVP 用 SQL insert 初始化）

---

## 2. 关键决策

| 决策 | 取值 | 备注 |
|---|---|---|
| 受众 | MVP 仅银湖许总一人；架构按多客户设计 | 第二客户接入时只新增 collector + yaml |
| 推送渠道 | 钉钉企业内部应用单聊 markdown 卡片 + dashboard 备份 | 与数据源同一个 corp app，鉴权一套 |
| 推送时间 | 工作日 07:30 (Asia/Shanghai) | 节假日过滤推后 |
| LLM | 沿用 yinhu 现有 `ANTHROPIC_BASE_URL=deepseek/anthropic` + `MODEL_PRO` 合成 + `MODEL_FLASH` 摘要 | 不引新 provider |
| 网搜 provider | Tavily | 中文新闻覆盖足够 |
| 数据持久化 | platform Postgres 两张新表，content + raw_collectors_json 都存；保留 90 天 | 容器无状态 |
| 失败处理 | 单 collector 失败不阻塞整份；section 渲染"今日数据暂缺：{原因}" | 韧性优先 |
| 财务板块 | composer 留槽位，`if collector.enabled` 守门，金蝶 API 通了再开 | 用户明确要求预埋 |
| 微信群 | 不做，v2 | 见非目标 |
| 钉钉审批 | 阻塞前置，但代码用 fixture 假数据先开发 | 不串行依赖审批 |

---

## 3. 架构

### 3.1 放置原则（针对原始问题"代码放平台还是 yinhu-rebuild"）

**两边都放，分工严格：**

- **`agent-platform/platform/` 放**：scheduler、Postgres 存储、dashboard UI、push delivery、orchestrator、订阅。这些是**任意客户的日报都会用**的通用件。
- **`yinhu-rebuild/generated/` 放**：collectors、composer、prompts、watchlist 配置。这些是**银湖私有的业务逻辑**，第二个客户接入时各自独立一份。
- **不放进**：`super-xiaochen/`（保持小陈纯 chat 职责）；不升格为独立 Railway service（违反 v2.0 客户=容器隔离）。

### 3.2 拓扑图

```
┌─────────── platform (1 Railway service, 多租户) ─────────┐
│ APScheduler (Postgres jobstore)  ←── '30 7 * * 1-5'      │
│        │                                                  │
│        ▼                                                  │
│ orchestrator.run(tenant, date)                            │
│        │  HMAC sign                                       │
│        ▼                                                  │
│  POST /{client}/daily-report/_internal/generate          │
│        │                                                  │
│        ▼                                                  │
│  ┌──── customer-yinhu container (Railway service) ────┐  │
│  │  super-xiaochen/  (现有)                            │  │
│  │  daily-report/    (新增子路由, 与小陈并列)            │  │
│  │    entry.py     ← FastAPI sub-app, HMAC verify     │  │
│  │    composer.py  ← asyncio.gather(collectors) → LLM │  │
│  │    collectors/                                      │  │
│  │      kingdee_sales       ──→ /data/yinhu.db         │  │
│  │      kingdee_production  ──→ /data/yinhu.db         │  │
│  │      dingtalk_chat       ──→ 钉钉企业 API + LLM 摘要 │  │
│  │      web_search          ──→ Tavily                 │  │
│  │    prompts/yinhu.md                                 │  │
│  │    config/yinhu.yaml (watchlist, 群 id, 收件人)      │  │
│  └─────────────────────────────────────────────────────┘  │
│        │ JSON {markdown, sections, sources}              │
│        ▼                                                  │
│ storage.write(daily_reports row, status=ready)            │
│        │                                                  │
│        ▼                                                  │
│ DingTalkPusher.push(recipient, markdown_card)             │
│                                                           │
│ Dashboard /daily-report/  (REST + Vite/React)             │
└───────────────────────────────────────────────────────────┘
```

### 3.3 与 v2.0 客户隔离架构的兼容

v2.0 文档（docs/v2.0-customer-isolation.md）规定"客户=容器，agents=容器内子路由"。本设计**完全顺应**：

- `daily-report/` 在 yinhu 容器内是 super-xiaochen 的同级子路由
- 容器内 sqlite (`/data/yinhu.db`) 在两个 agent 间共享读取，符合 v2.0 文档"同客户多 agent 共享数据"
- platform 永不直接持有客户的金蝶/钉钉凭证；这些 secret 全部塞在客户容器 env 里
- 第二客户接入：新建 `customer-abc` Railway service + 自己的 `daily-report/collectors/`，platform 完全无改动

---

## 4. 数据模型

### 4.1 platform Postgres 表（migration `004_daily_reports.sql`）

```sql
CREATE TABLE daily_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       TEXT NOT NULL,
  report_date     DATE NOT NULL,
  status          TEXT NOT NULL,        -- running | ready | partial | timeout | failed
  content_md      TEXT,
  content_html    TEXT,                 -- 预渲染，节省 dashboard CPU
  sections_json   JSONB,                -- {sales:{...}, production:{...}, chat:{...}, customer_news:{...}}
  raw_collectors  JSONB,                -- 各 collector 原始返回，调试 + 回放用
  error           TEXT,
  generated_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, report_date)
);
CREATE INDEX idx_daily_reports_tenant_date
  ON daily_reports(tenant_id, report_date DESC);

CREATE TABLE daily_report_subscriptions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         TEXT NOT NULL,
  recipient_label   TEXT NOT NULL,           -- '许总'
  push_channel      TEXT NOT NULL,           -- 'dingtalk' (MVP)
  push_target       TEXT NOT NULL,           -- 钉钉 userid
  push_cron         TEXT NOT NULL,           -- '30 7 * * 1-5'
  timezone          TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  sections_enabled  TEXT[] NOT NULL,         -- ['sales','production','chat','customer_news']
  enabled           BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_subs_tenant ON daily_report_subscriptions(tenant_id) WHERE enabled = true;

-- APScheduler 自带 schema：jobs / job_runs（apscheduler.jobstores.sqlalchemy 自建）
```

**初始化银湖订阅**（手工 SQL，MVP 阶段）：

```sql
INSERT INTO daily_report_subscriptions
  (tenant_id, recipient_label, push_channel, push_target, push_cron, sections_enabled)
VALUES
  ('yinhu', '许总', 'dingtalk', '<钉钉 userid>', '30 7 * * 1-5',
   ARRAY['sales','production','chat','customer_news']);
```

### 4.2 容器侧 collector 输出契约

```python
# yinhu-rebuild/generated/daily_report/collectors/base.py
from dataclasses import dataclass
from typing import Any, Literal

@dataclass
class CollectorResult:
    section_id: Literal['sales', 'production', 'chat', 'customer_news', 'finance']
    status: Literal['ok', 'empty', 'failed']
    data: dict[str, Any]          # 结构化数据，供 LLM 喂入
    summary_text: str | None      # 给 LLM 的预提炼（chat collector 用）
    sources: list[str]            # ['kingdee/sales_orders', 'dingtalk/group/123', 'tavily/url-x']
    error: str | None = None
```

### 4.3 entry endpoint 契约

```
POST /{client}/daily-report/_internal/generate?date=YYYY-MM-DD
Headers:
  X-Platform-Signature: <HMAC, 复用现有平台 → 容器签名机制>
  X-Tenant-Id: yinhu
Body: 空

Response 200:
{
  "tenant_id": "yinhu",
  "report_date": "2026-05-06",
  "markdown": "# 银湖经营快报 · 2026-05-06\n\n...",
  "sections": {
    "sales": {"status": "ok", "data": {...}},
    "production": {"status": "ok", "data": {...}},
    "chat": {"status": "ok", "data": {...}},
    "customer_news": {"status": "partial", "data": {...}, "error": "tavily timeout on 2 of 5 customers"}
  },
  "sources": [...],
  "generated_at": "2026-05-06T07:30:11+08:00",
  "duration_ms": 14823
}
```

---

## 5. 组件清单

### 5.1 platform/platform_app/daily_report/

| 文件 | 职责 |
|---|---|
| `__init__.py` |  |
| `scheduler.py` | APScheduler 单实例 + Postgres jobstore；启动时从 subscriptions 表加载所有 enabled cron |
| `orchestrator.py` | `run(tenant_id, date)`：插 running 行 → HMAC POST 容器 → 更新行 → 调 push |
| `storage.py` | 两张表 CRUD；只暴露 dataclass，不裸露 SQL |
| `pushers/base.py` | `class Pusher(ABC): async def push(subscription, content) -> PushResult` |
| `pushers/dingtalk.py` | 钉钉企业内部应用 OAuth (access_token 缓存 90% TTL) + `robot/oapi/message/send_v2` markdown 卡片 |
| `api.py` | FastAPI router 挂在 platform main 上；endpoints 见 §6 |
| `web/` | 纯静态 HTML + 内联 JS，沿用 platform 现有 `agents.html` / `login.html` 风格；markdown 渲染用 marked.js（CDN 或本地 vendor） |
| `web/daily-report.html` | 列表页 |
| `web/daily-report-detail.html` | 详情页（markdown 渲染 + 重跑按钮 + "问小陈"链接） |

migration: `platform/migrations/004_daily_reports.sql`

### 5.2 yinhu-rebuild/generated/daily_report/

| 文件 | 职责 |
|---|---|
| `__init__.py` |  |
| `entry.py` | `from fastapi import APIRouter; router.post("/_internal/generate")`；HMAC verify by 复用 `agent_auth.py` |
| `composer.py` | `async def compose(date) -> CompositionResult`；并发 collectors → 模板化 prompt → LLM pro |
| `collectors/__init__.py` | 注册表 |
| `collectors/base.py` | `Collector` ABC + `CollectorResult` dataclass |
| `collectors/kingdee_sales.py` | SQL on `sales_orders` + `shipments`：昨日成交、本月累计、上月同期、Top5 客户 |
| `collectors/kingdee_production.py` | SQL on `production_orders` + `production_processes`：在产 / 延期 / 瓶颈工序 |
| `collectors/dingtalk_chat.py` | 调钉钉企业 API `topapi/v2/im/chat/scenegroup/get_history` 拉昨日消息 → MODEL_FLASH 摘要 → 关键事件抽取 |
| `collectors/web_search.py` | 对 watchlist 每个客户用 Tavily 中文搜，1 天范围；每客户最多 3 条 |
| `prompts/yinhu.md` | 银湖私有 system prompt：公司业务背景 + 4 板块结构 + "知己知彼"风格指示 |
| `config/yinhu.yaml` | `dingtalk_groups: [...]`、`customer_watchlist: [...]`、`competitor_watchlist: [...]`、`tone: "简洁、量化优先、不寒暄"` |
| `tests/` | 见 §8 |

挂载方式：在 yinhu 容器 `web_agent.py` 启动时同时挂 `super-xiaochen` 子 app + `daily-report` 子 app（FastAPI `app.mount`）。

---

## 6. API 与 UI

### 6.1 Platform REST

```
GET  /api/daily-report/reports?tenant=yinhu&limit=30
       → 列表（不含 content_md，只 metadata）
GET  /api/daily-report/reports/{id}
       → 完整详情 (content_html + sections_json + sources)
POST /api/daily-report/reports/{tenant}/regenerate?date=YYYY-MM-DD
       → 删旧 row（如 status=failed/timeout）+ 立即触发 orchestrator.run
GET  /api/daily-report/subscriptions?tenant=yinhu
POST /api/daily-report/subscriptions  (MVP 不暴露给前端，留 admin 用)
```

鉴权：复用 platform 现有 SSO；只允许 tenant_id 匹配的 user 看自己客户的 report；admin 跨客户。

### 6.2 Dashboard 路由

```
app.fiveoranges.ai/daily-report/             ← 列表页（按客户分组）
app.fiveoranges.ai/daily-report/{id}         ← 详情页
app.fiveoranges.ai/yinhu/super-xiaochen/     ← 现有，并列
```

详情页"问小陈"按钮：`?prefill=<URL-encoded prompt>` 跳到 super-xiaochen，super-xiaochen 启动时如有 `?prefill=` 自动填入 chat 输入框（小陈侧改一行 inline JS）。

### 6.3 钉钉 markdown 卡片样例

```markdown
# 银湖经营快报 · 2026-05-06 周三

## 销售（昨日）
- 昨日成交 ¥1,238,400（环比 +12%）
- 本月累计 ¥18.4M / 目标 ¥25M（73.6%）
- Top5 客户：邦普 ¥520K · 国轩 ¥210K · ...

## 生产
- 在产订单 23 单；**延期 3 单**（PR-2026-04-180、...）
- 瓶颈工序：精密磨床（计划 vs 完成 68%）

## 群要事
- 邦普采购林总在 #银湖客户群-邦普 提到"6 月 10 日前需追加 300 套，能否承接"，**未回复**
- ...

## 客户动态
- 邦普：[发布 2025 Q1 财报，营收同比 +8%](https://...)
- 国轩：[与某车企签订 3 亿元长协](https://...)

[👉 打开完整版 + 问小陈](https://app.fiveoranges.ai/daily-report/{id})
```

---

## 7. 错误处理 / 韧性矩阵

| 失败模式 | 处理 |
|---|---|
| 单 collector 抛异常 | section 渲染 `> ⚠️ 今日数据暂缺：{error_safe_msg}`；report status=partial |
| 钉钉 API 限流 (`code=2200xxx`) | 容器侧 collector 内置 exponential backoff (1s/4s/10s)；3 次失败认输 |
| LLM 超时（>5s） | composer 退化模板：直接 SQL 数字 + bullets，无叙述化 |
| 容器整体不可达 | platform 重试 1 次（30s 后）；二次失败 status=failed，钉钉发"今日日报生成失败" |
| platform 调度器进程挂 | APScheduler Postgres jobstore，重启自动恢复 |
| 重复触发（同 tenant + date） | DB 唯一约束 `UNIQUE (tenant_id, report_date)`；orchestrator catch 后跳过 |
| 手动重跑 | dashboard 按钮 → DELETE old + POST regenerate；orchestrator.run 同步阻塞执行 |
| 钉钉 push 失败 | report 已存，DingTalkPusher 标记 push_status=failed；dashboard 出红条提示 |
| Tavily 配额耗尽 | web_search collector 返回 status=empty；section 显示"今日外网监测暂停" |

---

## 8. 测试策略

### 8.1 platform/tests/

```
test_daily_report_orchestrator.py
  - fixture: FastAPI TestClient mount 假容器，固定返回示例 JSON
  - 验完整流程：插 row → 调容器 → 更新 row → 调 pusher
  - 失败路径：容器返回 5xx → status=failed
  - 超时：容器响应 >60s → status=timeout

test_daily_report_pusher_dingtalk.py
  - mock httpx → 验 markdown 卡片 body / 鉴权头 / access_token 缓存

test_daily_report_scheduler.py
  - APScheduler 注入假 BlockingScheduler；快进时钟，验 cron 触发 orchestrator.run

test_daily_report_storage.py
  - 用 sqlite tmpdir（CI 不连 Postgres 也跑），DDL 兼容性靠 SQLAlchemy

test_daily_report_api.py
  - GET 列表 / 详情 / regenerate / 鉴权拒绝
```

### 8.2 yinhu-rebuild/generated/tests/

```
test_collectors_kingdee_sales.py
  - fixture sqlite 灌假销售单 + 出货单
  - 验 KPI 计算：本月累计、上月同期、Top5

test_collectors_kingdee_production.py
  - 验在产 / 延期识别（计划完工 < today AND 入库状态 != '完成'）

test_collectors_dingtalk_chat.py
  - fixture JSON record 钉钉响应；mock LLM 返回固定摘要
  - 验"@许总未回复"识别

test_collectors_web_search.py
  - mock Tavily HTTP；验 watchlist 展开 + 每客户 ≤3 条 + 1 天范围

test_composer.py
  - mock LLM；验所有 collector 失败时退化模板

test_entry_e2e.py
  - 全 stub collector，从 HMAC POST 到返回 JSON 端到端
  - HMAC 拒绝
```

### 8.3 联调

钉钉企业内部应用审批通过后做一次 joint dry-run：

- 用 sandbox 钉钉群（IT 测试群）+ 测试 userid 收 push
- 验"今日 5 月 6 日 银湖经营快报"卡片样式 + 跳转 dashboard 链接
- dashboard "问小陈"按钮 prefill 流程

---

## 9. 上线分期

| 阶段 | 内容 | 阻塞前置 |
|---|---|---|
| 0 | platform 表 + scheduler + orchestrator + DingTalkPusher 骨架（用 fake 容器响应） | 无 |
| 1 | yinhu 容器 daily-report 子路由 + kingdee_sales + kingdee_production 两 collector | 阶段 0 |
| 2 | Tavily web_search collector 接通 + 网搜板块 | 阶段 1（Tavily key） |
| 3 | dingtalk_chat collector + DingTalkPusher 真凭证 | **钉钉企业管理员审批通过** |
| 4 | 银湖灰度 1 周；调 prompt + watchlist | 阶段 3 |
| 5 | GA | 阶段 4 |

阶段 0-2 与钉钉审批并行；总周期约 **2 周代码 + 钉钉审批墙时间**。

---

## 10. 需许总 / 银湖 IT 提供

- 钉钉企业管理员账号，开「企业内部应用」并授「群消息查询」+「工作消息发送」权限
- 许总钉钉 userid（用于推送）
- 银湖侧确认要监控的钉钉群列表（chatId）
- 重点客户 watchlist（10–20 家，含公司全称用于精确搜索）

---

## 11. 后续（v1+）

- 微信群源（pending 实现路径调研）
- 财务/应收 collector（pending 金蝶 API 通道）
- 行业 / 政策 / 招标 collector
- 订阅 CRUD UI（许总自助调推送时间、增减板块、增减收件人）
- 邮件 push 通道
- 日报 → "问小陈"上下文打通：详情页每条 KPI 旁加"问小陈"按钮，跳转时把该条 KPI 数据作为 system context 注入小陈
- 多收件人（CFO / COO 各自定制板块）
- 节假日感知（接中国法定节假日 API，节后第一天合并 N 天）
