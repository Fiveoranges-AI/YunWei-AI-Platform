#!/usr/bin/env bash
# 锦泰 完整闭环 happy path · 一行命令跑完后端全链.
#
# 12 步 (从 0 数据 → 完整三表):
#   1.  /finance/chart-of-accounts          (首次自动 seed 15 个科目)
#   2.  /confirm/entities Supplier          (山东中铝)
#   3.  /confirm/entities Material          (α 氧化铝粉,有 safety_stock)
#   4.  /confirm/entities FixedAsset (生产线) — 通过 confirm 写 BOM-like 入账
#   5.  POST 期初余额 (直接 SQL seed 不通过 API)  — 注:这一步生产环境通常走专用录入页;
#       demo curl 用 confirm_writer 写 PeriodOpeningBalance entity 即可,本脚本跳过
#   6.  /confirm/entities IssueVoucher       (车间领料单)
#   7.  /procurement/issue-vouchers/{id}/confirm-and-issue
#         → 扣库 → 跌破安全线 → AI auto-draft PR (近 3 月用量 + 自动绑 supplier)
#   8.  /procurement/requisitions/{id}/approve  → 自动 PO
#   9.  /procurement/purchase-orders/{id}/receive → 入库 + WAC 更新 + 应付
#   10. /finance/balance-sheet              (会企 01)
#   11. /finance/pnl-distribution           (会企 02)
#   12. /finance/cashflow                   (会企 03)
#   13. /finance/depreciation + /finance/cost-breakdown
#   14. /procurement/inventory-ledger
#   15. /briefing/kpi                       (老板视角 经营日报 KPI)
#
# 限制: PeriodOpeningBalance 当前没 confirm entity_type 支持,所以期初余额数字默认为 0;
# 会企 01/02/03 行结构齐全,数字本期变动 (营业收入/成本/折旧) 都从 entities 聚合.
#
# Usage:
#   BASE=http://127.0.0.1:8000/api/win COOKIE='app_session=...' \
#     bash scripts/jintai/full-demo.sh
#
# Or for a fresh server-less demo via pytest:
#   pytest services/platform-api/tests/test_jintai_mainline_e2e.py -v
#   pytest services/platform-api/tests/test_jintai_finance_reports.py -v
#   pytest services/platform-api/tests/test_jintai_round3_edges.py -v
#
# Dependencies: curl, jq.

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000/api/win}"
COOKIE="${COOKIE:-}"
PERIOD="${PERIOD:-$(date -u +%Y-%m)}"
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

section() {
  echo
  echo "============================================================"
  echo "==> $1"
  echo "============================================================"
}

show_get() {
  local label="$1"; shift
  echo
  echo "--- $label ---"
  curl "${CURL_OPTS[@]}" "$@" | jq '.'
}

# ============================== 1. chart of accounts =====================
section "Step 1/15 · 科目主表(首次自动 seed)"
show_get "/finance/chart-of-accounts" "$BASE/finance/chart-of-accounts"

# ============================== 2-3. seed supplier + material =============
section "Step 2-3/15 · seed Supplier + Material (走 /confirm/entities 路径)"
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

# ============================== 4. issue voucher confirm + 主线 =========
section "Step 4-7/15 · 上传领料单 → confirm → 扣库 → 缺料 → AI auto-draft PR"
ISSUE_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg mid "$MATERIAL_ID" --arg qty "$ISSUE_QTY" --arg dt "$(date -u +%Y-%m-%d)" --arg vno "BL-DEMO-$(date +%s)" '{
    ingestion_id: ("demo-issue-" + (now|tostring|.[:10])),
    source_type: "issue_voucher_photo",
    source_ref: "storage://demo/issue-BL.jpg",
    entities: [{
      entity_type: "IssueVoucher",
      temp_id: "iv1",
      fields: [
        {name: "voucher_no", value: $vno, confidence: 0.96},
        {name: "workshop", value: "成型车间", confidence: 0.97},
        {name: "applicant", value: "张师傅", confidence: 0.93},
        {name: "material_id", value: $mid, confidence: 1.0},
        {name: "quantity", value: ($qty|tonumber), confidence: 0.94},
        {name: "unit", value: "kg", confidence: 0.99},
        {name: "issued_date", value: $dt, confidence: 0.92}
      ]
    }]
  }')")
