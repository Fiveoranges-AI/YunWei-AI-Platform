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
            "TRUNCATE api_keys, platform_sessions, agent_grants, "
            "enterprise_members, runtime_bindings, runtimes, "
            "tenants, enterprises, users, "
            "proxy_log, bronze_files, silver_mappings, "
            "daily_reports, daily_report_subscriptions, invite_codes "
            "RESTART IDENTITY CASCADE"
        )
    # Flush Redis test DB
    redis.from_url(os.environ["REDIS_URL"]).flushdb()
    yield
