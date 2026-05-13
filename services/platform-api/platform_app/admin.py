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
    for r in db.main().execute(
        "SELECT id, username, display_name, last_login, is_platform_admin FROM users"
    ).fetchall():
        flag = " [PLATFORM ADMIN]" if r["is_platform_admin"] else ""
        print(f"{r['id']:20} {r['username']:15} {r['display_name']:20} "
              f"last_login={r['last_login']}{flag}")


def cmd_add_enterprise(args):
    db.init()
    eid = args.id.strip().lower()
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, industry, "
        "region, plan, onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (id) DO NOTHING",
        (eid, args.legal_name or eid, args.display_name or eid,
         args.industry, args.region, args.plan, "signed_up", _now()),
    )
    print(f"created enterprise id={eid}")


def cmd_list_enterprises(args):
    db.init()
    rows = db.main().execute(
        "SELECT e.id, e.display_name, e.plan, e.onboarding_stage, e.active, "
        "(SELECT COUNT(*) FROM enterprise_members em WHERE em.enterprise_id=e.id) AS members, "
        "(SELECT COUNT(*) FROM tenants t WHERE t.client_id=e.id AND t.active=1) AS agents "
        "FROM enterprises e ORDER BY e.created_at DESC"
    ).fetchall()
    for r in rows:
        active = "" if r["active"] else " [INACTIVE]"
        print(f"{r['id']:20} {r['display_name']:20} plan={r['plan']:10} "
              f"stage={r['onboarding_stage']:10} members={r['members']} "
              f"agents={r['agents']}{active}")


def cmd_promote_admin(args):
    db.init()
    res = db.main().execute(
        "UPDATE users SET is_platform_admin=1 WHERE username=%s RETURNING id",
        (args.username,),
    ).fetchone()
    if not res:
        sys.exit(f"user not found: {args.username}")
    print(f"promoted {args.username} → platform admin")


def cmd_demote_admin(args):
    db.init()
    res = db.main().execute(
        "UPDATE users SET is_platform_admin=0 WHERE username=%s RETURNING id",
        (args.username,),
    ).fetchone()
    if not res:
        sys.exit(f"user not found: {args.username}")
    print(f"demoted {args.username}")


def cmd_set_password(args):
    db.init()
    user_id = f"u_{args.username}"
    row = db.main().execute("SELECT id FROM users WHERE id=%s", (user_id,)).fetchone()
    if not row:
        print(f"user not found: {args.username}", file=sys.stderr)
        sys.exit(1)
    pw = args.password or getpass.getpass(f"New password for {args.username}: ")
    db.main().execute(
        "UPDATE users SET password_hash=%s WHERE id=%s",
        (auth.hash_password(pw), user_id),
    )
    auth.revoke_user_sessions(user_id)
    print(f"password updated for {user_id}; existing sessions revoked")


