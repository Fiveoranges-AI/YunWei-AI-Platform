import os
from pathlib import Path

# Repo root: .../agent-platform/  (this file is .../platform/platform_app/settings.py)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings:
    # Required (startup-fail-fast):
    database_url = os.environ["DATABASE_URL"]
    redis_url = os.environ["REDIS_URL"]
    cookie_secret = os.environ["COOKIE_SECRET"]

    # Optional with defaults:
    host_app = os.environ.get("PLATFORM_HOST_APP", "app.fiveoranges.ai")
    host_api = os.environ.get("PLATFORM_HOST_API", "api.fiveoranges.ai")
    # Lakehouse root (docs/data-layer.md §2). Tenants live under <data_root>/tenants/<client_id>/.
    data_root = os.environ.get("PLATFORM_DATA_ROOT", str(_REPO_ROOT / "data"))
    # Data center sidebar assistant (docs/data-layer.md §3.3). Optional —
    # absence disables the assistant chat but everything else still works.
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    assistant_model = os.environ.get(
        "ASSISTANT_MODEL", "claude-opus-4-7"
    )
    assistant_effort = os.environ.get("ASSISTANT_EFFORT", "medium")
    assistant_max_tool_iterations = int(
        os.environ.get("ASSISTANT_MAX_TOOL_ITERATIONS", "8")
    )
    session_lifetime_seconds = 8 * 3600
    csrf_lifetime_seconds = 8 * 3600
    rate_limit_login_per_min_per_ip = 5
    rate_limit_login_per_hour_per_user = 10
    nonce_replay_window_seconds = 10
    clock_skew_seconds = 5
    health_probe_interval_seconds = 30


settings = Settings()
