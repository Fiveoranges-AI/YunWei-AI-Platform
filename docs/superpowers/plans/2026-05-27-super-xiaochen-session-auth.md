# super-xiaochen Session Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users open super-xiaochen from the win-web entry by adding a session-cookie auth path alongside the existing HMAC verification.

**Architecture:** agent-platform mints a 60s HMAC-signed bootstrap token at `/sso/super-xiaochen`, 303-redirects to super-xiaochen's `/sso/accept`, which validates the token and sets a 7-day `sx_session` cookie. `require_auth` is reworked to try the cookie first then fall back to HMAC so server-to-server callers (daily-report orchestrator) keep working unchanged.

**Tech Stack:** Python 3 + FastAPI on both sides. HMAC-SHA256 via stdlib `hmac` + base64url-encoded JSON payloads — no JWT library. Existing `_HMAC_SECRETS` dict / `tenants` row supplies the shared key.

**Two repos in play:**
- `/Users/eason/yinhu-super-xiaochen` (Railway container)
- `/Users/eason/agent-platform` (platform-api + win-web)

**Design reference:** `docs/superpowers/specs/2026-05-27-super-xiaochen-session-auth-design.md`

---

## Task 1: super-xiaochen — `session_cookie.py` primitives

**Files:**
- Create: `/Users/eason/yinhu-super-xiaochen/session_cookie.py`
- Create: `/Users/eason/yinhu-super-xiaochen/tests/test_session_cookie.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/eason/yinhu-super-xiaochen/tests/test_session_cookie.py`:

```python
"""Tests for session-cookie + bootstrap-token signing primitives."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from session_cookie import (
    sign_bootstrap_token, verify_bootstrap_token,
    sign_session_cookie, verify_session_cookie,
)
from agent_auth import NonceStore

SECRET = "QXJiaXRyYXJ5MzJieXRlc2VjcmV0Zm9ydGVzdHM="
KEY_ID = "k1"
SECRETS = {KEY_ID: SECRET}


def _kwargs(**over):
    base = dict(
        secret=SECRET, key_id=KEY_ID,
        user_id="u_xuzong", user_name="许总", user_role="user",
    )
    base.update(over)
    return base


def test_bootstrap_roundtrip():
    token = sign_bootstrap_token(**_kwargs())
    nonce_store = NonceStore()
    claims = verify_bootstrap_token(token, secrets=SECRETS, nonce_store=nonce_store)
    assert claims["sub"] == "u_xuzong"
    assert claims["name"] == "许总"
    assert claims["role"] == "user"
    assert claims["kid"] == KEY_ID
    assert claims["exp"] > int(time.time())


def test_bootstrap_replay_rejected():
    token = sign_bootstrap_token(**_kwargs())
    nonce_store = NonceStore()
    verify_bootstrap_token(token, secrets=SECRETS, nonce_store=nonce_store)
    with pytest.raises(ValueError, match="replay"):
        verify_bootstrap_token(token, secrets=SECRETS, nonce_store=nonce_store)


def test_bootstrap_expired_rejected():
    token = sign_bootstrap_token(**_kwargs(), ttl_seconds=-1)
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="expired"):
        verify_bootstrap_token(token, secrets=SECRETS, nonce_store=nonce_store)


def test_bootstrap_tampered_signature_rejected():
    token = sign_bootstrap_token(**_kwargs())
    payload, _sig = token.split(".")
    bad = f"{payload}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="signature"):
        verify_bootstrap_token(bad, secrets=SECRETS, nonce_store=nonce_store)


def test_bootstrap_unknown_kid_rejected():
    token = sign_bootstrap_token(**_kwargs(key_id="other_kid"))
    nonce_store = NonceStore()
    with pytest.raises(ValueError, match="unknown key id"):
        verify_bootstrap_token(token, secrets=SECRETS, nonce_store=nonce_store)


def test_session_cookie_roundtrip():
    cookie = sign_session_cookie(**_kwargs())
    claims = verify_session_cookie(cookie, secrets=SECRETS)
    assert claims["sub"] == "u_xuzong"
    assert claims["name"] == "许总"
    # Default TTL is 7 days
    assert claims["exp"] > int(time.time()) + 6 * 86400


def test_session_cookie_expired_rejected():
    cookie = sign_session_cookie(**_kwargs(), ttl_seconds=-1)
    with pytest.raises(ValueError, match="expired"):
        verify_session_cookie(cookie, secrets=SECRETS)


def test_session_cookie_tampered_payload_rejected():
    cookie = sign_session_cookie(**_kwargs())
    payload, sig = cookie.split(".")
    bad = f"{payload}AAAA.{sig}"
    with pytest.raises(ValueError, match="signature"):
        verify_session_cookie(bad, secrets=SECRETS)


def test_session_cookie_no_nonce_check():
    """Same cookie used many times — that's normal browser behavior."""
    cookie = sign_session_cookie(**_kwargs())
    for _ in range(3):
        verify_session_cookie(cookie, secrets=SECRETS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_session_cookie.py -v`
