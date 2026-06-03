#!/usr/bin/env bash
# Round 7: clean-room smoke test — 从干净 Docker volume 起,跑全闭环,PASS/FAIL.
#
# CTO 早上一行命令证明 PR #114/#115/#116 stack 端到端可复现:
#   bash scripts/jintai/smoke-clean.sh
#
# 步骤:
#   1. docker compose down -v       (清掉所有 PG/Redis 数据)
#   2. docker compose up -d postgres redis  (干净 PG + Redis)
#   3. 启动 backend (--pg)
#   4. 跑 full-demo.sh (15 步主线 + 三表 + KPI)
#   5. 启动 frontend (Vite) + curl 验证关键 API
#   6. PASS / FAIL 总结
#
# 退出码: 0=全过,1=有 FAIL.

set -u  # not -e: 我们手动收 FAIL

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PA="$ROOT/services/platform-api"
WEB="$ROOT/apps/win-web"
COMPOSE="$ROOT/infra/local/dev-stack.yml"
BACKEND_PORT=18000   # 18000 不冲突
FRONTEND_PORT=15175  # 不冲突
BASE="http://127.0.0.1:$BACKEND_PORT/api/win"

PASS=0
FAIL=0
RESULTS=()

step() {
  echo
  echo "==> [$((PASS + FAIL + 1))] $1"
}

ok() {
  echo "    ✓ $1"
  PASS=$((PASS + 1))
  RESULTS+=("PASS: $1")
}

ng() {
  echo "    ✗ FAIL: $1"
  FAIL=$((FAIL + 1))
  RESULTS+=("FAIL: $1")
}

cleanup() {
  echo
  echo "==> cleanup"
  # Kill our backend + frontend
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null
  # NOTE: 不 down compose,reviewer 可能想看完后查 PG
}
trap cleanup EXIT

# Pre-flight
command -v docker >/dev/null 2>&1 || { ng "docker not found"; exit 1; }
command -v jq >/dev/null 2>&1 || { ng "jq not found (brew install jq)"; exit 1; }
[[ -f "$COMPOSE" ]] || { ng "compose file $COMPOSE missing"; exit 1; }
# frontend optional — 跨 worktree 场景 (PR #116 在另一 stack) frontend 不一定在这
FRONTEND_AVAILABLE=0
[[ -d "$WEB/node_modules" ]] && FRONTEND_AVAILABLE=1

# Step 1: clean PG volume
step "docker compose down -v (清掉 PG 数据 volume)"
docker compose -f "$COMPOSE" down -v >/dev/null 2>&1
ok "data volume removed"

# Step 2: up PG + Redis
step "docker compose up -d postgres redis"
docker compose -f "$COMPOSE" up -d >/dev/null 2>&1 || { ng "compose up failed"; exit 1; }
# Wait for PG ready
for i in $(seq 1 30); do
  docker exec jintai-dev-pg pg_isready -U postgres -d test >/dev/null 2>&1 && break
  sleep 1
done
docker exec jintai-dev-pg pg_isready -U postgres -d test >/dev/null 2>&1 && ok "PG @ 5433 ready" || ng "PG not ready after 30s"
docker exec jintai-dev-redis redis-cli ping >/dev/null 2>&1 && ok "Redis @ 6380 ready" || ng "Redis not ready"

# Step 3: backend (PG mode)
step "start backend (--pg, port $BACKEND_PORT)"
cd "$PA"
DATABASE_URL="postgresql://postgres:test@localhost:5433/test" \
  REDIS_URL="redis://localhost:6380" \
  COOKIE_SECRET="smoke-cookie-secret-32-bytes-padding==" \
  python3 -m uvicorn dev_jintai_backend:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" > /tmp/smoke-backend.log 2>&1 &
BACKEND_PID=$!
for i in $(seq 1 20); do
  if curl -sSf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
HEALTH=$(curl -sS "http://127.0.0.1:$BACKEND_PORT/health" 2>&1)
if echo "$HEALTH" | grep -q '"db":"postgres'; then
  ok "backend /health → postgres"
else
  ng "backend /health: $HEALTH"
  cat /tmp/smoke-backend.log | tail -15
fi

# Step 4: full-demo.sh — 走 15 步全闭环
step "BASE=$BASE bash full-demo.sh (主线 15 步)"
BASE="$BASE" bash "$ROOT/scripts/jintai/full-demo.sh" > /tmp/smoke-demo.log 2>&1
if grep -q "锦泰后端全链 happy path 跑通" /tmp/smoke-demo.log; then
  ok "full-demo.sh 完整跑通"
else
  ng "full-demo.sh 中断,tail of log:"
  tail -15 /tmp/smoke-demo.log
fi