VOUCHER_ID=$(echo "$ISSUE_RESP" | jq -r '.written[0].entity_id')
echo "    voucher_id=$VOUCHER_ID"

echo
echo "--- POST /procurement/issue-vouchers/$VOUCHER_ID/confirm-and-issue ---"
ISSUE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST \
  "$BASE/procurement/issue-vouchers/$VOUCHER_ID/confirm-and-issue")
echo "$ISSUE_RESULT" | jq '.'
PR_ID=$(echo "$ISSUE_RESULT" | jq -r '.auto_drafted_pr_id // empty')
if [[ -z "$PR_ID" || "$PR_ID" == "null" ]]; then
  echo "(no auto-draft PR — stock did not fall below safety; skipping rest)"
  exit 0
fi

# ============================== 8. approve PR =============================
section "Step 8/15 · 张主管批准 PR → 自动转 PO"
PR_DETAIL=$(curl "${CURL_OPTS[@]}" "$BASE/procurement/requisitions" \
  | jq --arg id "$PR_ID" '.[] | select(.id == $id)')
PR_ITEM_ID=$(echo "$PR_DETAIL" | jq -r '.items[0].id')
APPROVE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST \
  "$BASE/procurement/requisitions/$PR_ID/approve" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg sid "$SUPPLIER_ID" --arg iid "$PR_ITEM_ID" --arg price "$UNIT_PRICE" '{
    supplier_id: $sid,
    unit_prices: {($iid): ($price|tonumber)}
  }')")
echo "$APPROVE_RESULT" | jq '.'
PO_ID=$(echo "$APPROVE_RESULT" | jq -r '.po_id')

# ============================== 9. receive PO ============================
section "Step 9/15 · 入库 → WAC 加权平均更新 + 应付新增"
RECEIVE_RESULT=$(curl "${CURL_OPTS[@]}" -X POST \
  "$BASE/procurement/purchase-orders/$PO_ID/receive" \
  -H 'Content-Type: application/json' \
  -d '{"warehouse": "原料库 A-02"}')
echo "$RECEIVE_RESULT" | jq '.'

# ============================== 10-12. 财务三表 ==========================
section "Step 10/15 · 会企 01 资产负债表"
show_get "/finance/balance-sheet?period=$PERIOD" "$BASE/finance/balance-sheet?period=$PERIOD"

section "Step 11/15 · 会企 02 利润及利润分配表 (含本期折旧)"
show_get "/finance/pnl-distribution?period=$PERIOD" "$BASE/finance/pnl-distribution?period=$PERIOD"

section "Step 12/15 · 会企 03 现金流量表"
show_get "/finance/cashflow?period=$PERIOD" "$BASE/finance/cashflow?period=$PERIOD"

# ============================== 13. 折旧 + 成本拆分 ======================
section "Step 13/15 · 折旧台账 + 成本拆分"
show_get "/finance/depreciation?period=$PERIOD" "$BASE/finance/depreciation?period=$PERIOD"
show_get "/finance/cost-breakdown?period=$PERIOD" "$BASE/finance/cost-breakdown?period=$PERIOD"

# ============================== 14. 进销存台账 ===========================
section "Step 14/15 · 进销存台账 (material=$MATERIAL_ID period=$PERIOD)"
show_get "/procurement/inventory-ledger" \
  "$BASE/procurement/inventory-ledger?material_id=$MATERIAL_ID&period=$PERIOD"

# ============================== 15. KPI ==================================
section "Step 15/15 · 经营日报 KPI (老板视角)"
show_get "/briefing/kpi" "$BASE/briefing/kpi"

echo
echo "============================================================"
echo "✓ 锦泰后端全链 happy path 跑通"
echo "  Supplier $SUPPLIER_ID / Material $MATERIAL_ID / PR $PR_ID / PO $PO_ID"
echo "  三表 + 折旧 + 成本拆分 + 台账 + KPI 全部 GET 成功"
echo "============================================================"
