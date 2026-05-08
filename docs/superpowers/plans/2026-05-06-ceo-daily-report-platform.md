# CEO 日报 — Platform 侧 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the platform-side half of the CEO daily report feature: cron scheduling, Postgres storage, dashboard UI, DingTalk push, and the orchestrator that bridges to the customer container's `/_internal/generate` endpoint.

**Architecture:** A new `daily_report` package inside `platform/platform_app/` containing four cooperating modules — `storage` (Postgres CRUD), `orchestrator` (HMAC-signed call to container + state machine), `scheduler` (croniter-driven asyncio loop), and `pushers/dingtalk` (corp-app access_token + send_workmsg). All runtime state lives in two new Postgres tables. Dashboard pages are static HTML in `platform/static/` calling new REST endpoints under `/api/daily-report/`. Mounted into the existing FastAPI app via `app.include_router` and a lifespan-managed scheduler task.

**Tech Stack:** FastAPI · psycopg (Postgres) · httpx (async) · croniter (cron parsing) · markdown-it-py (md→HTML) · existing `hmac_sign.py` (HMAC) · pytest + respx (mocking).

**Spec:** `docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md`

**Companion plan (parallel):** yinhu-rebuild side at `yinhu-super-xiaochen` repo, branch `design/ceo-daily-report-spec`. Coupling point is the `/_internal/generate` HTTP contract; both sides develop independently against fixtures.

---

## File Map

**New files:**
- `platform/migrations/005_daily_reports.sql` — two new tables (003 = data layer, 004 = enterprises are already taken)
- `platform/platform_app/daily_report/__init__.py`
- `platform/platform_app/daily_report/storage.py` — dataclasses + CRUD
- `platform/platform_app/daily_report/orchestrator.py` — `async run(tenant_id, date)`
- `platform/platform_app/daily_report/scheduler.py` — croniter loop
- `platform/platform_app/daily_report/api.py` — REST router + HTML routes
- `platform/platform_app/daily_report/markdown_render.py` — md→HTML helper
- `platform/platform_app/daily_report/pushers/__init__.py`
- `platform/platform_app/daily_report/pushers/base.py` — `Pusher` ABC + `PushResult`
- `platform/platform_app/daily_report/pushers/dingtalk.py` — DingTalk corp app pusher
- `platform/static/daily-report.html` — list page
- `platform/static/daily-report-detail.html` — detail page
- `platform/tests/fixtures/sample_collector_response.json` — fake container payload
- `platform/tests/test_daily_report_storage.py`
- `platform/tests/test_daily_report_orchestrator.py`
- `platform/tests/test_daily_report_scheduler.py`
- `platform/tests/test_daily_report_pusher_dingtalk.py`
- `platform/tests/test_daily_report_api.py`
- `docs/superpowers/runbooks/2026-05-06-daily-report-yinhu-bootstrap.md` — deployment SQL + env

**Modified files:**
- `platform/pyproject.toml` — add `croniter`, `markdown-it-py`
- `platform/platform_app/settings.py` — add DingTalk env vars
- `platform/platform_app/main.py` — include router + start scheduler in lifespan
- `platform/tests/conftest.py` — add new tables to truncate list

---

## Task 1: Add new dependencies to pyproject

**Files:**
- Modify: `platform/pyproject.toml`

- [ ] **Step 1: Add `croniter` and `markdown-it-py` to runtime deps**

Edit `platform/pyproject.toml`, locate the `dependencies` list, add two lines after the existing `pyarrow` entry:

```toml
[project]
name = "platform-app"
version = "1.4.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "httpx>=0.27",
    "bcrypt>=4.1",
    "python-multipart>=0.0.9",
    "psycopg[binary]>=3.2",
    "redis>=5.0",
    "duckdb>=1.1",
    "pyyaml>=6.0",
    "pandas>=2.2",
    "openpyxl>=3.1",
    "pyarrow>=15.0",
    "croniter>=2.0",
    "markdown-it-py>=3.0",
]
```

- [ ] **Step 2: Install + verify imports work**

Run:
```bash
cd platform && pip install -e ".[dev]"
python -c "from croniter import croniter; from markdown_it import MarkdownIt; print('ok')"
```
Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add platform/pyproject.toml
git commit -m "chore(daily-report): add croniter + markdown-it-py deps"
```

---

## Task 2: Migration 004 — create daily_reports + daily_report_subscriptions

**Files:**
- Create: `platform/migrations/005_daily_reports.sql`
- Modify: `platform/tests/conftest.py` (add new tables to TRUNCATE list)

- [ ] **Step 1: Write migration SQL**

Create `platform/migrations/005_daily_reports.sql`:

```sql
-- 004 · CEO daily report storage + subscriptions.
-- Spec: docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md §4.1

CREATE TABLE IF NOT EXISTS daily_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       TEXT NOT NULL,
  report_date     DATE NOT NULL,
  status          TEXT NOT NULL,
  content_md      TEXT,
  content_html    TEXT,
  sections_json   JSONB,
  raw_collectors  JSONB,
  push_status     TEXT,
  push_error      TEXT,
  error           TEXT,
  generated_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, report_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_tenant_date
  ON daily_reports(tenant_id, report_date DESC);

CREATE TABLE IF NOT EXISTS daily_report_subscriptions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         TEXT NOT NULL,
  recipient_label   TEXT NOT NULL,
  push_channel      TEXT NOT NULL,
  push_target       TEXT NOT NULL,
  push_cron         TEXT NOT NULL,
  timezone          TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  sections_enabled  TEXT[] NOT NULL,
  enabled           BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subs_tenant
  ON daily_report_subscriptions(tenant_id) WHERE enabled = true;
```

- [ ] **Step 2: Update conftest TRUNCATE list**

Edit `platform/tests/conftest.py`, locate the `_clean_state` fixture, append the two new tables to the existing TRUNCATE statement. Replace:

```python
        cur.execute(
            "TRUNCATE api_keys, platform_sessions, agent_grants, "
            "enterprise_members, user_tenant, tenants, enterprises, users, "
            "proxy_log, bronze_files, silver_mappings RESTART IDENTITY CASCADE"
        )
```

with:

```python
        cur.execute(
            "TRUNCATE api_keys, platform_sessions, agent_grants, "
            "enterprise_members, user_tenant, tenants, enterprises, users, "
            "proxy_log, bronze_files, silver_mappings, "
            "daily_reports, daily_report_subscriptions RESTART IDENTITY CASCADE"
        )
```

- [ ] **Step 3: Verify migration applies cleanly**

Run:
```bash
cd platform && pytest tests/test_data_layer_foundation.py -v -x
```
Expected: all existing tests pass (this verifies new migration doesn't break existing init).

- [ ] **Step 4: Verify tables exist with a quick smoke test**

Run:
```bash
cd platform && python -c "
import os
os.environ.setdefault('DATABASE_URL','postgresql://postgres:test@localhost:5433/test')
os.environ.setdefault('REDIS_URL','redis://localhost:6380')
os.environ.setdefault('COOKIE_SECRET','test-cookie-secret-32-bytes-padding=')
from platform_app import db
db.init()
r = db.main().execute('SELECT to_regclass(%s) AS t', ('daily_reports',)).fetchone()
print('daily_reports exists:', r['t'])
r = db.main().execute('SELECT to_regclass(%s) AS t', ('daily_report_subscriptions',)).fetchone()
print('subscriptions exists:', r['t'])
"
```
Expected:
```
daily_reports exists: daily_reports
subscriptions exists: daily_report_subscriptions
```

- [ ] **Step 5: Commit**

```bash
git add platform/migrations/005_daily_reports.sql platform/tests/conftest.py
git commit -m "feat(daily-report): migration 004 — daily_reports + subscriptions tables"
```

---

## Task 3: storage.py — dataclasses + create_running

**Files:**
- Create: `platform/platform_app/daily_report/__init__.py`
- Create: `platform/platform_app/daily_report/storage.py`
- Create: `platform/tests/test_daily_report_storage.py`

- [ ] **Step 1: Write the failing test for create_running**

Create `platform/tests/test_daily_report_storage.py`:

```python
"""Tests for daily_report.storage."""
from datetime import date
import pytest
from platform_app.daily_report import storage


def _seed_tenant(tenant_id: str = "yinhu", agent_id: str = "daily-report") -> None:
    """Insert a tenant row so storage.create_running has a parent."""
    from platform_app import db
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 0)",
        (tenant_id, agent_id, "Daily Report", "http://x", "secret", "k1",
         f"{tenant_id}-{agent_id}-uid"),
    )


