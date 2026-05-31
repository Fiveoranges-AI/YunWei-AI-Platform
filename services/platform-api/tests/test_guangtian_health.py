"""光天 dev backend 可观测性 — /api/health + request-id 追踪 (镜像锦泰 #129).

只验证 dev_guangtian_backend 自带的 /api/health 形状 + 追踪头; 不触 DB
(/api/health 不查库), 所以不需要 PG / seed。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# Override the project-level autouse Postgres-truncating fixture.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


@pytest.fixture
def client():
    import dev_guangtian_backend

    return TestClient(dev_guangtian_backend.create_app())


def test_api_health_shape(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["tenant"] == "guangtian_demo"
    assert "db" in body["checks"]
    assert "commit" in body
    assert "time" in body


def test_legacy_health_still_works(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["enterprise_id"] == "guangtian_demo"


def test_request_id_header_present_and_echoed(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Request-ID")
    assert r.headers.get("X-Commit-SHA")
    r2 = client.get("/api/health", headers={"X-Request-ID": "gt-trace-7"})
    assert r2.headers.get("X-Request-ID") == "gt-trace-7"


def test_commit_sha_from_env(monkeypatch):
    import dev_guangtian_backend

    for var in ("GIT_SHA", "RAILWAY_GIT_COMMIT_SHA", "SOURCE_COMMIT", "COMMIT_SHA"):
        monkeypatch.delenv(var, raising=False)
    assert dev_guangtian_backend._commit_sha() == "unknown"
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert dev_guangtian_backend._commit_sha() == "abcdef123456"
