# Platform v1.2 + Yinhu Super-Xiaochen 上线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把银湖的超级小陈作为 fiveoranges.ai 平台第一个 prod agent 上线,通过 `app.fiveoranges.ai/yinhu/super-xiaochen` 提供给许总使用。

**Architecture:** Platform-app(FastAPI 反向代理 + 登录 + ACL + HMAC 签名 + sqlite)运行在 Mac mini 上,通过 Cloudflare Tunnel 暴露 `app.fiveoranges.ai` + `api.fiveoranges.ai`。Agent 容器 `agent-yinhu-super-xiaochen` 由 platform 反代,接受 platform 注入的签名 header 完成鉴权。所有协议细节遵循 `~/agent-platform/docs/SSO.md` v1.2。

**Tech Stack:**
- Python 3.11+
- FastAPI + uvicorn(平台 + 改造后的 agent)
- httpx(反向代理,stream 模式)
- sqlite3(stdlib,平台主 DB + proxy log 独立 DB)
- bcrypt(密码哈希)
- cachetools.TTLCache(§7.3 缓存)
- pytest + pytest-asyncio(测试)
- Docker + docker compose(容器编排)
- colima(Mac 上的 Docker runtime,**不**用 Docker Desktop)
- cloudflared(CF Tunnel 客户端)
- anthropic SDK(已有,改 AsyncAnthropic)

**Reference:**
- 协议规范:`/Users/eason/agent-platform/docs/SSO.md` v1.2
- 现有 yinhu agent 代码:`/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/web_agent.py`
- 现有 yinhu Dockerfile:`/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/Dockerfile`

---

## 文件结构(实施前先确认)

```
~/agent-platform/
├── PLAN.md                              ← 本文件
├── docs/
│   └── SSO.md                           ← 已存在 v1.2
├── platform/                            ← Task 1 创建
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── platform_app/                    ← Python 包
│   │   ├── __init__.py
│   │   ├── main.py                      ← FastAPI 入口
│   │   ├── settings.py                  ← env 配置
│   │   ├── db.py                        ← sqlite 连接 + 迁移 + 缓存
│   │   ├── auth.py                      ← session / login / bcrypt
│   │   ├── csrf.py                      ← CSRF double-submit
│   │   ├── hmac_sign.py                 ← §1.2 签名
│   │   ├── proxy.py                     ← 反向代理核心
│   │   ├── firewall.py                  ← §7.2 跨 agent 防火墙
│   │   ├── response_headers.py          ← §3.1 净化 + §7.1 CSP
│   │   ├── health.py                    ← /healthz 后台探测
│   │   ├── admin.py                     ← admin CLI
│   │   └── api.py                       ← /api/* 路由
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_hmac_sign.py
│   │   ├── test_auth.py
│   │   ├── test_firewall.py
│   │   ├── test_proxy.py
│   │   └── test_e2e.py
│   ├── migrations/
│   │   └── 001_init.sql
│   └── static/
│       ├── login.html
│       └── agents.html
├── ops/                                 ← Task 12 创建
│   ├── docker-compose.yml
│   ├── cloudflared/
│   │   └── config.yml
│   ├── backup.sh
│   └── launchd/
│       └── com.fiveoranges.colima.plist
├── data/                                ← runtime 持久化(.gitignore'd)
│   ├── platform.db
│   ├── proxy_log.db
│   └── backups/
└── .env.example                         ← Task 1 创建
```

Yinhu agent 代码原地修改:`/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/`(Task 13-15)。

---

## Pre-flight(执行人手动做,无法代办)

- [ ] **P1: Cloudflare 账号 + 域名就绪**
  - 域名 `fiveoranges.ai` 已 transfer 到 Cloudflare(NS 指向 CF)
  - Vercel 上的 landing page 已绑 `fiveoranges.ai`(保留现状)
  - 验证:`dig +short fiveoranges.ai` 返回 Vercel IP

- [ ] **P2: Cloudflare Tunnel 创建**
  - 登录 https://one.dash.cloudflare.com/ → Networks → Tunnels → Create a tunnel
  - 选 Cloudflared,起名 `mac-mini-fiveoranges`
  - 复制 token(一长串以 `eyJ...` 开头的字符串),**记下来**(Task 17 用)
  - 暂不添加 public hostnames(Task 17 用配置文件方式做)

- [ ] **P3: Mac mini 装 colima + docker CLI**
  ```bash
  brew install colima docker docker-compose
  colima start --cpu 4 --memory 8 --disk 60 --vm-type vz
  docker version    # 确认 Server 段有内容
  ```

- [ ] **P4: Anthropic API key(DeepSeek 兼容端点)就绪**
  - 现有 `/Users/eason/yunwei-workspaces/yinhu-rebuild/.env` 已经有 `ANTHROPIC_API_KEY`,沿用

- [ ] **P5: 银湖现有数据卷位置已知**
  - 现有路径:`/Users/eason/yunwei-workspaces/yinhu-rebuild/.yunwei-cache/canary/super_xiaochen.db`
  - Task 16 docker-compose 会 mount 这个目录到容器 `/data`

---

## Task 1: 仓库脚手架 + 依赖 [完成 2026-04-30]

**Files:**
- Create: `~/agent-platform/platform/pyproject.toml`
- Create: `~/agent-platform/platform/Dockerfile`
- Create: `~/agent-platform/platform/platform_app/__init__.py`
- Create: `~/agent-platform/platform/platform_app/settings.py`
- Create: `~/agent-platform/.env.example`
- Create: `~/agent-platform/.gitignore`

- [ ] **Step 1: 创建目录骨架**
```bash
cd ~/agent-platform
mkdir -p platform/platform_app platform/tests platform/migrations platform/static
mkdir -p ops/launchd data/backups
```

- [ ] **Step 2: 写 `~/agent-platform/.gitignore`**
```
data/
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.db
*.db-shm
*.db-wal
```

- [ ] **Step 3: 写 `~/agent-platform/.env.example`**
```
# Cloudflare Tunnel
TUNNEL_TOKEN=eyJ...replace-me

# Platform
PLATFORM_PORT=8080
PLATFORM_DB_PATH=/data/platform.db
PROXY_LOG_DB_PATH=/data/proxy_log.db
PLATFORM_HOST_APP=app.fiveoranges.ai
PLATFORM_HOST_API=api.fiveoranges.ai
COOKIE_SECRET=replace-with-32-bytes-base64
ADMIN_BOOTSTRAP_USER=xuzong
ADMIN_BOOTSTRAP_PASSWORD=replace-after-first-login

# Yinhu agent (passed through to its container)
YINHU_HMAC_SECRET_CURRENT=replace-with-32-bytes-base64
YINHU_HMAC_KEY_ID_CURRENT=k1
ANTHROPIC_API_KEY=replace-from-existing-yinhu-env
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
MODEL_PRO=deepseek-v4-pro
MODEL_FLASH=deepseek-v4-flash
```

- [ ] **Step 4: 写 `~/agent-platform/platform/pyproject.toml`**
```toml
[project]
name = "platform-app"
version = "1.2.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "httpx>=0.27",
    "bcrypt>=4.1",
    "cachetools>=5.3",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]

[project.scripts]
platform-admin = "platform_app.admin:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 5: 创建 venv + 装依赖**
```bash
cd ~/agent-platform/platform
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 6: 写 `~/agent-platform/platform/platform_app/__init__.py`**
```python
"""Platform-app: fiveoranges.ai 多租户 agent 反向代理 + 鉴权层。"""
__version__ = "1.2.0"
```

- [ ] **Step 7: 写 `~/agent-platform/platform/platform_app/settings.py`**
```python
import os
from pathlib import Path

class Settings:
    db_path = Path(os.environ.get("PLATFORM_DB_PATH", "/data/platform.db"))
    proxy_log_db_path = Path(os.environ.get("PROXY_LOG_DB_PATH", "/data/proxy_log.db"))
    host_app = os.environ.get("PLATFORM_HOST_APP", "app.fiveoranges.ai")
    host_api = os.environ.get("PLATFORM_HOST_API", "api.fiveoranges.ai")
    cookie_secret = os.environ["COOKIE_SECRET"]
    session_lifetime_seconds = 8 * 3600
    csrf_lifetime_seconds = 8 * 3600
    rate_limit_login_per_min_per_ip = 5
    rate_limit_login_per_hour_per_user = 10
    nonce_replay_window_seconds = 10
    clock_skew_seconds = 5
    health_probe_interval_seconds = 30

settings = Settings()
```

- [ ] **Step 8: 验证 import 通**
```bash
python -c "from platform_app.settings import settings; print(settings.host_app)"
# 期望:期望抛 KeyError("COOKIE_SECRET") -- 因为我们没设
COOKIE_SECRET=test python -c "from platform_app.settings import settings; print(settings.host_app)"
# 期望:app.fiveoranges.ai
```

- [ ] **Step 9: Commit**
```bash
cd ~/agent-platform
git init
git add .
git commit -m "Task 1: scaffold platform-app skeleton"
```

---

## Task 2: 数据库 schema + 连接层 [完成 2026-04-30]

**Files:**
- Create: `~/agent-platform/platform/migrations/001_init.sql`
- Create: `~/agent-platform/platform/platform_app/db.py`
- Create: `~/agent-platform/platform/tests/conftest.py`
- Create: `~/agent-platform/platform/tests/test_db.py`

- [ ] **Step 1: 写 `~/agent-platform/platform/migrations/001_init.sql`**(逐字对应 SSO.md §5)
```sql
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  email         TEXT,
  created_at    INTEGER NOT NULL,
  last_login    INTEGER
);

CREATE TABLE IF NOT EXISTS tenants (
  client_id                TEXT NOT NULL,
  agent_id                 TEXT NOT NULL,
  display_name             TEXT NOT NULL,
  container_url            TEXT NOT NULL,
  hmac_secret_current      TEXT NOT NULL,
  hmac_key_id_current      TEXT NOT NULL,
  hmac_secret_prev         TEXT NOT NULL DEFAULT '',
  hmac_key_id_prev         TEXT NOT NULL DEFAULT '',
  hmac_rotated_at          INTEGER,
  agent_version            TEXT NOT NULL DEFAULT 'unknown',
  health                   TEXT NOT NULL DEFAULT 'unknown',
  health_checked_at        INTEGER,
  allowed_response_headers TEXT NOT NULL DEFAULT '[]',
  icon_url                 TEXT,
  description              TEXT,
  visibility               TEXT NOT NULL DEFAULT 'private',
  active                   INTEGER NOT NULL DEFAULT 1,
  tenant_uid               TEXT NOT NULL UNIQUE,
  created_at               INTEGER NOT NULL,
  PRIMARY KEY (client_id, agent_id)
);

CREATE TABLE IF NOT EXISTS user_tenant (
  user_id    TEXT NOT NULL REFERENCES users(id),
  client_id  TEXT NOT NULL,
  agent_id   TEXT NOT NULL,
  role       TEXT NOT NULL DEFAULT 'user',
  granted_at INTEGER NOT NULL,
  granted_by TEXT,
  PRIMARY KEY (user_id, client_id, agent_id),
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE TABLE IF NOT EXISTS platform_sessions (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id),
  csrf_token TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  ip         TEXT,
  user_agent TEXT
);

CREATE TABLE IF NOT EXISTS api_keys (
  id                TEXT PRIMARY KEY,
  user_id           TEXT NOT NULL REFERENCES users(id),
  client_id         TEXT NOT NULL,
  agent_id          TEXT NOT NULL,
  name              TEXT NOT NULL,
  prefix            TEXT NOT NULL,
  hash              TEXT NOT NULL,
  scope             TEXT NOT NULL DEFAULT 'rw',
  source_session_id TEXT REFERENCES platform_sessions(id),
  expires_at        INTEGER,
  created_at        INTEGER NOT NULL,
  last_used         INTEGER,
  revoked_at        INTEGER,
  FOREIGN KEY (client_id, agent_id) REFERENCES tenants(client_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON platform_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_keys_user ON api_keys(user_id);
```

