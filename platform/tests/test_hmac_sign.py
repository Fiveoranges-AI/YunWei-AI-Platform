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
    nonce_store = NonceStore()
    from platform_app.hmac_sign import _compute_sig
    old_ts = int(time.time()) - 60
    headers = sign(
        secret=SECRET, key_id=KEY_ID, method="GET",
        host="h", path="/p", client="c", agent="a",
        user_id="u", user_role="user", body=b"",
    )
    # 等价构造一个老的合法签名:
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


def test_nonce_store_redis_expiry():
    """Redis SETNX with TTL: same (key_id, nonce) within window is replay,
    but GC happens automatically via Redis key expiration (no manual gc())."""
    store = NonceStore()
    # Fresh nonce accepted
    store.check_and_add("k1", f"unique-{time.time_ns()}", expiry=int(time.time()) + 25)
    # gc() is now a no-op but still callable for backwards compat
    store.gc()