def test_create_running_inserts_with_status_running():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert rid is not None
    row = storage.get_by_id(rid)
    assert row.tenant_id == "yinhu"
    assert row.report_date == date(2026, 5, 6)
    assert row.status == "running"
    assert row.content_md is None


def test_create_running_idempotent_on_unique():
    _seed_tenant()
    rid1 = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    rid2 = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert rid1 == rid2  # returns existing row, not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: ImportError or "module daily_report has no attribute storage".

- [ ] **Step 3: Create empty `__init__.py`**

Create `platform/platform_app/daily_report/__init__.py` with content:

```python
"""CEO daily report — platform-side scheduling, storage, push, dashboard.

See docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md.
"""
```

- [ ] **Step 4: Implement storage minimally**

Create `platform/platform_app/daily_report/storage.py`:

```python
"""Postgres CRUD for daily_reports and daily_report_subscriptions."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
import json
from .. import db

ReportStatus = str  # 'running' | 'ready' | 'partial' | 'timeout' | 'failed'
PushStatus = str    # 'pending' | 'sent' | 'failed'


@dataclass
class Report:
    id: str
    tenant_id: str
    report_date: date
    status: ReportStatus
    content_md: str | None
    content_html: str | None
    sections_json: dict[str, Any] | None
    raw_collectors: dict[str, Any] | None
    push_status: PushStatus | None
    push_error: str | None
    error: str | None
    generated_at: datetime | None
    created_at: datetime


@dataclass
class Subscription:
    id: str
    tenant_id: str
    recipient_label: str
    push_channel: str
    push_target: str
    push_cron: str
    timezone: str
    sections_enabled: list[str]
    enabled: bool


def _row_to_report(row: dict) -> Report:
    return Report(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        report_date=row["report_date"],
        status=row["status"],
        content_md=row.get("content_md"),
        content_html=row.get("content_html"),
        sections_json=row.get("sections_json"),
        raw_collectors=row.get("raw_collectors"),
        push_status=row.get("push_status"),
        push_error=row.get("push_error"),
        error=row.get("error"),
        generated_at=row.get("generated_at"),
        created_at=row["created_at"],
    )


def create_running(*, tenant_id: str, report_date: date) -> str:
    """Insert a new running row. If one already exists for (tenant, date), return its id."""
    row = db.main().execute(
        "INSERT INTO daily_reports (tenant_id, report_date, status) "
        "VALUES (%s, %s, 'running') "
        "ON CONFLICT (tenant_id, report_date) DO UPDATE SET status='running' "
        "RETURNING id",
        (tenant_id, report_date),
    ).fetchone()
    return str(row["id"])


def get_by_id(report_id: str) -> Report | None:
    row = db.main().execute(
        "SELECT * FROM daily_reports WHERE id=%s", (report_id,)
    ).fetchone()
    return _row_to_report(row) if row else None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add platform/platform_app/daily_report/__init__.py \
        platform/platform_app/daily_report/storage.py \
        platform/tests/test_daily_report_storage.py
git commit -m "feat(daily-report): storage.create_running + get_by_id"
```

---

## Task 4: storage.py — write_result + state transitions

**Files:**
- Modify: `platform/platform_app/daily_report/storage.py`
- Modify: `platform/tests/test_daily_report_storage.py`

- [ ] **Step 1: Write the failing tests**

Append to `platform/tests/test_daily_report_storage.py`:

```python
def test_write_result_ready_sets_content_and_status():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid,
        status="ready",
        content_md="# foo",
        content_html="<h1>foo</h1>",
        sections_json={"sales": {"status": "ok"}},
        raw_collectors={"sales": {"raw": "..."}},
        generated_at=datetime(2026, 5, 6, 7, 30, 11),
    )
    row = storage.get_by_id(rid)
    assert row.status == "ready"
    assert row.content_md == "# foo"
    assert row.content_html == "<h1>foo</h1>"
    assert row.sections_json == {"sales": {"status": "ok"}}
    assert row.error is None


def test_write_failure_records_error_no_content():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_failure(report_id=rid, status="failed", error="container unreachable")
    row = storage.get_by_id(rid)
    assert row.status == "failed"
    assert row.error == "container unreachable"
    assert row.content_md is None


def test_update_push_status():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.update_push_status(report_id=rid, status="sent", error=None)
    assert storage.get_by_id(rid).push_status == "sent"
    storage.update_push_status(report_id=rid, status="failed", error="dingtalk 429")
    row = storage.get_by_id(rid)
    assert row.push_status == "failed"
    assert row.push_error == "dingtalk 429"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: 3 new failures (functions don't exist).

- [ ] **Step 3: Implement write_result + write_failure + update_push_status**

Append to `platform/platform_app/daily_report/storage.py`:

```python
def write_result(
    *, report_id: str, status: ReportStatus,
    content_md: str, content_html: str,
    sections_json: dict[str, Any], raw_collectors: dict[str, Any],
    generated_at: datetime,
) -> None:
    db.main().execute(
        "UPDATE daily_reports SET status=%s, content_md=%s, content_html=%s, "
        "sections_json=%s, raw_collectors=%s, generated_at=%s, error=NULL "
        "WHERE id=%s",
        (status, content_md, content_html,
         json.dumps(sections_json), json.dumps(raw_collectors),
         generated_at, report_id),
    )


def write_failure(*, report_id: str, status: ReportStatus, error: str) -> None:
    db.main().execute(
        "UPDATE daily_reports SET status=%s, error=%s WHERE id=%s",
        (status, error, report_id),
    )


def update_push_status(*, report_id: str, status: PushStatus, error: str | None) -> None:
    db.main().execute(
        "UPDATE daily_reports SET push_status=%s, push_error=%s WHERE id=%s",
        (status, error, report_id),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/storage.py \
        platform/tests/test_daily_report_storage.py
git commit -m "feat(daily-report): storage.write_result/write_failure/update_push_status"
```

---

## Task 5: storage.py — list reports + subscription CRUD

**Files:**
- Modify: `platform/platform_app/daily_report/storage.py`
- Modify: `platform/tests/test_daily_report_storage.py`

- [ ] **Step 1: Write the failing tests**

Append to `platform/tests/test_daily_report_storage.py`:

```python
def test_list_reports_orders_desc_and_caps_limit():
    _seed_tenant()
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 4))
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 5))
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    rows = storage.list_reports(tenant_id="yinhu", limit=2)
    assert [r.report_date for r in rows] == [date(2026, 5, 6), date(2026, 5, 5)]


