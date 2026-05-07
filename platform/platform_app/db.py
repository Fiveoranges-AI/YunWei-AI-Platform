"""Postgres connection + migrations + cache helpers.

v1.4: dropped sqlite + in-memory TTLCache. Backend is Postgres (psycopg)
plus Redis (cache.py). One shared connection with autocommit; OK for
single-uvicorn-worker hobby load. Bump to ConnectionPool when scaling.
"""
from __future__ import annotations
import time
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from .cache import tenant_cache, session_cache, acl_cache
from .settings import settings

_CONN: psycopg.Connection | None = None


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url,
        autocommit=True,
        row_factory=dict_row,
    )


class _DB:
    """Wrapper that auto-reconnects on broken connection so callers can
    keep the simple sqlite-shape API (`.execute(sql, params).fetchone()`).
    """

    def __init__(self) -> None:
        self._conn: psycopg.Connection | None = None

    def _get(self) -> psycopg.Connection:
        if self._conn is None or self._conn.closed:
            self._conn = _connect()
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> psycopg.Cursor:
        try:
            return self._get().execute(sql, params)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            # connection dropped; reconnect once
            self._conn = None
            return self._get().execute(sql, params)


_MAIN: _DB | None = None


def init() -> None:
    global _MAIN
    _MAIN = _DB()
    _migrate()


def _migrate() -> None:
    migrations_dir = Path(__file__).parent.parent / "migrations"
    files = sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
    assert _MAIN
    with _MAIN._get().cursor() as cur:
        for f in files:
            cur.execute(f.read_text())


def main() -> _DB:
    assert _MAIN, "db.init() not called"
    return _MAIN


# v1.2 had a separate _PROXY_DB sqlite file; in Postgres everything is one DB.
# Keep proxy_log_db() as alias for callsite stability.
def proxy_log_db() -> _DB:
    return main()


# ─── tenants ────────────────────────────────────────────────────

def get_tenant(client_id: str, agent_id: str) -> dict | None:
    key = f"{client_id}:{agent_id}"
    cached = tenant_cache.get(key)
    if cached is not None:
        return cached
    row = main().execute(
        "SELECT * FROM tenants WHERE client_id=%s AND agent_id=%s AND active=1",
        (client_id, agent_id),
    ).fetchone()
    if row:
        tenant_cache.set(key, dict(row))
    return row


def invalidate_tenant(client_id: str, agent_id: str) -> None:
    tenant_cache.delete(f"{client_id}:{agent_id}")


# ─── sessions ───────────────────────────────────────────────────

def get_session(session_id: str) -> dict | None:
    cached = session_cache.get(session_id)
    if cached is not None:
        if cached["expires_at"] > int(time.time()):
            return cached
        session_cache.delete(session_id)
        return None
    row = main().execute(
        "SELECT * FROM platform_sessions WHERE id=%s AND expires_at>%s",
        (session_id, int(time.time())),
    ).fetchone()
    if row:
        session_cache.set(session_id, dict(row))
    return row


def invalidate_session(session_id: str) -> None:
    session_cache.delete(session_id)


# ─── ACL ────────────────────────────────────────────────────────
#
# Migration 004 introduced enterprise_members + agent_grants. has_acl
# now grants access if EITHER:
#   - the user is a member of the enterprise (= legacy client_id), OR
#   - the user has an explicit per-agent grant (consultant exception).

_ROLE_RANK = {"member": 0, "admin": 1, "owner": 2}


def has_acl(user_id: str, client_id: str, agent_id: str) -> bool:
    key = f"{user_id}:{client_id}:{agent_id}"
    cached = acl_cache.get(key)
    if cached is not None:
        return cached
    row = main().execute(
        "SELECT 1 FROM enterprise_members "
        "WHERE user_id=%s AND enterprise_id=%s "
        "UNION ALL "
        "SELECT 1 FROM agent_grants "
        "WHERE user_id=%s AND client_id=%s AND agent_id=%s "
        "LIMIT 1",
        (user_id, client_id, user_id, client_id, agent_id),
    ).fetchone()
    result = row is not None
    acl_cache.set(key, result)
    return result


def invalidate_acl(user_id: str, client_id: str, agent_id: str) -> None:
    acl_cache.delete(f"{user_id}:{client_id}:{agent_id}")


def is_enterprise_member(user_id: str, enterprise_id: str) -> bool:
    row = main().execute(
        "SELECT 1 FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        (user_id, enterprise_id),
    ).fetchone()
    return row is not None


def get_enterprise_role(user_id: str, enterprise_id: str) -> str | None:
    row = main().execute(
        "SELECT role FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        (user_id, enterprise_id),
    ).fetchone()
    return row["role"] if row else None


def list_user_enterprises(user_id: str) -> list[dict]:
    """Return enterprises the user belongs to (as a member). Used by the
    data center to populate the client switcher."""
    rows = main().execute(
        "SELECT e.id, e.display_name, e.legal_name, em.role "
        "FROM enterprises e "
        "JOIN enterprise_members em ON em.enterprise_id = e.id "
        "WHERE em.user_id=%s AND e.active=1 "
        "ORDER BY e.display_name",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Platform admin (cross-enterprise) ──────────────────────────

def is_platform_admin(user_id: str) -> bool:
    row = main().execute(
        "SELECT is_platform_admin FROM users WHERE id=%s", (user_id,),
    ).fetchone()
    return bool(row and row["is_platform_admin"])


def invalidate_acl_for_enterprise(user_id: str, enterprise_id: str) -> None:
    """Drop cached has_acl entries for every (client, agent) under the
    enterprise — used after membership add/remove."""
    rows = main().execute(
        "SELECT agent_id FROM tenants WHERE client_id=%s",
        (enterprise_id,),
    ).fetchall()
    for r in rows:
        invalidate_acl(user_id, enterprise_id, r["agent_id"])


# ─── proxy_log ──────────────────────────────────────────────────

def write_proxy_log(
    *, user_id: str | None, client_id: str | None, agent_id: str | None,
    method: str, path: str, status: int, duration_ms: int, ip: str | None,
) -> None:
    proxy_log_db().execute(
        "INSERT INTO proxy_log (ts, user_id, client_id, agent_id, method, path, status, duration_ms, ip) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (int(time.time()), user_id, client_id, agent_id, method, path, status, duration_ms, ip),
    )
