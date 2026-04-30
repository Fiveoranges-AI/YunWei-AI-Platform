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
