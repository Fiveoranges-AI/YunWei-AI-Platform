"""End-to-end: scheduler tick → orchestrator → DB → API list/detail."""
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
import pytest
import httpx
import respx
from fastapi.testclient import TestClient
from platform_app import db
from platform_app.daily_report import orchestrator, storage

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "sample_collector_response.json").read_text()
)


def _seed_full_setup():
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u1','alice','x','Alice',0)"
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES ('yinhu','Yinhu','银湖','trial','active',0)"
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','日报',"
        "'http://yinhu-container.test:8000','secret-x','k1','yinhu-daily-uid',0)"
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u1','yinhu','member',0)"
    )
    db.main().execute(
        "INSERT INTO platform_sessions (id, user_id, csrf_token, created_at, expires_at) "
        "VALUES ('sess-1','u1','c1',0,9999999999)"
    )


@pytest.mark.asyncio
async def test_full_flow_orchestrator_then_api_list():
    _seed_full_setup()
    with respx.mock() as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=_FIXTURE)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu", report_date=date(2026, 5, 6),
            pusher=None, subscription=None,
        )

    from platform_app.main import app
    client = TestClient(app)
    list_resp = client.get(
        "/api/daily-report/reports?tenant=yinhu",
        cookies={"app_session": "sess-1"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["reports"][0]["id"] == rid

    detail_resp = client.get(
        f"/api/daily-report/reports/{rid}",
        cookies={"app_session": "sess-1"},
    )
    assert detail_resp.status_code == 200
    assert "银湖经营快报" in detail_resp.json()["content_md"]
    assert "<h1>" in detail_resp.json()["content_html"]
