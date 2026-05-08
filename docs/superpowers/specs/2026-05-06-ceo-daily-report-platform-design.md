# CEO 日报 — Platform 侧设计（v0）

> 起草：2026-05-06 · 状态：待 review · 仓库：`Fiveoranges-AI/YunWei-AI-Platform`
>
> 配对文档：`yinhu-rebuild/generated/docs/specs/2026-05-06-ceo-daily-report-yinhu-design.md`（容器侧 collectors / composer / prompts）。
>
> 范围：日报功能 platform 侧——cron 调度、Postgres 存储、dashboard 入口、push 投递、订阅。**不包含**任何客户专属业务逻辑（数据采集、prompt、watchlist 全在客户容器侧 spec）。

---

## 0. 与容器侧的边界与并行性

### 0.1 唯一耦合点

platform 与客户容器之间**只有一条 HTTP 契约**：

```
POST /{client}/daily-report/_internal/generate?date=YYYY-MM-DD
Headers:
  X-Platform-Signature  ← 复用现有 platform → 容器 HMAC
  X-Tenant-Id: yinhu
Response 200:
  {
    "tenant_id":   "yinhu",
    "report_date": "2026-05-06",
    "markdown":    "...",
    "sections":    { sales|production|chat|customer_news → {status, data, error?} },
    "sources":     [...],
    "generated_at":"2026-05-06T07:30:11+08:00",
    "duration_ms": 14823
  }
```

**冻结此契约**两边即可独立开发。契约改动需要双方 spec 同步更新 + 给彼此提交联调。

### 0.2 并行度评估

| 工作流 | 是否依赖容器侧 | 是否依赖钉钉审批 | 是否依赖银湖 IT 输入 |
|---|---|---|---|
| Postgres migration `008_daily_reports.sql` | ❌ | ❌ | ❌ |
| `storage.py` CRUD | ❌ | ❌ | ❌ |
| `orchestrator.py`（用 fake 容器响应跑通） | ❌ | ❌ | ❌ |
| `scheduler.py`（APScheduler + jobstore） | ❌ | ❌ | ❌ |
| `pushers/base.py` 抽象 | ❌ | ❌ | ❌ |
| `pushers/dingtalk.py`（实现） | ❌ | ❌ | 拿到 Client ID/Secret 才能跑真接口；可 mock 单测 |
| `api.py` REST endpoints | ❌ | ❌ | ❌ |
| `web/` 静态页 + markdown 渲染 | ❌ | ❌ | ❌ |
| 联调真容器 | ✅（容器侧到阶段 1） | ❌ | ❌ |
| 真钉钉推送验证 | ❌ | ✅ | ✅（许总 userid） |

**结论：platform 侧 95% 工作可独立完成**，唯一需要容器侧的只是「联调」环节（容器侧到阶段 1 完成两 collector 后），且联调失败也不阻塞 platform 单独 ship。

测试夹具：写一个 `platform/tests/fixtures/sample_collector_response.json`，与容器侧 spec §4.3 完全同构；platform 单测全部基于此 fixture，**不联实容器**。

---

## 1. 问题与目标（platform 视角）

许总每天需要早间快报，分散在金蝶 / 钉钉群 / 互联网。MVP 目标：每个工作日 07:30 前在钉钉收到结构化卡片，可点开 dashboard 看完整版 + 追问。

**platform 在整件事里的角色**：通用基础设施——任意客户的 CEO 日报都用得上的部分（调度、存储、推送、UI、订阅）。客户专属业务逻辑（采什么数据、prompt 怎么写、watchlist 是谁）不在 platform。

**非目标**：collectors / prompts / watchlist 配置（→ 容器侧 spec）。

---

## 2. 关键决策

| 决策 | 取值 |
|---|---|
| 数据持久化 | Postgres（已是 platform 默认） |
| 报告保留 | 90 天滚动 + 后续可调 retention |
| 调度器 | APScheduler in-process，Postgres jobstore（重启幂等） |
| 推送渠道 MVP | 钉钉企业内部应用单聊 markdown 卡片 |
| 推送渠道扩展 | `Pusher` ABC 抽象，邮件/企业微信将来加新 subclass |
| 受众管理 | `daily_report_subscriptions` 表；MVP 用 SQL insert，不暴露 UI |
| 触发模式 | cron 自动 + dashboard 手动重跑按钮 |
| 失败模式 | 容器返回 5xx → 1 次重试（30s 后）→ status=failed + 钉钉告警 |
| HMAC 鉴权 | 沿用 `platform_app/hmac_sign.py` 已有方案，不引新机制 |