- [ ] **Step 2: 写 `~/agent-platform/platform/migrations/002_proxy_log.sql`**(独立文件,不同 DB)
```sql
CREATE TABLE IF NOT EXISTS proxy_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER NOT NULL,
  user_id     TEXT,
  client_id   TEXT,
  agent_id    TEXT,
  method      TEXT,
  path        TEXT,
  status      INTEGER,
  duration_ms INTEGER,
  ip          TEXT
);
CREATE INDEX IF NOT EXISTS idx_proxy_log_ts ON proxy_log(ts);
```

- [ ] **Step 3: 写 `~/agent-platform/platform/platform_app/db.py`**
```python
"""sqlite 连接 + 迁移 + 缓存层(§7.3)."""
from __future__ import annotations
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from cachetools import TTLCache
from .settings import settings

_MAIN_DB: sqlite3.Connection | None = None
_PROXY_DB: sqlite3.Connection | None = None

# §7.3 缓存,容量 10000 条
_tenant_cache: TTLCache = TTLCache(maxsize=10000, ttl=60)
_session_cache: TTLCache = TTLCache(maxsize=10000, ttl=30)
_acl_cache: TTLCache = TTLCache(maxsize=10000, ttl=60)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init() -> None:
    global _MAIN_DB, _PROXY_DB
    _MAIN_DB = _connect(settings.db_path)
    _PROXY_DB = _connect(settings.proxy_log_db_path)
    _migrate()


def _migrate() -> None:
    main_sql = (Path(__file__).parent.parent / "migrations" / "001_init.sql").read_text()
    proxy_sql = (Path(__file__).parent.parent / "migrations" / "002_proxy_log.sql").read_text()
    assert _MAIN_DB and _PROXY_DB
    _MAIN_DB.executescript(main_sql)
    _PROXY_DB.executescript(proxy_sql)


def main() -> sqlite3.Connection:
    assert _MAIN_DB, "db.init() not called"
    return _MAIN_DB


def proxy_log_db() -> sqlite3.Connection:
    assert _PROXY_DB, "db.init() not called"
    return _PROXY_DB


def get_tenant(client_id: str, agent_id: str) -> sqlite3.Row | None:
    key = (client_id, agent_id)
    if key in _tenant_cache:
        return _tenant_cache[key]
    row = main().execute(
        "SELECT * FROM tenants WHERE client_id=? AND agent_id=? AND active=1",
        (client_id, agent_id),
    ).fetchone()
    if row:
        _tenant_cache[key] = row
    return row


def invalidate_tenant(client_id: str, agent_id: str) -> None:
    _tenant_cache.pop((client_id, agent_id), None)


def get_session(session_id: str) -> sqlite3.Row | None:
    if session_id in _session_cache:
        cached = _session_cache[session_id]
        if cached["expires_at"] > int(time.time()):
            return cached
        _session_cache.pop(session_id, None)
        return None
    row = main().execute(
        "SELECT * FROM platform_sessions WHERE id=? AND expires_at>?",
        (session_id, int(time.time())),
    ).fetchone()
    if row:
        _session_cache[session_id] = row
    return row


def invalidate_session(session_id: str) -> None:
    _session_cache.pop(session_id, None)


def has_acl(user_id: str, client_id: str, agent_id: str) -> bool:
    key = (user_id, client_id, agent_id)
    if key in _acl_cache:
        return _acl_cache[key]
    row = main().execute(
        "SELECT 1 FROM user_tenant WHERE user_id=? AND client_id=? AND agent_id=?",
        (user_id, client_id, agent_id),
    ).fetchone()
    result = row is not None
    _acl_cache[key] = result
    return result


def invalidate_acl(user_id: str, client_id: str, agent_id: str) -> None:
    _acl_cache.pop((user_id, client_id, agent_id), None)


def write_proxy_log(
    *, user_id: str | None, client_id: str | None, agent_id: str | None,
    method: str, path: str, status: int, duration_ms: int, ip: str | None,
) -> None:
    proxy_log_db().execute(
        "INSERT INTO proxy_log (ts, user_id, client_id, agent_id, method, path, status, duration_ms, ip) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (int(time.time()), user_id, client_id, agent_id, method, path, status, duration_ms, ip),
    )
```

- [ ] **Step 4: 写 `~/agent-platform/platform/tests/conftest.py`**

> 注:`settings.py` 在模块导入时就读 `os.environ["COOKIE_SECRET"]`,所以 env
> 必须在 conftest 模块加载阶段(任何 `from platform_app import ...` 之前)就设上。
> 用 fixture 的 `monkeypatch.setenv` 已经太晚——pytest collection 阶段
> `import platform_app` 就会触发 KeyError。

```python
import os
import tempfile
from pathlib import Path
import pytest

# Settings reads env at module import; set vars before any test module
# imports platform_app.* so the singleton sees test-friendly values.
_TMP = tempfile.mkdtemp()
os.environ["PLATFORM_DB_PATH"] = str(Path(_TMP) / "platform.db")
os.environ["PROXY_LOG_DB_PATH"] = str(Path(_TMP) / "proxy_log.db")
os.environ.setdefault("COOKIE_SECRET", "test-cookie-secret-32-bytes-padding=")


@pytest.fixture
def tmp_data_dir() -> str:
    return _TMP
```

- [ ] **Step 5: 写 `~/agent-platform/platform/tests/test_db.py`**
```python
from platform_app import db

def test_init_creates_tables():
    db.init()
    rows = db.main().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r["name"] for r in rows}
    assert {"users", "tenants", "user_tenant", "platform_sessions", "api_keys"} <= names

def test_proxy_log_in_separate_file():
    db.init()
    rows = db.proxy_log_db().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert "proxy_log" in {r["name"] for r in rows}
    # 主 DB 里**没有** proxy_log 表
    assert "proxy_log" not in {r["name"] for r in db.main().execute("SELECT name FROM sqlite_master").fetchall()}
```

- [ ] **Step 6: 跑测试,确认通过**
```bash
cd ~/agent-platform/platform
pytest tests/test_db.py -v
# 期望:2 passed
```

- [ ] **Step 7: Commit**
```bash
git add platform/
git commit -m "Task 2: db schema + cache layer (SSO.md §5, §7.3)"
```

---

## Task 3: HMAC 签名模块 + nonce store(§1.2)

**Files:**
- Create: `~/agent-platform/platform/platform_app/hmac_sign.py`
- Create: `~/agent-platform/platform/tests/test_hmac_sign.py`

**Design notes:**
- 实现两边都用:platform 签发(用 `current_secret/current_key_id`),agent 验签(支持 `current` + `prev` 双 key)
- 签名 payload 严格按 SSO.md §1.2 格式,字段间 `\n` 分隔,**字段为空也保留 `\n` 占位**
- nonce store 是进程内 `(key_id, nonce) → expiry` 字典,自动 GC

- [ ] **Step 1: 写 `~/agent-platform/platform/tests/test_hmac_sign.py`(先 fail)**
```python
import time
import pytest
from platform_app.hmac_sign import sign, verify, NonceStore

SECRET = "QXJiaXRyYXJ5MzJieXRlc2VjcmV0Zm9ydGVzdHM="  # any 32+ byte b64
KEY_ID = "k1"


def test_sign_then_verify_roundtrip():
    headers = sign(
        secret=SECRET, key_id=KEY_ID,
        method="POST", host="app.fiveoranges.ai",
        path="/yinhu/super-xiaochen/chat?foo=bar",
        client="yinhu", agent="super-xiaochen",
        user_id="u_xuzong", user_role="user",
        body=b'{"q":"hi"}',
    )
    assert headers["X-Auth-Key-Id"] == KEY_ID
    nonce_store = NonceStore()
    verify(
        headers=headers, secrets={KEY_ID: SECRET},
        method="POST", host="app.fiveoranges.ai",
        path="/yinhu/super-xiaochen/chat?foo=bar",
        client="yinhu", agent="super-xiaochen",
        body=b'{"q":"hi"}', nonce_store=nonce_store,
    )


def test_method_tampering_fails():
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="signature"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},
            method="POST",  # 篡改
            host="h", path="/p", client="c", agent="a",
            body=b"", nonce_store=nonce_store,
        )


def test_role_tampering_fails():
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    headers["X-User-Role"] = "admin"  # 篡改
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="signature"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},
            method="GET", host="h", path="/p",
            client="c", agent="a", body=b"", nonce_store=nonce_store,
        )


def test_body_tampering_fails():
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="POST",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b'{"q":"hi"}',
    )
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="signature"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},
            method="POST", host="h", path="/p",
            client="c", agent="a", body=b'{"q":"bye"}', nonce_store=nonce_store,
        )


def test_replay_rejected():
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    nonce_store = NonceStore()
    verify(
        headers=headers, secrets={KEY_ID: SECRET},
        method="GET", host="h", path="/p",
        client="c", agent="a", body=b"", nonce_store=nonce_store,
    )
    with pytest.raises(ValueError, match="replay"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},
            method="GET", host="h", path="/p",
            client="c", agent="a", body=b"", nonce_store=nonce_store,
        )


def test_stale_timestamp_rejected():
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    headers["X-Auth-Timestamp"] = str(int(time.time()) - 60)
    # 重新计算签名以用户新 ts
    # 实际场景:攻击者拿到旧签名 → ts 不匹配,签名也不再合法。这里直接测「ts 老但签名匹配」是不可能构造的,所以测「ts 老 raw header」
    # 切换:测 ts 偏离过远直接抛 stale,不进 hmac
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    # monkey-patch: 把 ts 改老,签名跟着改不出来
    nonce_store = NonceStore()
    # 等价构造一个老的合法签名:
    old_ts = int(time.time()) - 60
    from platform_app.hmac_sign import _compute_sig
    headers["X-Auth-Timestamp"] = str(old_ts)
    headers["X-Auth-Signature"] = _compute_sig(
        secret=SECRET, ts=old_ts, nonce=headers["X-Auth-Nonce"],
        method="GET", host="h", path="/p",
        client="c", agent="a", user_id="u", user_role="user", body=b"",
    )
    with pytest.raises(ValueError, match="stale"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},
            method="GET", host="h", path="/p",
            client="c", agent="a", body=b"", nonce_store=nonce_store,
        )


def test_unknown_key_id_rejected():
    headers = sign(
        secret=SECRET, key_id="other-kid", method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="key"):
        verify(
            headers=headers, secrets={KEY_ID: SECRET},  # 没 other-kid
            method="GET", host="h", path="/p",
            client="c", agent="a", body=b"", nonce_store=nonce_store,
        )


def test_nonce_store_gc():
    store = NonceStore()
    store.check_and_add("k1", "n1", expiry=int(time.time()) - 1)  # 已过期
    # GC 后再加同 nonce 应通过
    store.gc()
    store.check_and_add("k1", "n1", expiry=int(time.time()) + 25)
```

