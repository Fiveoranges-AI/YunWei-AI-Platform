import os
import pytest

# Set required env BEFORE platform_app modules import (settings reads on import).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:test@localhost:5433/test",
)
os.environ.setdefault(
    "REDIS_URL",
    "redis://localhost:6380",
)
os.environ.setdefault("COOKIE_SECRET", "test-cookie-secret-32-bytes-padding=")


@pytest.fixture(autouse=True)
def _clean_state():
    """Truncate all tables + flush redis between tests."""
    import psycopg, redis
    # Make sure tables exist before truncating (init runs once per session).
    from platform_app import db as _db
    if _db._MAIN is None:
        _db.init()
    # Truncate (PostgreSQL CASCADE handles FK chain)
    with _db.main()._get().cursor() as cur:
        cur.execute(
            "TRUNCATE jintai_mvp.production_step_records, "
            "jintai_mvp.ai_query_logs, jintai_mvp.ai_extraction_queue, "
            "jintai_mvp.attachments, jintai_mvp.document_templates, "
            "jintai_mvp.production_flow_cards, jintai_mvp.process_steps, "
            "jintai_mvp.process_routes, jintai_mvp.sales_orders, "
            "jintai_mvp.products, jintai_mvp.customers, jintai_mvp.profiles, "
            "jintai_mvp.external_source_mappings, jintai_mvp.tenants, "
            "api_keys, platform_sessions, agent_grants, "
            "enterprise_members, runtime_bindings, runtimes, "
            "enterprise_integrations, "
            "tenants, enterprises, users, "
            "proxy_log, bronze_files, silver_mappings, "
            "daily_reports, daily_report_subscriptions, invite_codes "
            "RESTART IDENTITY CASCADE"
        )
    # Flush Redis test DB
    redis.from_url(os.environ["REDIS_URL"]).flushdb()
    yield
