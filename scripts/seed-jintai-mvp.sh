#!/usr/bin/env bash
# Apply migrations and 锦泰耐火材料 MVP seed data to the configured platform Postgres DB.
#
# Migrations normally run when platform_app starts. Running them here as well
# keeps this script useful on a fresh local DB before the web service boots.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set. Create .env from .env.example or export DATABASE_URL." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql is required to apply the seed file." >&2
  exit 1
fi

echo "→ applying platform migrations"
for migration in services/platform-api/migrations/[0-9][0-9][0-9]_*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration" >/dev/null
done

echo "→ applying 锦泰 MVP seed data"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f services/platform-api/seeds/001_jintai_mvp_seed.sql

echo "✓ seed applied"
