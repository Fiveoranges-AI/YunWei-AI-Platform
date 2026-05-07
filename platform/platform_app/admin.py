"""管理 CLI:用户、tenant、密钥轮换。SSO.md §13.2-13.3."""
from __future__ import annotations
import argparse
import getpass
import json
import secrets
import sys
import time
import uuid
from . import auth, db


def _now() -> int: return int(time.time())


def cmd_add_user(args):
    db.init()
    pw = args.password or getpass.getpass(f"Password for {args.username}: ")
    user_id = f"u_{args.username}"
    db.main().execute(
        "INSERT INTO users (id, username, password_hash, display_name, email, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (user_id, args.username, auth.hash_password(pw), args.display_name, args.email, _now()),
    )
    print(f"created user_id={user_id}")


def cmd_add_tenant(args):
    db.init()
    secret = secrets.token_urlsafe(32)
    key_id = f"k-{int(time.time())}"
    uid = str(uuid.uuid4())
    # Auto-provision the enterprise if this is the first agent for the client.
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s, %s, %s, 'trial', 'signed_up', %s) "
        "ON CONFLICT (id) DO NOTHING",
        (args.client, args.client, args.display_name, _now()),
    )
    db.main().execute(
        "INSERT INTO tenants (client_id, agent_id, display_name, container_url, "
        "hmac_secret_current, hmac_key_id_current, tenant_uid, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (args.client, args.agent, args.display_name, args.container_url,
         secret, key_id, uid, _now()),
    )
    db.invalidate_tenant(args.client, args.agent)
    print(json.dumps({
        "client_id": args.client, "agent_id": args.agent,
        "hmac_secret_current": secret, "hmac_key_id_current": key_id,
        "tenant_uid": uid,
    }, indent=2))
    print("\n== AGENT .env ==")
    print(f"TENANT_CLIENT={args.client}")
    print(f"TENANT_AGENT={args.agent}")
    print(f"HMAC_SECRET_CURRENT={secret}")
    print(f"HMAC_KEY_ID_CURRENT={key_id}")
    print("HMAC_SECRET_PREV=")
    print("HMAC_KEY_ID_PREV=")


def cmd_grant(args):
    """Default: grant *enterprise membership* (blanket access to all
    agents). Use ``--agent-only`` for the consultant exception path —
    writes to agent_grants instead.
    """
    db.init()
    user_id = f"u_{args.username}"
    if args.agent_only:
        if not args.agent:
            sys.exit("--agent-only requires the agent argument")
        db.main().execute(
            "INSERT INTO agent_grants (user_id, client_id, agent_id, role, granted_at, granted_by) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (user_id, client_id, agent_id) DO UPDATE "
            "SET role=EXCLUDED.role, granted_at=EXCLUDED.granted_at, granted_by=EXCLUDED.granted_by",
            (user_id, args.client, args.agent, args.role, _now(), "cli"),
        )
        db.invalidate_acl(user_id, args.client, args.agent)
        print(f"granted (agent-only) {args.username} -> {args.client}/{args.agent} ({args.role})")
        return
    role = args.role if args.role in ("owner", "admin", "member") else "member"
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at, granted_by) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (user_id, enterprise_id) DO UPDATE "
        "SET role=EXCLUDED.role, granted_at=EXCLUDED.granted_at, granted_by=EXCLUDED.granted_by",
        (user_id, args.client, role, _now(), "cli"),
    )
    # Invalidate ACL cache for any agent the user might have queried.
    # We don't know which agents, so invalidate for all known agents under
    # this client — cheap, since this is a CLI command, not a hot path.
    for r in db.main().execute(
        "SELECT agent_id FROM tenants WHERE client_id=%s", (args.client,)
    ).fetchall():
        db.invalidate_acl(user_id, args.client, r["agent_id"])
    print(f"granted {args.username} as {role} of enterprise {args.client}")


