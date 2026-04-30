import os
from pathlib import Path

class Settings:
    db_path = Path(os.environ.get("PLATFORM_DB_PATH", "/data/platform.db"))
    proxy_log_db_path = Path(os.environ.get("PROXY_LOG_DB_PATH", "/data/proxy_log.db"))
    host_app = os.environ.get("PLATFORM_HOST_APP", "app.fiveoranges.ai")
    host_api = os.environ.get("PLATFORM_HOST_API", "api.fiveoranges.ai")
    cookie_secret = os.environ["COOKIE_SECRET"]
    session_lifetime_seconds = 8 * 3600
    csrf_lifetime_seconds = 8 * 3600
    rate_limit_login_per_min_per_ip = 5
    rate_limit_login_per_hour_per_user = 10
    nonce_replay_window_seconds = 10
    clock_skew_seconds = 5
    health_probe_interval_seconds = 30

settings = Settings()
