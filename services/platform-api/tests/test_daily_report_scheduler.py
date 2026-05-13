"""Scheduler tests — uses fake time + mocks orchestrator.run."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from platform_app.daily_report import scheduler, storage
from platform_app import db


def _seed_yinhu_daily_report_tenant() -> None:
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES ('yinhu','daily-report','Daily Report',"
        " 'http://x','secret','k1','yinhu-daily-uid',0)"
    )


def test_compute_next_fire_uses_subscription_cron_and_tz():
    sub = storage.Subscription(
        id="s1", tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="u",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales"], enabled=True,
    )
    # Sunday 2026-05-03 23:00 Shanghai → next is Mon 2026-05-04 07:30 Shanghai
    base = datetime(2026, 5, 3, 23, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    nxt = scheduler.compute_next_fire(sub, now=base)
    assert nxt == datetime(2026, 5, 4, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_compute_next_fire_skips_weekend():
    sub = storage.Subscription(
        id="s1", tenant_id="yinhu", recipient_label="x",
        push_channel="dingtalk", push_target="u",
        push_cron="30 7 * * 1-5", timezone="Asia/Shanghai",
        sections_enabled=["sales"], enabled=True,
    )
    # Friday 2026-05-08 08:00 → next is Mon 2026-05-11 07:30
    base = datetime(2026, 5, 8, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    nxt = scheduler.compute_next_fire(sub, now=base)
    assert nxt == datetime(2026, 5, 11, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


@pytest.mark.asyncio
async def test_loop_fires_orchestrator_when_due(monkeypatch):
    _seed_yinhu_daily_report_tenant()
    storage.create_subscription(
        tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="* * * * *",  # every minute, fires immediately on next tick
        sections_enabled=["sales"],
    )

    fired: list[tuple] = []

    async def fake_run(**kw):
        fired.append(kw)
        return "rid-fake"

    monkeypatch.setattr(scheduler, "_orchestrator_run", fake_run)
    # Tick faster than 60s for test.
    monkeypatch.setattr(scheduler, "_TICK_SECONDS", 0.05)

    task = asyncio.create_task(scheduler.run_forever())
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(fired) >= 1
    assert fired[0]["tenant_id"] == "yinhu"
