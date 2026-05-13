"""Enterprise schema + ACL tests (migration 004).

Validates the option-3 design:
- enterprises / enterprise_members / agent_grants tables exist
- has_acl grants access via enterprise membership AND via agent_grants
- has_acl denies when neither path applies
- list_user_enterprises returns the user's enterprises with role
- when a NEW agent is added to an enterprise, existing members get
  access automatically (the headline win over option 2)
"""
from __future__ import annotations
import time
import pytest
from platform_app import auth, db


def _now() -> int:
    return int(time.time())


@pytest.fixture
def seeded():
    db.init()
    now = _now()
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_alice", "alice", auth.hash_password("p"), "Alice", now),
    )
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_bob", "bob", auth.hash_password("p"), "Bob", now),
    )
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        ("yinhu", "银湖", "银湖", now),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        ("yinhu", "super-xiaochen", "Super Xiaochen", "http://x",
         "s", "k", "uid_yinhu_sx", now),
    )
    return now


# ─── schema ─────────────────────────────────────────────────────

def test_004_creates_enterprise_tables():
    db.init()
    rows = db.main().execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchall()
    names = {r["table_name"] for r in rows}
    assert {"enterprises", "enterprise_members", "agent_grants"} <= names


def test_enterprises_columns_present():
    db.init()
    rows = db.main().execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='enterprises'"
    ).fetchall()
    cols = {r["column_name"] for r in rows}
    assert {"id", "legal_name", "display_name", "industry", "region",
            "size_tier", "tax_id", "primary_contact_user_id", "billing_email",
            "plan", "contract_start", "contract_end", "onboarding_stage",
            "active", "created_at"} <= cols


# ─── ACL semantics ──────────────────────────────────────────────

def test_member_has_access_to_all_agents_under_enterprise(seeded):
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "yinhu", "member", seeded),
    )
    assert db.has_acl("u_alice", "yinhu", "super-xiaochen") is True


def test_non_member_denied(seeded):
    assert db.has_acl("u_bob", "yinhu", "super-xiaochen") is False


def test_agent_grant_is_a_separate_path(seeded):
    """Bob isn't a yinhu member but has an explicit agent_grant — he
    should still be allowed on that one agent."""
    db.main().execute(
        "INSERT INTO agent_grants (user_id, client_id, agent_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("u_bob", "yinhu", "super-xiaochen", "user", seeded),
    )
    assert db.has_acl("u_bob", "yinhu", "super-xiaochen") is True
    # but only that agent — a different agent under same client is denied
    assert db.has_acl("u_bob", "yinhu", "finance-helper") is False


def test_new_agent_under_enterprise_auto_visible_to_members(seeded):
    """Headline option-3 win: adding a new tenant under an existing
    enterprise should NOT require ACL changes for existing members."""
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "yinhu", "member", seeded),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        ("yinhu", "finance-helper", "Finance Helper", "http://f",
         "s2", "k2", "uid_yinhu_fh", seeded),
    )
    # No grant change for the new agent — Alice still has access via membership.
    assert db.has_acl("u_alice", "yinhu", "finance-helper") is True


def test_get_enterprise_role_returns_role_or_none(seeded):
    assert db.get_enterprise_role("u_alice", "yinhu") is None
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "yinhu", "admin", seeded),
    )
    assert db.get_enterprise_role("u_alice", "yinhu") == "admin"


def test_list_user_enterprises_returns_visible_orgs(seeded):
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',%s)",
        ("acme", "ACME", "ACME", seeded),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "yinhu", "owner", seeded),
    )
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "acme", "member", seeded),
    )
    rows = db.list_user_enterprises("u_alice")
    by_id = {r["id"]: r for r in rows}
    assert set(by_id) == {"yinhu", "acme"}
    assert by_id["yinhu"]["role"] == "owner"
    assert by_id["acme"]["role"] == "member"


def test_inactive_enterprise_hidden_from_list(seeded):
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s)",
        ("u_alice", "yinhu", "member", seeded),
    )
    db.main().execute("UPDATE enterprises SET active=0 WHERE id=%s", ("yinhu",))
    assert db.list_user_enterprises("u_alice") == []
