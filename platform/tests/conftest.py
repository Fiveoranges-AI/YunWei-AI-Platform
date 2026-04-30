import os
import tempfile
from pathlib import Path
import pytest

# Settings reads env at module import; set vars before any test module
# imports platform_app.* so the singleton sees test-friendly values.
_TMP = tempfile.mkdtemp()
os.environ["PLATFORM_DB_PATH"] = str(Path(_TMP) / "platform.db")
os.environ["PROXY_LOG_DB_PATH"] = str(Path(_TMP) / "proxy_log.db")
os.environ.setdefault("COOKIE_SECRET", "test-cookie-secret-32-bytes-padding=")


@pytest.fixture
def tmp_data_dir() -> str:
    return _TMP


@pytest.fixture(autouse=True)
def _clean_db_state():
    """Wipe all rows + TTL caches between tests so tests don't bleed state."""
    from platform_app import db as _db
    if _db._MAIN_DB is not None:
        for tbl in ("api_keys", "platform_sessions", "user_tenant", "tenants", "users"):
            _db._MAIN_DB.execute(f"DELETE FROM {tbl}")
    if _db._PROXY_DB is not None:
        _db._PROXY_DB.execute("DELETE FROM proxy_log")
    _db._tenant_cache.clear()
    _db._session_cache.clear()
    _db._acl_cache.clear()
    yield