- [ ] **Step 2: 跑测试,确认 fail**
```bash
pytest tests/test_hmac_sign.py -v
# 期望:ImportError 或 ModuleNotFoundError
```

- [ ] **Step 3: 写 `~/agent-platform/platform/platform_app/hmac_sign.py`**
```python
"""SSO.md §1.2 HMAC 签名 / 验证 + nonce store."""
from __future__ import annotations
import base64
import hashlib
import hmac
import time
import uuid


def _compute_sig(
    *, secret: str, ts: int, nonce: str,
    method: str, host: str, path: str,
    client: str, agent: str, user_id: str, user_role: str,
    body: bytes,
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    payload = "\n".join([
        "v1", str(ts), nonce,
        method.upper(), host, path,
        client, agent, user_id, user_role, body_hash,
    ]).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.b64encode(sig).decode("ascii")


def sign(
    *, secret: str, key_id: str,
    method: str, host: str, path: str,
    client: str, agent: str, user_id: str, user_role: str,
    body: bytes, user_name: str = "",
) -> dict[str, str]:
    ts = int(time.time())
    nonce = str(uuid.uuid4())
    sig = _compute_sig(
        secret=secret, ts=ts, nonce=nonce, method=method, host=host, path=path,
        client=client, agent=agent, user_id=user_id, user_role=user_role, body=body,
    )
    return {
        "X-Tenant-Client": client,
        "X-Tenant-Agent": agent,
        "X-User-Id": user_id,
        "X-User-Name": user_name,
        "X-User-Role": user_role,
        "X-Auth-Timestamp": str(ts),
        "X-Auth-Nonce": nonce,
        "X-Auth-Key-Id": key_id,
        "X-Auth-Signature": sig,
    }


def verify(
    *, headers: dict[str, str], secrets: dict[str, str],
    method: str, host: str, path: str,
    client: str, agent: str, body: bytes,
    nonce_store: "NonceStore",
    clock_skew_seconds: int = 5, replay_window_seconds: int = 10,
) -> None:
    """Raises ValueError on any failure. Returns None on success."""
    key_id = headers.get("X-Auth-Key-Id", "")
    if key_id not in secrets:
        raise ValueError(f"unknown key id")
    secret = secrets[key_id]

    try:
        ts = int(headers.get("X-Auth-Timestamp", "0"))
    except ValueError:
        raise ValueError("bad timestamp")
    now = int(time.time())
    if ts < now - replay_window_seconds or ts > now + clock_skew_seconds:
        raise ValueError("stale or future timestamp")

    if headers.get("X-Tenant-Client", "") != client:
        raise ValueError("client mismatch")
    if headers.get("X-Tenant-Agent", "") != agent:
        raise ValueError("agent mismatch")

    expected = _compute_sig(
        secret=secret, ts=ts, nonce=headers.get("X-Auth-Nonce", ""),
        method=method, host=host, path=path,
        client=client, agent=agent,
        user_id=headers.get("X-User-Id", ""),
        user_role=headers.get("X-User-Role", ""),
        body=body,
    )
    if not hmac.compare_digest(expected, headers.get("X-Auth-Signature", "")):
        raise ValueError("signature mismatch")

    nonce = headers.get("X-Auth-Nonce", "")
    nonce_store.check_and_add(key_id, nonce, expiry=ts + replay_window_seconds + clock_skew_seconds + 10)


class NonceStore:
    """进程内 (key_id, nonce) -> expiry_ts。Thread-safe enough for asyncio single-loop usage."""
    def __init__(self, max_size: int = 100_000):
        self._store: dict[tuple[str, str], int] = {}
        self._max = max_size

    def check_and_add(self, key_id: str, nonce: str, expiry: int) -> None:
        now = int(time.time())
        key = (key_id, nonce)
        if key in self._store and self._store[key] > now:
            raise ValueError("replay detected")
        if len(self._store) >= self._max:
            self.gc()
        self._store[key] = expiry

    def gc(self) -> None:
        now = int(time.time())
        expired = [k for k, v in self._store.items() if v <= now]
        for k in expired:
            self._store.pop(k, None)
```

- [ ] **Step 4: 跑测试,确认通过**
```bash
pytest tests/test_hmac_sign.py -v
# 期望:8 passed
```

- [ ] **Step 5: Commit**
```bash
git add platform/platform_app/hmac_sign.py platform/tests/test_hmac_sign.py
git commit -m "Task 3: HMAC sign/verify + nonce store (SSO.md §1.2)"
```

---

## Task 4: 用户/会话 / Login / CSRF(§1.1, §7.2)

**Files:**
- Create: `~/agent-platform/platform/platform_app/auth.py`
- Create: `~/agent-platform/platform/platform_app/csrf.py`
- Create: `~/agent-platform/platform/tests/test_auth.py`

- [ ] **Step 1: 写 `~/agent-platform/platform/platform_app/auth.py`**
```python
"""SSO.md §1.1 + §1.4 session 管理。"""
from __future__ import annotations
import secrets
import time
import bcrypt
from . import db
from .settings import settings

DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()  # 防 timing oracle


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def authenticate(username: str, password: str) -> str | None:
    """Returns user_id or None. Always runs bcrypt to avoid timing oracle."""
    row = db.main().execute(
        "SELECT id, password_hash FROM users WHERE username=?", (username,),
    ).fetchone()
    if row is None:
        verify_password(password, DUMMY_HASH)  # constant-time decoy
        return None
    if verify_password(password, row["password_hash"]):
        db.main().execute("UPDATE users SET last_login=? WHERE id=?", (int(time.time()), row["id"]))
        return row["id"]
    return None


def create_session(user_id: str, ip: str | None, ua: str | None) -> tuple[str, str]:
    """Returns (session_id, csrf_token). Caller sets cookies."""
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = int(time.time())
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at, ip, user_agent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sid, user_id, csrf, now, now + settings.session_lifetime_seconds, ip, ua),
    )
    return sid, csrf


def revoke_session(session_id: str) -> None:
    db.main().execute("DELETE FROM platform_sessions WHERE id=?", (session_id,))
    db.main().execute(
        "UPDATE api_keys SET revoked_at=? WHERE source_session_id=? AND revoked_at IS NULL",
        (int(time.time()), session_id),
    )
    db.invalidate_session(session_id)


def revoke_user_sessions(user_id: str) -> None:
    rows = db.main().execute("SELECT id FROM platform_sessions WHERE user_id=?", (user_id,)).fetchall()
    for r in rows:
        revoke_session(r["id"])


def current_user_from_request(cookie_value: str | None) -> dict | None:
    if not cookie_value:
        return None
    sess = db.get_session(cookie_value)
    if sess is None:
        return None
    user = db.main().execute(
        "SELECT id, username, display_name FROM users WHERE id=?", (sess["user_id"],),
    ).fetchone()
    if not user:
        return None
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"],
            "csrf": sess["csrf_token"], "session_id": sess["id"]}
```

- [ ] **Step 2: 写 `~/agent-platform/platform/platform_app/csrf.py`**
```python
"""SSO.md §7.2 CSRF double-submit."""
import hmac

def verify_double_submit(header_value: str | None, cookie_value: str | None) -> bool:
    if not header_value or not cookie_value:
        return False
    return hmac.compare_digest(header_value, cookie_value)
```

- [ ] **Step 3: 写 `~/agent-platform/platform/tests/test_auth.py`**
```python
import time
from platform_app import auth, db


def test_authenticate_unknown_user_returns_none():
    db.init()
    assert auth.authenticate("nobody", "anything") is None


def test_authenticate_wrong_password():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (?,?,?,?,?)",
        ("u_a", "alice", auth.hash_password("correct"), "Alice", int(time.time())),
    )
    assert auth.authenticate("alice", "wrong") is None
    assert auth.authenticate("alice", "correct") == "u_a"


def test_create_session_then_lookup():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (?,?,?,?,?)",
        ("u_a", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    sid, csrf = auth.create_session("u_a", "127.0.0.1", "test-ua")
    me = auth.current_user_from_request(sid)
    assert me is not None
    assert me["id"] == "u_a"
    assert me["csrf"] == csrf


def test_revoke_session_invalidates_lookup():
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (?,?,?,?,?)",
        ("u_a", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    sid, _ = auth.create_session("u_a", None, None)
    assert auth.current_user_from_request(sid) is not None
    auth.revoke_session(sid)
    assert auth.current_user_from_request(sid) is None
```

- [ ] **Step 4: 跑测试**
```bash
pytest tests/test_auth.py -v
# 期望:4 passed
```

- [ ] **Step 5: Commit**
```bash
git add platform/platform_app/auth.py platform/platform_app/csrf.py platform/tests/test_auth.py
git commit -m "Task 4: auth + session + CSRF (SSO.md §1.1, §7.2)"
```

---

## Task 5: Admin CLI(`platform-admin`)

**Files:**
- Create: `~/agent-platform/platform/platform_app/admin.py`

