#!/usr/bin/env bash
# Seed the platform DB with the bootstrap admin user, the yinhu tenant,
# and the user's tenant ACL. Idempotent if you don't mind the SQL UPDATE
# rerunning. Reads .env via set -a so $ADMIN_BOOTSTRAP_PASSWORD is
# substituted by the host shell before docker compose run sees it.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

COMPOSE="docker compose -f ops/docker-compose.yml"

echo "→ creating user xuzong"
$COMPOSE run --rm platform-app \
  python -m platform_app.admin add-user xuzong "许总" \
  --password "$ADMIN_BOOTSTRAP_PASSWORD" --email "xu@yinhu.example"

echo "→ adding tenant yinhu/super-xiaochen"
$COMPOSE run --rm platform-app \
  python -m platform_app.admin add-tenant yinhu super-xiaochen \
  --display-name "银湖石墨 - 超级小陈" \
  --container-url "http://agent-yinhu-super-xiaochen:8000" \
  > /tmp/tenant-out.txt
cat /tmp/tenant-out.txt

# add-tenant generated its own random secret/key_id, but the agent
# container only knows the values from .env. Sync the DB row to the
# .env values so both ends share the same HMAC key material.
echo "→ syncing tenant HMAC secret from .env into DB"
$COMPOSE run --rm platform-app python -c "
from platform_app import db
import os
db.init()
db.main().execute(
    'UPDATE tenants SET hmac_secret_current=?, hmac_key_id_current=? WHERE client_id=? AND agent_id=?',
    (os.environ['YINHU_HMAC_SECRET_CURRENT'], os.environ['YINHU_HMAC_KEY_ID_CURRENT'], 'yinhu', 'super-xiaochen'),
)
print('synced secret from .env to DB')
"

echo "→ granting xuzong → yinhu/super-xiaochen"
$COMPOSE run --rm platform-app \
  python -m platform_app.admin grant xuzong yinhu super-xiaochen --role user

echo "✓ bootstrap done. login: xuzong / [ADMIN_BOOTSTRAP_PASSWORD]"
