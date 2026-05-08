"""Enterprise self-service API tests (`/api/enterprise/*`).

Validates the role-gated edit model:
- 403 for non-members
- members read-only
- admins can manage members but not edit profile
- owners can edit profile + manage members
- platform admin can do anything
- last-owner protection blocks self-removal of the only owner
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


def _mk_user(uid: str, username: str, *, platform_admin: bool = False) -> str:
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, "
        "is_platform_admin, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (uid, username, auth.hash_password("p"), username,
         1 if platform_admin else 0, int(time.time())),
    )
    sid, _ = auth.create_session(uid, "127.0.0.1", "test")
    return sid


def _mk_enterprise(eid: str = "yinhu") -> None:
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        (eid, eid, eid, int(time.time())),
    )


def _grant(uid: str, eid: str, role: str) -> None:
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        (uid, eid, role, int(time.time())),
    )


@pytest.fixture
def setup():
    db.init()
    _mk_enterprise("yinhu")
    sids = {
        "owner": _mk_user("u_o", "owner_alice"),
        "admin": _mk_user("u_a", "admin_bob"),
        "member": _mk_user("u_m", "member_carol"),
        "outsider": _mk_user("u_x", "outsider_dan"),
        "platform": _mk_user("u_p", "plat_eve", platform_admin=True),
    }
    _grant("u_o", "yinhu", "owner")
    _grant("u_a", "yinhu", "admin")
    _grant("u_m", "yinhu", "member")
    return sids


# ─── auth gating ────────────────────────────────────────────────

def test_outsider_denied(client, setup):
    r = client.get("/api/enterprise/yinhu",
                   cookies={"app_session": setup["outsider"]})
    assert r.status_code == 403


def test_member_can_read_profile(client, setup):
    r = client.get("/api/enterprise/yinhu",
                   cookies={"app_session": setup["member"]})
    assert r.status_code == 200
    assert r.json()["id"] == "yinhu"


# ─── profile edit gating ────────────────────────────────────────

def test_member_cannot_edit_profile(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu",
        json={"industry": "manufacturing"},
        cookies={"app_session": setup["member"]},
    )
    assert r.status_code == 403


def test_admin_cannot_edit_profile(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu",
        json={"industry": "manufacturing"},
        cookies={"app_session": setup["admin"]},
    )
    assert r.status_code == 403


def test_owner_can_edit_profile_safe_subset(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu",
        json={
            "industry": "manufacturing",
            "billing_email": "billing@yinhu.com",
            "plan": "enterprise",      # rejected by owner scope — silently dropped
            "active": 0,                # rejected
        },
        cookies={"app_session": setup["owner"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["industry"] == "manufacturing"
    assert body["billing_email"] == "billing@yinhu.com"
    # Owner cannot escalate plan or deactivate self.
    assert body["plan"] == "trial"
    assert body["active"] == 1


def test_platform_admin_can_edit_through_self_service(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu",
        json={"industry": "any"},
        cookies={"app_session": setup["platform"]},
    )
    assert r.status_code == 200


# ─── member management gating ───────────────────────────────────

def test_member_cannot_invite(client, setup):
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_new','newbie',%s,'Newbie',%s)",
        (auth.hash_password("p"), int(time.time())),
    )
    r = client.post(
        "/api/enterprise/yinhu/members",
        json={"username": "newbie"},
        cookies={"app_session": setup["member"]},
    )
    assert r.status_code == 403


def test_admin_can_invite_member(client, setup):
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_new','newbie',%s,'Newbie',%s)",
        (auth.hash_password("p"), int(time.time())),
    )
    r = client.post(
        "/api/enterprise/yinhu/members",
        json={"username": "newbie", "role": "member"},
        cookies={"app_session": setup["admin"]},
    )
    assert r.status_code == 200


def test_admin_cannot_mint_owner(client, setup):
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_new','newbie',%s,'Newbie',%s)",
        (auth.hash_password("p"), int(time.time())),
    )
    r = client.post(
        "/api/enterprise/yinhu/members",
        json={"username": "newbie", "role": "owner"},
        cookies={"app_session": setup["admin"]},
    )
    assert r.status_code == 403


def test_owner_can_mint_owner(client, setup):
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_new','newbie',%s,'Newbie',%s)",
        (auth.hash_password("p"), int(time.time())),
    )
    r = client.post(
        "/api/enterprise/yinhu/members",
        json={"username": "newbie", "role": "owner"},
        cookies={"app_session": setup["owner"]},
    )
    assert r.status_code == 200
    assert db.get_enterprise_role("u_new", "yinhu") == "owner"


def test_owner_can_change_role(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu/members/u_m",
        json={"role": "admin"},
        cookies={"app_session": setup["owner"]},
    )
    assert r.status_code == 200
    assert db.get_enterprise_role("u_m", "yinhu") == "admin"


def test_admin_cannot_change_role(client, setup):
    r = client.patch(
        "/api/enterprise/yinhu/members/u_m",
        json={"role": "admin"},
        cookies={"app_session": setup["admin"]},
    )
    assert r.status_code == 403


def test_last_owner_cannot_be_removed(client, setup):
    """Sole owner removal is blocked to keep the enterprise administered."""
    r = client.delete(
        "/api/enterprise/yinhu/members/u_o",
        cookies={"app_session": setup["owner"]},
    )
    assert r.status_code == 409


def test_owner_can_be_removed_when_another_owner_exists(client, setup):
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES ('u_o2','owner2',%s,'Owner2',%s)",
        (auth.hash_password("p"), int(time.time())),
    )
    _grant("u_o2", "yinhu", "owner")
    r = client.delete(
        "/api/enterprise/yinhu/members/u_o",
        cookies={"app_session": setup["owner"]},
    )
    assert r.status_code == 200
