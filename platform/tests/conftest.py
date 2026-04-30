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
