#!/usr/bin/env bash
# 锦泰主线 happy path · 一行命令跑完全链.
#
# Demonstrates the backend mainline against a running API at $BASE
# (default: http://127.0.0.1:8000/api/win):
#
#   Step 1.  Seed Supplier + Material   (POST /confirm/entities × 2 + 自定义 seed)
#            ↳ 直接 SQL 插入,因为生产环境的 Supplier/Material 是 reference 数据。
#   Step 2.  POST /confirm/entities      写 IssueVoucher (草稿)
#   Step 3.  POST /procurement/issue-vouchers/{id}/confirm-and-issue
#            ↳ 库存 -800 kg → 跌破安全线 → 自动生成 AI auto-draft PR
#   Step 4.  POST /procurement/requisitions/{id}/approve  → 自动 PO
#   Step 5.  POST /procurement/purchase-orders/{id}/receive  → 入库 + 应付
#   Step 6.  GET  /briefing/kpi  → KPI 实时反映
#
# Usage:
#   BASE=http://127.0.0.1:8000/api/win COOKIE='app_session=...' \
#     bash scripts/jintai/mainline-demo.sh
#
# Or for a fresh demo via the integration test (no server needed):
#   pytest services/platform-api/tests/test_jintai_mainline_e2e.py -v
#
# Dependencies: curl, jq.

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000/api/win}"
COOKIE="${COOKIE:-}"
SUPPLIER_NAME="${SUPPLIER_NAME:-山东中铝物资}"
MATERIAL_CODE="${MATERIAL_CODE:-RM-AL2O3-CT3000SG-$(date +%s)}"
MATERIAL_NAME="${MATERIAL_NAME:-α 氧化铝粉}"
ISSUE_QTY="${ISSUE_QTY:-800}"
UNIT_PRICE="${UNIT_PRICE:-24.00}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required (brew install jq)" >&2
  exit 1
fi

CURL_OPTS=(-sS)
if [[ -n "$COOKIE" ]]; then
  CURL_OPTS+=(-H "Cookie: $COOKIE")
fi

echo "==> [Step 1] Seed Supplier '$SUPPLIER_NAME' + Material '$MATERIAL_CODE'"
SUPPLIER_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg name "$SUPPLIER_NAME" '{
    ingestion_id: "demo-seed-supplier",
    source_type: "manual",
    source_ref: "",
    entities: [{
      entity_type: "Supplier",
      temp_id: "sup1",
      fields: [
        {name: "name", value: $name, confidence: 1.0},
        {name: "payment_terms_days", value: 60, confidence: 1.0}
      ]
    }]
  }')")
SUPPLIER_ID=$(echo "$SUPPLIER_RESP" | jq -r '.written[0].entity_id')
echo "    supplier_id=$SUPPLIER_ID"

MATERIAL_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg code "$MATERIAL_CODE" --arg name "$MATERIAL_NAME" '{
    ingestion_id: "demo-seed-material",
    source_type: "manual",
    source_ref: "",
    entities: [{
      entity_type: "Material",
      temp_id: "mat1",
      fields: [
        {name: "code", value: $code, confidence: 1.0},
        {name: "name", value: $name, confidence: 1.0},
        {name: "unit", value: "kg", confidence: 1.0},
        {name: "safety_stock", value: 1500, confidence: 1.0},
        {name: "last_balance", value: 1880, confidence: 1.0}
      ]
    }]
  }')")
MATERIAL_ID=$(echo "$MATERIAL_RESP" | jq -r '.written[0].entity_id')
echo "    material_id=$MATERIAL_ID"

echo
echo "==> [Step 2] Upload + confirm IssueVoucher (领料单 / 张师傅 / $ISSUE_QTY kg)"
ISSUE_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg mid "$MATERIAL_ID" --arg qty "$ISSUE_QTY" --arg date "$(date -u +%Y-%m-%d)" '{
    ingestion_id: ("demo-issue-" + (now|tostring|.[:10])),
    source_type: "issue_voucher_photo",
    source_ref: "storage://demo/issue-BL-DEMO.jpg",
    entities: [{
      entity_type: "IssueVoucher",
      temp_id: "iv1",
      fields: [
        {name: "voucher_no", value: ("BL-DEMO-" + (now|floor|tostring)), confidence: 0.96},
        {name: "workshop", value: "成型车间", confidence: 0.97},
        {name: "applicant", value: "张师傅", confidence: 0.93},
        {name: "material_id", value: $mid, confidence: 1.0},
        {name: "quantity", value: ($qty|tonumber), confidence: 0.94},
        {name: "unit", value: "kg", confidence: 0.99},
        {name: "purpose", value: "demo curl run", confidence: 0.85},
        {name: "issued_date", value: $date, confidence: 0.92}
      ]
    }]
  }')")
VOUCHER_ID=$(echo "$ISSUE_RESP" | jq -r '.written[0].entity_id')
echo "    voucher_id=$VOUCHER_ID"

echo
echo "==> [Step 3] Confirm-and-issue: 扣库存 + 缺料预警 + AI auto-draft PR"
ISSUE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/procurement/issue-vouchers/$VOUCHER_ID/confirm-and-issue")
echo "$ISSUE_RESULT" | jq '.'
PR_ID=$(echo "$ISSUE_RESULT" | jq -r '.auto_drafted_pr_id // empty')
if [[ -z "$PR_ID" || "$PR_ID" == "null" ]]; then
  echo "(no auto-draft PR — stock did not fall below safety; demo ends here)"
  exit 0
fi

echo
echo "==> [Step 4] Approve PR $PR_ID  (supplier=$SUPPLIER_ID, unit_price=$UNIT_PRICE)"
# Fetch the PR item id first so we can supply unit_price.
PR_DETAIL=$(curl "${CURL_OPTS[@]}" "$BASE/procurement/requisitions" \
  | jq --arg id "$PR_ID" '.[] | select(.id == $id)')
PR_ITEM_ID=$(echo "$PR_DETAIL" | jq -r '.items[0].id')
APPROVE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/procurement/requisitions/$PR_ID/approve" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg sid "$SUPPLIER_ID" --arg iid "$PR_ITEM_ID" --arg price "$UNIT_PRICE" '{
    supplier_id: $sid,
    unit_prices: {($iid): ($price|tonumber)}
  }')")
echo "$APPROVE_RESULT" | jq '.'
PO_ID=$(echo "$APPROVE_RESULT" | jq -r '.po_id')

echo
echo "==> [Step 5] Receive PO $PO_ID  → 库存回补 + 应付新增"
RECEIVE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/procurement/purchase-orders/$PO_ID/receive" \
  -H 'Content-Type: application/json' \
  -d '{"warehouse": "原料库 A-02"}')
echo "$RECEIVE_RESULT" | jq '.'

echo
echo "==> [Step 6] GET /briefing/kpi  (老板视角 经营日报)"
curl "${CURL_OPTS[@]}" "$BASE/briefing/kpi" | jq '.'
echo
echo "✓ 锦泰主线 backend happy path 全链跑通"