def test_delete_report_for_regenerate():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.delete_by_tenant_date(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert storage.get_by_id(rid) is None


def test_subscription_create_and_list():
    _seed_tenant()
    sub_id = storage.create_subscription(
        tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="30 7 * * 1-5",
        sections_enabled=["sales", "production", "chat", "customer_news"],
    )
    subs = storage.list_enabled_subscriptions()
    assert len(subs) == 1
    assert subs[0].id == sub_id
    assert subs[0].push_target == "userid_xu"
    assert subs[0].sections_enabled == ["sales", "production", "chat", "customer_news"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: 3 new failures.

- [ ] **Step 3: Implement list_reports + delete_by_tenant_date + subscription helpers**

Append to `platform/platform_app/daily_report/storage.py`:

```python
def list_reports(*, tenant_id: str, limit: int = 30) -> list[Report]:
    rows = db.main().execute(
        "SELECT * FROM daily_reports WHERE tenant_id=%s "
        "ORDER BY report_date DESC LIMIT %s",
        (tenant_id, limit),
    ).fetchall()
    return [_row_to_report(r) for r in rows]


def delete_by_tenant_date(*, tenant_id: str, report_date: date) -> None:
    db.main().execute(
        "DELETE FROM daily_reports WHERE tenant_id=%s AND report_date=%s",
        (tenant_id, report_date),
    )


def create_subscription(
    *, tenant_id: str, recipient_label: str,
    push_channel: str, push_target: str, push_cron: str,
    sections_enabled: list[str], timezone: str = "Asia/Shanghai",
) -> str:
    row = db.main().execute(
        "INSERT INTO daily_report_subscriptions "
        "(tenant_id, recipient_label, push_channel, push_target, push_cron, "
        "timezone, sections_enabled) VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id",
        (tenant_id, recipient_label, push_channel, push_target, push_cron,
         timezone, sections_enabled),
    ).fetchone()
    return str(row["id"])


def list_enabled_subscriptions() -> list[Subscription]:
    rows = db.main().execute(
        "SELECT * FROM daily_report_subscriptions WHERE enabled = true"
    ).fetchall()
    return [
        Subscription(
            id=str(r["id"]), tenant_id=r["tenant_id"],
            recipient_label=r["recipient_label"],
            push_channel=r["push_channel"], push_target=r["push_target"],
            push_cron=r["push_cron"], timezone=r["timezone"],
            sections_enabled=list(r["sections_enabled"]),
            enabled=r["enabled"],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_storage.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/storage.py \
        platform/tests/test_daily_report_storage.py
git commit -m "feat(daily-report): storage list_reports + subscription CRUD"
```

---

## Task 6: markdown_render.py — md→HTML helper

**Files:**
- Create: `platform/platform_app/daily_report/markdown_render.py`
- Create: `platform/tests/test_daily_report_markdown_render.py`

- [ ] **Step 1: Write the failing test**

Create `platform/tests/test_daily_report_markdown_render.py`:

```python
from platform_app.daily_report import markdown_render


def test_render_markdown_to_html_basic():
    md = "# Title\n\n- item 1\n- item 2"
    html = markdown_render.render(md)
    assert "<h1>" in html
    assert "<ul>" in html
    assert "<li>item 1</li>" in html


def test_render_strips_dangerous_html():
    md = "<script>alert('x')</script>\n\n# ok"
    html = markdown_render.render(md)
    assert "<script>" not in html
    assert "<h1>ok</h1>" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_markdown_render.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement renderer**

Create `platform/platform_app/daily_report/markdown_render.py`:

```python
"""Markdown → HTML for the daily report dashboard.

CommonMark via markdown-it-py with html: False so any inline <script>/<iframe>
the LLM might emit becomes literal text, not executable HTML.
"""
from __future__ import annotations
from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False})


def render(markdown_source: str) -> str:
    """Render trusted-but-defensive markdown. Strips raw HTML."""
    return _MD.render(markdown_source)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_markdown_render.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/markdown_render.py \
        platform/tests/test_daily_report_markdown_render.py
git commit -m "feat(daily-report): markdown_render with html-stripping"
```

---

## Task 7: pushers/base.py — Pusher ABC + PushResult

**Files:**
- Create: `platform/platform_app/daily_report/pushers/__init__.py`
- Create: `platform/platform_app/daily_report/pushers/base.py`
- Create: `platform/tests/test_daily_report_pusher_base.py`

- [ ] **Step 1: Write the failing test**

Create `platform/tests/test_daily_report_pusher_base.py`:

```python
import pytest
from platform_app.daily_report.pushers import base


def test_pusher_is_abstract():
    with pytest.raises(TypeError):
        base.Pusher()


def test_push_result_dataclass():
    r = base.PushResult(success=True, error=None)
    assert r.success is True
    assert r.error is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_pusher_base.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement base classes**

Create `platform/platform_app/daily_report/pushers/__init__.py` with:

```python
"""Push delivery channels for daily reports."""
```

Create `platform/platform_app/daily_report/pushers/base.py`:

```python
"""Pusher abstraction. Each channel (DingTalk, email, etc.) implements this."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..storage import Subscription


@dataclass
class PushResult:
    success: bool
    error: str | None


class Pusher(ABC):
    """One implementation per push channel."""

    @abstractmethod
    async def push(
        self, *,
        subscription: Subscription,
        markdown_body: str,
        link_url: str,
        title: str,
    ) -> PushResult: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_pusher_base.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/pushers/__init__.py \
        platform/platform_app/daily_report/pushers/base.py \
        platform/tests/test_daily_report_pusher_base.py
git commit -m "feat(daily-report): Pusher ABC + PushResult"
```

---

## Task 8: settings.py — DingTalk env vars

**Files:**
- Modify: `platform/platform_app/settings.py`

- [ ] **Step 1: Add DingTalk env vars to Settings**

Edit `platform/platform_app/settings.py`. After the `health_probe_interval_seconds = 30` line, add:

```python
    # DingTalk corp app credentials (for daily report push).
    # Optional at startup so platform can run without the daily-report feature.
    dingtalk_client_id = os.environ.get("DINGTALK_CLIENT_ID", "")
    dingtalk_client_secret = os.environ.get("DINGTALK_CLIENT_SECRET", "")
    dingtalk_agent_id = os.environ.get("DINGTALK_AGENT_ID", "")
    dingtalk_robot_code = os.environ.get("DINGTALK_ROBOT_CODE", "")
```

- [ ] **Step 2: Verify import still works**

Run:
```bash
cd platform && python -c "
import os
os.environ.setdefault('DATABASE_URL','postgresql://x')
os.environ.setdefault('REDIS_URL','redis://x')
os.environ.setdefault('COOKIE_SECRET','x'*32)
from platform_app.settings import settings
print('client_id:', repr(settings.dingtalk_client_id))
print('agent_id:', repr(settings.dingtalk_agent_id))
"
```
Expected:
```
client_id: ''
agent_id: ''
```

- [ ] **Step 3: Commit**

```bash
git add platform/platform_app/settings.py
git commit -m "feat(daily-report): DingTalk env vars in Settings"
```

---

## Task 9: pushers/dingtalk.py — access_token cache

**Files:**
- Create: `platform/platform_app/daily_report/pushers/dingtalk.py`
- Create: `platform/tests/test_daily_report_pusher_dingtalk.py`

- [ ] **Step 1: Write the failing test**

Create `platform/tests/test_daily_report_pusher_dingtalk.py`:

```python
"""DingTalkPusher tests — all DingTalk HTTP calls mocked via respx."""
import time
import pytest
import httpx
import respx
from platform_app.daily_report.pushers.dingtalk import DingTalkPusher


def _make_pusher(monkeypatch) -> DingTalkPusher:
    monkeypatch.setenv("DINGTALK_CLIENT_ID", "cli_test")
    monkeypatch.setenv("DINGTALK_CLIENT_SECRET", "sec_test")
    monkeypatch.setenv("DINGTALK_AGENT_ID", "agent_test")
    monkeypatch.setenv("DINGTALK_ROBOT_CODE", "robot_test")
    # Reload settings so env changes take effect.
    import importlib, platform_app.settings as s
    importlib.reload(s)
    return DingTalkPusher()


@pytest.mark.asyncio
async def test_access_token_fetched_and_cached(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        token_route = mock.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        ).mock(return_value=httpx.Response(200, json={
            "accessToken": "TOK1", "expireIn": 7200,
        }))
        t1 = await p._get_access_token()
        t2 = await p._get_access_token()  # served from cache
        assert t1 == "TOK1" == t2
        assert token_route.call_count == 1


@pytest.mark.asyncio
async def test_access_token_refetches_after_expiry(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            side_effect=[
                httpx.Response(200, json={"accessToken": "TOK1", "expireIn": 7200}),
                httpx.Response(200, json={"accessToken": "TOK2", "expireIn": 7200}),
            ]
        )
        await p._get_access_token()
        # Force expiry.
        p._token_expires_at = time.time() - 1
        t = await p._get_access_token()
        assert t == "TOK2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_pusher_dingtalk.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement DingTalkPusher access_token**

Create `platform/platform_app/daily_report/pushers/dingtalk.py`:

```python
"""DingTalk corp app pusher. Sends the daily report markdown card to a userid."""
from __future__ import annotations
import time
import httpx
from .base import Pusher, PushResult
from ..storage import Subscription
from ...settings import settings

_TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
_SEND_URL = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"


