"""Self-health endpoint + request tracing.

Closes the ``/api/health`` 404 gap (uptime monitor target) and gives every
prod error a request-id + commit-hash trail so a log line can be traced back
to a single request and the exact deployed commit.

Intentionally dependency-free (stdlib + the existing platform_app.db). No
Sentry/OTEL here — that's a follow-up that needs a DSN from ops.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("platform_app.observability")

# Env vars different PaaS providers expose the deployed commit under.
_COMMIT_ENV_VARS = ("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "SOURCE_COMMIT", "COMMIT_SHA")


def commit_sha() -> str:
    for var in _COMMIT_ENV_VARS:
        v = os.environ.get(var, "").strip()
        if v:
            return v[:12]
    return "unknown"


def llm_provider_mode() -> str:
    """Which extraction provider live traffic will use — operational signal so
    ops can tell at a glance whether real LLM is wired (vs the demo fallback)."""
    return "claude" if os.environ.get("ANTHROPIC_API_KEY", "").strip() else "demo-mock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_health_payload(*, db_ok: bool, extra: dict | None = None) -> tuple[dict, int]:
    """Shared health shape for both the prod app and the demo dev backend.

    Returns (payload, http_status). ``db_ok=False`` → 503 so a load balancer /
    uptime monitor takes the instance out of rotation.
    """
    checks = {
        "db": "ok" if db_ok else "error",
        "llm_provider": llm_provider_mode(),
    }
    if extra:
        checks.update(extra)
    payload = {
        "status": "ok" if db_ok else "degraded",
        "version": _version(),
        "commit": commit_sha(),
        "checks": checks,
        "time": _now_iso(),
    }
    return payload, (200 if db_ok else 503)


def _version() -> str:
    from . import __version__

    return __version__


def ping_platform_db() -> bool:
    """Lightweight ``SELECT 1`` against the platform Postgres."""
    try:
        from . import db

        db.main().execute("SELECT 1")
        return True
    except Exception:
        logger.warning("health: platform db ping failed", exc_info=True)
        return False


async def add_request_context(request, call_next):
    """Stamp a request-id on each request, echo it + the commit sha on the
    response, and log any unhandled exception against that id before re-raising.

    Deliberately does NOT change the error response envelope (re-raises as-is)
    so it can't alter behaviour the existing test suite asserts on.
    """
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "unhandled request error rid=%s method=%s path=%s",
            rid,
            request.method,
            request.url.path,
        )
        raise
    response.headers["X-Request-ID"] = rid
    response.headers["X-Commit-SHA"] = commit_sha()
    return response
