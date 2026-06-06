#!/usr/bin/env python3
"""One-shot, idempotent provisioning of a customer login.

Creates (or no-ops on) an enterprise, a user, and the user's membership in
that enterprise — in a single command — so the boss runs ONE thing instead
of three `platform-admin` subcommands. Built for onboarding 邹总 (光天):

    python scripts/admin/provision_user.py \\
        --username zou_zong --display-name "邹总" \\
        --email zou@gtnckj.com \\
        --enterprise guangtian --enterprise-name "宜兴光天耐火材料" \\
        --role owner

It reuses platform_app.auth / platform_app.db, so the SQL matches the
existing `platform-admin` CLI (admin.py) exactly — no new schema, no new
abstractions. Run it inside the platform-api environment (Railway shell or
`railway run`) where DATABASE_URL is set.

PASSWORD HANDLING — the password is read interactively via getpass and is
NEVER printed, logged, written to a file, or passed as a CLI flag. Only its
bcrypt hash touches the database. Existing users are NOT re-passworded unless
you pass --reset-password.
"""
from __future__ import annotations

import argparse
import getpass
import sys
import time
from pathlib import Path

# Make platform_app importable whether run from repo root or anywhere else:
# this file is <repo>/scripts/admin/provision_user.py and the package lives
# at <repo>/services/platform-api/platform_app.
_API_DIR = Path(__file__).resolve().parents[2] / "services" / "platform-api"
sys.path.insert(0, str(_API_DIR))

from platform_app import auth, db  # noqa: E402


def _now() -> int:
    return int(time.time())


def _ensure_enterprise(eid: str, legal_name: str, display_name: str) -> None:
    """Create the enterprise if absent (idempotent). Mirrors admin.py
    cmd_add_enterprise; leaves an existing enterprise untouched."""
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, industry, "
        "region, plan, onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (id) DO NOTHING",
        (eid, legal_name, display_name, None, None, "trial", "signed_up", _now()),
    )
    print(f"  enterprise '{eid}' ready")


def _ensure_user(username: str, display_name: str, email: str | None,
                 reset_password: bool) -> str:
    """Create the user if absent (idempotent). Prompts for a password only
    when actually creating (or when --reset-password). Returns user_id."""
    user_id = f"u_{username}"
    existing = db.main().execute(
        "SELECT id FROM users WHERE id=%s", (user_id,)
    ).fetchone()

    if existing and not reset_password:
        print(f"  user '{user_id}' already exists — password left unchanged")
        return user_id

    pw = getpass.getpass(f"  Set password for {username}: ")
    if not pw:
        sys.exit("aborted: empty password")
    pw2 = getpass.getpass("  Confirm password: ")
    if pw != pw2:
        sys.exit("aborted: passwords do not match")
    pw_hash = auth.hash_password(pw)

    if existing:
        db.main().execute(
            "UPDATE users SET password_hash=%s WHERE id=%s", (pw_hash, user_id),
        )
        auth.revoke_user_sessions(user_id)
        print(f"  user '{user_id}' password reset; existing sessions revoked")
    else:
        db.main().execute(
            "INSERT INTO users (id, username, password_hash, display_name, "
            "email, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, username, pw_hash, display_name, email, _now()),
        )
        print(f"  user '{user_id}' created")
    return user_id


def _ensure_membership(user_id: str, eid: str, role: str) -> None:
    """Grant enterprise membership (idempotent upsert). Mirrors admin.py
    cmd_grant; invalidates the ACL cache for every agent under the enterprise."""
    role = role if role in ("owner", "admin", "member") else "member"
    db.main().execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, "
        "granted_at, granted_by) VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (user_id, enterprise_id) DO UPDATE "
        "SET role=EXCLUDED.role, granted_at=EXCLUDED.granted_at, "
        "granted_by=EXCLUDED.granted_by",
        (user_id, eid, role, _now(), "provision_user"),
    )
    for r in db.main().execute(
        "SELECT agent_id FROM tenants WHERE client_id=%s", (eid,)
    ).fetchall():
        db.invalidate_acl(user_id, eid, r["agent_id"])
    print(f"  '{user_id}' is now {role} of enterprise '{eid}'")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="provision_user.py",
        description="Idempotently create enterprise + user + membership.",
    )
    p.add_argument("--username", required=True, help="login id stem; user_id = u_<username>")
    p.add_argument("--display-name", required=True)
    p.add_argument("--email", default=None)
    p.add_argument("--enterprise", required=True, help="enterprise_id, e.g. guangtian")
    p.add_argument("--enterprise-name", default=None,
                   help="display name; defaults to --enterprise")
    p.add_argument("--legal-name", default=None,
                   help="legal name; defaults to --enterprise-name")
    p.add_argument("--role", default="owner", choices=["owner", "admin", "member"])
    p.add_argument("--reset-password", action="store_true",
                   help="if the user already exists, prompt and reset their password")
    args = p.parse_args()

    eid = args.enterprise.strip().lower()
    ent_display = args.enterprise_name or eid
    ent_legal = args.legal_name or ent_display

    db.init()
    print(f"Provisioning '{args.username}' → enterprise '{eid}' (role={args.role})")
    _ensure_enterprise(eid, ent_legal, ent_display)
    user_id = _ensure_user(args.username, args.display_name, args.email,
                           args.reset_password)
    _ensure_membership(user_id, eid, args.role)
    print("Done. Verify login at https://app.fiveoranges.ai/")


if __name__ == "__main__":
    main()