def _generate_invite_code() -> str:
    """Format: WIN-XXXX-XXXX. Confusion-resistant alphabet
    (no 0/1/I/O/L/Z) so codes are dictation-safe over phone."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXY23456789"
    rand = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"WIN-{rand[:4]}-{rand[4:]}"


def cmd_invites_generate(args):
    db.init()
    expires_at_epoch: int | None = None
    if args.days:
        expires_at_epoch = _now() + args.days * 86400
    codes: list[str] = []
    for _ in range(args.count):
        # Retry on the rare collision (1-in-30^8 ≈ 1.5e-12 per draw, but be safe).
        for attempt in range(5):
            c = _generate_invite_code()
            try:
                db.insert_invite(
                    c,
                    created_by=args.created_by,
                    note=args.note,
                    expires_at_epoch=expires_at_epoch,
                )
                codes.append(c)
                break
            except Exception as e:
                if attempt == 4:
                    raise
                if "duplicate key" not in str(e).lower():
                    raise
    print(f"# Generated {len(codes)} invite codes")
    if args.note:
        print(f"# note: {args.note}")
    if args.days:
        print(f"# expires: {args.days} days")
    print("# Share URL pattern: https://app.fiveoranges.ai/register?code=<CODE>")
    print()
    for c in codes:
        print(c)


def cmd_invites_list(args):
    db.init()
    rows = db.list_invites(active_only=args.active_only)
    if not rows:
        print("(no invite codes)")
        return
    for r in rows:
        status = "redeemed" if r["redeemed_at"] else "revoked" if r["revoked_at"] else "active"
        extra = ""
        if r["redeemed_by_user_id"]:
            extra = f" → {r['redeemed_by_user_id']}"
        if r["expires_at"]:
            extra += f"  exp={r['expires_at']:%Y-%m-%d}"
        if r["note"]:
            extra += f"  ({r['note']})"
        print(f"{r['code']}  {status:<8}{extra}")


def cmd_invites_revoke(args):
    db.init()
    ok = db.revoke_invite(args.code.strip().upper())
    if ok:
        print(f"revoked {args.code}")
    else:
        sys.exit(f"code not found or already revoked: {args.code}")


def cmd_delete_user(args):
    db.init()
    user_id = f"u_{args.username}"
    row = db.main().execute("SELECT id FROM users WHERE id=%s", (user_id,)).fetchone()
    if not row:
        print(f"user not found: {args.username}", file=sys.stderr)
        sys.exit(1)
    if not args.yes:
        confirm = input(f"DELETE user {args.username} and all sessions/keys/grants? [y/N] ").strip().lower()
        if confirm != "y":
            print("aborted")
            return
    auth.revoke_user_sessions(user_id)
    db.main().execute("DELETE FROM api_keys WHERE user_id=%s", (user_id,))
    # Collect (client_id, agent_id) pairs we need to invalidate from the
    # ACL cache: every agent under enterprises the user belongs to, plus
    # any per-agent grants.
    pairs: set[tuple[str, str]] = set()
    enterprises = db.main().execute(
        "SELECT enterprise_id FROM enterprise_members WHERE user_id=%s",
        (user_id,),
    ).fetchall()
    for em in enterprises:
        for t in db.main().execute(
            "SELECT agent_id FROM tenants WHERE client_id=%s",
            (em["enterprise_id"],),
        ).fetchall():
            pairs.add((em["enterprise_id"], t["agent_id"]))
    for ag in db.main().execute(
        "SELECT client_id, agent_id FROM agent_grants WHERE user_id=%s",
        (user_id,),
    ).fetchall():
        pairs.add((ag["client_id"], ag["agent_id"]))
    for client_id, agent_id in pairs:
        db.invalidate_acl(user_id, client_id, agent_id)
    db.main().execute("DELETE FROM agent_grants WHERE user_id=%s", (user_id,))
    db.main().execute("DELETE FROM enterprise_members WHERE user_id=%s", (user_id,))
    db.main().execute("DELETE FROM users WHERE id=%s", (user_id,))
    print(f"deleted user_id={user_id}")


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

    s = sp.add_parser("set-password")
    s.add_argument("username")
    s.add_argument("--password")
    s.set_defaults(func=cmd_set_password)

    s = sp.add_parser("delete-user")
    s.add_argument("username")
    s.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    s.set_defaults(func=cmd_delete_user)

    s = sp.add_parser("add-enterprise",
        help="Create an enterprise (auto-created on add-tenant for new client_ids).")
    s.add_argument("id", help="enterprise_id (= legacy client_id)")
    s.add_argument("--legal-name")
    s.add_argument("--display-name")
    s.add_argument("--industry")
    s.add_argument("--region")
    s.add_argument("--plan", default="trial",
        choices=["trial", "standard", "enterprise"])
    s.set_defaults(func=cmd_add_enterprise)

    s = sp.add_parser("list-enterprises")
    s.set_defaults(func=cmd_list_enterprises)

    s = sp.add_parser("promote-admin",
        help="Promote a user to platform admin (cross-enterprise access).")
    s.add_argument("username")
    s.set_defaults(func=cmd_promote_admin)

    s = sp.add_parser("demote-admin")
    s.add_argument("username")
    s.set_defaults(func=cmd_demote_admin)

    # ─── invite codes ───────────────────────────────────────
    s = sp.add_parser("invites-generate",
        help="Generate N invite codes for /register self-signup.")
    s.add_argument("--count", type=int, default=1,
        help="How many codes to mint (default 1)")
    s.add_argument("--days", type=int, default=30,
        help="Validity in days (default 30; 0 = never expires)")
    s.add_argument("--note", default=None,
        help="Free-text label, surfaced in invites-list")
    s.add_argument("--created-by", default="platform-admin",
        help="Bookkeeping; usually leave default")
    s.set_defaults(func=cmd_invites_generate)

    s = sp.add_parser("invites-list",
        help="List all invite codes with status.")
    s.add_argument("--active-only", action="store_true",
        help="Only show codes that can still be redeemed")
    s.set_defaults(func=cmd_invites_list)

    s = sp.add_parser("invites-revoke",
        help="Disable an invite code (already-redeemed accounts unaffected).")
    s.add_argument("code")
    s.set_defaults(func=cmd_invites_revoke)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