- [ ] **Step 1: 写 `~/agent-platform/platform/platform_app/admin.py`**
```python
"""管理 CLI:用户、tenant、密钥轮换。SSO.md §13.2-13.3."""
from __future__ import annotations
import argparse
import getpass
import json
import secrets
import sys
import time
import uuid
from . import auth, db


def _now() -> int: return int(time.time())


def cmd_add_user(args):
    db.init()
    pw = args.password or getpass.getpass(f"Password for {args.username}: ")
    user_id = f"u_{args.username}"
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, email, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, args.username, auth.hash_password(pw), args.display_name, args.email, _now()),
    )
    print(f"created user_id={user_id}")


def cmd_add_tenant(args):
    db.init()
    secret = secrets.token_urlsafe(32)
    key_id = f"k-{int(time.time())}"
    uid = str(uuid.uuid4())
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (args.client, args.agent, args.display_name, args.container_url,
         secret, key_id, uid, _now()),
    )
    db.invalidate_tenant(args.client, args.agent)
    print(json.dumps({
        "client_id": args.client, "agent_id": args.agent,
        "hmac_secret_current": secret, "hmac_key_id_current": key_id,
        "tenant_uid": uid,
    }, indent=2))
    print("\n== AGENT .env ==")
    print(f"TENANT_CLIENT={args.client}")
    print(f"TENANT_AGENT={args.agent}")
    print(f"HMAC_SECRET_CURRENT={secret}")
    print(f"HMAC_KEY_ID_CURRENT={key_id}")
    print("HMAC_SECRET_PREV=")
    print("HMAC_KEY_ID_PREV=")


def cmd_grant(args):
    db.init()
    user_id = f"u_{args.username}"
    db.main().execute(
        "INSERT OR REPLACE INTO user_tenant (user_id, client_id, agent_id, role, granted_at, granted_by) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, args.client, args.agent, args.role, _now(), "cli"),
    )
    db.invalidate_acl(user_id, args.client, args.agent)
    print(f"granted {args.username} -> {args.client}/{args.agent} ({args.role})")


def cmd_revoke(args):
    db.init()
    user_id = f"u_{args.username}"
    db.main().execute(
        "DELETE FROM user_tenant WHERE user_id=? AND client_id=? AND agent_id=?",
        (user_id, args.client, args.agent),
    )
    db.invalidate_acl(user_id, args.client, args.agent)
    print("revoked")


def cmd_rotate_key(args):
    db.init()
    new_secret = secrets.token_urlsafe(32)
    new_kid = f"k-{int(time.time())}"
    row = db.main().execute(
        "SELECT hmac_secret_current, hmac_key_id_current FROM tenants WHERE client_id=? AND agent_id=?",
        (args.client, args.agent),
    ).fetchone()
    assert row, "tenant not found"
    db.main().execute(
        "UPDATE tenants SET hmac_secret_current=?, hmac_key_id_current=?, "
        "hmac_secret_prev=?, hmac_key_id_prev=?, hmac_rotated_at=? "
        "WHERE client_id=? AND agent_id=?",
        (new_secret, new_kid, row["hmac_secret_current"], row["hmac_key_id_current"], _now(),
         args.client, args.agent),
    )
    db.invalidate_tenant(args.client, args.agent)
    print(f"rotated. new_kid={new_kid}\nnew_secret={new_secret}\n(prev kept for 24h)")


def cmd_clear_prev_key(args):
    db.init()
    db.main().execute(
        "UPDATE tenants SET hmac_secret_prev='', hmac_key_id_prev='' WHERE client_id=? AND agent_id=?",
        (args.client, args.agent),
    )
    db.invalidate_tenant(args.client, args.agent)
    print("prev key cleared")


def cmd_list_users(args):
    db.init()
    for r in db.main().execute("SELECT id, username, display_name, last_login FROM users").fetchall():
        print(f"{r['id']:20} {r['username']:15} {r['display_name']:20} last_login={r['last_login']}")


def main():
    p = argparse.ArgumentParser(prog="platform-admin")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("add-user")
    s.add_argument("username"); s.add_argument("display_name")
    s.add_argument("--password"); s.add_argument("--email")
    s.set_defaults(func=cmd_add_user)

    s = sp.add_parser("add-tenant")
    s.add_argument("client"); s.add_argument("agent")
    s.add_argument("--display-name", required=True)
    s.add_argument("--container-url", required=True)
    s.set_defaults(func=cmd_add_tenant)

    s = sp.add_parser("grant")
    s.add_argument("username"); s.add_argument("client"); s.add_argument("agent")
    s.add_argument("--role", default="user")
    s.set_defaults(func=cmd_grant)

    s = sp.add_parser("revoke")
    s.add_argument("username"); s.add_argument("client"); s.add_argument("agent")
    s.set_defaults(func=cmd_revoke)

    s = sp.add_parser("rotate-tenant-key")
    s.add_argument("client"); s.add_argument("agent")
    s.set_defaults(func=cmd_rotate_key)

    s = sp.add_parser("clear-prev-key")
    s.add_argument("client"); s.add_argument("agent")
    s.set_defaults(func=cmd_clear_prev_key)

    s = sp.add_parser("list-users")
    s.set_defaults(func=cmd_list_users)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 测试可用**
```bash
cd ~/agent-platform/platform
mkdir -p /tmp/platform-test-data
PLATFORM_DB_PATH=/tmp/platform-test-data/platform.db \
PROXY_LOG_DB_PATH=/tmp/platform-test-data/proxy_log.db \
COOKIE_SECRET=test \
.venv/bin/platform-admin add-user xuzong "许总" --password test123 --email xuzong@example.com
# 期望:created user_id=u_xuzong

PLATFORM_DB_PATH=/tmp/platform-test-data/platform.db \
PROXY_LOG_DB_PATH=/tmp/platform-test-data/proxy_log.db \
COOKIE_SECRET=test \
.venv/bin/platform-admin list-users
# 期望:1 行 u_xuzong xuzong 许总 ...
```

- [ ] **Step 3: Commit**
```bash
git add platform/platform_app/admin.py
git commit -m "Task 5: platform-admin CLI"
```

---

## Task 6: 反向代理核心 + SSE 透传(§3, §3.1, §3.2)

**Files:**
- Create: `~/agent-platform/platform/platform_app/response_headers.py`
- Create: `~/agent-platform/platform/platform_app/proxy.py`
- Create: `~/agent-platform/platform/tests/test_proxy.py`

**Design notes:**
- 反代必须 stream 模式,**绝不**整体 buffer
- 浏览器断开 → propagate 到上游 close
- §3.1 响应头净化在这里做,§7.1 CSP 在 Task 7

- [ ] **Step 1: 写 `~/agent-platform/platform/platform_app/response_headers.py`**
```python
"""SSO.md §3.1 响应头净化 + §7.1 安全响应头。"""
from __future__ import annotations
import json
import secrets

# §3.1 必须从 agent 响应剥离的 header(小写比对)
STRIPPED = {
    "set-cookie", "strict-transport-security", "content-security-policy",
    "x-frame-options", "x-content-type-options", "referrer-policy",
    "permissions-policy", "cross-origin-opener-policy", "cross-origin-resource-policy",
    "server", "x-powered-by",
    # hop-by-hop
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    # CORS 应由平台 api 统一管理
    "access-control-allow-origin", "access-control-allow-credentials",
    "access-control-allow-methods", "access-control-allow-headers",
    "access-control-expose-headers", "access-control-max-age",
}


def sanitize_agent_response_headers(
    agent_headers: list[tuple[bytes, bytes]],
    *, allowed_set_cookie_prefixes: list[str],
) -> list[tuple[bytes, bytes]]:
    """剥离危险 header;Set-Cookie 仅放行前缀白名单中的 cookie 名。"""
    out: list[tuple[bytes, bytes]] = []
    for k, v in agent_headers:
        kl = k.decode("latin-1").lower()
        if kl == "set-cookie":
            cookie_name = v.decode("latin-1").split("=", 1)[0].strip()
            if any(cookie_name.startswith(p) for p in allowed_set_cookie_prefixes):
                out.append((k, v))
            continue
        if kl in STRIPPED:
            continue
        out.append((k, v))
    return out


def inject_security_headers(
    headers: list[tuple[bytes, bytes]],
    *, csp_nonce: str, is_app_subdomain: bool,
) -> list[tuple[bytes, bytes]]:
    """SSO.md §7.1 全套响应头。"""
    csp = (
        "default-src 'none'; "
        f"script-src 'self' 'strict-dynamic' 'nonce-{csp_nonce}'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'; "
        "require-trusted-types-for 'script'; "
        "report-uri /csp-report"
    )
    additions = [
        (b"X-Content-Type-Options", b"nosniff"),
        (b"X-Frame-Options", b"DENY"),
        (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
        (b"Permissions-Policy", b"geolocation=(), microphone=(), camera=()"),
        (b"Strict-Transport-Security", b"max-age=31536000; includeSubDomains; preload"),
        (b"Cross-Origin-Opener-Policy", b"same-origin"),
        (b"Cross-Origin-Resource-Policy", b"same-origin"),
        (b"Content-Security-Policy", csp.encode("latin-1")),
    ]
    if is_app_subdomain:
        additions.append((b"X-Robots-Tag", b"noindex, nofollow"))
    return headers + additions


def make_csp_nonce() -> str:
    return secrets.token_urlsafe(16)
```

- [ ] **Step 2: 写 `~/agent-platform/platform/platform_app/proxy.py`**

用 `httpx.AsyncClient.send(stream=True)` 模式。不能用 `async with client.stream(...) as r:` 因为它的 context manager 会在函数返回前关闭 response,而 StreamingResponse 的 generator 在函数返回后才消费。正确做法是手动管理 lifecycle:

```python
"""SSO.md §3, §3.2 反向代理核心(SSE 透传 + 断开传播)."""
from __future__ import annotations
import time
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from . import db, hmac_sign
from .response_headers import (
    sanitize_agent_response_headers, inject_security_headers, make_csp_nonce,
)

_HTTP_CLIENT = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=None, write=30, pool=5),
)


async def reverse_proxy(
    request: Request, *, client_id: str, agent_id: str,
    user: dict, subpath: str,
) -> StreamingResponse:
    tenant = db.get_tenant(client_id, agent_id)
    if tenant is None:
        raise HTTPException(404, {"error": "unknown_tenant", "message": "tenant 不存在"})
    if tenant["health"] == "unhealthy":
        raise HTTPException(502, {"error": "agent_unavailable", "message": "agent 暂时不可达"})

    # path 重写 + 保留 query
    qs = request.url.query
    upstream_path = subpath if subpath.startswith("/") else "/" + subpath
    if qs:
        upstream_path += "?" + qs
    upstream_url = tenant["container_url"].rstrip("/") + upstream_path

    body = await request.body()

    auth_headers = hmac_sign.sign(
        secret=tenant["hmac_secret_current"], key_id=tenant["hmac_key_id_current"],
        method=request.method, host=request.headers.get("host", ""),
        path=upstream_path,
        client=client_id, agent=agent_id,
        user_id=user["id"], user_role="user", user_name=user.get("display_name", ""),
        body=body,
    )
    forward_headers = {**auth_headers}
    for h in ("content-type", "accept", "accept-language", "x-csrf-token"):
        v = request.headers.get(h)
        if v:
            forward_headers[h] = v
    nonce = make_csp_nonce()
    forward_headers["X-CSP-Nonce"] = nonce

    started = time.time()

    # 关键:build_request + send(stream=True) 不会 auto-close,可以手动管理
    upstream_req = _HTTP_CLIENT.build_request(
        request.method, upstream_url, headers=forward_headers, content=body,
    )
    try:
        upstream_resp = await _HTTP_CLIENT.send(upstream_req, stream=True)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise HTTPException(502, {"error": "agent_unavailable", "message": str(e)})

    async def body_iter():
        try:
            async for chunk in upstream_resp.aiter_raw():
                if await request.is_disconnected():
                    break
                yield chunk
        except httpx.RemoteProtocolError:
            pass
        finally:
            await upstream_resp.aclose()
            duration_ms = int((time.time() - started) * 1000)
            db.write_proxy_log(
                user_id=user["id"], client_id=client_id, agent_id=agent_id,
                method=request.method, path=subpath,
                status=upstream_resp.status_code, duration_ms=duration_ms,
                ip=request.client.host if request.client else None,
            )

    sanitized = sanitize_agent_response_headers(
        list(upstream_resp.headers.raw),
        allowed_set_cookie_prefixes=[f"{client_id}_{agent_id}_"],
    )
    is_app = request.headers.get("host", "").startswith(("app.", "demo.", "api."))
    final = inject_security_headers(sanitized, csp_nonce=nonce, is_app_subdomain=is_app)
    out_headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in final}
    media_type = out_headers.get("content-type")

    return StreamingResponse(
        body_iter(),
        status_code=upstream_resp.status_code,
        headers=out_headers,
        media_type=media_type,
    )