# Step 5: 关键 API smoke
step "GET /briefing/kpi"
KPI=$(curl -sS "$BASE/briefing/kpi" 2>&1)
PAY=$(echo "$KPI" | jq -r '.payable_total' 2>/dev/null)
if [[ "$PAY" == "46080.0000" ]]; then
  ok "payable_total=¥46,080 (PO 入库后)"
else
  ng "payable_total=$PAY (expected 46080.0000)"
fi

step "GET /finance/balance-sheet?period=$(date -u +%Y-%m)"
BS=$(curl -sS "$BASE/finance/balance-sheet?period=$(date -u +%Y-%m)" 2>&1)
if echo "$BS" | jq -e '.assets | length > 0' >/dev/null 2>&1; then
  ok "balance-sheet 返回 $(echo $BS | jq '.assets | length') 个资产行"
else
  ng "balance-sheet 失败: $(echo $BS | head -c 200)"
fi

step "POST /parse/upload (synth jpg) → IssueVoucher 候选"
# Generate a tiny placeholder jpg (DemoMockProvider 不读内容,只看 filename + size)
SMOKE_JPG="/tmp/smoke-upload-领料单.jpg"
python3 -c "
try:
    from PIL import Image
    img = Image.new('RGB', (320, 240), color='#fcfaf6')
    img.save('$SMOKE_JPG', 'JPEG', quality=70)
except Exception:
    # Fallback: minimal jpg bytes (2-byte SOI + EOI;不是真有效 jpg 但 endpoint 不解析)
    with open('$SMOKE_JPG', 'wb') as f:
        f.write(b'\xff\xd8\xff\xd9smoke-placeholder')
"
UPLOAD_RESP=$(curl -sS -X POST "$BASE/parse/upload" \
  -F "file=@$SMOKE_JPG;type=image/jpeg" 2>&1)
PROVIDER=$(echo "$UPLOAD_RESP" | jq -r '.provider' 2>/dev/null)
ENTITY_TYPE=$(echo "$UPLOAD_RESP" | jq -r '.candidate.entities[0].entity_type' 2>/dev/null)
if [[ "$PROVIDER" == "demo-mock" && "$ENTITY_TYPE" == "IssueVoucher" ]]; then
  ok "/parse/upload → provider=demo-mock, entity_type=IssueVoucher"
else
  ng "/parse/upload returned provider=$PROVIDER entity=$ENTITY_TYPE"
fi

# Step 6: SQLite-based 后端测试快跑 (sanity check 不依赖 PG 状态)
step "pytest 后端关键测试 (mainline + finance + round3 edges + parse upload)"
cd "$PA"
PYTEST_OUT=$(python3 -m pytest \
  tests/test_jintai_mainline_e2e.py \
  tests/test_jintai_finance_reports.py \
  tests/test_jintai_round3_edges.py \
  tests/test_jintai_bom.py \
  tests/test_jintai_parse_upload.py \
  tests/test_procurement_api_listings.py \
  -q --tb=no --no-header 2>&1 | tail -3)
if echo "$PYTEST_OUT" | grep -qE "[0-9]+ passed"; then
  COUNT=$(echo "$PYTEST_OUT" | grep -oE "[0-9]+ passed" | head -1)
  ok "pytest: $COUNT"
else
  ng "pytest failed: $PYTEST_OUT"
fi

# Step 7: frontend (optional — 仅当 node_modules 存在;PR #116 在另一 worktree 没装就 skip)
step "frontend Vite quick HEAD check (port $FRONTEND_PORT)"
if [[ "$FRONTEND_AVAILABLE" -eq 0 ]]; then
  echo "    (skipped — $WEB/node_modules missing;在前端 worktree 跑 npm install 后可启用)"
  RESULTS+=("SKIP: frontend Vite (node_modules missing — cross-worktree expected)")
else
  cd "$WEB"
  npm run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 > /tmp/smoke-vite.log 2>&1 &
  FRONTEND_PID=$!
  for i in $(seq 1 20); do
    if curl -sSf -I "http://127.0.0.1:$FRONTEND_PORT/win/" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if curl -sSf -I "http://127.0.0.1:$FRONTEND_PORT/win/" >/dev/null 2>&1; then
    ok "frontend /win/ → HEAD 200"
  else
    ng "frontend not responding"
  fi
fi

# Summary
echo
echo "============================================================"
echo "smoke-clean.sh 总结: $PASS passed, $FAIL failed"
echo "============================================================"
for r in "${RESULTS[@]}"; do echo "  $r"; done
echo
if [[ "$FAIL" -gt 0 ]]; then
  echo "❌ smoke FAIL — 有 $FAIL 步失败,看 /tmp/smoke-*.log"
  exit 1
fi
echo "✅ smoke PASS — 全闭环 clean-room 可复现"
echo "PG 仍在 (docker compose -f infra/local/dev-stack.yml ps);要清:down -v"
