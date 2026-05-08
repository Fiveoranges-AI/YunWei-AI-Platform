"""Platform admin API tests (`/api/admin/*`).

Covers cross-enterprise operations gated on ``is_platform_admin``:
- 403 when caller lacks the flag
- enterprise CRUD + listing with member/agent counts
- member add/update/remove with ACL cache invalidation
- agent_grant add/remove
- user listing + platform-admin flag toggle
"""
from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient
from platform_app import auth, db
from platform_app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def platform_admin():
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, "
        "is_platform_admin, created_at) VALUES (%s,%s,%s,%s,1,%s)",
        ("u_root", "root", auth.hash_password("p"), "Root", now),
    )
    sid, _ = auth.create_session("u_root", "127.0.0.1", "test")
    return sid


@pytest.fixture
def regular_user():
    db.init()
    now = int(time.time())
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", now),
    )
    sid, _ = auth.create_session("u_alice", "127.0.0.1", "test")
    return sid


def _seed_enterprise(eid: str, *, with_tenant: bool = True) -> None:
    now = int(time.time())
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        (eid, eid, eid, now),
    )
    if with_tenant:
        db.main().execute(
            "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
            "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
            "VALUES (%s,%s,%s,'http://x','s','k',%s,%s)",
            (eid, "agent1", f"{eid} agent1", f"uid_{eid}", now),
        )


# ─── auth gating ────────────────────────────────────────────────

def test_admin_endpoints_reject_unauthed(client):
    db.init()
    r = client.get("/api/admin/enterprises")
    assert r.status_code == 401


def test_admin_endpoints_reject_non_admin(client, regular_user):
    r = client.get("/api/admin/enterprises", cookies={"app_session": regular_user})
    assert r.status_code == 403


# ─── enterprises list / create / get / update ──────────────────

def test_list_enterprises_with_counts(client, platform_admin):
    _seed_enterprise("yinhu")
    _seed_enterprise("acme", with_tenant=False)
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_bob", "bob", auth.hash_password("p"), "Bob", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,'member',%s)",
        ("u_bob", "yinhu", int(time.time())),
    )
    r = client.get("/api/admin/enterprises", cookies={"app_session": platform_admin})
    assert r.status_code == 200
    by_id = {e["id"]: e for e in r.json()["enterprises"]}
    assert by_id["yinhu"]["member_count"] == 1
    assert by_id["yinhu"]["agent_count"] == 1
    assert by_id["acme"]["member_count"] == 0
    assert by_id["acme"]["agent_count"] == 0


def test_create_enterprise(client, platform_admin):
    r = client.post(
        "/api/admin/enterprises",
        json={"id": "newco", "legal_name": "NewCo Ltd", "industry": "manufacturing"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "newco"
    assert body["industry"] == "manufacturing"


def test_create_enterprise_rejects_bad_id(client, platform_admin):
    r = client.post(
        "/api/admin/enterprises",
        json={"id": "Bad ID With Spaces"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 400


def test_get_enterprise_returns_members_and_agents(client, platform_admin):
    _seed_enterprise("yinhu")
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u_alice','yinhu','owner',%s)",
        (int(time.time()),),
    )
    r = client.get("/api/admin/enterprises/yinhu",
                   cookies={"app_session": platform_admin})
    assert r.status_code == 200
    body = r.json()
    assert len(body["members"]) == 1
    assert body["members"][0]["username"] == "alice"
    assert body["members"][0]["role"] == "owner"
    assert len(body["agents"]) == 1


def test_update_enterprise_admin_scope_can_change_plan(client, platform_admin):
    _seed_enterprise("yinhu", with_tenant=False)
    r = client.patch(
        "/api/admin/enterprises/yinhu",
        json={"plan": "enterprise", "industry": "refractory", "active": 0},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["plan"] == "enterprise"
    assert body["industry"] == "refractory"
    assert body["active"] == 0


def test_deactivate_enterprise(client, platform_admin):
    _seed_enterprise("yinhu", with_tenant=False)
    r = client.delete("/api/admin/enterprises/yinhu",
                      cookies={"app_session": platform_admin})
    assert r.status_code == 200
    row = db.main().execute("SELECT active FROM enterprises WHERE id='yinhu'").fetchone()
    assert row["active"] == 0


# ─── members ────────────────────────────────────────────────────

def test_add_member_by_username_and_invalidates_acl(client, platform_admin):
    _seed_enterprise("yinhu")
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    # Prime the cache with a denial
    assert db.has_acl("u_alice", "yinhu", "agent1") is False

    r = client.post(
        "/api/admin/enterprises/yinhu/members",
        json={"username": "alice", "role": "owner"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    # ACL re-resolved → True
    assert db.has_acl("u_alice", "yinhu", "agent1") is True


def test_update_member_role(client, platform_admin):
    _seed_enterprise("yinhu", with_tenant=False)
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u_alice','yinhu','member',%s)",
        (int(time.time()),),
    )
    r = client.patch(
        "/api/admin/enterprises/yinhu/members/u_alice",
        json={"role": "admin"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    assert db.get_enterprise_role("u_alice", "yinhu") == "admin"


def test_remove_member(client, platform_admin):
    _seed_enterprise("yinhu", with_tenant=False)
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES ('u_alice','yinhu','member',%s)",
        (int(time.time()),),
    )
    r = client.delete("/api/admin/enterprises/yinhu/members/u_alice",
                      cookies={"app_session": platform_admin})
    assert r.status_code == 200
    assert db.get_enterprise_role("u_alice", "yinhu") is None


# ─── agent grants ───────────────────────────────────────────────

def test_add_and_remove_agent_grant(client, platform_admin):
    _seed_enterprise("yinhu")
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_consult", "consult", auth.hash_password("p"), "Consultant", int(time.time())),
    )
    r = client.post(
        "/api/admin/enterprises/yinhu/agent-grants",
        json={"username": "consult", "agent_id": "agent1"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    assert db.has_acl("u_consult", "yinhu", "agent1") is True

    r2 = client.delete(
        "/api/admin/enterprises/yinhu/agent-grants/u_consult/agent1",
        cookies={"app_session": platform_admin},
    )
    assert r2.status_code == 200
    assert db.has_acl("u_consult", "yinhu", "agent1") is False


# ─── users ──────────────────────────────────────────────────────

def test_list_users_includes_platform_admin_flag(client, platform_admin):
    r = client.get("/api/admin/users", cookies={"app_session": platform_admin})
    assert r.status_code == 200
    users = {u["username"]: u for u in r.json()["users"]}
    assert users["root"]["is_platform_admin"] == 1


def test_create_user(client, platform_admin):
    r = client.post(
        "/api/admin/users",
        json={"username": "carol", "password": "secret", "display_name": "Carol"},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    assert auth.authenticate("carol", "secret") == "u_carol"


def test_set_platform_admin_flag(client, platform_admin):
    db.init()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", int(time.time())),
    )
    r = client.patch(
        "/api/admin/users/u_alice/admin",
        json={"is_platform_admin": True},
        cookies={"app_session": platform_admin},
    )
    assert r.status_code == 200
    assert db.is_platform_admin("u_alice") is True

    r2 = client.patch(
        "/api/admin/users/u_alice/admin",
        json={"is_platform_admin": False},
        cookies={"app_session": platform_admin},
    )
    assert r2.status_code == 200
    assert db.is_platform_admin("u_alice") is False
