import os


class Settings:
    # Required (startup-fail-fast):
    database_url = os.environ["DATABASE_URL"]
    redis_url = os.environ["REDIS_URL"]
    cookie_secret = os.environ["COOKIE_SECRET"]

    # Optional with defaults:
    host_app = os.environ.get("PLATFORM_HOST_APP", "app.fiveoranges.ai")
    host_api = os.environ.get("PLATFORM_HOST_API", "api.fiveoranges.ai")
    session_lifetime_seconds = 8 * 3600
    csrf_lifetime_seconds = 8 * 3600
    rate_limit_login_per_min_per_ip = 5
    rate_limit_login_per_hour_per_user = 10
    nonce_replay_window_seconds = 10
    clock_skew_seconds = 5
    health_probe_interval_seconds = 30


settings = Settings()