Expected: ImportError / ModuleNotFoundError on `session_cookie`.

- [ ] **Step 3: Implement `session_cookie.py`**

Create `/Users/eason/yinhu-super-xiaochen/session_cookie.py`:

```python
"""SSO.md §1.3 — bootstrap-token + session-cookie sign / verify.

Sits next to agent_auth.py (HMAC headers) and reuses _HMAC_SECRETS.

Format:  base64url(json(claims)) + "." + base64url(hmac_sha256(secret, payload))
Algorithm:  HMAC-SHA256, stdlib only.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
import uuid


def _b64url_enc(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_dec(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(secret: str, payload_b64: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url_enc(sig)


def _encode_signed(secret: str, claims: dict) -> str:
    body = json.dumps(claims, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = _b64url_enc(body)
    return f"{payload}.{_sign(secret, payload)}"


def _decode_signed(token: str, *, secrets: dict[str, str]) -> dict:
    try:
        payload_b64, sig = token.split(".")
    except ValueError:
        raise ValueError("malformed token")
    try:
        claims = json.loads(_b64url_dec(payload_b64))
    except Exception:
        raise ValueError("malformed payload")
    kid = claims.get("kid")
    if kid not in secrets:
        raise ValueError("unknown key id")
    expected = _sign(secrets[kid], payload_b64)
    if not hmac.compare_digest(expected, sig):
        raise ValueError("signature mismatch")
    if int(claims.get("exp", 0)) < int(time.time()):
        raise ValueError("expired")
    return claims


def sign_bootstrap_token(
    *, secret: str, key_id: str,
    user_id: str, user_name: str, user_role: str,
    ttl_seconds: int = 60,
) -> str:
    return _encode_signed(secret, {
        "sub": user_id,
        "name": user_name,
        "role": user_role,
        "exp": int(time.time()) + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "kid": key_id,
    })


def verify_bootstrap_token(
    token: str, *, secrets: dict[str, str], nonce_store,
) -> dict:
    claims = _decode_signed(token, secrets=secrets)
    jti = claims.get("jti", "")
    if not jti:
        raise ValueError("missing jti")
    # NonceStore.check_and_add raises ValueError("replay detected") on duplicate.
    nonce_store.check_and_add(claims.get("kid", ""), jti, expiry=int(claims["exp"]) + 10)
    return claims


def sign_session_cookie(
    *, secret: str, key_id: str,
    user_id: str, user_name: str, user_role: str,
    ttl_seconds: int = 7 * 86400,
) -> str:
    return _encode_signed(secret, {
        "sub": user_id,
        "name": user_name,
        "role": user_role,
        "exp": int(time.time()) + ttl_seconds,
        "kid": key_id,
    })


def verify_session_cookie(cookie: str, *, secrets: dict[str, str]) -> dict:
    return _decode_signed(cookie, secrets=secrets)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_session_cookie.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/eason/yinhu-super-xiaochen
git add session_cookie.py tests/test_session_cookie.py
git commit -m "feat(auth): add session-cookie + bootstrap-token signing primitives"
```

