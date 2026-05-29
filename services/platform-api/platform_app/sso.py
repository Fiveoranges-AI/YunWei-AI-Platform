"""SSO bootstrap for super-xiaochen.

User clicks the win-web entry → /sso/super-xiaochen → we verify their
app_session, check ACL via has_acl(), sign a 60s HMAC token, and
303-redirect to the super-xiaochen Railway URL with the token in the
query string. super-xiaochen's /sso/accept exchanges it for a 7-day
session cookie.

Reuses the HMAC secret/key_id stored in the tenants table — same key
the daily-report orchestrator uses for server-to-server calls.

Token format (mirrors yinhu-super-xiaochen/session_cookie.py):
  base64url(json(claims)) + "." + base64url(hmac_sha256(secret, payload))
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import db
from .context import require_auth_context

router = APIRouter()

_CLIENT_ID = "yinhu"
_AGENT_ID = "super-xiaochen"
_DEFAULT_URL = "https://agent-yinhu-super-xiaochen-production.up.railway.app"


def _b64url_enc(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_dec(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(secret: str, payload_b64: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url_enc(sig)


def sign_bootstrap_token(
    *, secret: str, key_id: str,
    user_id: str, user_name: str, user_role: str,
    ttl_seconds: int = 60,
) -> str:
    claims = {
        "sub": user_id,
        "name": user_name,
        "role": user_role,
        "exp": int(time.time()) + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "kid": key_id,
    }
    body = json.dumps(claims, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = _b64url_enc(body)
    return f"{payload}.{_sign(secret, payload)}"


def _verify_for_test(token: str, *, secrets: dict[str, str]) -> dict:
    """Test helper — mirrors verify on super-xiaochen side, minus the
    nonce check. Real verification happens in the container.

    Mirrors super-xiaochen's `_decode_signed` semantics: any structural
    failure (malformed payload, unknown kid, bad signature) collapses to
    'signature mismatch' so a kid is never an oracle.
    """
    try:
        payload_b64, sig = token.split(".")
    except ValueError:
        raise ValueError("malformed token")
    try:
        claims = json.loads(_b64url_dec(payload_b64))
    except (json.JSONDecodeError, ValueError):
        raise ValueError("signature mismatch")
    if not isinstance(claims, dict):
        raise ValueError("signature mismatch")
    kid = claims.get("kid")
    secret = secrets.get(kid) if isinstance(kid, str) else None
    if secret is None:
        raise ValueError("signature mismatch")
    expected = _sign(secret, payload_b64)
    if not hmac.compare_digest(expected, sig):
        raise ValueError("signature mismatch")
    if int(claims.get("exp", 0)) < int(time.time()):
        raise ValueError("expired")
    return claims


@router.get("/sso/super-xiaochen")
def sso_super_xiaochen(request: Request):
    # 1. require login — bounce to / which serves login.html when no cookie
    if not request.cookies.get("app_session"):
        return RedirectResponse("/", status_code=302)
    try:
        ctx = require_auth_context(request)
    except HTTPException as exc:
        # 401 = stale/invalid cookie → back to login. Anything else (e.g.
        # 403 no_enterprise) means the cookie is valid but the user can't
        # access super-xiaochen — surface as 403 below.
        if exc.status_code == 401:
            return RedirectResponse("/", status_code=302)
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8>"
            "<h1>403</h1><p>当前账号无权访问超级小陈。</p>",
            status_code=403,
        )

    # 2. ACL gate
    if not db.has_acl(ctx.user_id, _CLIENT_ID, _AGENT_ID):
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8>"
            "<h1>403</h1><p>当前账号无权访问超级小陈。</p>",
            status_code=403,
        )

    # 3. fetch shared HMAC secret from tenants row
    row = db.main().execute(
        "SELECT hmac_secret_current, hmac_key_id_current FROM tenants "
        "WHERE client_id=%s AND agent_id=%s",
        (_CLIENT_ID, _AGENT_ID),
    ).fetchone()
    if not row:
        raise HTTPException(500, "super-xiaochen tenant not registered")

    # 4. sign bootstrap token
    token = sign_bootstrap_token(
        secret=row["hmac_secret_current"],
        key_id=row["hmac_key_id_current"],
        user_id=ctx.user_id,
        user_name=ctx.display_name,
        user_role=ctx.enterprise_role,
    )

    # 5. 303 to super-xiaochen
    base = os.environ.get("SUPER_XIAOCHEN_PUBLIC_URL", _DEFAULT_URL)
    return RedirectResponse(f"{base}/sso/accept?t={token}", status_code=303)
