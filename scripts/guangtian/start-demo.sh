#!/usr/bin/env bash
# 光天 · AI 库存管家 demo — one-liner to start backend + frontend.
# 克隆自 scripts/jintai/start-demo.sh (含 round-25 PY_BIN 探针修复), 改成光天专用.
#
# Usage:
#   bash scripts/guangtian/start-demo.sh         # 启动
#   bash scripts/guangtian/start-demo.sh stop    # 停止
#
# Notes:
#   - SQLite (无 docker / 无 PG). 后端 = dev_guangtian_backend.py (tenant guangtian_demo).
#   - 启动时自动 seed 8 个 SKU + 开账 + 3 订单.
#   - Logs: /tmp/guangtian-demo-{backend,vite}.log; PIDs: /tmp/guangtian-demo-{backend,vite}.pid

set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT/services/platform-api"

# 前端在 backend worktree 找不到光天屏幕时, 探测 sibling worktree.
# 用 GuangtianDemoPage.tsx 存在与否判断, 而非 apps/win-web 目录存在 (backend worktree
# 有一个旧 apps/win-web 不含 ?tab=guangtian 路由, 会白屏).
_has_guangtian_screens() { [[ -f "$1/src/screens/guangtian/GuangtianDemoPage.tsx" ]]; }

WEB_DIR=""
for candidate in \
  "$ROOT/apps/win-web" \
  "$ROOT/../guangtian-frontend-mode/apps/win-web" \
  "$ROOT/../jintai-frontend-mode/apps/win-web" \
  "$ROOT/../jintai-frontend-backend-mode/apps/win-web" \
  ; do
  if _has_guangtian_screens "$candidate"; then
    WEB_DIR=$(cd "$candidate" && pwd)
    break
  fi
done

if [[ -z "$WEB_DIR" ]]; then
  echo "ERR: cannot locate the guangtian-aware apps/win-web."
  echo "     Need a checkout where src/screens/guangtian/GuangtianDemoPage.tsx exists."
  echo "     Tried: $ROOT/apps/win-web + sibling worktrees"
  exit 1
fi

BACKEND_PORT=8000
VITE_PORT=5175
BACKEND_PID_FILE=/tmp/guangtian-demo-backend.pid
VITE_PID_FILE=/tmp/guangtian-demo-vite.pid
BACKEND_LOG=/tmp/guangtian-demo-backend.log
VITE_LOG=/tmp/guangtian-demo-vite.log

_port_listening() { lsof -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }

_stop() {
  echo "==> stopping demo"
  for f in "$BACKEND_PID_FILE" "$VITE_PID_FILE"; do
    [[ -f "$f" ]] && pid=$(cat "$f") && [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid (from $f)" && rm -f "$f"
  done
  for port in "$BACKEND_PORT" "$VITE_PORT"; do
    pid=$(_port_listening "$port")
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid on :$port"
  done
  echo "✓ done"; exit 0
}

[[ "${1:-}" == "stop" || "${1:-}" == "--stop" ]] && _stop

command -v npm >/dev/null 2>&1 || { echo "ERR: npm missing"; exit 1; }

# Find a python3 that can `import uvicorn` (round-25 fix: don't assume bare python3).
PY_BIN=""
for cand in \
  "${GUANGTIAN_PYTHON:-}" \
  "${JINTAI_PYTHON:-}" \
  "$(command -v python3 2>/dev/null)" \
  /usr/local/bin/python3 \
  /opt/homebrew/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  ; do
  [[ -z "$cand" ]] && continue
  [[ -x "$cand" ]] || continue
  if "$cand" -c "import uvicorn" >/dev/null 2>&1; then
    PY_BIN="$cand"; break
  fi
done
if [[ -z "$PY_BIN" ]]; then
  echo "ERR: no python3 with uvicorn found."
  echo "     Install: pip3 install uvicorn fastapi sqlalchemy aiosqlite"
  echo "     Or set: GUANGTIAN_PYTHON=/path/to/python3 bash $0"
  exit 1
fi
echo "    python : $PY_BIN ($("$PY_BIN" --version 2>&1))"

echo "==> 光天 demo · start backend + vite"
echo "    backend: $BACKEND_DIR"
echo "    web    : $WEB_DIR"

# Backend
existing=$(_port_listening "$BACKEND_PORT")
if [[ -n "$existing" ]]; then
  echo "  backend already on :$BACKEND_PORT (pid=$existing) — leaving alone"
  echo "$existing" > "$BACKEND_PID_FILE"
else
  cd "$BACKEND_DIR"
  DATABASE_URL="sqlite+aiosqlite:///$(pwd)/guangtian_dev_admin.db" \
    REDIS_URL="redis://localhost:6379" \
    COOKIE_SECRET="start-demo-cookie-secret-32-bytes-padding=" \
    "$PY_BIN" -m uvicorn dev_guangtian_backend:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning \
      > "$BACKEND_LOG" 2>&1 &
  echo "$!" > "$BACKEND_PID_FILE"
  echo "  backend pid=$! (log: $BACKEND_LOG)"
  cd "$ROOT"
fi

# Vite
existing=$(_port_listening "$VITE_PORT")
if [[ -n "$existing" ]]; then
  echo "  vite already on :$VITE_PORT (pid=$existing) — leaving alone"
  echo "$existing" > "$VITE_PID_FILE"
else
  cd "$WEB_DIR"
  if [[ ! -d node_modules ]]; then
    echo "  npm install (one-time, ~30s)..."; npm install --silent
  fi
  npm run dev -- --port "$VITE_PORT" --host 127.0.0.1 > "$VITE_LOG" 2>&1 &
  echo "$!" > "$VITE_PID_FILE"
  echo "  vite pid=$! (log: $VITE_LOG)"
  cd "$ROOT"
fi

echo; echo "==> health check"
for i in $(seq 1 30); do
  curl -sS -m 1 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done
H=$(curl -sS -m 1 "http://127.0.0.1:$BACKEND_PORT/health" 2>&1)
if echo "$H" | grep -q '"status":"ok"'; then
  echo "  ✓ backend /health → $(echo "$H" | sed 's/.*"db":"\([^"]*\)".*/\1/')"
else
  echo "  ✗ backend NOT reachable: $H"; echo "    see $BACKEND_LOG"
fi

for i in $(seq 1 30); do
  curl -sS -m 1 -I "http://127.0.0.1:$VITE_PORT/win/" >/dev/null 2>&1 && break
  sleep 0.5
done
if curl -sS -m 1 -I "http://127.0.0.1:$VITE_PORT/win/" 2>/dev/null | grep -q "200 OK"; then
  echo "  ✓ vite /win/ → 200 OK"
else
  echo "  ✗ vite NOT reachable"; echo "    see $VITE_LOG"
fi

echo
echo "============================================================"
echo "  demo URL:"
echo "    http://127.0.0.1:$VITE_PORT/win/?tab=guangtian"
echo
echo "  with backend overlay (?mode=backend) + inspector:"
echo "    http://127.0.0.1:$VITE_PORT/win/?tab=guangtian&mode=backend&inspect=1"
echo
echo "  stop later:"
echo "    bash scripts/guangtian/start-demo.sh stop"
echo "============================================================"