def cmd_revoke(args):
    db.init()
    user_id = f"u_{args.username}"
    if args.agent_only:
        if not args.agent:
            sys.exit("--agent-only requires the agent argument")
        db.main().execute(
            "DELETE FROM agent_grants "
            "WHERE user_id=%s AND client_id=%s AND agent_id=%s",
            (user_id, args.client, args.agent),
        )
        db.invalidate_acl(user_id, args.client, args.agent)
        print(f"revoked agent_grant {args.username} on {args.client}/{args.agent}")
        return
    db.main().execute(
        "DELETE FROM enterprise_members WHERE user_id=%s AND enterprise_id=%s",
        (user_id, args.client),
    )
    for r in db.main().execute(
        "SELECT agent_id FROM tenants WHERE client_id=%s", (args.client,)
    ).fetchall():
        db.invalidate_acl(user_id, args.client, r["agent_id"])
    print(f"revoked membership of {args.username} from enterprise {args.client}")


def cmd_rotate_key(args):
    db.init()
    new_secret = secrets.token_urlsafe(32)
    new_kid = f"k-{int(time.time())}"
    row = db.main().execute(
        "SELECT hmac_secret_current, hmac_key_id_current FROM tenants WHERE client_id=%s AND agent_id=%s",
        (args.client, args.agent),
    ).fetchone()
    assert row, "tenant not found"
    db.main().execute(
        "UPDATE tenants SET hmac_secret_current=%s, hmac_key_id_current=%s, "
        "hmac_secret_prev=%s, hmac_key_id_prev=%s, hmac_rotated_at=%s "
        "WHERE client_id=%s AND agent_id=%s",
        (new_secret, new_kid, row["hmac_secret_current"], row["hmac_key_id_current"], _now(),
         args.client, args.agent),
    )
    db.invalidate_tenant(args.client, args.agent)
    print(f"rotated. new_kid={new_kid}\nnew_secret={new_secret}\n(prev kept for 24h)")


def cmd_clear_prev_key(args):
    db.init()
    db.main().execute(
        "UPDATE tenants SET hmac_secret_prev='', hmac_key_id_prev='' WHERE client_id=%s AND agent_id=%s",
        (args.client, args.agent),
    )
    db.invalidate_tenant(args.client, args.agent)
    print("prev key cleared")


def cmd_list_users(args):
    db.init()
    for r in db.main().execute("SELECT id, username, display_name, last_login FROM users").fetchall():
        print(f"{r['id']:20} {r['username']:15} {r['display_name']:20} last_login={r['last_login']}")


def main():
    p = argparse.ArgumentParser(prog="platform-admin")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("add-user")
    s.add_argument("username"); s.add_argument("display_name")
    s.add_argument("--password"); s.add_argument("--email")
    s.set_defaults(func=cmd_add_user)

    s = sp.add_parser("add-tenant")
    s.add_argument("client"); s.add_argument("agent")
    s.add_argument("--display-name", required=True)
    s.add_argument("--container-url", required=True)
    s.set_defaults(func=cmd_add_tenant)

    s = sp.add_parser("grant",
        help="Grant enterprise membership (default) or per-agent grant.")
    s.add_argument("username")
    s.add_argument("client", help="enterprise_id")
    s.add_argument("agent", nargs="?", help="required only with --agent-only")
    s.add_argument("--role", default="member",
        help="member | admin | owner (enterprise) | user (--agent-only)")
    s.add_argument("--agent-only", action="store_true",
        help="Write to agent_grants instead of enterprise_members.")
    s.set_defaults(func=cmd_grant)

    s = sp.add_parser("revoke",
        help="Revoke enterprise membership (default) or per-agent grant.")
    s.add_argument("username")
    s.add_argument("client")
    s.add_argument("agent", nargs="?")
    s.add_argument("--agent-only", action="store_true")
    s.set_defaults(func=cmd_revoke)

    s = sp.add_parser("rotate-tenant-key")
    s.add_argument("client"); s.add_argument("agent")
    s.set_defaults(func=cmd_rotate_key)

    s = sp.add_parser("clear-prev-key")
    s.add_argument("client"); s.add_argument("agent")
    s.set_defaults(func=cmd_clear_prev_key)

    s = sp.add_parser("list-users")
    s.set_defaults(func=cmd_list_users)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
