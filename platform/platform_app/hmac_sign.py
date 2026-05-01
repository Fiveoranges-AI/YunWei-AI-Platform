"""SSO.md §1.2 HMAC 签名 / 验证 + nonce store."""
from __future__ import annotations
import base64
import hashlib
import hmac
import time
import uuid
from urllib.parse import quote


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
        # URL-encode so non-ASCII display names ("许总") survive HTTP header
        # ASCII enforcement; agent can urldecode if it needs to display.
        # Not part of the HMAC payload, so encoding doesn't affect signature.
        "X-User-Name": quote(user_name, safe=""),
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