```

- [ ] **Step 3: 写最简单的 smoke 测试 `~/agent-platform/platform/tests/test_proxy.py`**
```python
import pytest
import httpx
import respx
from platform_app.response_headers import sanitize_agent_response_headers, STRIPPED


def test_strips_set_cookie_by_default():
    headers = [(b"set-cookie", b"app_session=evil; Path=/"), (b"content-type", b"text/html")]
    out = sanitize_agent_response_headers(headers, allowed_set_cookie_prefixes=[])
    assert (b"set-cookie", b"app_session=evil; Path=/") not in out
    assert (b"content-type", b"text/html") in out


def test_allows_whitelisted_set_cookie():
    headers = [(b"set-cookie", b"yinhu_super-xiaochen_state=v; Path=/")]
    out = sanitize_agent_response_headers(
        headers, allowed_set_cookie_prefixes=["yinhu_super-xiaochen_"],
    )
    assert headers[0] in out


def test_strips_security_headers_from_agent():
    headers = [(b"strict-transport-security", b"max-age=10"),
               (b"x-frame-options", b"SAMEORIGIN")]
    out = sanitize_agent_response_headers(headers, allowed_set_cookie_prefixes=[])
    assert out == []
```

- [ ] **Step 4: 跑测试**
```bash
pytest tests/test_proxy.py -v
# 期望:3 passed
```

- [ ] **Step 5: Commit**
```bash
git add platform/platform_app/proxy.py platform/platform_app/response_headers.py platform/tests/test_proxy.py
git commit -m "Task 6: reverse proxy + SSE + response header sanitization (SSO.md §3, §3.1, §7.1)"
```

---

## Task 7: §7.2 跨 agent 防火墙

**Files:**
- Create: `~/agent-platform/platform/platform_app/firewall.py`
- Create: `~/agent-platform/platform/tests/test_firewall.py`

- [ ] **Step 1: 写 `~/agent-platform/platform/platform_app/firewall.py`**
```python
"""SSO.md §7.2 跨 agent 防火墙."""
from __future__ import annotations
from urllib.parse import urlparse
from . import csrf as _csrf


class FirewallReject(Exception):
    pass


def check_request(
    *, sec_fetch_mode: str | None, sec_fetch_site: str | None,
    referer: str | None, host: str,
    dest_path_prefix: str,
    csrf_header: str | None, csrf_cookie: str | None,
) -> None:
    """Raises FirewallReject on any failure. dest_path_prefix 形如 '/yinhu/super-xiaochen/'."""
    if sec_fetch_mode is None and sec_fetch_site is None:
        # 老浏览器,v1.2 拒绝
        raise FirewallReject("missing Sec-Fetch-* headers")

    if sec_fetch_mode == "navigate":
        return  # 顶级导航放行

    if sec_fetch_site == "cross-site":
        raise FirewallReject("cross-site request blocked")

    # cors / no-cors / websocket / same-origin → 必须 referer 路径匹配 + CSRF
    if not referer:
        raise FirewallReject("missing Referer for non-navigate")
    parsed = urlparse(referer)
    if parsed.netloc != host:
        raise FirewallReject(f"referer host mismatch: {parsed.netloc} != {host}")
    if not parsed.path.startswith(dest_path_prefix):
        raise FirewallReject(f"referer path {parsed.path} does not start with {dest_path_prefix}")

    if not _csrf.verify_double_submit(csrf_header, csrf_cookie):
        raise FirewallReject("csrf failure")
```

- [ ] **Step 2: 写 `~/agent-platform/platform/tests/test_firewall.py`**
```python
import pytest
from platform_app.firewall import check_request, FirewallReject

HOST = "app.fiveoranges.ai"
DEST = "/yinhu/super-xiaochen/"


def _ok_kwargs(**override):
    base = dict(
        sec_fetch_mode="cors", sec_fetch_site="same-origin",
        referer="https://app.fiveoranges.ai/yinhu/super-xiaochen/",
        host=HOST, dest_path_prefix=DEST,
        csrf_header="abc", csrf_cookie="abc",
    )
    base.update(override)
    return base


def test_navigate_allowed_without_csrf():
    check_request(**_ok_kwargs(sec_fetch_mode="navigate", csrf_header=None, csrf_cookie=None))


def test_cors_with_matching_referer_passes():
    check_request(**_ok_kwargs())


def test_cross_site_blocked():
    with pytest.raises(FirewallReject, match="cross-site"):
        check_request(**_ok_kwargs(sec_fetch_site="cross-site"))


def test_referer_path_mismatch_blocked():
    with pytest.raises(FirewallReject, match="referer path"):
        check_request(**_ok_kwargs(referer="https://app.fiveoranges.ai/other-tenant/agent/"))


def test_referer_host_mismatch_blocked():
    with pytest.raises(FirewallReject, match="host mismatch"):
        check_request(**_ok_kwargs(referer="https://evil.com/yinhu/super-xiaochen/"))


def test_missing_csrf_blocked():
    with pytest.raises(FirewallReject, match="csrf"):
        check_request(**_ok_kwargs(csrf_header=None))


def test_csrf_mismatch_blocked():
    with pytest.raises(FirewallReject, match="csrf"):
        check_request(**_ok_kwargs(csrf_header="xxx", csrf_cookie="yyy"))


def test_missing_sec_fetch_blocked():
    with pytest.raises(FirewallReject, match="missing Sec"):
        check_request(**_ok_kwargs(sec_fetch_mode=None, sec_fetch_site=None))
```

- [ ] **Step 3: 跑测试**
```bash
pytest tests/test_firewall.py -v
# 期望:8 passed
```

- [ ] **Step 4: Commit**
```bash
git add platform/platform_app/firewall.py platform/tests/test_firewall.py
git commit -m "Task 7: cross-agent request firewall (SSO.md §7.2)"
```

---

## Task 8: Health 探测 + main.py 路由组装

**Files:**
- Create: `~/agent-platform/platform/platform_app/health.py`
- Create: `~/agent-platform/platform/platform_app/api.py`
- Create: `~/agent-platform/platform/platform_app/main.py`
- Create: `~/agent-platform/platform/static/login.html`
- Create: `~/agent-platform/platform/static/agents.html`

- [ ] **Step 1: 写 `~/agent-platform/platform/platform_app/health.py`**
```python
"""SSO.md §11.6 周期 healthz 探测."""
from __future__ import annotations
import asyncio
import time
import httpx
from . import db
from .settings import settings


async def probe_loop():
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                rows = db.main().execute(
                    "SELECT client_id, agent_id, container_url FROM tenants WHERE active=1",
                ).fetchall()
                for r in rows:
                    health = "unhealthy"
                    try:
                        resp = await client.get(r["container_url"].rstrip("/") + "/healthz")
                        if resp.status_code == 200:
                            health = "healthy"
                    except Exception:
                        pass
                    db.main().execute(
                        "UPDATE tenants SET health=?, health_checked_at=? WHERE client_id=? AND agent_id=?",
                        (health, int(time.time()), r["client_id"], r["agent_id"]),
                    )
                    db.invalidate_tenant(r["client_id"], r["agent_id"])
            except Exception:
                pass
            await asyncio.sleep(settings.health_probe_interval_seconds)