---

## 3. 架构

### 3.1 在 platform 内部的位置

```
platform/platform_app/
├── main.py                  ← include_router(daily_report.api.router)
├── api.py                   ← 现有
├── proxy.py                 ← 现有反代逻辑（不动）
├── auth.py / hmac_sign.py   ← 复用
├── ...
└── daily_report/            ← 本 spec 新增
    ├── __init__.py
    ├── api.py
    ├── orchestrator.py
    ├── scheduler.py
    ├── storage.py
    ├── pushers/
    │   ├── base.py
    │   └── dingtalk.py
    └── web/
        ├── daily-report.html        ← 列表
        └── daily-report-detail.html ← 详情
```

### 3.2 触发流（一次完整 tick）

```
07:30:00  scheduler 触发（APScheduler 从 subscriptions 表加载所有 enabled cron）
07:30:01  orchestrator.run(tenant='yinhu', date='2026-05-06')
            ├─ storage.create_running(tenant, date) → status='running'
            ├─ http POST {tenant}/daily-report/_internal/generate (HMAC)
            │     timeout=60s
            │     ┌─ 容器侧 (本 spec 不展开，见 yinhu-design.md)
            │     └─ return JSON
            ├─ storage.write_result(report_id, status='ready', content_md, sections, raw)
            └─ pushers.dingtalk.push(subscription, markdown)
                  ├─ access_token 缓存（90% TTL）
                  └─ POST 钉钉 oapi/message/send_to_conversation
07:30:18  完成；dashboard 列表立即可见
```

### 3.3 故障路径

| 故障 | 处理 |
|---|---|
| 容器 HTTP 5xx / timeout | 重试 1 次（+30s）；二次失败 status='failed' + 推送告警 |
| 容器 200 但 sections 全 status='failed' | status='partial'；仍正常推送（CEO 看到"今日数据全部暂缺，请联系运维"） |
| HMAC 不通过 | platform 端拒签前已经测过，相当于代码 bug，直接 status='failed' + 报警 |
| Pusher 失败 | 报告已存盘，pusher 标记 push_status='failed'；dashboard 显示红条；不删报告 |
| Scheduler 进程挂 | APScheduler Postgres jobstore 自恢复 |
| 重复触发同 (tenant, date) | DB `UNIQUE (tenant_id, report_date)` 兜底 |

---

## 4. 数据模型

### 4.1 Postgres 迁移 `platform/migrations/008_daily_reports.sql`

```sql
CREATE TABLE daily_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       TEXT NOT NULL,
  report_date     DATE NOT NULL,
  status          TEXT NOT NULL,        -- running | ready | partial | timeout | failed
  content_md      TEXT,
  content_html    TEXT,                 -- 写时预渲染（marked.js 服务端等价或 markdown-it Python 包）
  sections_json   JSONB,                -- 见容器侧 spec §4 collector 输出契约
  raw_collectors  JSONB,                -- 各 collector 原始返回，调试 + 回放
  push_status     TEXT,                 -- pending | sent | failed
  push_error      TEXT,
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
  recipient_label   TEXT NOT NULL,
  push_channel      TEXT NOT NULL,            -- 'dingtalk' (MVP)
  push_target       TEXT NOT NULL,            -- 钉钉 userid
  push_cron         TEXT NOT NULL,            -- '30 7 * * 1-5'
  timezone          TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  sections_enabled  TEXT[] NOT NULL,
  enabled           BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_subs_tenant ON daily_report_subscriptions(tenant_id) WHERE enabled = true;
```

银湖订阅初始化（部署阶段手工 SQL）：

```sql
INSERT INTO daily_report_subscriptions
  (tenant_id, recipient_label, push_channel, push_target, push_cron, sections_enabled)
VALUES
  ('yinhu', '许总', 'dingtalk', :xu_zong_userid, '30 7 * * 1-5',
   ARRAY['sales','production','chat','customer_news']);
```

