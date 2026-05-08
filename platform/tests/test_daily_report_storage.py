"""Tests for daily_report.storage."""
from datetime import date
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
