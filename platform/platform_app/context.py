"""Server-side auth + enterprise context.

This is the single source of truth for ``user_id`` / ``enterprise_id`` /
``plan`` / ``role`` used by ``/win/api/*``, the shared assistant, and the
runtime resolver. Data isolation must never be derived from a request
body or LLM tool argument; everything reads from this context.

The cookie format and one-user-to-first-enterprise behaviour are
unchanged from the previous inlined middleware in ``main.py``; this
module just centralises the lookup so other code paths can reuse it.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from . import auth, db


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    username: str
    display_name: str
    session_id: str
    enterprise_id: str
    enterprise_plan: str
    enterprise_role: str


def require_auth_context(request: Request) -> AuthContext:
    """Resolve the caller's :class:`AuthContext` or raise ``HTTPException``.

    - Missing / invalid ``app_session`` cookie → 401 ``not_logged_in``.
    - Logged in but with no enterprise membership → 403 ``no_enterprise``.

    Otherwise returns the first enterprise the user belongs to
    (deterministic, matches existing behaviour).
    """
    cookie = request.cookies.get("app_session")
    user = auth.current_user_from_request(cookie)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "not_logged_in", "message": "请登录"},
        )
    enterprises = db.list_user_enterprises(user["id"])
    if not enterprises:
        raise HTTPException(
            status_code=403,
            detail={"error": "no_enterprise", "message": "当前账号未绑定企业"},
        )
    ent = enterprises[0]
    return AuthContext(
        user_id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        session_id=user["session_id"],
        enterprise_id=ent["id"],
        enterprise_plan=ent.get("plan") or "trial",
        enterprise_role=ent.get("role") or "member",
    )
