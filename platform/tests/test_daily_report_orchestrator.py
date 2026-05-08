"""Orchestrator tests — container HTTP mocked via respx."""
import json
from datetime import date
from pathlib import Path
import pytest
import httpx
import respx
from platform_app.daily_report import orchestrator, storage
from platform_app import db

_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sample_collector_response.json").read_text())


def _seed_yinhu_daily_report_tenant() -> None:
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report',"
        " 'http://yinhu-container.test:8000','secret-x','k1','yinhu-daily-uid',0)",
    )


@pytest.mark.asyncio
async def test_run_happy_path_marks_ready_and_calls_push():
    _seed_yinhu_daily_report_tenant()
    pushed = []

    class _FakePusher:
        async def push(self, **kw):
            pushed.append(kw)
            from platform_app.daily_report.pushers.base import PushResult
            return PushResult(success=True, error=None)

    with respx.mock(assert_all_called=True) as mock:
        mock.post("http://yinhu-container.test:8000/daily-report/_internal/generate").mock(
            return_value=httpx.Response(200, json=_FIXTURE)
        )
        rid = await orchestrator.run(
            tenant_id="yinhu",
            report_date=date(2026, 5, 6),
            pusher=_FakePusher(),
            subscription=None,  # tested separately
        )
    row = storage.get_by_id(rid)
    assert row.status == "ready"
    assert "银湖经营快报" in row.content_md
    assert "<h1>" in row.content_html  # md→html ran
    assert row.sections_json["sales"]["status"] == "ok"
    # No subscription passed → no push attempted
    assert pushed == []
