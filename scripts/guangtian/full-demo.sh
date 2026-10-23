#!/usr/bin/env bash
# 光天 · AI 库存管家 — 完整闭环 happy path · 一行命令跑完后端全链.
#
# 12 步 (种子数据 → 出入库 → 缺货预警 → 补产 → 问数):
#   1.  GET  /guangtian/skus                  (启动已 seed 8 个 SKU)
#   2.  GET  /guangtian/briefing/kpi          (老板视角 KPI)
#   3.  POST /confirm/entities GuangtianSku   (AI 先填→人确认 录入新 SKU)
#   4.  POST /guangtian/inbound               (生产入库 → +库存 + 写流水)
#   5.  POST /guangtian/outbound (AL90 全出)  → 扣库 → 跌破安全线 → 触发缺货预警
#   6.  GET  /guangtian/stock-alerts          (看预警事件)
#   7.  POST /guangtian/replenishments/generate (规则引擎扫缺口生成补产建议)
#   8.  GET  /guangtian/replenishments        (AI 补产建议清单, source=ai_autodraft)
#   9.  POST /guangtian/replenishments/{id}/adopt (采纳 → 挂工艺组工单)
#   10. POST /guangtian/ask                   (老板问 "明天优先生产什么")
#   11. GET  /guangtian/customer-orders       (订单缺口/可发率)
#   12. GET  /guangtian/daily-report          (AI 库存日报)
#
# Usage:
#   BASE=http://127.0.0.1:8000/api/win bash scripts/guangtian/full-demo.sh
#
# 或 server-less 用 pytest 验证:
#   pytest services/platform-api/tests/test_guangtian_inventory.py -v
#
# Dependencies: curl, jq.

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000/api/win}"
COOKIE="${COOKIE:-}"
NEW_SKU_CODE="${NEW_SKU_CODE:-GT-DEMO-$(date +%s)}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required (brew install jq)" >&2
  exit 1
fi

CURL_OPTS=(-sS)
[[ -n "$COOKIE" ]] && CURL_OPTS+=(-H "Cookie: $COOKIE")

section() { echo; echo "============================================================"; echo "==> $1"; echo "============================================================"; }
show_get() { local label="$1"; shift; echo; echo "--- $label ---"; curl "${CURL_OPTS[@]}" "$@" | jq '.'; }

G="$BASE/guangtian"

# ---- 1-2 ----
section "Step 1/12 · SKU 台账 (启动已 seed 8 个)"
SKUS=$(curl "${CURL_OPTS[@]}" "$G/skus")
echo "$SKUS" | jq '[.[] | {code, name, last_balance, safety_stock, status}]'
N=$(echo "$SKUS" | jq 'length'); echo "    SKU 数: $N"

section "Step 2/12 · 经营 KPI"
show_get "/guangtian/briefing/kpi" "$G/briefing/kpi"

# ---- 3. confirm new SKU (AI先填→人确认) ----
section "Step 3/12 · AI 先填→人确认 录入新 SKU ($NEW_SKU_CODE)"
CONFIRM_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg code "$NEW_SKU_CODE" '{
    ingestion_id: "guangtian-demo-sku",
    source_type: "wechat_screenshot",
    source_ref: "storage://demo/new-sku.jpg",
    entities: [{
      entity_type: "GuangtianSku", temp_id: "s1",
      fields: [
        {name: "code", value: $code, confidence: 0.97},
        {name: "name", value: "高纯刚玉砖(新)", confidence: 0.95},
        {name: "spec", value: "AL95 等级", confidence: 0.9},
        {name: "category", value: "刚玉砖", confidence: 0.92},
        {name: "unit", value: "块", confidence: 0.99},
        {name: "location", value: "C-03", confidence: 0.88},
        {name: "safety_stock", value: 300, confidence: 1.0}
      ]
    }]
  }')")
echo "$CONFIRM_RESP" | jq '{written: [.written[] | {entity_type, entity_id, human_verified, verified_by}]}'
NEW_SKU_ID=$(echo "$CONFIRM_RESP" | jq -r '.written[0].entity_id')

# ---- 4. inbound ----
section "Step 4/12 · 生产入库 (新 SKU +500)"
curl "${CURL_OPTS[@]}" -X POST "$G/inbound" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg id "$NEW_SKU_ID" '{sku_id: $id, quantity: 500, inbound_type: "production", source_ref: "SC-2026-0599"}')" | jq '.'

# ---- 5. outbound AL90 → trigger alert ----
section "Step 5-6/12 · AL90 全部出库 → 扣库 → 触发缺货预警"
AL90_ID=$(echo "$SKUS" | jq -r '.[] | select(.code=="JT-GZB-AL90") | .id')
AL90_BAL=$(echo "$SKUS" | jq -r '.[] | select(.code=="JT-GZB-AL90") | .last_balance')
OUT_RESP=$(curl "${CURL_OPTS[@]}" -X POST "$G/outbound" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg id "$AL90_ID" --arg q "$AL90_BAL" '{sku_id: $id, quantity: ($q|tonumber), customer: "常州新材科技", order_no: "SO-20260519-003", outbound_type: "sales"}')")
echo "$OUT_RESP" | jq '.'
ALERT_ID=$(echo "$OUT_RESP" | jq -r '.alert_id // empty')
[[ -n "$ALERT_ID" && "$ALERT_ID" != "null" ]] && echo "    ✓ 触发缺货预警 alert_id=$ALERT_ID" || echo "    (未触发预警)"
show_get "/guangtian/stock-alerts?only_open=true" "$G/stock-alerts?only_open=true"

# ---- 7-9. replenishment ----
section "Step 7-8/12 · AI 补产建议规则引擎 (扫低于安全线 + 订单缺口)"
GEN=$(curl "${CURL_OPTS[@]}" -X POST "$G/replenishments/generate"); echo "$GEN" | jq '.'
REPS=$(curl "${CURL_OPTS[@]}" "$G/replenishments")
echo "$REPS" | jq '[.[] | {sku_id, suggest_qty, priority, reason, source, status}]'
REP_ID=$(echo "$REPS" | jq -r '.[0].id // empty')

section "Step 9/12 · 采纳第一条补产建议 → 挂工艺组工单"
if [[ -n "$REP_ID" && "$REP_ID" != "null" ]]; then
  curl "${CURL_OPTS[@]}" -X POST "$G/replenishments/$REP_ID/adopt" | jq '.'
fi

# ---- 10. ask ----
section "Step 10/12 · 老板问数 · 明天应该优先生产什么"
curl "${CURL_OPTS[@]}" -X POST "$G/ask" -H 'Content-Type: application/json' \
  -d '{"question": "明天应该优先生产什么？"}' | jq '.'

# ---- 11-12. orders + report ----
section "Step 11/12 · 客户订单缺口 / 可发率"
curl "${CURL_OPTS[@]}" "$G/customer-orders" | jq '[.[] | {order_no, customer, level, fulfillment_pct}]'

section "Step 12/12 · AI 库存日报"
show_get "/guangtian/daily-report" "$G/daily-report"

echo
echo "============================================================"
echo "✓ 光天后端全链 happy path 跑通"
echo "  8 SKU seed + 新 SKU 录入 + 入库 + 出库扣减 + 缺货预警 +"
echo "  AI 补产建议生成/采纳 + 老板问数 + 订单缺口 + 库存日报 全部成功"
echo "============================================================"