### 4.2 容器响应契约（platform 视角，按 caller 写）

见 §0.1。完整字段语义（status / data 内部结构等）由容器侧 spec §4 owns。platform 把 sections_json 作为不透明 JSONB 存储，dashboard 详情页直接渲染 `content_html` 即可，**不解析 sections 内部结构**——这层解耦让容器侧能自由演化 collector data shape 不打扰 platform。

### 4.3 钉钉推送 access_token 缓存

```
in-memory dict[tenant_id, (token, expires_at)]
expires_at = now + ttl * 0.9    # 90% TTL，避免边界过期
首次 / 过期 → POST https://api.dingtalk.com/v1.0/oauth2/accessToken
```

多实例场景（platform 横向扩展时）：将 token 缓存挪到 Redis 共享。MVP 单实例不需要。

---

## 5. 组件清单

| 文件 | 行数估 | 职责 |
|---|---|---|
| `daily_report/__init__.py` | 5 | 模块入口 |
| `daily_report/scheduler.py` | ~100 | APScheduler 单例；启动加载 subscriptions；signal 优雅关闭 |
| `daily_report/orchestrator.py` | ~150 | `async run(tenant_id, date)`；HMAC POST 容器；状态机；触发 push |
| `daily_report/storage.py` | ~200 | dataclass + asyncpg；CRUD reports / subscriptions |
| `daily_report/pushers/base.py` | ~40 | `Pusher` ABC：`async def push(sub, markdown, link) -> PushResult` |
| `daily_report/pushers/dingtalk.py` | ~180 | 钉钉企业内部应用 OAuth + access_token 缓存 + send_to_conversation |
| `daily_report/api.py` | ~250 | FastAPI router；endpoints 见 §6 |
| `daily_report/web/daily-report.html` | ~150 | 列表 |
| `daily_report/web/daily-report-detail.html` | ~200 | 详情：marked.js 渲染 + 重跑按钮 + 问小陈链接 |
| `migrations/008_daily_reports.sql` | ~40 | 见 §4.1 |
| 修改 `platform_app/main.py` | +5 | mount router + 启动 scheduler |

---

## 6. API 与 UI

### 6.1 REST（挂在 platform 现有 SSO 后）

```
GET  /api/daily-report/reports?tenant=yinhu&limit=30
       → 列表（不含 content_md/_html，仅 metadata）
GET  /api/daily-report/reports/{id}
       → 详情（content_html + sections_json + sources）
POST /api/daily-report/reports/{tenant}/regenerate
       Body: {"date": "2026-05-06"}
       → 删旧 row（如 status ∈ {failed,timeout,partial}）+ orchestrator.run
GET  /api/daily-report/subscriptions?tenant=yinhu
       → 仅 admin 或 tenant owner
POST /api/daily-report/subscriptions  (admin only, MVP 不暴露给前端)
```

鉴权：复用 platform 现有 SSO；普通用户只能看自己 tenant 的 report；admin 跨客户。

### 6.2 Dashboard 路由

```
app.fiveoranges.ai/daily-report/                  ← 列表（按客户分组）
app.fiveoranges.ai/daily-report/{id}              ← 详情
app.fiveoranges.ai/yinhu/super-xiaochen/?prefill= ← "问小陈"跳转目标（带 prefill query）
```

详情页"问小陈"按钮：把当前日报某 section 的关键数据 URL-encode 后作为 `?prefill=<text>` 拼到小陈 URL，小陈侧加一行 inline JS 检测此 query 自动填入 chat 输入框（**这一行小陈侧改动属于本 spec scope，需同步在容器侧 spec 标记**）。

### 6.3 钉钉 markdown 卡片格式

```
报告通过 oapi/message/send_to_conversation_v2 发送，msgtype=action_card
title: "银湖经营快报 · 2026-05-06 周三"
markdown: 完整 markdown body（钉钉支持子集，无表格但支持列表/链接/粗体）
single_title: "打开完整版 + 问小陈"
single_url: https://app.fiveoranges.ai/daily-report/{id}
```