---

## Task 2: super-xiaochen — `require_auth` cookie-first fallback

**Files:**
- Modify: `/Users/eason/yinhu-super-xiaochen/web_agent.py:124-149`
- Create: `/Users/eason/yinhu-super-xiaochen/tests/test_require_auth.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/eason/yinhu-super-xiaochen/tests/test_require_auth.py`:

```python
"""Tests for the cookie-first / HMAC-fallback require_auth dependency."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub envs BEFORE importing web_agent (it reads them at import time).
os.environ.setdefault("HMAC_KEY_ID_CURRENT", "k1")
os.environ.setdefault("HMAC_SECRET_CURRENT", "QXJiaXRyYXJ5MzJieXRlc2VjcmV0Zm9ydGVzdHM=")
os.environ.setdefault("TENANT_CLIENT", "yinhu")
os.environ.setdefault("TENANT_AGENT", "super-xiaochen")
os.environ.setdefault("SUPER_XIAOCHEN_DB", ":memory:")

import pytest
from fastapi.testclient import TestClient
import web_agent
from session_cookie import sign_session_cookie

SECRET = os.environ["HMAC_SECRET_CURRENT"]
KEY_ID = os.environ["HMAC_KEY_ID_CURRENT"]


@pytest.fixture
def client():
    return TestClient(web_agent.app)


def test_healthz_no_auth(client):
    """Healthcheck endpoint must remain public."""
    r = client.get("/healthz")
    assert r.status_code == 200


def test_no_credentials_rejected(client):
    r = client.get("/sessions")
    assert r.status_code == 401


def test_session_cookie_accepted(client):
    cookie = sign_session_cookie(
        secret=SECRET, key_id=KEY_ID,
        user_id="u_xuzong", user_name="许总", user_role="user",
    )
    # Bypass DB by hitting /sessions which only needs user_id; if DB
    # isn't available the 5xx still proves auth let us through.
    r = client.get("/sessions", cookies={"sx_session": cookie})
    assert r.status_code != 401  # auth passed; downstream may 500 on empty DB


def test_tampered_cookie_rejected(client):
    cookie = sign_session_cookie(
        secret=SECRET, key_id=KEY_ID,
        user_id="u_xuzong", user_name="许总", user_role="user",
    )
    bad = cookie[:-4] + "AAAA"
    r = client.get("/sessions", cookies={"sx_session": bad})
    assert r.status_code == 401


def test_hmac_fallback_still_works(client):
    """When no cookie is set, the existing HMAC headers path must still work."""
    from agent_auth import sign
    headers = sign(
        secret=SECRET, key_id=KEY_ID,
        method="GET", host="testserver", path="/sessions",
        client="yinhu", agent="super-xiaochen",
        user_id="u_xuzong", user_role="user", body=b"",
    )
    r = client.get("/sessions", headers=headers)
    assert r.status_code != 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_require_auth.py -v`
Expected: `test_session_cookie_accepted` and `test_tampered_cookie_rejected` fail with 401 because cookie isn't checked yet.

- [ ] **Step 3: Modify `require_auth` in web_agent.py**

Open `/Users/eason/yinhu-super-xiaochen/web_agent.py`. Find the existing `require_auth` function (lines 124-149). Replace it with:

```python
async def require_auth(request: Request) -> str:
    """SSO.md §1.2/§1.3 — cookie-first, HMAC fallback.

    Browser users come in with `sx_session` cookie (set by /sso/accept).
    Server-to-server callers (daily-report orchestrator etc) keep using
    HMAC headers; we fall through to the existing verify() in that case.
    """
    # 1. Cookie path (browser)
    cookie = request.cookies.get("sx_session")
    if cookie:
        try:
            claims = verify_session_cookie(cookie, secrets=_HMAC_SECRETS)
            return claims["sub"]
        except ValueError:
            pass  # fall through to HMAC

    # 2. HMAC path (server-to-server)
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
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

Also add the `verify_session_cookie` import near the top of the file (next to the existing `from agent_auth import verify, NonceStore` line):

```python
from session_cookie import verify_session_cookie
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_require_auth.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/eason/yinhu-super-xiaochen
git add web_agent.py tests/test_require_auth.py
git commit -m "feat(auth): require_auth tries sx_session cookie before HMAC fallback"
```

---

## Task 3: super-xiaochen — `/sso/accept` and `/logout` routes

**Files:**
- Modify: `/Users/eason/yinhu-super-xiaochen/web_agent.py` (add two routes near other `@app` routes)
- Create: `/Users/eason/yinhu-super-xiaochen/tests/test_sso_routes.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/eason/yinhu-super-xiaochen/tests/test_sso_routes.py`:

```python
"""Tests for /sso/accept and /logout."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("HMAC_KEY_ID_CURRENT", "k1")
os.environ.setdefault("HMAC_SECRET_CURRENT", "QXJiaXRyYXJ5MzJieXRlc2VjcmV0Zm9ydGVzdHM=")
os.environ.setdefault("TENANT_CLIENT", "yinhu")
os.environ.setdefault("TENANT_AGENT", "super-xiaochen")
os.environ.setdefault("SUPER_XIAOCHEN_DB", ":memory:")

import pytest
from fastapi.testclient import TestClient
import web_agent
from session_cookie import sign_bootstrap_token

SECRET = os.environ["HMAC_SECRET_CURRENT"]
KEY_ID = os.environ["HMAC_KEY_ID_CURRENT"]


@pytest.fixture
def client():
    # disable auto-follow so we can inspect the 303 + Set-Cookie
    return TestClient(web_agent.app, follow_redirects=False)


def _token(**over):
    base = dict(
        secret=SECRET, key_id=KEY_ID,
        user_id="u_xuzong", user_name="许总", user_role="user",
    )
    base.update(over)
    return sign_bootstrap_token(**base)


def test_accept_happy_path_sets_cookie_and_redirects(client):
    r = client.get(f"/sso/accept?t={_token()}")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    set_cookie = r.headers["set-cookie"]
    assert "sx_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie.lower()
    assert "Path=/" in set_cookie


def test_accept_missing_token_401(client):
    r = client.get("/sso/accept")
    assert r.status_code == 401


def test_accept_expired_token_401(client):
    r = client.get(f"/sso/accept?t={_token(ttl_seconds=-1)}")
    assert r.status_code == 401


def test_accept_tampered_token_401(client):
    bad = _token()[:-4] + "AAAA"
    r = client.get(f"/sso/accept?t={bad}")
    assert r.status_code == 401


def test_accept_replay_rejected(client):
    token = _token()
    r1 = client.get(f"/sso/accept?t={token}")
    assert r1.status_code == 303
    r2 = client.get(f"/sso/accept?t={token}")
    assert r2.status_code == 401  # NonceStore caught it


def test_logout_clears_cookie(client):
    r = client.post("/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    set_cookie = r.headers["set-cookie"]
    assert "sx_session=" in set_cookie
    # delete_cookie emits Max-Age=0 (or expires in the past)
    assert "Max-Age=0" in set_cookie or "01 Jan 1970" in set_cookie
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_sso_routes.py -v`
Expected: all tests fail with 404 (routes don't exist yet).

- [ ] **Step 3: Add the two routes to `web_agent.py`**

In `/Users/eason/yinhu-super-xiaochen/web_agent.py`, add this import near the top with the other `from session_cookie` line:

```python
from session_cookie import verify_session_cookie, verify_bootstrap_token, sign_session_cookie
```

Add these two route handlers in the routes section (after `@app.get("/healthz")` is a good spot — keep them grouped with other unauthenticated routes):

```python
@app.get("/sso/accept")
def sso_accept(request: Request) -> Response:
    """Exchange a one-shot bootstrap token (from agent-platform) for a 7-day
    session cookie. See SSO.md §1.3."""
    token = request.query_params.get("t", "")
    if not token:
        return HTMLResponse(
            "<h1>登录失败</h1><p>登录链接已过期,请回到平台重新进入。</p>",
            status_code=401,
        )
    try:
        claims = verify_bootstrap_token(token, secrets=_HMAC_SECRETS, nonce_store=_NONCE_STORE)
    except ValueError:
        return HTMLResponse(
            "<h1>登录失败</h1><p>登录链接已过期,请回到平台重新进入。</p>",
            status_code=401,
        )

    # Mint a 7-day cookie using the same key as the token.
    cookie = sign_session_cookie(
        secret=_HMAC_SECRETS[claims["kid"]],
        key_id=claims["kid"],
        user_id=claims["sub"],
        user_name=claims.get("name", ""),
        user_role=claims.get("role", "user"),
    )
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        "sx_session", cookie,
        httponly=True, secure=True, samesite="lax",
        max_age=7 * 86400, path="/",
    )
    return resp


@app.post("/logout")
def logout() -> Response:
    """Clear the session cookie. No CSRF needed — nothing destructive."""
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("sx_session", path="/")
    return resp
```

You will need to ensure these names are imported at the top of `web_agent.py` (most should already be there from existing code):
- `RedirectResponse`, `HTMLResponse` from `fastapi.responses`
- `Response` from `fastapi`
- `Request` from `fastapi`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/test_sso_routes.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `cd /Users/eason/yinhu-super-xiaochen && pytest tests/ -v`
Expected: all tests PASS, including the existing `test_agent_auth.py`.

- [ ] **Step 6: Commit**

```bash
cd /Users/eason/yinhu-super-xiaochen
git add web_agent.py tests/test_sso_routes.py
git commit -m "feat(sso): /sso/accept exchanges bootstrap token for sx_session cookie; /logout clears it"
```

---

## Task 4: super-xiaochen — push to remote

This unblocks Task 5 (agent-platform side) because we want super-xiaochen deployed first so the `/sso/accept` endpoint is live before any user hits `/sso/super-xiaochen`. The new code is backwards-compatible (HMAC still works) so deploying first is safe.

- [ ] **Step 1: Push and open PR**

```bash
cd /Users/eason/yinhu-super-xiaochen
git push -u origin <current-branch-name>
gh pr create --title "feat(sso): cookie-based session auth alongside HMAC" --body "$(cat <<'EOF'
## Summary
- Add `session_cookie.py` with bootstrap-token (60s, one-shot) + session-cookie (7d) signing
- Reuse `_HMAC_SECRETS` env vars — no new config
- `require_auth` now tries `sx_session` cookie first, falls back to HMAC headers
- New `/sso/accept?t=...` exchanges a bootstrap token for the session cookie
- New `POST /logout` clears the cookie
- HMAC path is untouched; daily-report orchestrator continues to work

## Test plan
- [ ] `pytest tests/` green (existing + new)
- [ ] Deploy to Railway, hit `/healthz` returns 200
- [ ] Without the cookie, `GET /` still returns the legacy 401 `auth: unknown key id` (HMAC fallback)
- [ ] platform-side PR will be merged next to wire the entry button
EOF
)"
```

- [ ] **Step 2: Wait for Railway deploy to succeed**

Railway auto-deploys on merge to main. Verify by curling `/healthz`:

```bash
curl -s https://agent-yinhu-super-xiaochen-production.up.railway.app/healthz
```
Expected: `{"ok":true,"version":"..."}`.

Verify the new `/sso/accept` route is mounted (will 401 without a token, that's correct):

```bash
curl -i https://agent-yinhu-super-xiaochen-production.up.railway.app/sso/accept
```
Expected: HTTP 401 with body `"登录失败"`.

---

## Task 5: agent-platform — `sso.py` module + `/sso/super-xiaochen` route

**Files:**
- Create: `/Users/eason/agent-platform/services/platform-api/platform_app/sso.py`
- Modify: `/Users/eason/agent-platform/services/platform-api/platform_app/main.py:32-36`
- Create: `/Users/eason/agent-platform/services/platform-api/tests/test_sso.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/eason/agent-platform/services/platform-api/tests/test_sso.py`:

```python
"""Tests for the /sso/super-xiaochen bootstrap endpoint."""
import os
import time
import pytest
from fastapi.testclient import TestClient
from platform_app import db


SECRET = "QXJiaXRyYXJ5MzJieXRlc2VjcmV0Zm9ydGVzdHM="
KEY_ID = "k1"


def _seed(*, with_acl: bool) -> str:
    """Insert user + session + tenant. Returns session id."""
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_xuzong','xuzong','x','许总',0)"
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('yinhu','Yinhu','银湖','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','super-xiaochen','Super Xiaochen','http://x',%s,%s,'y-sx-uid',0)",
        (SECRET, KEY_ID),
    )
    if with_acl:
        db.main().execute(
            "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
            "VALUES ('u_xuzong','yinhu','member',0)"
        )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-sso','u_xuzong','csrf-sso',0,9999999999)"
    )
    return "sess-sso"


@pytest.fixture
def client():
    from platform_app.main import app
    return TestClient(app, follow_redirects=False)


def test_no_cookie_redirects_to_root(client):
    r = client.get("/sso/super-xiaochen")
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_acl_ok_303_to_railway_with_token(client, monkeypatch):
    monkeypatch.setenv("SUPER_XIAOCHEN_PUBLIC_URL", "https://sx.example.com")
    sid = _seed(with_acl=True)
    r = client.get("/sso/super-xiaochen", cookies={"app_session": sid})
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("https://sx.example.com/sso/accept?t=")
    token = loc.split("?t=", 1)[1]
    # Token must verify with the seeded secret.
    from platform_app.sso import _verify_for_test
    claims = _verify_for_test(token, secrets={KEY_ID: SECRET})
    assert claims["sub"] == "u_xuzong"
    assert claims["name"] == "许总"
    assert claims["exp"] > int(time.time())
    assert "jti" in claims


def test_acl_denied_403(client):
    sid = _seed(with_acl=False)
    r = client.get("/sso/super-xiaochen", cookies={"app_session": sid})
    assert r.status_code == 403
```

> **Note for the engineer:** `platform_app.db` and the schema fixtures are wired up by the existing `conftest.py` — no extra setup needed. If your test invocation gives "table does not exist" errors, run `pytest tests/test_daily_report_api.py -v` first to confirm the test DB is healthy in your environment; both tests use the same seed pattern.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/eason/agent-platform/services/platform-api && pytest tests/test_sso.py -v`
Expected: ImportError on `platform_app.sso`.

- [ ] **Step 3: Implement `platform_app/sso.py`**

Create `/Users/eason/agent-platform/services/platform-api/platform_app/sso.py`:

```python
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
    """Test helper — mirrors the verify on the super-xiaochen side
    minus the nonce check. Real verification happens in the container."""
    try:
        payload_b64, sig = token.split(".")
    except ValueError:
        raise ValueError("malformed token")
    claims = json.loads(_b64url_dec(payload_b64))
    kid = claims["kid"]
    if kid not in secrets:
        raise ValueError("unknown key id")
    expected = _sign(secrets[kid], payload_b64)
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
    except HTTPException:
        return RedirectResponse("/", status_code=302)

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
```

- [ ] **Step 4: Mount the router in `main.py`**

Open `/Users/eason/agent-platform/services/platform-api/platform_app/main.py`. Find this block (around line 32-36):

```python
app.include_router(api.router)
app.include_router(data_api.router)
app.include_router(admin_api.router)
app.include_router(enterprise_api.router)
app.include_router(daily_report_api.router)
```

Update the import line at the top of the file (currently `from . import admin_api, api, context as _context, db, enterprise_api`) to add `sso`:

```python
from . import admin_api, api, context as _context, db, enterprise_api, sso
```

And add the include_router call:

```python
app.include_router(api.router)
app.include_router(data_api.router)
app.include_router(admin_api.router)
app.include_router(enterprise_api.router)
app.include_router(daily_report_api.router)
app.include_router(sso.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/eason/agent-platform/services/platform-api && pytest tests/test_sso.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6: Run the full platform-api test suite to confirm no regressions**

Run: `cd /Users/eason/agent-platform/services/platform-api && pytest tests/ -v`
Expected: all tests PASS. Pay particular attention to `test_url_contract.py` — it has a stale reference to `/yinhu/super-xiaochen/foo`; if it fails, read the test and adjust only if it's our change that broke it (it shouldn't be, since we're adding `/sso/...` not `/yinhu/...`).

- [ ] **Step 7: Commit**

```bash
cd /Users/eason/agent-platform
git add services/platform-api/platform_app/sso.py services/platform-api/platform_app/main.py services/platform-api/tests/test_sso.py
git commit -m "feat(sso): /sso/super-xiaochen mints bootstrap token + redirects"
```

---

## Task 6: win-web — point entry at `/sso/super-xiaochen`

**Files:**
- Modify: `/Users/eason/agent-platform/apps/win-web/src/components/URail.tsx:105-126`
- Modify: `/Users/eason/agent-platform/apps/win-web/src/screens/Profile.tsx:154-158`

- [ ] **Step 1: Edit `URail.tsx`**

Open `/Users/eason/agent-platform/apps/win-web/src/components/URail.tsx`. Find the `<a>` block (lines 105-126):

```tsx
      {/* App switcher · 超级小陈 (external) */}
      <a
        href="https://agent-yinhu-super-xiaochen-production.up.railway.app"
        target="_blank"
        rel="noopener noreferrer"
        title="超级小陈"
        aria-label="超级小陈"
```

Change it to:

```tsx
      {/* App switcher · 超级小陈 (via platform SSO) */}
      <a
        href="/sso/super-xiaochen"
        title="超级小陈"
        aria-label="超级小陈"
```

(Remove the `target="_blank"` and `rel="noopener noreferrer"` lines — same-tab navigation through the platform SSO endpoint is the right UX now.)

- [ ] **Step 2: Edit `Profile.tsx`**

Open `/Users/eason/agent-platform/apps/win-web/src/screens/Profile.tsx`. Find the `<a>` block (lines 154-158):

```tsx
        {/* External app: 超级小陈 */}
        <a
          href="https://agent-yinhu-super-xiaochen-production.up.railway.app"
          target="_blank"
          rel="noopener noreferrer"
```

Change it to:

```tsx
        {/* App switcher · 超级小陈 (via platform SSO) */}
        <a
          href="/sso/super-xiaochen"
```

- [ ] **Step 3: Build win-web to confirm no TS errors**

Run: `cd /Users/eason/agent-platform/apps/win-web && pnpm build`
Expected: build succeeds, no TS / lint errors. (If pnpm isn't the package manager in your setup, use `npm run build` or check `package.json`.)

- [ ] **Step 4: Commit**

```bash
cd /Users/eason/agent-platform
git add apps/win-web/src/components/URail.tsx apps/win-web/src/screens/Profile.tsx
git commit -m "feat(win-web): route super-xiaochen entry through /sso/super-xiaochen"
```

---

## Task 7: Push and open PR

- [ ] **Step 1: Push the agent-platform branch and open the PR**

```bash
cd /Users/eason/agent-platform
git push -u origin <current-branch-name>
gh pr create --title "feat(sso): wire super-xiaochen entry through platform SSO endpoint" --body "$(cat <<'EOF'
## Summary
- Add `/sso/super-xiaochen` endpoint that mints a 60s HMAC-signed bootstrap token and 303-redirects to super-xiaochen's new `/sso/accept`.
- Update win-web entry button (URail + Profile) to point at the relative `/sso/super-xiaochen` instead of the raw Railway origin.
- Reuses the existing `tenants.hmac_secret_current` row that daily-report already shares — no new config.
- Companion super-xiaochen PR (which adds `/sso/accept` + cookie-based `require_auth` fallback) must merge first.

## Test plan
- [ ] `pytest services/platform-api/tests/test_sso.py -v` green
- [ ] Full platform-api test suite green
- [ ] win-web `pnpm build` green
- [ ] After deploy: log in to app.fiveoranges.ai as a yinhu member → click the entry → land on super-xiaochen index with a `sx_session` cookie set
- [ ] Log in as a non-yinhu user → click the entry → see the 403 page
EOF
)"
```

---

## Task 8: Post-deploy verification

- [ ] **Step 1: Verify the end-to-end flow once both PRs are merged and deployed**

Manual steps:

1. Open `https://app.fiveoranges.ai` in a fresh browser window.
2. Log in as a yinhu-enterprise user (e.g. 许总's account).
3. Click the spark/超级小陈 button in the URail sidebar.
4. Open DevTools → Network tab before clicking. Expected sequence:
   - `GET /sso/super-xiaochen` → 303 with `Location: https://...railway.app/sso/accept?t=...`
   - `GET /sso/accept?t=...` → 303 with `Set-Cookie: sx_session=...; HttpOnly; Secure; SameSite=Lax`
   - `GET /` → 200 (super-xiaochen index loads, no more "auth: unknown key id")
5. Reload the super-xiaochen page directly — should still load (the cookie persists for 7 days).
6. Log in as a non-yinhu user → click button → should see the 403 page.
7. (Optional) Trigger the daily-report cron or call the orchestrator manually — should still succeed using the HMAC fallback path.

- [ ] **Step 2: If anything 401s, capture and report**

Look in Railway logs for `auth:` lines to see which leg failed.
Look in platform-api logs for any 500 from `/sso/super-xiaochen`.

---

## Self-Review

(Author's check after writing — engineer can skip.)

1. **Spec coverage:**
   - §3 流程 → Tasks 5, 3
   - §4.1 Bootstrap token → Task 1 (`sign_bootstrap_token` / `verify_bootstrap_token`)
   - §4.2 Session cookie → Task 1 (`sign_session_cookie` / `verify_session_cookie`)
   - §4.3 require_auth → Task 2
   - §5.1 `/sso/super-xiaochen` → Task 5
   - §5.2 `/sso/accept` → Task 3
   - §5.3 `/logout` → Task 3
   - §6 frontend → Task 6
   - §8 test list (10 cases) → all covered across `test_session_cookie.py` (3, 5, 7, 8, 10), `test_sso_routes.py` (4, 5, 6, 7), `test_require_auth.py` (8, 9), `test_sso.py` (1, 2, 3). All ten boxes ticked.
   - §9 deployment steps → Tasks 4, 7, 8 in that order.
   - §10 known limitations: not implementing the in-app logout UX or button-hiding — explicitly listed as out of scope.

2. **Placeholder scan:** No TBDs / TODOs / "fill in" left.

3. **Type consistency:** `sign_bootstrap_token` / `verify_bootstrap_token` / `sign_session_cookie` / `verify_session_cookie` names match between Task 1 (impl), Task 2 (uses verify), Task 3 (uses verify + sign), Task 5 (uses `sign_bootstrap_token` on platform side with same name but a separate copy). `_verify_for_test` matches Task 5 step 1 (test) and step 3 (impl).
