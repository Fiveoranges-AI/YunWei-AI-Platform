#!/usr/bin/env bash
# Seed the platform DB with the bootstrap admin user, register the yinhu
# tenant, and write the issued HMAC secret/kid into the agent's .env file.
# DB is the source of truth for HMAC keys; the agent .env is its on-disk
# reflection.
#
# Prereqs:
#   - .env populated (TUNNEL_TOKEN, COOKIE_SECRET, ADMIN_BOOTSTRAP_*)
#   - agents/yinhu-super-xiaochen/.env populated (ANTHROPIC_API_KEY etc.;
#     placeholder HMAC values get overwritten by this script)
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

COMPOSE="docker compose -f ops/docker-compose.yml"
AGENT_ENV="agents/yinhu-super-xiaochen/.env"

if [ ! -f "$AGENT_ENV" ]; then
    echo "ERROR: $AGENT_ENV not found." >&2
    echo "  Copy agents/yinhu-super-xiaochen/.env.example, fill in" >&2
    echo "  ANTHROPIC_API_KEY, then re-run this script." >&2
    exit 1
fi

echo "→ creating user xuzong"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin add-user xuzong "许总" \
    --password "$ADMIN_BOOTSTRAP_PASSWORD" --email "xu@yinhu.example"

echo "→ adding tenant yinhu/super-xiaochen"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin add-tenant yinhu super-xiaochen \
    --display-name "银湖石墨 - 超级小陈" \
    --container-url "http://agent-yinhu-super-xiaochen:8000" \
    | tee /tmp/tenant-out.txt

# Pull the freshly-issued HMAC values out of stdout and patch the agent
# env in place so the agent container reads exactly what the platform
# stored.
NEW_SECRET=$(awk -F= '/^HMAC_SECRET_CURRENT=/{print $2}' /tmp/tenant-out.txt)
NEW_KID=$(awk -F= '/^HMAC_KEY_ID_CURRENT=/{print $2}' /tmp/tenant-out.txt)

if [ -z "$NEW_SECRET" ] || [ -z "$NEW_KID" ]; then
    echo "ERROR: could not parse HMAC values from add-tenant output." >&2
    exit 1
fi

sed -i.bak \
    -e "s|^HMAC_SECRET_CURRENT=.*|HMAC_SECRET_CURRENT=$NEW_SECRET|" \
    -e "s|^HMAC_KEY_ID_CURRENT=.*|HMAC_KEY_ID_CURRENT=$NEW_KID|" \
    "$AGENT_ENV"
rm -f "$AGENT_ENV.bak"
echo "  patched HMAC_SECRET_CURRENT / HMAC_KEY_ID_CURRENT in $AGENT_ENV"

echo "→ granting xuzong → yinhu/super-xiaochen"
$COMPOSE run --rm platform-app \
    python -m platform_app.admin grant xuzong yinhu super-xiaochen --role user

echo
echo "✓ bootstrap done. login: xuzong / [ADMIN_BOOTSTRAP_PASSWORD from .env]"
echo "  Restart agent so it picks up new HMAC env:"
echo "    $COMPOSE up -d agent-yinhu-super-xiaochen"