钉钉 markdown 受限点（platform 实现需注意）：
- 不支持表格 → 容器侧已知约束，markdown 用列表表示
- 链接末尾用 `pc_slice` 参数让 PC/手机端表现一致
- 长度上限 ~5000 字符 → 超出截断 + "完整版见 dashboard"

---

## 7. 错误处理 / 韧性

见 §3.3。补充几条 platform 特有：

| 场景 | 处理 |
|---|---|
| Postgres 不可达 | orchestrator 直接抛；scheduler 日志告警；下次 cron 自动重试 |
| APScheduler jobstore 数据冲突 | jobstore 设置 `replace_existing=True`；重启即恢复 |
| dashboard 详情页大 JSONB 渲染慢 | content_html 已预渲染；sections_json 仅在「调试视图」按需展开 |
| 跨 tenant 越权访问 | api 层强制 `tenant_id == current_user.tenant_id OR is_admin` |

---

## 8. 测试

### 8.1 单元 & 集成（platform/tests/）

```
test_daily_report_storage.py
  - DDL 跑通 + CRUD 往返；用 sqlite tmpdir 兼容 CI

test_daily_report_orchestrator.py
  - fixture httpx mock 容器返回 sample_collector_response.json（见 §0.2）
  - 路径：success / 容器 5xx 重试 / 二次失败 / timeout / partial
  - 验状态机正确转换 + push 是否被调用

test_daily_report_pusher_dingtalk.py
  - mock httpx；验 access_token 缓存命中 / 过期重取
  - 验 markdown 卡片 body / 单聊 vs 群聊 / 截断逻辑

test_daily_report_scheduler.py
  - 注入假时钟；验 cron 在指定时刻触发 orchestrator.run
  - 验启动时从 subscriptions 表加载 enabled cron 任务

test_daily_report_api.py
  - GET 列表 / 详情 / regenerate；非 owner 拒绝；admin 跨 tenant
```

### 8.2 联调（依赖容器侧）

仅一项硬集成：容器侧 daily-report 子路由真起后，跑一次端到端。

```
1. 部署容器侧到 Railway dev 环境
2. platform 配 fake subscription（push_target=测试钉钉账号）
3. 手动 POST regenerate → 看 dashboard 出 ready row + 钉钉收到测试卡片
```

---

## 9. 上线分期（platform 侧）

| 阶段 | 内容 | 阻塞前置 |
|---|---|---|
| 0 | migration + storage + orchestrator + scheduler 骨架（基于 fixture，**不依赖容器**） | 无 |
| 1 | api + dashboard 静态页（fixture 数据驱动） | 阶段 0 |
| 2 | DingTalkPusher（mock httpx 单测；真凭证后再补真接口冒烟） | 阶段 0 |
| 3 | 联调真容器（容器侧到 yinhu-spec 阶段 1） | 容器侧阶段 1 |
| 4 | 真钉钉冒烟 | 钉钉审批通过 + 银湖 IT 给凭证/userid |
| 5 | 银湖灰度 1 周；GA | 全部上 |

阶段 0–2 完全独立可并行（与容器侧、钉钉审批均无关）。阶段 3 唯一硬同步点。

---

## 10. 部署输入（运维）

| 来源 | 内容 | 存放 |
|---|---|---|
| 银湖 IT | 钉钉 Client ID / Client Secret / AgentId | platform Railway env：`DINGTALK_CLIENT_ID` `DINGTALK_CLIENT_SECRET` `DINGTALK_AGENT_ID` |
| 银湖 IT | 许总 userid | 部署时手工 SQL 写入 `daily_report_subscriptions.push_target` |

> ⚠️ secret 不入 git 不入 chat。Client Secret 走 Railway env / 1Password 由你直接录入。

---

## 11. 后续（v1+）

- 订阅 CRUD UI（许总自助调推送时间、增减板块、增减收件人）
- 邮件 push 通道（`pushers/email.py` 实现 `Pusher` ABC）
- 多收件人支持（一个 tenant 多个 subscription）
- 节假日感知（接中国法定节假日 API；节后第一天合并 N 天）
- 多 platform 实例横向扩展时把 access_token 缓存挪到 Redis
- 详情页"问小陈"打通深度上下文注入
