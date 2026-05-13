#!/usr/bin/env bash
# Seed the platform DB with the bootstrap admin user, ensure the
# enterprise exists, and grant the user enterprise membership.
#
# v3 default flow does NOT provision a tenant + HMAC pair — dedicated
# runtimes are opt-in per enterprise and are registered via
# `runtime_registry` rather than the legacy `tenants` table. The
# minimal stack (platform-app + cloudflared) is enough to log in and
# use the shared `/win/` product.
#
# Flags:
#   --with-runtime   Register the example yinhu dedicated runtime in
#                    the runtime_registry (requires the runtime
#                    container reachable at the configured URL).
#
# Prereqs:
#   - .env populated with ADMIN_BOOTSTRAP_USER, ADMIN_BOOTSTRAP_PASSWORD,
#     TUNNEL_TOKEN, COOKIE_SECRET.
#   - infra/local stack up (`docker compose -f infra/local/docker-compose.yml up -d`).
set -euo pipefail
cd "$(dirname "$0")/.."

WITH_RUNTIME=0
for arg in "$@"; do
    case "$arg" in
        --with-runtime) WITH_RUNTIME=1 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

set -a
# shellcheck disable=SC1091
source .env
set +a

COMPOSE="docker compose -f infra/local/docker-compose.yml"

ADMIN_USER="${ADMIN_BOOTSTRAP_USER:-xuzong}"
ENTERPRISE_ID="${BOOTSTRAP_ENTERPRISE_ID:-yinhu}"
ENTERPRISE_DISPLAY_NAME="${BOOTSTRAP_ENTERPRISE_NAME:-银湖石墨}"

if [ -z "${ADMIN_BOOTSTRAP_PASSWORD:-}" ]; then
    echo "ERROR: ADMIN_BOOTSTRAP_PASSWORD missing in .env." >&2
    exit 1
fi

echo "→ ensuring enterprise $ENTERPRISE_ID"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin add-enterprise "$ENTERPRISE_ID" \
    --display-name "$ENTERPRISE_DISPLAY_NAME" \
    --plan trial

echo "→ creating user $ADMIN_USER"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin add-user "$ADMIN_USER" "$ENTERPRISE_DISPLAY_NAME" \
    --password "$ADMIN_BOOTSTRAP_PASSWORD" \
    --email "${ADMIN_BOOTSTRAP_EMAIL:-$ADMIN_USER@example.com}"

echo "→ granting $ADMIN_USER → $ENTERPRISE_ID (owner)"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin grant "$ADMIN_USER" "$ENTERPRISE_ID" --role owner

if [ "$WITH_RUNTIME" -eq 1 ]; then
    RUNTIME_ID="${RUNTIME_ID:-rt_yinhu_super_xiaochen}"
    RUNTIME_PROVIDER="${RUNTIME_PROVIDER:-super-xiaochen}"
    RUNTIME_URL="${RUNTIME_URL:-http://agent-yinhu-super-xiaochen:8000}"
    RUNTIME_VERSION="${RUNTIME_VERSION:-v1}"
    RUNTIME_CAPABILITY="${RUNTIME_CAPABILITY:-assistant}"

    echo "→ registering dedicated runtime $RUNTIME_ID → $RUNTIME_URL"
    $COMPOSE run --rm platform-app python -c "
from platform_app import db, runtime_registry
db.init()
runtime_registry.upsert_runtime(
    runtime_id='$RUNTIME_ID',
    mode='dedicated',
    provider='$RUNTIME_PROVIDER',
    endpoint_url='$RUNTIME_URL',
    version='$RUNTIME_VERSION',
)
runtime_registry.bind_runtime(
    enterprise_id='$ENTERPRISE_ID',
    capability='$RUNTIME_CAPABILITY',
    runtime_id='$RUNTIME_ID',
)
print('runtime bound: $ENTERPRISE_ID/$RUNTIME_CAPABILITY → $RUNTIME_ID')
"
fi

echo
echo "✓ bootstrap done. login: $ADMIN_USER / [ADMIN_BOOTSTRAP_PASSWORD from .env]"
if [ "$WITH_RUNTIME" -eq 1 ]; then
    echo "  dedicated runtime bound — verify with:"
    echo "    $COMPOSE exec platform-app python -c 'from platform_app import db,runtime_registry; db.init(); print(runtime_registry.get_runtime_for(\"$ENTERPRISE_ID\",\"${RUNTIME_CAPABILITY:-assistant}\"))'"
fi
