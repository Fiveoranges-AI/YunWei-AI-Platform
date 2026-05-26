#!/usr/bin/env bash
# 锦泰 财务三表 + 进销存台账 + BOM explode demo curl.
#
# 假设 mainline-demo.sh 已经跑过 (有 supplier / material / 出入库 / payable 数据).
# 这里 GET 出三表 + 折旧 + 成本拆分 + 进销存 + BOM explode (如有 BOM).
#
# Usage:
#   BASE=http://127.0.0.1:8000/api/win COOKIE='app_session=...' PERIOD=2026-05 \
#     bash scripts/jintai/finance-demo.sh
#
# Dependencies: curl, jq.

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000/api/win}"
COOKIE="${COOKIE:-}"
PERIOD="${PERIOD:-$(date -u +%Y-%m)}"

CURL_OPTS=(-sS)
if [[ -n "$COOKIE" ]]; then
  CURL_OPTS+=(-H "Cookie: $COOKIE")
fi

show() {
  local label="$1"; shift
  echo
  echo "==> $label"
  curl "${CURL_OPTS[@]}" "$@" | jq '.'
}

# 1. 科目主表 (首次访问自动 seed)
show "chart of accounts" "$BASE/finance/chart-of-accounts"

# 2. 会企01 资产负债表
show "balance sheet ($PERIOD)" "$BASE/finance/balance-sheet?period=$PERIOD"

# 3. 会企02 利润及利润分配表
show "PNL distribution ($PERIOD)" "$BASE/finance/pnl-distribution?period=$PERIOD"

# 4. 会企03 现金流量表
show "cashflow ($PERIOD)" "$BASE/finance/cashflow?period=$PERIOD"

# 5. 折旧台账
show "depreciation ($PERIOD)" "$BASE/finance/depreciation?period=$PERIOD"

# 6. 成本拆分 (按物料 / 按供应商)
show "cost breakdown ($PERIOD)" "$BASE/finance/cost-breakdown?period=$PERIOD"

# 7. 进销存台账 (拿第一个物料示意)
MATERIAL_ID=$(curl "${CURL_OPTS[@]}" "$BASE/procurement/materials" | jq -r '.[0].id // empty')
if [[ -n "$MATERIAL_ID" ]]; then
  show "inventory ledger (material=$MATERIAL_ID period=$PERIOD)" \
    "$BASE/procurement/inventory-ledger?material_id=$MATERIAL_ID&period=$PERIOD"
fi

# 8. BOM list + explode (如有)
BOM_ID=$(curl "${CURL_OPTS[@]}" "$BASE/procurement/boms" | jq -r '.[0].id // empty')
if [[ -n "$BOM_ID" ]]; then
  show "BOM detail" "$BASE/procurement/boms/$BOM_ID"
  echo
  echo "==> BOM explode (batch_quantity=10)"
  curl "${CURL_OPTS[@]}" -X POST "$BASE/procurement/boms/$BOM_ID/explode" \
    -H 'Content-Type: application/json' \
    -d '{"batch_quantity": "10"}' | jq '.'
fi

echo
echo "✓ 财务三表 + 台账 + BOM happy path 跑通"
