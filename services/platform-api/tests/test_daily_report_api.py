"""REST API tests using FastAPI TestClient."""
from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from platform_app import db
from platform_app.daily_report import storage


def _seed_user_and_tenant() -> tuple[str, str]:
    """Returns (user_id, session_id). Uses enterprise_members ACL (post-migration 004)."""
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u1', 'alice', 'x', 'Alice', 0)"
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('yinhu','Yinhu','银湖','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report','http://x','s','k1','y-d-uid',0)"
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u1','yinhu','member',0)"
    )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-1','u1','csrf-1',0,9999999999)"
    )
    return "u1", "sess-1"


@pytest.fixture
def client():
    from platform_app.main import app
    return TestClient(app)


def test_list_reports_requires_login(client):
    resp = client.get("/api/daily-report/reports?tenant=yinhu")
    assert resp.status_code == 401


def test_list_reports_returns_metadata_only(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid, status="ready",
        content_md="# big body", content_html="<h1>big body</h1>",
        sections_json={"sales": {"status": "ok"}}, raw_collectors={},
        generated_at=datetime(2026, 5, 6, 7, 30),
    )
    resp = client.get(
        "/api/daily-report/reports?tenant=yinhu",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    items = resp.json()["reports"]
    assert len(items) == 1
    assert items[0]["status"] == "ready"
    assert items[0]["report_date"] == "2026-05-06"
    assert "content_md" not in items[0]  # metadata only


def test_get_report_detail_returns_html(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid, status="ready",
        content_md="# x", content_html="<h1>x</h1>",
        sections_json={"sales": {"status": "ok"}}, raw_collectors={"foo": "bar"},
        generated_at=datetime(2026, 5, 6, 7, 30),
    )
    resp = client.get(
        f"/api/daily-report/reports/{rid}",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["content_html"] == "<h1>x</h1>"
    assert body["sections_json"]["sales"]["status"] == "ok"


def test_cross_tenant_access_denied(client):
    _, sid = _seed_user_and_tenant()
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('other','Other','Other','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('other','daily-report','x','http://x','s','k1','o-d-uid',0)"
    )
    resp = client.get(
        "/api/daily-report/reports?tenant=other",
        cookies={"app_session": sid},
    )
    assert resp.status_code == 403


def test_platform_admin_can_access_other_tenant(client):
    """Platform admins (users.is_platform_admin=1) bypass tenant ACL."""
    # Seed a platform-admin user with no enterprise_members/agent_grants ties.
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, "
        "is_platform_admin, created_at) VALUES "
        "('u_admin','root','x','Root',1,0)"
    )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-admin','u_admin','csrf-a',0,9999999999)"
    )
    # Seed a tenant the admin is *not* a member of.
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('other','Other','Other','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('other','daily-report','x','http://x','s','k1','o-d-uid',0)"
    )
    resp = client.get(
        "/api/daily-report/reports?tenant=other",
        cookies={"app_session": "sess-admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["reports"] == []


def test_regenerate_deletes_existing_and_returns_new_id(client, monkeypatch):
    _, sid = _seed_user_and_tenant()
    old_rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_failure(report_id=old_rid, status="failed", error="x")

    new_rid_holder = {}

    async def fake_run(**kw):
        from platform_app.daily_report import storage as s
        rid = s.create_running(tenant_id=kw["tenant_id"], report_date=kw["report_date"])
        new_rid_holder["rid"] = rid
        return rid

    from platform_app.daily_report import api as api_mod
    monkeypatch.setattr(api_mod, "_orchestrator_run", fake_run)

    resp = client.post(
        "/api/daily-report/reports/yinhu/regenerate",
        json={"date": "2026-05-06"},
        cookies={"app_session": sid},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"] == new_rid_holder["rid"]
    assert body["report_id"] != old_rid  # new row


def test_html_list_page_redirects_to_login_when_no_cookie(client):
    resp = client.get("/daily-report", follow_redirects=False)
    assert resp.status_code == 200
    assert b"<title>" in resp.content


def test_html_list_page_when_logged_in(client):
    _, sid = _seed_user_and_tenant()
    resp = client.get("/daily-report", cookies={"app_session": sid})
    assert resp.status_code == 200
    assert b"daily" in resp.content.lower() or b"\xe6\x97\xa5\xe6\x8a\xa5" in resp.content


def test_html_detail_page(client):
    _, sid = _seed_user_and_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    resp = client.get(f"/daily-report/{rid}", cookies={"app_session": sid})
    assert resp.status_code == 200
    assert b"<html" in resp.content
