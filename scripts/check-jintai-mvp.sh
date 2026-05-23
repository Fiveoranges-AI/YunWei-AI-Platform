#!/usr/bin/env bash
# Verify that the 锦泰耐火材料 MVP seed data exists with the expected counts.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql is required to verify the seed data." >&2
  exit 1
fi

rows=$(
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At <<'SQL'
WITH tenant AS (
  SELECT id FROM jintai_mvp.tenants WHERE slug = 'jintai-refractory'
),
checks AS (
  SELECT 'profiles' AS key, 5 AS expected, COUNT(*)::int AS actual
    FROM jintai_mvp.profiles WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'customers', 5, COUNT(*)::int
    FROM jintai_mvp.customers WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'products', 8, COUNT(*)::int
    FROM jintai_mvp.products WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'process_routes', 8, COUNT(*)::int
    FROM jintai_mvp.process_routes WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'process_steps', 24, COUNT(*)::int
    FROM jintai_mvp.process_steps WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'sales_orders', 15, COUNT(*)::int
    FROM jintai_mvp.sales_orders WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'production_flow_cards', 15, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'production_step_records', 45, COUNT(*)::int
    FROM jintai_mvp.production_step_records WHERE tenant_id = (SELECT id FROM tenant)
  UNION ALL SELECT 'delayed_flow_cards', 3, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards
    WHERE tenant_id = (SELECT id FROM tenant) AND status = 'delayed'
  UNION ALL SELECT 'sintering_flow_cards', 4, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards
    WHERE tenant_id = (SELECT id FROM tenant) AND current_step_code = 'sintering'
  UNION ALL SELECT 'quantity_exception_flow_cards', 2, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards
    WHERE tenant_id = (SELECT id FROM tenant) AND status = 'quantity_exception'
  UNION ALL SELECT 'completed_flow_cards', 2, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards
    WHERE tenant_id = (SELECT id FROM tenant) AND status = 'completed'
  UNION ALL SELECT 'created_flow_cards', 2, COUNT(*)::int
    FROM jintai_mvp.production_flow_cards
    WHERE tenant_id = (SELECT id FROM tenant) AND status = 'created'
  UNION ALL SELECT 'high_risk_products', 2, COUNT(*)::int
    FROM jintai_mvp.products
    WHERE tenant_id = (SELECT id FROM tenant) AND quality_risk_level = 'high'
)
SELECT key || '=' || actual || '/' || expected || '=' ||
       CASE WHEN actual = expected THEN 'ok' ELSE 'fail' END
FROM checks
ORDER BY key;
SQL
)

failed=0
while IFS= read -r row; do
  echo "$row"
  case "$row" in
    *=fail) failed=1 ;;
  esac
done <<< "$rows"

if [ "$failed" -ne 0 ]; then
  echo "ERROR: 锦泰 MVP seed data check failed." >&2
  exit 1
fi

echo "✓ 锦泰 MVP seed data check passed"
