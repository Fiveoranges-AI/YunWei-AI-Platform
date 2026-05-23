#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/services/platform-api"
PYTHON_BIN="${PYTHON_BIN:-$API_DIR/.venv/bin/python}"

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:test@127.0.0.1:5433/test}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6380}"
export COOKIE_SECRET="${COOKIE_SECRET:-test-cookie-secret-32-bytes-padding=}"
export JINTAI_DEMO_USERNAME="${JINTAI_DEMO_USERNAME:-jintai_owner}"
export JINTAI_DEMO_PASSWORD="${JINTAI_DEMO_PASSWORD:-jintai-demo-pass}"
export JINTAI_DEMO_ENTERPRISE_ID="${JINTAI_DEMO_ENTERPRISE_ID:-jintai-demo}"

cd "$API_DIR"

"$PYTHON_BIN" - <<'PY'
import os
import time

from platform_app import auth, db

username = os.environ["JINTAI_DEMO_USERNAME"]
password = os.environ["JINTAI_DEMO_PASSWORD"]
enterprise_id = os.environ["JINTAI_DEMO_ENTERPRISE_ID"]
user_id = f"u_{enterprise_id.replace('-', '_')}_owner"
now = int(time.time())

db.init()
with db.main()._get().cursor() as cur:
    cur.execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (id) DO UPDATE SET "
        "username=EXCLUDED.username, "
        "password_hash=EXCLUDED.password_hash, "
        "display_name=EXCLUDED.display_name",
        (user_id, username, auth.hash_password(password), "锦泰演示 Owner", now),
    )
    cur.execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (id) DO UPDATE SET "
        "legal_name=EXCLUDED.legal_name, "
        "display_name=EXCLUDED.display_name, "
        "plan=EXCLUDED.plan, "
        "onboarding_stage=EXCLUDED.onboarding_stage",
        (enterprise_id, "锦泰耐火材料", "锦泰耐火材料", "trial", "active", now),
    )
    cur.execute(
        "INSERT INTO enterprise_members (user_id, enterprise_id, role, granted_at) "
        "VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (user_id, enterprise_id) DO UPDATE SET role=EXCLUDED.role",
        (user_id, enterprise_id, "owner", now),
    )

print(f"✓ demo user ready: {username} / {password} ({enterprise_id})")
PY