class DingTalkPusher(Pusher):
    """One pusher instance per platform process. Token cache is in-memory."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_TOKEN_URL, json={
                "appKey": settings.dingtalk_client_id,
                "appSecret": settings.dingtalk_client_secret,
            })
            resp.raise_for_status()
            data = resp.json()
        self._access_token = data["accessToken"]
        # 90% TTL to avoid edge expiry.
        self._token_expires_at = time.time() + data["expireIn"] * 0.9
        return self._access_token

    async def push(
        self, *,
        subscription: Subscription,
        markdown_body: str,
        link_url: str,
        title: str,
    ) -> PushResult:
        raise NotImplementedError("Implemented in next task")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_pusher_dingtalk.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/pushers/dingtalk.py \
        platform/tests/test_daily_report_pusher_dingtalk.py
git commit -m "feat(daily-report): DingTalkPusher access_token cache"
```

---

## Task 10: pushers/dingtalk.py — send markdown card + truncation

**Files:**
- Modify: `platform/platform_app/daily_report/pushers/dingtalk.py`
- Modify: `platform/tests/test_daily_report_pusher_dingtalk.py`

- [ ] **Step 1: Write the failing tests**

Append to `platform/tests/test_daily_report_pusher_dingtalk.py`:

```python
from platform_app.daily_report.storage import Subscription


def _sub() -> Subscription:
    return Subscription(
        id="sub-1", tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales", "production", "chat", "customer_news"],
        enabled=True,
    )


@pytest.mark.asyncio
async def test_push_sends_markdown_card_to_userid(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        send = mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(200, json={"processQueryKey": "ok"})
        )
        result = await p.push(
            subscription=_sub(),
            markdown_body="# 销售\n- 昨日成交 ¥1.2M",
            link_url="https://app.fiveoranges.ai/daily-report/abc-123",
            title="银湖经营快报 · 2026-05-06 周三",
        )
    assert result.success is True
    body = send.calls[0].request.read().decode()
    assert "userid_xu" in body
    assert "银湖经营快报" in body
    assert "robot_test" in body  # robotCode in payload


@pytest.mark.asyncio
async def test_push_failure_returns_error(monkeypatch):
    p = _make_pusher(monkeypatch)
    with respx.mock() as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(500, json={"code": "err", "message": "bad"})
        )
        result = await p.push(
            subscription=_sub(),
            markdown_body="x", link_url="y", title="z",
        )
    assert result.success is False
    assert "500" in result.error or "bad" in result.error


@pytest.mark.asyncio
async def test_push_truncates_long_body(monkeypatch):
    p = _make_pusher(monkeypatch)
    big = "x" * 6000
    with respx.mock() as mock:
        mock.post("https://api.dingtalk.com/v1.0/oauth2/accessToken").mock(
            return_value=httpx.Response(200, json={"accessToken": "TOK", "expireIn": 7200})
        )
        send = mock.post("https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend").mock(
            return_value=httpx.Response(200, json={"processQueryKey": "ok"})
        )
        await p.push(subscription=_sub(), markdown_body=big, link_url="y", title="t")
    body = send.calls[0].request.read().decode()
    assert len(body) < 6500  # truncated payload
    assert "完整版" in body or "dashboard" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_pusher_dingtalk.py -v`
Expected: 3 new failures (`NotImplementedError`).

- [ ] **Step 3: Implement push() with truncation**

Replace the `push` method in `platform/platform_app/daily_report/pushers/dingtalk.py`:

```python
    async def push(
        self, *,
        subscription: Subscription,
        markdown_body: str,
        link_url: str,
        title: str,
    ) -> PushResult:
        token = await self._get_access_token()
        body = self._truncate(markdown_body, link_url)
        payload = {
            "robotCode": settings.dingtalk_robot_code,
            "userIds": [subscription.push_target],
            "msgKey": "sampleActionCard",
            "msgParam": (
                # actionCard params per DingTalk docs; serialized as JSON-string-of-string-map
                '{"title":' + _json_str(title) + ','
                '"text":' + _json_str(body) + ','
                '"singleTitle":"打开完整版 + 问小陈",'
                '"singleURL":' + _json_str(link_url) + '}'
            ),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _SEND_URL,
                headers={"x-acs-dingtalk-access-token": token},
                json=payload,
            )
        if resp.status_code >= 400:
            return PushResult(success=False, error=f"{resp.status_code}: {resp.text[:200]}")
        return PushResult(success=True, error=None)

    @staticmethod
    def _truncate(body: str, link_url: str) -> str:
        """DingTalk markdown is ~5000 char; keep generous headroom."""
        MAX = 4500
        if len(body) <= MAX:
            return body
        return body[:MAX].rstrip() + f"\n\n（完整版见 dashboard：{link_url} ）"


def _json_str(s: str) -> str:
    """Embed string as JSON literal (with quotes and escapes) inside the msgParam."""
    import json as _json
    return _json.dumps(s, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_pusher_dingtalk.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/pushers/dingtalk.py \
        platform/tests/test_daily_report_pusher_dingtalk.py
git commit -m "feat(daily-report): DingTalkPusher.push with truncation"
```

---

## Task 11: orchestrator.py — happy path with fake container fixture

**Files:**
- Create: `platform/tests/fixtures/sample_collector_response.json`
- Create: `platform/platform_app/daily_report/orchestrator.py`
- Create: `platform/tests/test_daily_report_orchestrator.py`

- [ ] **Step 1: Create the fixture**

Create `platform/tests/fixtures/sample_collector_response.json`:

```json
{
  "tenant_id": "yinhu",
  "report_date": "2026-05-06",
  "markdown": "# 银湖经营快报 · 2026-05-06 周三\n\n## 销售（昨日）\n- 昨日成交 ¥1,238,400（环比 +12%）\n- 本月累计 ¥18.4M / 目标 ¥25M（73.6%）\n\n## 生产\n- 在产订单 23 单；**延期 3 单**（PR-2026-04-180）\n\n## 群要事\n- 邦普采购林总询问6.10前能否追加300套，**许总未回复**\n\n## 客户动态\n- 邦普：[发布 2026 Q1 财报](https://example.com/news/1)\n",
  "sections": {
    "sales":         {"status": "ok",  "data": {"yesterday_total": 1238400}},
    "production":    {"status": "ok",  "data": {"in_progress_count": 23}},
    "chat":          {"status": "ok",  "data": {"messages_in_window": 142}},
    "customer_news": {"status": "ok",  "data": {"items": [{"customer": "邦普"}]}}
  },
  "sources": [
    "kingdee/sales_orders", "kingdee/production_orders",
    "dingtalk/group/cidXXX1", "tavily/example.com/news/1"
  ],
  "generated_at": "2026-05-06T07:30:11+08:00",
  "duration_ms": 14823
}
```

- [ ] **Step 2: Write the failing happy-path test**

Create `platform/tests/test_daily_report_orchestrator.py`:

```python
"""Orchestrator tests — container HTTP mocked via respx."""
import json
from datetime import date
from pathlib import Path
import pytest
import httpx
import respx
from platform_app.daily_report import orchestrator, storage
from platform_app import db

_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sample_collector_response.json").read_text())


def _seed_yinhu_daily_report_tenant() -> None:
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report',"
        " 'http://yinhu-container.test:8000','secret-x','k1','yinhu-daily-uid',0)",
    )


@pytest.mark.asyncio
async def test_run_happy_path_marks_ready_and_calls_push():
    _seed_yinhu_daily_report_tenant()
    pushed = []

    class _FakePusher:
        async def push(self, **kw):
            pushed.append(kw)
            from platform_app.daily_report.pushers.base import PushResult
            return PushResult(success=True, error=None)

    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=_FIXTURE)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu",
            report_date=date(2026, 5, 6),
            pusher=_FakePusher(),
            subscription=None,  # tested separately
        )
    row = storage.get_by_id(rid)
    assert row.status == "ready"
    assert "银湖经营快报" in row.content_md
    assert "<h1>" in row.content_html  # md→html ran
    assert row.sections_json["sales"]["status"] == "ok"
    # No subscription passed → no push attempted
    assert pushed == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest platform/tests/test_daily_report_orchestrator.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement orchestrator (happy path only)**

Create `platform/platform_app/daily_report/orchestrator.py`:

```python
"""Orchestrator: drives one report generation tick.

Flow: insert running row → HMAC POST container → write result → push.
Spec §3.2.
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from typing import Any
import httpx
from . import storage, markdown_render
from .pushers.base import Pusher
from .. import db, hmac_sign

_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)


async def run(
    *,
    tenant_id: str,
    report_date: date,
    pusher: Pusher | None,
    subscription: storage.Subscription | None,
) -> str:
    """Run one tick. Returns the report id (existing or newly created)."""
    rid = storage.create_running(tenant_id=tenant_id, report_date=report_date)

    tenant = db.get_tenant(tenant_id, "daily-report")
    if tenant is None:
        storage.write_failure(report_id=rid, status="failed",
                              error="tenant (yinhu, daily-report) not registered")
        return rid

    payload = await _call_container(tenant=tenant, report_date=report_date)

    storage.write_result(
        report_id=rid,
        status=_status_from_payload(payload),
        content_md=payload["markdown"],
        content_html=markdown_render.render(payload["markdown"]),
        sections_json=payload["sections"],
        raw_collectors=payload,
        generated_at=datetime.fromisoformat(payload["generated_at"]),
    )

    if pusher and subscription:
        link = f"https://{_dashboard_host()}/daily-report/{rid}"
        result = await pusher.push(
            subscription=subscription,
            markdown_body=payload["markdown"],
            link_url=link,
            title=_card_title(report_date),
        )
        storage.update_push_status(
            report_id=rid,
            status="sent" if result.success else "failed",
            error=result.error,
        )
    return rid