```

- [ ] **Step 2: 写 `~/agent-platform/platform/platform_app/api.py`**
```python
"""/api/* 路由(SSO.md §2)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from . import auth, db
from .settings import settings

router = APIRouter()


def _user_from_request(request: Request) -> dict:
    cookie = request.cookies.get("app_session")
    user = auth.current_user_from_request(cookie)
    if not user:
        raise HTTPException(401, {"error": "not_logged_in", "message": "请登录"})
    return user


@router.get("/api/me")
def me(request: Request):
    user = _user_from_request(request)
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"]}


@router.get("/api/agents")
def agents(request: Request):
    user = _user_from_request(request)
    rows = db.main().execute(
        "SELECT t.client_id, t.agent_id, t.display_name, t.icon_url, t.description, t.health "
        "FROM tenants t JOIN user_tenant ut ON t.client_id=ut.client_id AND t.agent_id=ut.agent_id "
        "WHERE ut.user_id=? AND t.active=1",
        (user["id"],),
    ).fetchall()
    return {"agents": [
        {"client": r["client_id"], "agent": r["agent_id"],
         "display_name": r["display_name"], "icon": r["icon_url"],
         "description": r["description"], "health": r["health"],
         "url": f"/{r['client_id']}/{r['agent_id']}/"}
        for r in rows
    ]}


@router.post("/auth/login")
async def login(request: Request, response: Response):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    user_id = auth.authenticate(username, password)
    if not user_id:
        raise HTTPException(401, {"error": "invalid_credentials", "message": "用户名或密码错误"})
    # 旧 cookie 撤销(防 fixation)
    old = request.cookies.get("app_session")
    if old:
        auth.revoke_session(old)
    sid, csrf = auth.create_session(
        user_id, request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    response.set_cookie("app_session", sid, httponly=True, secure=True, samesite="lax",
                       max_age=settings.session_lifetime_seconds, path="/")
    response.set_cookie("app_csrf", csrf, httponly=False, secure=True, samesite="strict",
                       max_age=settings.csrf_lifetime_seconds, path="/")
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    sid = request.cookies.get("app_session")
    if sid:
        auth.revoke_session(sid)
    response.delete_cookie("app_session", path="/")
    response.delete_cookie("app_csrf", path="/")
    return {"ok": True}


@router.post("/csp-report")
async def csp_report(request: Request):
    body = await request.body()
    print(f"[csp-report] {body[:500]!r}", flush=True)
    return Response(status_code=204)
```

- [ ] **Step 3: 写 `~/agent-platform/platform/platform_app/main.py`**
```python
"""FastAPI 入口 + 路由分发."""
from __future__ import annotations
import asyncio
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from . import api, db, firewall, proxy
from .settings import settings

PATH_RE = re.compile(r"^/(?P<client>[a-z0-9-]{1,32})/(?P<agent>[a-z0-9-]{1,32})(?P<sub>/.*)?$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    from . import health
    task = asyncio.create_task(health.probe_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.include_router(api.router)

_STATIC = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
def index(request: Request):
    if request.cookies.get("app_session"):
        return FileResponse(_STATIC / "agents.html")
    return FileResponse(_STATIC / "login.html")


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def catch_all(full_path: str, request: Request):
    m = PATH_RE.match("/" + full_path)
    if not m:
        raise HTTPException(404)

    client_id = m.group("client")
    agent_id = m.group("agent")
    subpath = m.group("sub") or "/"

    # auth
    user = api._user_from_request(request)

    # ACL
    if not db.has_acl(user["id"], client_id, agent_id):
        raise HTTPException(403, {"error": "not_authorized_for_tenant", "message": "无权访问"})

    # §7.2 firewall
    try:
        firewall.check_request(
            sec_fetch_mode=request.headers.get("sec-fetch-mode"),
            sec_fetch_site=request.headers.get("sec-fetch-site"),
            referer=request.headers.get("referer"),
            host=request.headers.get("host", ""),
            dest_path_prefix=f"/{client_id}/{agent_id}/",
            csrf_header=request.headers.get("x-csrf-token"),
            csrf_cookie=request.cookies.get("app_csrf"),
        )
    except firewall.FirewallReject as e:
        raise HTTPException(403, {"error": "cross_agent_blocked", "message": str(e)})

    return await proxy.reverse_proxy(
        request, client_id=client_id, agent_id=agent_id, user=user, subpath=subpath,
    )
```

- [ ] **Step 4: 写 `~/agent-platform/platform/static/login.html`**
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>fiveoranges.ai 登录</title>
<style>
body { font-family: -apple-system, sans-serif; background: #fafafa; max-width: 400px; margin: 80px auto; padding: 24px; }
h1 { font-size: 18px; margin-bottom: 24px; color: #333; }
form { background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
input { width: 100%; padding: 10px; margin: 6px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button { width: 100%; padding: 12px; background: #ff7a00; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; margin-top: 12px; }
.err { color: #c00; font-size: 13px; min-height: 18px; margin-top: 8px; }
</style>
</head>
<body>
<h1>fiveoranges.ai · 登录</h1>
<form id="f">
<input name="username" placeholder="用户名" autocomplete="username" required>
<input name="password" type="password" placeholder="密码" autocomplete="current-password" required>
<button type="submit">登录</button>
<div class="err" id="err"></div>
</form>
<script>
document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const r = await fetch('/auth/login', { method: 'POST', body: fd, credentials: 'same-origin' });
  if (r.ok) location.href = '/';
  else {
    const j = await r.json().catch(() => ({}));
    document.getElementById('err').textContent = (j.detail && j.detail.message) || '登录失败';
  }
});
</script>
</body>
</html>
```

- [ ] **Step 5: 写 `~/agent-platform/platform/static/agents.html`**
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>fiveoranges.ai · Agent 列表</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 24px; }
h1 { font-size: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 24px; }
.card { padding: 20px; background: white; border: 1px solid #eee; border-radius: 8px; cursor: pointer; transition: box-shadow 0.15s; }
.card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.card h3 { margin: 0 0 8px 0; font-size: 16px; }
.card .desc { color: #666; font-size: 13px; }
.health-healthy { color: #1a8c1a; }
.health-unhealthy { color: #c00; }
.logout { float: right; color: #999; cursor: pointer; }
</style>
</head>
<body>
<h1>我的 Agents <span class="logout" onclick="logout()">退出</span></h1>
<div id="list" class="grid"></div>
<script>
async function logout() {
  await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
  location.href = '/';
}
async function load() {
  const r = await fetch('/api/agents', { credentials: 'same-origin' });
  if (r.status === 401) { location.href = '/'; return; }
  const data = await r.json();
  document.getElementById('list').innerHTML = data.agents.map(a => `
    <div class="card" onclick="location.href='${a.url}'">
      <h3>${a.display_name}</h3>
      <div class="desc">${a.description || ''}</div>
      <div class="health-${a.health}">● ${a.health}</div>
    </div>
  `).join('');
}
load();
</script>
</body>
</html>
```

- [ ] **Step 6: 本地启动 + 验证(还没接 yinhu agent)**
```bash
cd ~/agent-platform/platform
mkdir -p /tmp/platform-test-data
PLATFORM_DB_PATH=/tmp/platform-test-data/platform.db \
PROXY_LOG_DB_PATH=/tmp/platform-test-data/proxy_log.db \
COOKIE_SECRET="$(openssl rand -base64 32)" \
.venv/bin/uvicorn platform_app.main:app --host 0.0.0.0 --port 8080 &
SERVER_PID=$!
sleep 2
curl -i http://localhost:8080/
# 期望:200 OK + login.html 内容
kill $SERVER_PID
```

- [ ] **Step 7: Commit**
```bash
git add platform/
git commit -m "Task 8: main.py + api.py + health prober + login UI"
```

---

## Task 9: Yinhu agent 改造 — HMAC 验签中间件 + AsyncAnthropic

**Files:**
- Modify: `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/web_agent.py`
- Create: `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/agent_auth.py`
- Modify: `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/Dockerfile`

**Note**:这一步**修改客户产物 generated/ 副本,不动 yunwei-kernel 的 plugins/**(符合用户记忆中的 dry-run 规则)。

- [ ] **Step 1: 写 `generated/agent_auth.py`(从 platform 复制 HMAC 模块)**

直接复制 `~/agent-platform/platform/platform_app/hmac_sign.py` 到 `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/agent_auth.py`。后续 Task 16 把这条做成 Docker build 时拷贝。

```bash
cp ~/agent-platform/platform/platform_app/hmac_sign.py \
   /Users/eason/yunwei-workspaces/yinhu-rebuild/generated/agent_auth.py
```

- [ ] **Step 2: 改 `web_agent.py` `require_auth` 为 HMAC 验签**

打开 `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/web_agent.py`,找到现有的 `require_auth` 函数(line 77 附近),整体替换为:

```python
# 顶部 import 区加:
from agent_auth import verify, NonceStore  # noqa: E402

_NONCE_STORE = NonceStore()
_TENANT_CLIENT = os.environ["TENANT_CLIENT"]
_TENANT_AGENT = os.environ["TENANT_AGENT"]
_HMAC_SECRETS: dict[str, str] = {}
if os.environ.get("HMAC_KEY_ID_CURRENT"):
    _HMAC_SECRETS[os.environ["HMAC_KEY_ID_CURRENT"]] = os.environ["HMAC_SECRET_CURRENT"]
if os.environ.get("HMAC_KEY_ID_PREV"):
    _HMAC_SECRETS[os.environ["HMAC_KEY_ID_PREV"]] = os.environ["HMAC_SECRET_PREV"]


async def require_auth(request: Request) -> str:
    """SSO.md §1.2 验签中间件,返回 user_id。"""
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    try:
        verify(
            headers={
                "X-Auth-Key-Id": headers.get("x-auth-key-id", ""),
                "X-Auth-Timestamp": headers.get("x-auth-timestamp", ""),
                "X-Auth-Nonce": headers.get("x-auth-nonce", ""),
                "X-Auth-Signature": headers.get("x-auth-signature", ""),
                "X-Tenant-Client": headers.get("x-tenant-client", ""),
                "X-Tenant-Agent": headers.get("x-tenant-agent", ""),
                "X-User-Id": headers.get("x-user-id", ""),
                "X-User-Role": headers.get("x-user-role", ""),
            },
            secrets=_HMAC_SECRETS,
            method=request.method,
            host=headers.get("host", ""),
            path=request.url.path + ("?" + request.url.query if request.url.query else ""),
            client=_TENANT_CLIENT, agent=_TENANT_AGENT,
            body=body, nonce_store=_NONCE_STORE,
        )
    except ValueError as e:
        raise HTTPException(401, f"auth: {e}")
    return headers.get("x-user-id", "")
```

同时**删除**原来的 HTTP Basic 相关 `import` 和 `security = HTTPBasic()` 行。

- [ ] **Step 3: web_agent.py 全部 `Depends(require_auth)` 站点保持不变**

`require_auth` 签名仍然返回 `str`,只是含义从 username 变成 user_id。代码层调用面零改动。

> **重要数据迁移注意**:现有 SQLite 里 `chat_turns.user_id` 等字段值是 `xuzong`(Basic Auth 的 username),新的 user_id 是 `u_xuzong`。需要在 Task 12 启动前跑一次:
> ```sql
> UPDATE chat_turns SET user_id='u_xuzong' WHERE user_id='xuzong';
> UPDATE user_memories SET user_id='u_xuzong' WHERE user_id='xuzong';
> -- 任何其他用了 user_id 的表
> ```

- [ ] **Step 4: 把同步 anthropic SDK 改异步**

在 `web_agent.py` 顶部 import 保留 `import anthropic`,但**所有客户端实例化**从 `anthropic.Anthropic(...)` 改为 `anthropic.AsyncAnthropic(...)`。然后所有 stream 调用要改成 async 上下文。

具体替换(用 grep 定位):

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
grep -n "anthropic.Anthropic\|messages.stream\|stream.get_final_message" web_agent.py
```

**对每个 `anthropic.Anthropic(api_key=...)` 实例**:改为 `anthropic.AsyncAnthropic(api_key=...)`。函数签名上 `client: anthropic.Anthropic` 类型注解改为 `client: anthropic.AsyncAnthropic`。

**对每个 `with client.messages.stream(...) as stream:` 块**:
```python
# Before:
with client.messages.stream(model=..., ...) as stream:
    for _ in stream:
        pass
    final = stream.get_final_message()
```
改为:
```python
# After:
async with client.messages.stream(model=..., ...) as stream:
    async for _ in stream:
        pass
    final = await stream.get_final_message()
```

**调用 stream 函数本身的代码**:如果原本同步函数 `def _classify_model(...)` 内部用 stream,这个函数应已经是 `async def`(检查现有代码 — 看到 `_classify_model` 已经是 async,内部 `with client.messages.stream(...)` 应改 `async with`)。

> **代码量**:5-6 个 stream 调用点(line 111, 195, 296, 502, 616 附近)。每个改 3 行(`with` → `async with`,`for` → `async for`,`get_final_message` 加 await)。

> **验证方式**:改完后 docker build,直接 docker run 测一条「你好」,看流式输出是否一个 token 一个 token 出。如果是,说明 async 链路通了。

- [ ] **Step 5: 改 `Dockerfile`**

打开 `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/Dockerfile`,**整体替换**为:
```dockerfile
FROM hermes:0.10
WORKDIR /app

COPY mcp_server/ /app/mcp_server/
COPY pyproject.toml /app/
COPY web_agent.py test_agent.py agent_auth.py /app/
COPY static/ /app/static/
COPY hermes-profile/ /root/.hermes/

RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir 'fastapi>=0.110' 'uvicorn[standard]>=0.27' 'anthropic>=0.40'

VOLUME ["/data"]
ENV TENANT_ID=yinhu-rebuild \
    DOTENV_DISABLE=1 \
    SUPER_XIAOCHEN_DB=/data/super_xiaochen.db \
    SUPER_XIAOCHEN_DATA=/data \
    AUDIT_DIR=/data/audit

EXPOSE 8000

# Healthcheck endpoint must exist in web_agent.py (Task 11 will add it)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["uvicorn", "web_agent:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: 改 `web_agent.py` 加 `/healthz`**

在 `web_agent.py` 路由定义区加:
```python
@app.get("/healthz")
def healthz():
    return {"ok": True, "version": os.environ.get("AGENT_VERSION", "yinhu-1.0.0")}
```

这个端点**不**用 `Depends(require_auth)`,平台直接探测。

- [ ] **Step 7: Commit yinhu repo**
```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
git add web_agent.py agent_auth.py Dockerfile
git commit -m "feat: SSO.md v1.2 retrofit (HMAC verify + AsyncAnthropic + /healthz)"
```

---

## Task 10: 前端 `<base href>` + 相对 fetch

**Files:**
- Modify: `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static/index.html`
- Modify: `/Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static/blueprint/*.js`(如适用)

- [ ] **Step 1: 检查现有 fetch 调用点**
```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static
grep -rn "fetch(" .
# 列出所有 fetch 调用
```

- [ ] **Step 2: 改 `index.html` head 中加 `<base>`**

需要让 base 指向当前路径前缀。最稳妥:让 platform 反代时**重写 HTML body** 注入 base 标签。但更简单:agent 自己读 X-* header 拼路径。

最简单方案:**在 index.html 中读 `window.location.pathname` 自动推**:

```html
<!-- 在 <head> 里加: -->
<script>
(function() {
  // 提取 /yinhu/super-xiaochen/ 前缀
  const m = location.pathname.match(/^(\/[^/]+\/[^/]+\/)/);
  if (m) {
    const base = document.createElement('base');
    base.href = m[1];
    document.head.appendChild(base);
  }
})();
</script>
```

这段必须**第一个**进 `<head>`,在所有其他 script 之前。

- [ ] **Step 3: 把所有 `fetch('/x')` 改 `fetch('x')` 相对路径**

```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated/static
# 主要是 index.html 内联脚本和 blueprint/*.js
# 用 sed 谨慎替换:
# fetch('/chat → fetch('chat
# fetch('/sessions → fetch('sessions
# fetch('/history → fetch('history
# 但要避免改 fetch('/api/...') 这种
```

人工检查 + 替换。需要改的:
- `fetch('/chat'`  → `fetch('chat'`
- `fetch('/history'`  → `fetch('history'`
- `fetch('/sessions'`  → `fetch('sessions'`
- 任何指向 agent 自己端点的 `/path` 都改相对

**不要改**:`<img src="/static/...">` 这种 —— 因为 `<base>` 自动会让相对路径生效;但绝对路径 `/static/` 仍然会绕过 base,会 404。要么改成相对 `static/`,要么让平台保留 `/static/` 路径透传(后者更复杂)。

推荐:把 `<script src="/static/x.js">` 改 `<script src="static/x.js">`。

- [ ] **Step 4: 直接 docker run 验证(还没接 platform)**
```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
# 先生成测试 secret
HMAC_SECRET=$(openssl rand -base64 32)
KEY_ID=k-test

docker build -t agent-yinhu-super-xiaochen:dev .
docker run --rm -p 18000:8000 \
  -e TENANT_CLIENT=yinhu \
  -e TENANT_AGENT=super-xiaochen \
  -e HMAC_SECRET_CURRENT=$HMAC_SECRET \
  -e HMAC_KEY_ID_CURRENT=$KEY_ID \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic \
  -e MODEL_PRO=deepseek-v4-pro -e MODEL_FLASH=deepseek-v4-flash \
  -v /Users/eason/yunwei-workspaces/yinhu-rebuild/.yunwei-cache/canary:/data \
  agent-yinhu-super-xiaochen:dev &
sleep 5

# /healthz 不需要鉴权
curl -i http://localhost:18000/healthz
# 期望:200 + {"ok":true,"version":...}

# 业务端点没签名应 401
curl -i http://localhost:18000/chat
# 期望:401

docker stop $(docker ps -q --filter ancestor=agent-yinhu-super-xiaochen:dev)
```

- [ ] **Step 5: Commit yinhu repo**
```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
git add static/
git commit -m "feat: relative fetch paths + auto base href"
```

---

## Task 11: Docker Compose 编排

**Files:**
- Create: `~/agent-platform/ops/docker-compose.yml`
- Create: `~/agent-platform/.env`(从 `.env.example` 填好)

- [ ] **Step 1: 生成实际的 secret**
```bash
cd ~/agent-platform
cp .env.example .env
# 编辑 .env,填:
# TUNNEL_TOKEN=<从 Pre-flight P2 拿到>
# COOKIE_SECRET=$(openssl rand -base64 32)
# YINHU_HMAC_SECRET_CURRENT=$(openssl rand -base64 32)
# YINHU_HMAC_KEY_ID_CURRENT=k-$(date +%s)
# ANTHROPIC_API_KEY=<从 yinhu .env 复制>
# ADMIN_BOOTSTRAP_PASSWORD=<给许总用的初始密码,会强制改>
```

- [ ] **Step 2: 写 `~/agent-platform/ops/docker-compose.yml`**
```yaml
version: "3.8"

services:
  platform-app:
    build: ../platform
    container_name: platform-app
    restart: unless-stopped
    env_file: ../.env
    environment:
      PLATFORM_DB_PATH: /data/platform.db
      PROXY_LOG_DB_PATH: /data/proxy_log.db
    volumes:
      - ../data:/data
    networks:
      - cf-tunnel
    expose:
      - "80"
    command: uvicorn platform_app.main:app --host 0.0.0.0 --port 80 --workers 1
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost/').status"]
      interval: 30s
      timeout: 5s
      retries: 3

  agent-yinhu-super-xiaochen:
    build: /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
    container_name: agent-yinhu-super-xiaochen
    restart: unless-stopped
    environment:
      TENANT_CLIENT: yinhu
      TENANT_AGENT: super-xiaochen
      HMAC_SECRET_CURRENT: ${YINHU_HMAC_SECRET_CURRENT}
      HMAC_KEY_ID_CURRENT: ${YINHU_HMAC_KEY_ID_CURRENT}
      HMAC_SECRET_PREV: ""
      HMAC_KEY_ID_PREV: ""
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL}
      MODEL_PRO: ${MODEL_PRO}
      MODEL_FLASH: ${MODEL_FLASH}
      AGENT_VERSION: yinhu-1.0.0
    volumes:
      - /Users/eason/yunwei-workspaces/yinhu-rebuild/.yunwei-cache/canary:/data
    networks:
      - cf-tunnel
    expose:
      - "8000"

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared
    restart: unless-stopped
    # token 模式:不挂 config.yml,routes 在 CF dashboard 配
    command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
    networks:
      - cf-tunnel
    depends_on:
      - platform-app

networks:
  cf-tunnel:
    name: cf-tunnel
```

- [ ] **Step 3: 在 platform 数据库 seed admin 用户 + tenant + ACL**

写 `~/agent-platform/ops/bootstrap.sh`:
```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

source .env
docker compose -f ops/docker-compose.yml run --rm platform-app \
  python -m platform_app.admin add-user xuzong "许总" --password "$ADMIN_BOOTSTRAP_PASSWORD" --email "xu@yinhu.example"

docker compose -f ops/docker-compose.yml run --rm platform-app \
  python -m platform_app.admin add-tenant yinhu super-xiaochen \
  --display-name "银湖石墨 - 超级小陈" \
  --container-url "http://agent-yinhu-super-xiaochen:8000" \
  > /tmp/tenant-out.txt
cat /tmp/tenant-out.txt

# 注意:add-tenant 重新生成了 secret,但 .env 里的 YINHU_HMAC_SECRET_CURRENT 是另一个值。
# 我们要让 .env 的值覆盖 DB 的值(因为 agent 拿的是 .env 的值)。
# 或者反过来:让 add-tenant 接受 --secret 参数。简单做法:手动 SQL update。
docker compose -f ops/docker-compose.yml run --rm platform-app \
  python -c "
from platform_app import db
import os
db.init()
db.main().execute(
  'UPDATE tenants SET hmac_secret_current=?, hmac_key_id_current=? WHERE client_id=? AND agent_id=?',
  (os.environ['YINHU_HMAC_SECRET_CURRENT'], os.environ['YINHU_HMAC_KEY_ID_CURRENT'], 'yinhu', 'super-xiaochen'),
)
print('synced secret from .env to DB')
"

docker compose -f ops/docker-compose.yml run --rm platform-app \
  python -m platform_app.admin grant xuzong yinhu super-xiaochen --role user

echo "✓ bootstrap done. login: xuzong / [ADMIN_BOOTSTRAP_PASSWORD]"
```
```bash
chmod +x ~/agent-platform/ops/bootstrap.sh
```

- [ ] **Step 4: 数据迁移(把现有 user_id='xuzong' 改 'u_xuzong')**
```bash
sqlite3 /Users/eason/yunwei-workspaces/yinhu-rebuild/.yunwei-cache/canary/super_xiaochen.db <<'EOF'
.tables
-- 查所有有 user_id 的表
SELECT name FROM sqlite_master WHERE type='table';
EOF
# 根据实际表逐个 update;主要应该是 chat_turns, user_memories, profile 这几张
```

- [ ] **Step 5: Commit**
```bash
cd ~/agent-platform
git add ops/ .env.example PLAN.md
# 不要 git add .env(已 .gitignore'd)
git commit -m "Task 11: docker-compose orchestration + bootstrap script"
```

---

## Task 12: Cloudflared Tunnel 路由(token 模式,routes 在 dashboard)

我们用 **token 模式**(参考 Task 11 的 docker-compose 命令 `tunnel run --token ${TUNNEL_TOKEN}`)。Routes 在 Cloudflare dashboard 配置,不需要本地 config.yml。这种方式最简单,管理界面直观。

- [ ] **Step 1: 在 CF dashboard 添加 public hostnames**

打开 https://one.dash.cloudflare.com/ → Networks → Tunnels → 点开 `mac-mini-fiveoranges` → **Public Hostname** 标签 → **Add a public hostname**:

第 1 条:
- Subdomain: `app`
- Domain: `fiveoranges.ai`
- Type: `HTTP`
- URL: `platform-app:80`

第 2 条:
- Subdomain: `api`
- Domain: `fiveoranges.ai`
- Type: `HTTP`
- URL: `platform-app:80`

> CF 会自动建 CNAME `app.fiveoranges.ai` 和 `api.fiveoranges.ai`,几秒生效,TLS 自动颁发。

- [ ] **Step 2: 验证 cloudflared 容器已连上**
```bash
docker logs cloudflared 2>&1 | grep -i "registered\|connected"
# 期望:Registered tunnel connection (×4) - 连到 4 个 CF edge 节点
```

- [ ] **Step 3: 启动整套**
```bash
cd ~/agent-platform
docker compose -f ops/docker-compose.yml up -d --build
docker compose -f ops/docker-compose.yml logs -f
# 期望看到:
# - platform-app: Uvicorn running on 0.0.0.0:80
# - agent-yinhu-super-xiaochen: Uvicorn running on 0.0.0.0:8000
# - cloudflared: Registered tunnel connection (4 connections)
```

- [ ] **Step 4: bootstrap 用户和 tenant**
```bash
./ops/bootstrap.sh
# 期望:
# - created user_id=u_xuzong
# - tenant 创建 + secret 同步
# - granted xuzong -> yinhu/super-xiaochen
```

- [ ] **Step 5: 外部连通性 smoke**
```bash
# 期望 app.fiveoranges.ai 正常响应 login 页
curl -i https://app.fiveoranges.ai/
# 期望:200 + login.html

# /api/agents 没登录应 401
curl -i https://app.fiveoranges.ai/api/agents
# 期望:401 not_logged_in
```

- [ ] **Step 6: Commit**
```bash
git add ops/cloudflared/config.yml
git commit -m "Task 12: cloudflared config + tunnel ingress"
```

---

## Task 13: End-to-End Smoke

**目标**:完整跑一遍许总的体验 —— 浏览器 → 登录 → 看到 agent → 点击 → 真问一句话。

- [ ] **Step 1: 浏览器登录**
- 打开 `https://app.fiveoranges.ai`
- 输入 `xuzong` / `<ADMIN_BOOTSTRAP_PASSWORD>`
- 期望:跳转到 agent 列表,看到「银湖石墨 - 超级小陈」卡片,health 显示 healthy

- [ ] **Step 2: 点击进入 agent**
- 点卡片
- 期望:跳到 `app.fiveoranges.ai/yinhu/super-xiaochen/`,渲染超级小陈的聊天界面

- [ ] **Step 3: 验证 fetch 路径正确**
- 浏览器 F12 → Network
- 应看到 `GET /yinhu/super-xiaochen/sessions` 等请求,**不是** `GET /sessions`
- 状态全 200

- [ ] **Step 4: 发一条小消息**
- 输入「你好」
- 期望:SSE 流式输出回复(token 一个一个出),不是卡几秒后整段冒出
- 网络面板看到 `POST /yinhu/super-xiaochen/chat` 是 EventStream 类型

- [ ] **Step 5: 验证 §3.1 + §7.1 头**
```bash
curl -I -b "app_session=<拿一个真 cookie>" https://app.fiveoranges.ai/yinhu/super-xiaochen/
# 期望响应头有:
# Content-Security-Policy: default-src 'none'; ...
# Strict-Transport-Security: ...
# X-Frame-Options: DENY
# X-Robots-Tag: noindex, nofollow
# 不应该有 Set-Cookie 来自 agent(只有 platform 的 app_session, app_csrf)
```

- [ ] **Step 6: 验证 §7.2 防火墙**
```bash
# 跨 site 请求应被拒
curl -i -X POST https://app.fiveoranges.ai/yinhu/super-xiaochen/chat \
  -H "Sec-Fetch-Site: cross-site" \
  -H "Origin: https://evil.com" \
  -b "app_session=<真 cookie>"
# 期望:403 cross_agent_blocked
```

- [ ] **Step 7: 用手机蜂窝网络测一遍**
- 关掉 wifi,用 4G/5G 访问 `https://app.fiveoranges.ai`
- 验证国内运营商能访问 + 速度可接受(应 <2s 首屏)
- 如果速度差,记下作为后续 ICP / CN2 的决策依据

- [ ] **Step 8: 拿掉 ADMIN_BOOTSTRAP_PASSWORD 改正式密码**
```bash
docker compose -f ops/docker-compose.yml exec platform-app \
  python -m platform_app.admin reset-password xuzong  # ← 这条命令我们没实现,先简单 SQL 替代:
docker compose -f ops/docker-compose.yml exec platform-app \
  python -c "
from platform_app import auth, db
import getpass
db.init()
pw = getpass.getpass('New password: ')
db.main().execute('UPDATE users SET password_hash=? WHERE username=?',
  (auth.hash_password(pw), 'xuzong'))
print('done')
"
```

- [ ] **Step 9: 给许总试用**
- 把 URL + 用户名密码私下交给许总
- 让他打开发一两个真实查询(比如「上个月销售」)
- 观察是否能跑 + 答案是否合理

---

## Task 14: 备份 + 开机自启

**Files:**
- Create: `~/agent-platform/ops/backup.sh`
- Create: `~/agent-platform/ops/launchd/com.fiveoranges.colima.plist`
- Create: `~/agent-platform/ops/launchd/com.fiveoranges.compose.plist`

- [ ] **Step 1: 写备份脚本**

`~/agent-platform/ops/backup.sh`:
```bash
#!/usr/bin/env bash
set -e
DATA=$HOME/agent-platform/data
BACKUP=$DATA/backups
DATE=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP"
sqlite3 "$DATA/platform.db" ".backup '$BACKUP/platform-$DATE.db'"
sqlite3 "$DATA/proxy_log.db" ".backup '$BACKUP/proxy_log-$DATE.db'" || true

# 30 天清理
find "$BACKUP" -name "*.db" -mtime +30 -delete

echo "[$DATE] backup ok"
```
```bash
chmod +x ~/agent-platform/ops/backup.sh
```

- [ ] **Step 2: 加 cron**
```bash
crontab -l 2>/dev/null > /tmp/cron.tmp
echo "0 2 * * * /Users/eason/agent-platform/ops/backup.sh >> /Users/eason/agent-platform/data/backup.log 2>&1" >> /tmp/cron.tmp
crontab /tmp/cron.tmp
crontab -l   # 确认
```

- [ ] **Step 3: launchd colima 自启**

`~/agent-platform/ops/launchd/com.fiveoranges.colima.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.fiveoranges.colima</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/colima</string>
    <string>start</string>
    <string>--cpu</string><string>4</string>
    <string>--memory</string><string>8</string>
    <string>--vm-type</string><string>vz</string>
  </array>
  <key>StandardOutPath</key><string>/Users/eason/agent-platform/data/colima.out.log</string>
  <key>StandardErrorPath</key><string>/Users/eason/agent-platform/data/colima.err.log</string>
  <key>SoftResourceLimits</key>
  <dict><key>NumberOfFiles</key><integer>8192</integer></dict>
</dict>
</plist>
```

- [ ] **Step 4: launchd 自启 docker compose**

`~/agent-platform/ops/launchd/com.fiveoranges.compose.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.fiveoranges.compose</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
  <key>WorkingDirectory</key><string>/Users/eason/agent-platform</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-c</string>
    <string>sleep 30 &amp;&amp; /opt/homebrew/bin/docker compose -f ops/docker-compose.yml up -d</string>
  </array>
  <key>StandardOutPath</key><string>/Users/eason/agent-platform/data/compose.out.log</string>
  <key>StandardErrorPath</key><string>/Users/eason/agent-platform/data/compose.err.log</string>
</dict>
</plist>
```

- [ ] **Step 5: 启用 launchd**
```bash
cp ~/agent-platform/ops/launchd/com.fiveoranges.colima.plist ~/Library/LaunchAgents/
cp ~/agent-platform/ops/launchd/com.fiveoranges.compose.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fiveoranges.colima.plist
launchctl load ~/Library/LaunchAgents/com.fiveoranges.compose.plist
```

- [ ] **Step 6: 重启验证**
```bash
sudo shutdown -r now
# 重启后等 1-2 分钟,然后:
curl -I https://app.fiveoranges.ai/
# 期望:200,服务自动恢复
```

- [ ] **Step 7: Commit**
```bash
cd ~/agent-platform
git add ops/backup.sh ops/launchd/
git commit -m "Task 14: backup cron + launchd auto-start"
```

---

## End-state 验收清单

- [ ] `https://app.fiveoranges.ai` 返回 login 页
- [ ] `xuzong` / 正式密码 能登录
- [ ] 登录后看到 agent 列表,health=healthy
- [ ] 点击进入超级小陈,SSE 流式正常
- [ ] 重启 Mac mini 后所有服务自动恢复
- [ ] 每天 2:00 sqlite backup 文件生成
- [ ] CSP / HSTS / noindex 等响应头存在
- [ ] 跨 site 请求被防火墙拦截
- [ ] 许总在手机蜂窝网络下能正常用

---

## 回滚

如果 Task 9-13 任何一步出错导致超级小陈不可用:

1. **快速回滚**(最多 5 分钟内恢复):
```bash
cd /Users/eason/yunwei-workspaces/yinhu-rebuild/generated
git revert HEAD~3..HEAD     # 回滚 SSO retrofit 几个 commit
docker stop agent-yinhu-super-xiaochen
docker rm agent-yinhu-super-xiaochen
# 改回直接对外用 Basic Auth(暂时绕过 platform):
docker run -d --name agent-yinhu-tmp -p 0.0.0.0:8000:8000 \
  --env-file /Users/eason/yunwei-workspaces/yinhu-rebuild/.env \
  hermes:0.10
```
然后告知许总临时换 URL。

2. **平台问题但 agent 自身好**:
- 把 cloudflared 直接 ingress 到 `agent-yinhu-super-xiaochen:8000`(绕过 platform)
- 同时保留 platform 调试

3. **数据库损坏**:
```bash
cp ~/agent-platform/data/backups/platform-LATEST.db ~/agent-platform/data/platform.db
docker compose -f ops/docker-compose.yml restart platform-app
```

---

## 已知 v1.2 范围外(后续迭代)

- MFA(TOTP)— v1.3 必加
- demo.fiveoranges.ai 演示环境(§12.2 in SSO.md)
- 第二家客户接入(§12.3 in SSO.md)
- platform 蓝绿部署(目前 deploy 会断 SSE)
- agent-platform 独立 git remote + GitHub Actions CI
- ICP 备案 + 国内云迁移(规模上来后)

---

## 进度跟踪

每个 Task 完成后,在本文件 commit 时把 Task 标题加上 `[完成]` 标记,例如:
```
## Task 1: 仓库脚手架 + 依赖 [完成 2026-04-30]
```

如果中途中断,从未标记完成的最早 Task 继续。每个 Task 内部步骤是 commit 粒度,中断时可以确定到 step 级。
