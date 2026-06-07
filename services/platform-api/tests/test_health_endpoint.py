"""Tests for the /api/health self-health endpoint + request-context middleware.

Covers the demo→prod observability gap: a load-balancer-pollable health route
(was 404) plus a request-id / commit-sha trail on every response.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from platform_app import observability
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ok_shape(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"] == "ok"
    # version + commit + llm provider mode are always reported
    assert "version" in body
    assert "commit" in body
    assert body["checks"]["llm_provider"] in ("claude", "demo-mock")
    assert "time" in body


def test_health_503_when_db_down(client, monkeypatch):
    monkeypatch.setattr(observability, "ping_platform_db", lambda: False)
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"] == "error"


def test_health_is_unauthenticated(client):
    # No app_session cookie — health must still answer (it sits above the
    # /api/win/* auth gate).
    r = client.get("/api/health")
    assert r.status_code == 200


def test_request_id_header_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Request-ID")
    assert r.headers.get("X-Commit-SHA")


def test_request_id_is_echoed_when_supplied(client):
    r = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers.get("X-Request-ID") == "trace-abc-123"


def test_llm_provider_mode_reflects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert observability.llm_provider_mode() == "demo-mock"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert observability.llm_provider_mode() == "claude"


def test_commit_sha_from_env(monkeypatch):
    for var in ("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "SOURCE_COMMIT", "COMMIT_SHA"):
        monkeypatch.delenv(var, raising=False)
    assert observability.commit_sha() == "unknown"
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert observability.commit_sha() == "abcdef123456"  # first 12 chars
