#!/usr/bin/env bash
# Round 13: 锦泰合同上传 end-to-end 一行命令演示.
#
# 跑这个之前 backend 必须在 :8000 跑 (or BASE env var override):
#   cd services/platform-api
#   python3 -m uvicorn dev_jintai_backend:app --host 127.0.0.1 --port 8000
#
# Demo 上传 3 份合同 PDF (来自 apps/win-web/public/samples/jintai/采购合同.pdf
# 复用 + 2 个 mock filename) → confirm 全部 → GET /contracts 验证落库 → curl
# 一份详情 (含 customer FK 解析后的对方信息).
#
# Usage:
#   bash scripts/jintai/contract-demo.sh
# Env:
#   BASE  (default http://127.0.0.1:8000/api/win)
#   COOKIE  (default '' — dev_jintai_backend 无 auth)

set -u  # not -e: we manually count PASS/FAIL

BASE="${BASE:-http://127.0.0.1:8000/api/win}"
COOKIE="${COOKIE:-}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SAMPLE_PDF="$ROOT/apps/win-web/public/samples/jintai/采购合同.pdf"

# Falls back to a tiny mock PDF if the real sample isn't checked into this
# worktree (e.g. the backend-only worktree without apps/win-web).
if [[ ! -f "$SAMPLE_PDF" ]]; then
  SAMPLE_PDF=$(mktemp --suffix=.pdf 2>/dev/null || mktemp -t r13-contract).pdf
  printf '%%PDF-1.4\n%%mock contract bytes for round-13 demo\n' > "$SAMPLE_PDF"
fi

CURL_OPTS=(-sS)
[[ -n "$COOKIE" ]] && CURL_OPTS+=(-H "Cookie: $COOKIE")

PASS=0
FAIL=0
log_pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }
log_fail() { echo "  ✗ FAIL: $1"; FAIL=$((FAIL+1)); }

# Pre-flight
command -v jq >/dev/null 2>&1 || { log_fail "jq not installed (brew install jq)"; exit 1; }

echo
echo "==> [1/6] backend /health 检查"
HEALTH=$(curl "${CURL_OPTS[@]}" -m 3 "${BASE%/api/win}/health" 2>&1)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
  log_pass "backend up · $(echo "$HEALTH" | jq -r '.db // .mode')"
else
  log_fail "backend not reachable at $BASE: $HEALTH"
  exit 1
fi

echo
echo "==> [2/6] 上传 3 份合同 PDF + confirm Customer+Contract"

LABELS=(
  "锂电_承烧板合同_容百Q3"
  "MLCC_匣钵供货合同_东磁2026"
  "磁材_氧化铝匣钵_当升Q4合同"
)

WRITTEN_CONTRACTS=()
for label in "${LABELS[@]}"; do
  FN="${label}.pdf"
  UPLOAD=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/parse/upload" \
    -F "file=@${SAMPLE_PDF};filename=${FN};type=application/pdf" 2>&1)
  ENT_TYPES=$(echo "$UPLOAD" | jq -r '[.candidate.entities[].entity_type] | sort | join("+")')
  REL=$(echo "$UPLOAD" | jq -r '[.candidate.relationships[].type] | join(",")')
  if [[ "$ENT_TYPES" != "Contract+Customer" ]]; then
    log_fail "${FN}: expected Customer+Contract, got [$ENT_TYPES]"
    continue
  fi
  if [[ "$REL" != *"Customer-has-Contract"* ]]; then
    log_fail "${FN}: missing Customer-has-Contract relationship"
    continue
  fi
  # Build confirm request (jq-only, no Python dep)
  CF_REQ=$(echo "$UPLOAD" | jq '{
    ingestion_id: .candidate.ingestion_id,
    source_type: .source_type,
    source_ref: .candidate.source.file_ref,
    entities: [.candidate.entities[] | {
      temp_id, entity_type,
      fields: [.fields[] | {
        name, value, confidence,
        was_edited: false,
        source_span: (.source_span // {}),
      }],
    }],
    relationships: .candidate.relationships,
  }')
  CF=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/confirm/entities" \
    -H 'Content-Type: application/json' --data-binary "$CF_REQ" 2>&1)
  WRITTEN=$(echo "$CF" | jq -r '[.written[].entity_type] | sort | join("+")')
  if [[ "$WRITTEN" != "Contract+Customer" ]]; then
    log_fail "${FN}: confirm written [$WRITTEN] (expected Contract+Customer)"
    continue
  fi
  CONTRACT_ID=$(echo "$CF" | jq -r '.written[] | select(.entity_type=="Contract") | .entity_id')
  WRITTEN_CONTRACTS+=("$CONTRACT_ID")
  log_pass "${FN} → Customer+Contract (contract_id=${CONTRACT_ID:0:8}...)"
done

echo
echo "==> [3/6] GET /contracts 列表验证"
LIST=$(curl "${CURL_OPTS[@]}" "$BASE/contracts" 2>&1)
LIST_COUNT=$(echo "$LIST" | jq 'length')
if [[ "$LIST_COUNT" -ge ${#LABELS[@]} ]]; then
  log_pass "list returned ${LIST_COUNT} contracts (≥ ${#LABELS[@]} uploaded)"
else
  log_fail "list returned ${LIST_COUNT} contracts, expected ≥ ${#LABELS[@]}"
fi

# Spot-check the response shape includes round 13 keys
SAMPLE_KEYS=$(echo "$LIST" | jq -r '.[0] | keys | join(",")')
for required in status payment_terms human_verified verified_by customer_id amount_total signing_date expiry_date; do
  if [[ ",$SAMPLE_KEYS," == *",$required,"* ]]; then
    log_pass "list row has '$required' key"
  else
    log_fail "list row missing '$required' key (have: $SAMPLE_KEYS)"
  fi
done

echo
echo "==> [4/6] GET /contracts/{id} 详情验证 customer FK 解析"
if [[ ${#WRITTEN_CONTRACTS[@]} -gt 0 ]]; then
  DETAIL=$(curl "${CURL_OPTS[@]}" "$BASE/contracts/${WRITTEN_CONTRACTS[0]}" 2>&1)
  CUSTOMER_NAME=$(echo "$DETAIL" | jq -r '.customer.full_name // "NULL"')
  if [[ "$CUSTOMER_NAME" != "NULL" ]] && [[ -n "$CUSTOMER_NAME" ]]; then
    log_pass "detail.customer.full_name='${CUSTOMER_NAME}' (Customer-has-Contract relationship resolved)"
  else
    log_fail "detail.customer is NULL — Customer-has-Contract relationship did not resolve contract.customer_id"
  fi
fi

echo
echo "==> [5/6] 数据完整性 — 合同金额 currency + 状态非空"
TOTAL_AMOUNT=$(echo "$LIST" | jq '[.[] | .amount_total // 0] | add')
WITH_STATUS=$(echo "$LIST" | jq '[.[] | select(.status != null)] | length')
echo "  · 合同金额合计: ¥${TOTAL_AMOUNT}"
echo "  · 状态非空: ${WITH_STATUS}/${LIST_COUNT}"

echo
echo "==> [6/6] 总结"
echo "============================================================"
echo "  PASS: ${PASS}"
echo "  FAIL: ${FAIL}"
echo "============================================================"
if [[ "$FAIL" -gt 0 ]]; then
  echo "❌ contract-demo: 有 ${FAIL} 步失败"
  exit 1
fi
echo "✅ contract-demo: 全闭环跑通"
echo
echo "看 UI:"
echo "  cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1"
echo "  浏览器: http://127.0.0.1:5175/win/?tab=jintai&mode=backend&inspect=1#inbox"
echo
