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
    data center to populate the client switcher and by ``context.require_auth_context``
    to resolve the caller's plan + role."""
    rows = main().execute(
        "SELECT e.id, e.display_name, e.legal_name, e.plan, em.role "
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


# ─── invite codes (migration 009) ───────────────────────────────


class InviteError(Exception):
    """Domain-specific failure during invite redemption.

    `code` is a stable error tag (invalid_code / code_redeemed /
    code_revoked / code_expired / username_taken); `message` is a
    Chinese end-user message safe to surface in the register page.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def redeem_invite_and_register(
    *,
    invite_code: str,
    user_id: str,
    username: str,
    password_hash: str,
    display_name: str,
    email: str | None,
    enterprise_id: str,
) -> None:
    """Atomic flow for /api/auth/register: redeem the invite + create the user
    + create the per-user enterprise + add membership row. All-or-nothing.

    Raises InviteError on user-fixable failures (bad code, already used,
    username taken). Other exceptions propagate so they get logged.
    """
    conn = main()._get()
    with conn.transaction():
        # 1. Lock the invite row so concurrent redeems serialize.
        row = conn.execute(
            "SELECT redeemed_at, revoked_at, expires_at "
            "  FROM invite_codes WHERE code = %s FOR UPDATE",
            (invite_code,),
        ).fetchone()
        if not row:
            raise InviteError("invalid_code", "邀请码无效")
        if row["redeemed_at"]:
            raise InviteError("code_redeemed", "邀请码已使用")
        if row["revoked_at"]:
            raise InviteError("code_revoked", "邀请码已撤销")
        if row["expires_at"]:
            expired_row = conn.execute(
                "SELECT (expires_at < now()) AS expired "
                "FROM invite_codes WHERE code = %s",
                (invite_code,),
            ).fetchone()
            if expired_row and expired_row["expired"]:
                raise InviteError("code_expired", "邀请码已过期")

        # 2. Create user. (FK on invite_codes.redeemed_by_user_id requires
        #    the user row to exist before we mark the code redeemed.)
        now = int(time.time())
        try:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, display_name, email, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, username, password_hash, display_name, email or None, now),
            )
        except psycopg.errors.UniqueViolation as e:
            raise InviteError("username_taken", "用户名已被占用") from e

        # 3. Create per-user enterprise (id format e_<username>).
        conn.execute(
            "INSERT INTO enterprises "
            "(id, legal_name, display_name, plan, onboarding_stage, created_at) "
            "VALUES (%s, %s, %s, 'trial', 'signed_up', %s)",
            (enterprise_id, display_name, display_name, now),
        )

        # 4. Link user → enterprise as owner.
        conn.execute(
            "INSERT INTO enterprise_members "
            "(user_id, enterprise_id, role, granted_at, granted_by) "
            "VALUES (%s, %s, 'owner', %s, 'register-flow')",
            (user_id, enterprise_id, now),
        )

        # 5. Mark the code redeemed. We still hold the FOR UPDATE lock from
        #    step 1 so this is atomic with the user/enterprise creation.
        conn.execute(
            "UPDATE invite_codes "
            "   SET redeemed_at = now(), "
            "       redeemed_by_user_id = %s, "
            "       redeemed_enterprise_id = %s "
            " WHERE code = %s",
            (user_id, enterprise_id, invite_code),
        )


def get_invite(code: str) -> dict | None:
    row = main().execute(
        "SELECT code, created_at, expires_at, redeemed_at, revoked_at, "
        "       redeemed_by_user_id, redeemed_enterprise_id, note "
        "FROM invite_codes WHERE code=%s",
        (code,),
    ).fetchone()
    return dict(row) if row else None


def list_invites(active_only: bool = False) -> list[dict]:
    sql = (
        "SELECT code, created_at, expires_at, redeemed_at, revoked_at, "
        "       redeemed_by_user_id, redeemed_enterprise_id, note "
        "FROM invite_codes"
    )
    if active_only:
        sql += " WHERE redeemed_at IS NULL AND revoked_at IS NULL"
    sql += " ORDER BY created_at DESC"
    return [dict(r) for r in main().execute(sql).fetchall()]


def insert_invite(code: str, *, created_by: str | None, note: str | None,
                  expires_at_epoch: int | None) -> None:
    main().execute(
        "INSERT INTO invite_codes (code, created_by, note, expires_at) "
        "VALUES (%s, %s, %s, to_timestamp(%s))"
        if expires_at_epoch
        else
        "INSERT INTO invite_codes (code, created_by, note) "
        "VALUES (%s, %s, %s)",
        (code, created_by, note, expires_at_epoch) if expires_at_epoch else (code, created_by, note),
    )


def revoke_invite(code: str) -> bool:
    cur = main().execute(
        "UPDATE invite_codes SET revoked_at = now() "
        "WHERE code = %s AND revoked_at IS NULL "
        "RETURNING code",
        (code,),
    )
    return cur.rowcount == 1


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
