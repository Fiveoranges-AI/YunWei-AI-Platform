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