def _status_from_payload(payload: dict[str, Any]) -> str:
    sections = payload.get("sections", {})
    statuses = {s.get("status") for s in sections.values()}
    if statuses <= {"ok"}:
        return "ready"
    return "partial"


def _card_title(d: date) -> str:
    weekday = "一二三四五六日"[d.weekday()]
    return f"银湖经营快报 · {d.isoformat()} 周{weekday}"


def _dashboard_host() -> str:
    from ..settings import settings
    return settings.host_app


async def _call_container(*, tenant: dict, report_date: date) -> dict:
    from ..settings import settings
    upstream_path = f"/daily-report/_internal/generate?date={report_date.isoformat()}"
    upstream_url = tenant["container_url"].rstrip("/") + upstream_path
    body = b""
    headers = hmac_sign.sign(
        secret=tenant["hmac_secret_current"], key_id=tenant["hmac_key_id_current"],
        method="POST", host=settings.host_app, path=upstream_path,
        client=tenant["client_id"], agent=tenant["agent_id"],
        user_id="system", user_role="system", user_name="daily-report-orchestrator",
        body=body,
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(upstream_url, headers=headers, content=body)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest platform/tests/test_daily_report_orchestrator.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add platform/tests/fixtures/sample_collector_response.json \
        platform/platform_app/daily_report/orchestrator.py \
        platform/tests/test_daily_report_orchestrator.py
git commit -m "feat(daily-report): orchestrator happy path"
```

---

## Task 12: orchestrator.py — retry + timeout + partial

**Files:**
- Modify: `platform/platform_app/daily_report/orchestrator.py`
- Modify: `platform/tests/test_daily_report_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Append to `platform/tests/test_daily_report_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_run_retries_once_then_marks_failed():
    _seed_yinhu_daily_report_tenant()
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            side_effect=[
                httpx.Response(503, text="temporarily unavailable"),
                httpx.Response(503, text="still down"),
            ]
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )
    row = storage.get_by_id(rid)
    assert row.status == "failed"
    assert "503" in row.error


@pytest.mark.asyncio
async def test_run_succeeds_on_retry():
    _seed_yinhu_daily_report_tenant()
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=_FIXTURE),
            ]
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )
    assert storage.get_by_id(rid).status == "ready"


@pytest.mark.asyncio
async def test_run_timeout_marks_timeout():
    _seed_yinhu_daily_report_tenant()
    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            side_effect=httpx.ReadTimeout("read timeout")
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )
    row = storage.get_by_id(rid)
    assert row.status == "timeout"


@pytest.mark.asyncio
async def test_run_partial_when_some_sections_failed():
    _seed_yinhu_daily_report_tenant()
    payload = {**_FIXTURE}
    payload["sections"] = {
        "sales":         {"status": "ok"},
        "production":    {"status": "ok"},
        "chat":          {"status": "failed", "error": "dingtalk timeout"},
        "customer_news": {"status": "ok"},
    }
    with respx.mock() as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=payload)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )
    assert storage.get_by_id(rid).status == "partial"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_orchestrator.py -v`
Expected: 3 new failures (no retry; no timeout handling).

- [ ] **Step 3: Add retry + timeout handling**

In `platform/platform_app/daily_report/orchestrator.py`, replace `_call_container` and the `run` body around the call so it handles retry and exceptions:

```python
async def run(
    *,
    tenant_id: str,
    report_date: date,
    pusher: Pusher | None,
    subscription: storage.Subscription | None,
) -> str:
    rid = storage.create_running(tenant_id=tenant_id, report_date=report_date)
    tenant = db.get_tenant(tenant_id, "daily-report")
    if tenant is None:
        storage.write_failure(report_id=rid, status="failed",
                              error="tenant (yinhu, daily-report) not registered")
        return rid

    try:
        payload = await _call_container_with_retry(tenant=tenant, report_date=report_date)
    except _ContainerTimeout as e:
        storage.write_failure(report_id=rid, status="timeout", error=str(e))
        return rid
    except _ContainerError as e:
        storage.write_failure(report_id=rid, status="failed", error=str(e))
        return rid

    storage.write_result(
        report_id=rid,
        status=_status_from_payload(payload),
        content_md=payload["markdown"],
        content_html=markdown_render.render(payload["markdown"]),
        sections_json=payload["sections"],
        raw_collectors=payload,
        generated_at=datetime.fromisoformat(payload["generated_at"]),
    )

    if pusher and subscription:
        link = f"https://{_dashboard_host()}/daily-report/{rid}"
        result = await pusher.push(
            subscription=subscription,
            markdown_body=payload["markdown"],
            link_url=link,
            title=_card_title(report_date),
        )
        storage.update_push_status(
            report_id=rid,
            status="sent" if result.success else "failed",
            error=result.error,
        )
    return rid


class _ContainerTimeout(Exception):
    pass


class _ContainerError(Exception):
    pass


async def _call_container_with_retry(*, tenant: dict, report_date: date) -> dict:
    """Try once, retry once after 30s on 5xx or transient connection error."""
    try:
        return await _call_container(tenant=tenant, report_date=report_date)
    except httpx.ReadTimeout as e:
        raise _ContainerTimeout(f"read timeout: {e}")
    except (httpx.HTTPStatusError, httpx.ConnectError) as first:
        await asyncio.sleep(30)
        try:
            return await _call_container(tenant=tenant, report_date=report_date)
        except httpx.ReadTimeout as e:
            raise _ContainerTimeout(f"read timeout on retry: {e}")
        except (httpx.HTTPStatusError, httpx.ConnectError) as second:
            raise _ContainerError(f"first={_short(first)} retry={_short(second)}")


def _short(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"{e.response.status_code}"
    return type(e).__name__
```

(`_call_container` from Task 11 already calls `resp.raise_for_status()`, which raises `HTTPStatusError` on 5xx — `_call_container_with_retry` catches it. No change to `_call_container` itself.)

- [ ] **Step 4: Speed up retry sleep for tests**

Add at the top of `orchestrator.py`:

```python
_RETRY_DELAY_SECONDS = 30  # overridable in tests
```

Replace `await asyncio.sleep(30)` with `await asyncio.sleep(_RETRY_DELAY_SECONDS)`.

In the test file, add a fixture at top (after imports):

```python
@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(orchestrator, "_RETRY_DELAY_SECONDS", 0)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_orchestrator.py -v`
Expected: all 5 passed (1 prior + 4 new minus 1 = 4 new added; total 5).

- [ ] **Step 6: Commit**

```bash
git add platform/platform_app/daily_report/orchestrator.py \
        platform/tests/test_daily_report_orchestrator.py
git commit -m "feat(daily-report): orchestrator retry + timeout + partial state"
```

---

## Task 13: orchestrator.py — push integration test

**Files:**
- Modify: `platform/tests/test_daily_report_orchestrator.py`

- [ ] **Step 1: Write failing test**

Append to `platform/tests/test_daily_report_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_run_calls_pusher_when_subscription_given():
    _seed_yinhu_daily_report_tenant()
    sub_id = storage.create_subscription(
        tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="30 7 * * 1-5",
        sections_enabled=["sales", "production", "chat", "customer_news"],
    )
    sub = next(s for s in storage.list_enabled_subscriptions() if s.id == sub_id)

    captured = []

    class _CapturingPusher:
        async def push(self, **kw):
            captured.append(kw)
            from platform_app.daily_report.pushers.base import PushResult
            return PushResult(success=True, error=None)

    with respx.mock() as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=_FIXTURE)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=_CapturingPusher(), subscription=sub,
        )
    assert len(captured) == 1
    assert captured[0]["subscription"].push_target == "userid_xu"
    assert "银湖经营快报" in captured[0]["title"]
    assert captured[0]["link_url"].endswith(f"/daily-report/{rid}")
    assert storage.get_by_id(rid).push_status == "sent"
```

- [ ] **Step 2: Run test to verify it passes**

The orchestrator already has push logic (Task 11). Run:

```bash
pytest platform/tests/test_daily_report_orchestrator.py::test_run_calls_pusher_when_subscription_given -v
```
Expected: PASS (no implementation change needed).

- [ ] **Step 3: Commit**

```bash
git add platform/tests/test_daily_report_orchestrator.py
git commit -m "test(daily-report): orchestrator push integration"
```

---

## Task 14: scheduler.py — load subscriptions + cron loop

**Files:**
- Create: `platform/platform_app/daily_report/scheduler.py`
- Create: `platform/tests/test_daily_report_scheduler.py`

- [ ] **Step 1: Write failing test**

Create `platform/tests/test_daily_report_scheduler.py`:

```python
"""Scheduler tests — uses fake time + mocks orchestrator.run."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from platform_app.daily_report import scheduler, storage
from platform_app import db


def _seed_yinhu_daily_report_tenant() -> None:
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report',"
        " 'http://x','secret','k1','yinhu-daily-uid',0)"
    )


def test_compute_next_fire_uses_subscription_cron_and_tz():
    sub = storage.Subscription(
        id="s1", tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="u",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales"], enabled=True,
    )
    # Sunday 2026-05-03 23:00 Shanghai → next is Mon 2026-05-04 07:30 Shanghai
    base = datetime(2026, 5, 3, 23, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    nxt = scheduler.compute_next_fire(sub, now=base)
    assert nxt == datetime(2026, 5, 4, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_compute_next_fire_skips_weekend():
    sub = storage.Subscription(
        id="s1", tenant_id="yinhu", recipient_label="x",
        push_channel="dingtalk", push_target="u",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales"], enabled=True,
    )
    # Friday 2026-05-08 08:00 → next is Mon 2026-05-11 07:30
    base = datetime(2026, 5, 8, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    nxt = scheduler.compute_next_fire(sub, now=base)
    assert nxt == datetime(2026, 5, 11, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


@pytest.mark.asyncio
async def test_loop_fires_orchestrator_when_due(monkeypatch):
    _seed_yinhu_daily_report_tenant()
    storage.create_subscription(
        tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="* * * * *",  # every minute, fires immediately on next tick
        sections_enabled=["sales"],
    )

    fired: list[tuple] = []

    async def fake_run(**kw):
        fired.append(kw)
        return "rid-fake"

    monkeypatch.setattr(scheduler, "_orchestrator_run", fake_run)
    # Tick faster than 60s for test.
    monkeypatch.setattr(scheduler, "_TICK_SECONDS", 0.05)

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(fired) >= 1
    assert fired[0]["tenant_id"] == "yinhu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest platform/tests/test_daily_report_scheduler.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement scheduler**

Create `platform/platform_app/daily_report/scheduler.py`:

```python
"""Cron loop driving daily report generation.

Croniter computes next fire time per subscription; one async loop sleeps until
the soonest fire then dispatches orchestrator.run. Subscriptions are reloaded
from the DB once per loop iteration so adds/removes pick up without restart.
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo
from croniter import croniter
from . import orchestrator, storage
from .pushers.dingtalk import DingTalkPusher

_TICK_SECONDS: float = 60.0  # default cap; tests override
_pusher = DingTalkPusher()


def compute_next_fire(sub: storage.Subscription, *, now: datetime) -> datetime:
    """Next fire time for this subscription strictly after `now`."""
    tz = ZoneInfo(sub.timezone)
    base = now.astimezone(tz)
    it = croniter(sub.push_cron, base)
    return it.get_next(datetime).replace(tzinfo=tz)


# Indirection for test monkeypatching.
async def _orchestrator_run(**kw):
    return await orchestrator.run(**kw)


async def run_forever() -> None:
    """Top-level scheduler loop. Cancellable from lifespan shutdown."""
    while True:
        try:
            await _tick_once()
        except Exception as e:
            # Never let scheduler die on a bad sub.
            print(f"[daily-report scheduler] tick error: {e!r}", flush=True)
        await asyncio.sleep(_TICK_SECONDS)


async def _tick_once() -> None:
    subs = storage.list_enabled_subscriptions()
    if not subs:
        return
    now = datetime.now(tz=ZoneInfo("UTC"))
    for sub in subs:
        # Fire if next-fire-from-(now-tick) ≤ now, i.e. due within last tick window.
        prev_window = now.timestamp() - _TICK_SECONDS - 1
        prev_dt = datetime.fromtimestamp(prev_window, tz=ZoneInfo("UTC"))
        next_fire = compute_next_fire(sub, now=prev_dt)
        if next_fire.timestamp() <= now.timestamp():
            asyncio.create_task(_dispatch(sub))


async def _dispatch(sub: storage.Subscription) -> None:
    today = date.today()
    await _orchestrator_run(
        tenant_id=sub.tenant_id,
        report_date=today,
        pusher=_pusher,
        subscription=sub,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_scheduler.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/scheduler.py \
        platform/tests/test_daily_report_scheduler.py
git commit -m "feat(daily-report): scheduler cron loop"
```

---

## Task 15: api.py — REST endpoints (list / detail / regenerate)

**Files:**
- Create: `platform/platform_app/daily_report/api.py`
- Create: `platform/tests/test_daily_report_api.py`

- [ ] **Step 1: Write failing tests**

Create `platform/tests/test_daily_report_api.py`:

```python
"""REST API tests using FastAPI TestClient."""
from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from platform_app import db
from platform_app.daily_report import storage


def _seed_user_and_tenant() -> tuple[str, str]:
    """Returns (user_id, session_id). Uses enterprise_members ACL (post-migration 004)."""
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u1', 'alice', 'x', 'Alice', 0)"
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('yinhu','Yinhu','银湖','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report','http://x','s','k1','y-d-uid',0)"
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u1','yinhu','member',0)"
    )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-1','u1','csrf-1',0,9999999999)"
    )
    return "u1", "sess-1"


@pytest.fixture
def client():
    from platform_app.main import app
    return TestClient(app)


def test_list_reports_requires_login(client):
    resp = client.get("/api/daily-report/reports?tenant=yinhu")
    assert resp.status_code == 401


def test_list_reports_returns_metadata_only(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid, status="ready",
        content_md="# big body", content_html="<h1>big body</h1>",
        sections_json={"sales": {"status": "ok"}}, raw_collectors={},
        generated_at=datetime(2026, 5, 6, 7, 30),
    )
    resp = client.get(
        "/api/daily-report/reports?tenant=yinhu",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    items = resp.json()["reports"]
    assert len(items) == 1
    assert items[0]["status"] == "ready"
    assert items[0]["report_date"] == "2026-05-06"
    assert "content_md" not in items[0]  # metadata only


def test_get_report_detail_returns_html(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid, status="ready",
        content_md="# x", content_html="<h1>x</h1>",
        sections_json={"sales": {"status": "ok"}}, raw_collectors={"foo": "bar"},
        generated_at=datetime(2026, 5, 6, 7, 30),
    )
    resp = client.get(
        f"/api/daily-report/reports/{rid}",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_html"] == "<h1>x</h1>"
    assert body["sections_json"]["sales"]["status"] == "ok"


def test_cross_tenant_access_denied(client):
    _, sid = _seed_user_and_tenant()
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('other','Other','Other','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('other','daily-report','x','http://x','s','k1','o-d-uid',0)"
    )
    resp = client.get(
        "/api/daily-report/reports?tenant=other",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest platform/tests/test_daily_report_api.py -v`
Expected: 404s — router not yet registered.

- [ ] **Step 3: Implement API router (REST only — HTML routes in next task)**

Create `platform/platform_app/daily_report/api.py`:

```python
"""REST + HTML routes for daily report dashboard."""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, HTTPException, Query, Request
from .. import api as platform_api, db
from . import storage

router = APIRouter()


@router.get("/api/daily-report/reports")
def list_reports(request: Request, tenant: str = Query(...), limit: int = Query(30, le=100)):
    user = platform_api._user_from_request(request)
    _enforce_tenant_acl(user, tenant)
    rows = storage.list_reports(tenant_id=tenant, limit=limit)
    return {"reports": [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "report_date": r.report_date.isoformat(),
            "status": r.status,
            "push_status": r.push_status,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        } for r in rows
    ]}


@router.get("/api/daily-report/reports/{report_id}")
def get_report(request: Request, report_id: str):
    user = platform_api._user_from_request(request)
    row = storage.get_by_id(report_id)
    if row is None:
        raise HTTPException(404, {"error": "not_found"})
    _enforce_tenant_acl(user, row.tenant_id)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "report_date": row.report_date.isoformat(),
        "status": row.status,
        "content_html": row.content_html,
        "content_md": row.content_md,
        "sections_json": row.sections_json,
        "push_status": row.push_status,
        "push_error": row.push_error,
        "error": row.error,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


def _enforce_tenant_acl(user: dict, tenant: str) -> None:
    """Allow if user has has_acl(user, tenant, 'daily-report'). Admin bypasses.

    Reuses platform's ACL helper (post-migration 004), which checks
    enterprise_members ∪ agent_grants.
    """
    if user.get("role") == "admin":
        return
    if not db.has_acl(user["id"], tenant, "daily-report"):
        raise HTTPException(403, {"error": "not_authorized_for_tenant"})
```

- [ ] **Step 4: Wire into main.py**

Edit `platform/platform_app/main.py`. After the existing `app.include_router(data_api.router)` line, add:

```python
from .daily_report import api as daily_report_api
app.include_router(daily_report_api.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_api.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add platform/platform_app/daily_report/api.py \
        platform/platform_app/main.py \
        platform/tests/test_daily_report_api.py
git commit -m "feat(daily-report): REST list/detail with tenant ACL"
```

---

## Task 16: api.py — POST regenerate endpoint

**Files:**
- Modify: `platform/platform_app/daily_report/api.py`
- Modify: `platform/tests/test_daily_report_api.py`

- [ ] **Step 1: Write failing test**

Append to `platform/tests/test_daily_report_api.py`:

```python
def test_regenerate_deletes_existing_and_returns_new_id(client, monkeypatch):
    _, sid = _seed_user_and_tenant()
    old_rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_failure(report_id=old_rid, status="failed", error="x")

    new_rid_holder = {}

    async def fake_run(**kw):
        from platform_app.daily_report import storage as s
        rid = s.create_running(tenant_id=kw["tenant_id"], report_date=kw["report_date"])
        new_rid_holder["rid"] = rid
        return rid

    from platform_app.daily_report import api as api_mod
    monkeypatch.setattr(api_mod, "_orchestrator_run", fake_run)

    resp = client.post(
        "/api/daily-report/reports/yinhu/regenerate",
        json={"date": "2026-05-06"},
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == new_rid_holder["rid"]
    assert body["report_id"] != old_rid  # new row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest platform/tests/test_daily_report_api.py::test_regenerate_deletes_existing_and_returns_new_id -v`
Expected: 404 (endpoint not registered).

- [ ] **Step 3: Implement regenerate endpoint**

Append to `platform/platform_app/daily_report/api.py`:

```python
from datetime import date as _date_cls
from pydantic import BaseModel
from . import orchestrator
from .pushers.dingtalk import DingTalkPusher

_pusher = DingTalkPusher()


class RegenerateBody(BaseModel):
    date: str  # YYYY-MM-DD


# Indirection for tests.
async def _orchestrator_run(**kw):
    return await orchestrator.run(**kw)


@router.post("/api/daily-report/reports/{tenant}/regenerate")
async def regenerate(request: Request, tenant: str, body: RegenerateBody):
    user = platform_api._user_from_request(request)
    _enforce_tenant_acl(user, tenant)
    try:
        rd = _date_cls.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, {"error": "bad_date"})
    storage.delete_by_tenant_date(tenant_id=tenant, report_date=rd)
    # Look up active subscription for this tenant (single recipient in MVP).
    sub = next((s for s in storage.list_enabled_subscriptions() if s.tenant_id == tenant), None)
    rid = await _orchestrator_run(
        tenant_id=tenant, report_date=rd,
        pusher=_pusher if sub else None, subscription=sub,
    )
    return {"report_id": rid}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest platform/tests/test_daily_report_api.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add platform/platform_app/daily_report/api.py \
        platform/tests/test_daily_report_api.py
git commit -m "feat(daily-report): POST regenerate endpoint"
```

---

## Task 17: api.py — HTML routes for /daily-report and /daily-report/{id}

**Files:**
- Modify: `platform/platform_app/daily_report/api.py`
- Modify: `platform/tests/test_daily_report_api.py`

- [ ] **Step 1: Write failing test**

Append to `platform/tests/test_daily_report_api.py`:

```python
def test_html_list_page_redirects_to_login_when_no_cookie(client):
    resp = client.get("/daily-report", follow_redirects=False)
    assert resp.status_code == 200
    assert b"<title>" in resp.content
    # The login.html or daily-report.html — easier to just check it's HTML.


def test_html_list_page_when_logged_in(client):
    _, sid = _seed_user_and_tenant()
    resp = client.get("/daily-report", cookies={"app_session": sid})
    assert resp.status_code == 200
    assert b"daily" in resp.content.lower() or b"\xe6\x97\xa5\xe6\x8a\xa5" in resp.content


def test_html_detail_page(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    resp = client.get(f"/daily-report/{rid}", cookies={"app_session": sid})
    assert resp.status_code == 200
    assert b"<html" in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest platform/tests/test_daily_report_api.py::test_html_list_page_when_logged_in -v`
Expected: 404 (route not registered).

- [ ] **Step 3: Implement HTML routes**

Append to `platform/platform_app/daily_report/api.py`:

```python
from pathlib import Path
from fastapi.responses import FileResponse

_STATIC = Path(__file__).resolve().parent.parent.parent / "static"
_NO_STORE = {"Cache-Control": "no-store, must-revalidate"}


@router.get("/daily-report")
@router.get("/daily-report/")
def html_list(request: Request):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "daily-report.html", headers=_NO_STORE)


@router.get("/daily-report/{report_id}")
def html_detail(request: Request, report_id: str):
    if not request.cookies.get("app_session"):
        return FileResponse(_STATIC / "login.html", headers=_NO_STORE)
    return FileResponse(_STATIC / "daily-report-detail.html", headers=_NO_STORE)
```

- [ ] **Step 4: Create placeholder HTML files so FileResponse doesn't 404**

Create `platform/static/daily-report.html`:

```html
<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<title>日报 · 运帷 AI</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
</head><body>
<h1>日报中心</h1>
<div id="reports">加载中...</div>
<script>
fetch('/api/daily-report/reports?tenant=yinhu')
  .then(r => r.json())
  .then(d => {
    const el = document.getElementById('reports');
    if (!d.reports || d.reports.length === 0) { el.textContent = '暂无日报'; return; }
    el.innerHTML = d.reports.map(r =>
      '<div style="padding:8px;border-bottom:1px solid #eee">' +
      '<a href="/daily-report/' + r.id + '">' + r.report_date + '</a> · ' + r.status +
      '</div>'
    ).join('');
  });
</script>
</body></html>
```

Create `platform/static/daily-report-detail.html`:

```html
<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/>
<title>日报详情 · 运帷 AI</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>body{max-width:800px;margin:24px auto;padding:0 16px;font-family:system-ui;line-height:1.6}</style>
</head><body>
<div id="header"></div>
<div id="content">加载中...</div>
<script>
const id = location.pathname.split('/').pop();
fetch('/api/daily-report/reports/' + id)
  .then(r => r.json())
  .then(d => {
    document.getElementById('header').innerHTML =
      '<h1>' + (d.report_date || '?') + ' · ' + (d.status || '?') + '</h1>' +
      '<button onclick="regen()">重新生成</button> ' +
      '<a href="/yinhu/super-xiaochen/?prefill=' +
        encodeURIComponent('刚才看了' + d.report_date + '的日报，能展开聊聊吗？') +
        '">问小陈</a>';
    document.getElementById('content').innerHTML = d.content_html || '<em>报告内容暂缺</em>';
  });
function regen() {
  fetch(location.pathname.replace('/daily-report/', '/api/daily-report/reports/yinhu/regenerate'),
    {method:'POST', headers:{'content-type':'application/json'},
     body: JSON.stringify({date: location.pathname.split('/').pop()})});
  alert('已触发重生成，几秒后刷新页面');
}
</script>
</body></html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest platform/tests/test_daily_report_api.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add platform/platform_app/daily_report/api.py \
        platform/static/daily-report.html \
        platform/static/daily-report-detail.html \
        platform/tests/test_daily_report_api.py
git commit -m "feat(daily-report): dashboard HTML pages + 'ask 小陈' button"
```

---

## Task 18: main.py — start scheduler in lifespan

**Files:**
- Modify: `platform/platform_app/main.py`

- [ ] **Step 1: Update lifespan to start scheduler**

In `platform/platform_app/main.py`, replace the existing `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    from . import health
    from .daily_report import scheduler as dr_scheduler
    health_task = asyncio.create_task(health.probe_loop())
    scheduler_task = asyncio.create_task(dr_scheduler.run_forever())
    yield
    health_task.cancel()
    scheduler_task.cancel()
```

- [ ] **Step 2: Smoke-test app startup**

Run:
```bash
cd platform && python -c "
import os
os.environ.setdefault('DATABASE_URL','postgresql://postgres:test@localhost:5433/test')
os.environ.setdefault('REDIS_URL','redis://localhost:6380')
os.environ.setdefault('COOKIE_SECRET','test-cookie-secret-32-bytes-padding=')
from platform_app.main import app
print('app loaded; routes:', len(app.routes))
"
```
Expected: `app loaded; routes: <some number>`. No traceback.

- [ ] **Step 3: Run full test suite**

Run: `pytest platform/tests -v -x`
Expected: all tests pass (including pre-existing).

- [ ] **Step 4: Commit**

```bash
git add platform/platform_app/main.py
git commit -m "feat(daily-report): start scheduler in app lifespan"
```

---

## Task 19: Bootstrap runbook for yinhu deployment

**Files:**
- Create: `docs/superpowers/runbooks/2026-05-06-daily-report-yinhu-bootstrap.md`

- [ ] **Step 1: Write the runbook**

Create `docs/superpowers/runbooks/2026-05-06-daily-report-yinhu-bootstrap.md`:

```markdown
# Bootstrap: 银湖日报上线 SQL + env

> Runbook · 2026-05-06 · 触发：platform 侧 daily-report 阶段 1 完成 + 钉钉审批通过
>
> 配套 spec: `docs/superpowers/specs/2026-05-06-ceo-daily-report-platform-design.md`

## 前置

- [ ] platform Postgres 迁移 004 已应用（`daily_reports` / `daily_report_subscriptions` 表存在）
- [ ] yinhu container daily-report 子路由已部署到 Railway（容器侧 spec 阶段 1 完成）
- [ ] 银湖钉钉企业管理员审批通过：「工作消息发送」+「企业群消息读取」+「通讯录读取」
- [ ] 银湖 IT 提供：钉钉 Client ID / Client Secret / AgentId / RobotCode / 许总 userid

## 1. platform Railway env

在 platform Railway service 设置以下 env vars：

```
DINGTALK_CLIENT_ID=<dingxxx...>
DINGTALK_CLIENT_SECRET=<...>
DINGTALK_AGENT_ID=4527131008
DINGTALK_ROBOT_CODE=<...>
```

> ⚠️ Client Secret 不入 git。

## 2. 注册 (yinhu, daily-report) tenant

```sql
-- 生成新的 HMAC secret pair（与 super-xiaochen 不复用）
-- 在本地：
--   python -c "import secrets; print(secrets.token_urlsafe(32))"

INSERT INTO tenants (
  client_id, agent_id, display_name,
  container_url, hmac_secret_current, hmac_key_id_current,
  tenant_uid, active, created_at
) VALUES (
  'yinhu', 'daily-report', '日报',
  'http://customer-yinhu.railway.internal:8000',
  '<新 HMAC secret>', 'k-daily-1',
  'yinhu-daily-report-uid', 1, EXTRACT(EPOCH FROM NOW())::BIGINT
);
```

将相同的 HMAC secret 设置到 yinhu container env：
```
HMAC_SECRET_CURRENT=<同上>
HMAC_KEY_ID_CURRENT=k-daily-1
```

> 容器内 super-xiaochen + daily-report 共用一个 HMAC pair（同一容器只有一对凭证），二者通过 `X-Tenant-Agent` header 区分。

## 3. 给许总授权 ACL（dashboard 可见性）

```sql
-- 假设许总在 platform 已有用户行 user_id='u-xu-zong'
-- 银湖 enterprise 由 migration 004 backfill 自动建好；如未建则先 INSERT enterprises
INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at)
VALUES ('u-xu-zong', 'yinhu', 'member',
        EXTRACT(EPOCH FROM NOW())::BIGINT)
ON CONFLICT (user_id, enterprise_id) DO NOTHING;
```

## 4. 创建日报订阅

```sql
INSERT INTO daily_report_subscriptions (
  tenant_id, recipient_label, push_channel, push_target, push_cron,
  timezone, sections_enabled, enabled
) VALUES (
  'yinhu', '许总', 'dingtalk', '<许总 userid>', '30 7 * * 1-5',
  'Asia/Shanghai',
  ARRAY['sales','production','chat','customer_news']::TEXT[],
  true
);
```

## 5. 冒烟验证

```bash
# 强制立刻生成一份（dashboard 重生成按钮也行）
curl -X POST -b "app_session=<管理员 session>" \
  -H 'content-type: application/json' \
  -d '{"date":"2026-05-06"}' \
  https://app.fiveoranges.ai/api/daily-report/reports/yinhu/regenerate
# → {"report_id": "..."}

# 浏览器打开 https://app.fiveoranges.ai/daily-report/<rid> 看渲染
# 钉钉 → 许总测试号 → 应收到 markdown 卡片
```

## 6. 启用 cron

环境变量 + 订阅 + tenant 都到位后，scheduler 在下一个 07:30 上海时间自动触发。无需额外操作。
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/runbooks/2026-05-06-daily-report-yinhu-bootstrap.md
git commit -m "docs(daily-report): yinhu deployment bootstrap runbook"
```

---

## Task 20: Final integration test — full stack with mock container

**Files:**
- Create: `platform/tests/test_daily_report_e2e.py`

- [ ] **Step 1: Write the e2e test**

Create `platform/tests/test_daily_report_e2e.py`:

```python
"""End-to-end: scheduler tick → orchestrator → DB → API list/detail."""
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
import pytest
import httpx
import respx
from fastapi.testclient import TestClient
from platform_app import db
from platform_app.daily_report import orchestrator, storage

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "sample_collector_response.json").read_text()
)


def _seed_full_setup():
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u1','alice','x','Alice',0)"
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('yinhu','Yinhu','银湖','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','日报',"
        "'http://yinhu-container.test:8000','secret-x','k1','yinhu-daily-uid',0)"
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u1','yinhu','member',0)"
    )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-1','u1','c1',0,9999999999)"
    )


@pytest.mark.asyncio
async def test_full_flow_orchestrator_then_api_list():
    _seed_full_setup()
    with respx.mock() as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=_FIXTURE)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )

    from platform_app.main import app
    client = TestClient(app)
    list_resp = client.get(
        "/api/daily-report/reports?tenant=yinhu",
        cookies={"app_session": "sess-1"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["reports"][0]["id"] == rid

    detail_resp = client.get(
        f"/api/daily-report/reports/{rid}",
        cookies={"app_session": "sess-1"},
    )
    assert detail_resp.status_code == 200
    assert "银湖经营快报" in detail_resp.json()["content_md"]
    assert "<h1>" in detail_resp.json()["content_html"]
```

- [ ] **Step 2: Run the test**

Run: `pytest platform/tests/test_daily_report_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

Run: `pytest platform/tests -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add platform/tests/test_daily_report_e2e.py
git commit -m "test(daily-report): e2e — orchestrator + API list/detail"
```

---

## Done — what's next

After all 20 tasks land:

1. **Push branch** (already on `design/ceo-daily-report-spec`):
   ```bash
   git push
   ```
2. **Wait for yinhu container side** to reach its plan's阶段 1 (kingdee collectors + entry).
3. **Joint dry-run**: deploy both sides to dev, manually trigger regenerate via dashboard, verify report renders.
4. **Run runbook (Task 19)** when钉钉审批 + 银湖 IT 凭证全部到位.
5. **Schedule first真实 push**: scheduler picks up subscription automatically; first 07:30 (上海) 周一 fires.

## Out of scope for this plan (defer to v1+)

- 邮件 push 通道
- 订阅 CRUD UI
- 多收件人
- 节假日感知
- 多 platform 实例 access_token Redis 共享
- 详情页"问小陈"深度上下文注入（需要小陈侧改动；当前只做 prefill query）
