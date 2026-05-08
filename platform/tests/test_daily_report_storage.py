"""Tests for daily_report.storage."""
from datetime import date, datetime
import pytest
from platform_app.daily_report import storage


def _seed_tenant(tenant_id: str = "yinhu", agent_id: str = "daily-report") -> None:
    """Insert a tenant row so storage.create_running has a parent."""
    from platform_app import db
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 0)",
        (tenant_id, agent_id, "Daily Report", "http://x", "secret", "k1",
         f"{tenant_id}-{agent_id}-uid"),
    )


def test_create_running_inserts_with_status_running():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert rid is not None
    row = storage.get_by_id(rid)
    assert row.tenant_id == "yinhu"
    assert row.report_date == date(2026, 5, 6)
    assert row.status == "running"
    assert row.content_md is None


def test_create_running_idempotent_on_unique():
    _seed_tenant()
    rid1 = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    rid2 = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert rid1 == rid2  # returns existing row, not raise


def test_write_result_ready_sets_content_and_status():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_result(
        report_id=rid,
        status="ready",
        content_md="# foo",
        content_html="<h1>foo</h1>",
        sections_json={"sales": {"status": "ok"}},
        raw_collectors={"sales": {"raw": "..."}},
        generated_at=datetime(2026, 5, 6, 7, 30, 11),
    )
    row = storage.get_by_id(rid)
    assert row.status == "ready"
    assert row.content_md == "# foo"
    assert row.content_html == "<h1>foo</h1>"
    assert row.sections_json == {"sales": {"status": "ok"}}
    assert row.error is None


def test_write_failure_records_error_no_content():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.write_failure(report_id=rid, status="failed", error="container unreachable")
    row = storage.get_by_id(rid)
    assert row.status == "failed"
    assert row.error == "container unreachable"
    assert row.content_md is None


def test_update_push_status():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.update_push_status(report_id=rid, status="sent", error=None)
    assert storage.get_by_id(rid).push_status == "sent"
    storage.update_push_status(report_id=rid, status="failed", error="dingtalk 429")
    row = storage.get_by_id(rid)
    assert row.push_status == "failed"
    assert row.push_error == "dingtalk 429"


def test_list_reports_orders_desc_and_caps_limit():
    _seed_tenant()
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 4))
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 5))
    storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    rows = storage.list_reports(tenant_id="yinhu", limit=2)
    assert [r.report_date for r in rows] == [date(2026, 5, 6), date(2026, 5, 5)]


def test_delete_report_for_regenerate():
    _seed_tenant()
    rid = storage.create_running(tenant_id="yinhu", report_date=date(2026, 5, 6))
    storage.delete_by_tenant_date(tenant_id="yinhu", report_date=date(2026, 5, 6))
    assert storage.get_by_id(rid) is None


def test_subscription_create_and_list():
    _seed_tenant()
    sub_id = storage.create_subscription(
        tenant_id="yinhu", recipient_label="许总",
        push_channel="dingtalk", push_target="userid_xu",
        push_cron="30 7 * * 1-5",
        sections_enabled=["sales", "production", "chat", "customer_news"],
    )
    subs = storage.list_enabled_subscriptions()
    assert len(subs) == 1
    assert subs[0].id == sub_id
    assert subs[0].push_target == "userid_xu"
    assert subs[0].sections_enabled == ["sales", "production", "chat", "customer_news"]
