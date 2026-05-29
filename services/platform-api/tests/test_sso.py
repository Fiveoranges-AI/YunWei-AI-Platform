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
