#!/usr/bin/env bash
# Round 25 (post-round-13 hotfix): one-liner to start backend + frontend
# for the 锦泰 demo. Prevents the recurring "白屏" report whose root cause
# is "dev servers got killed overnight (laptop sleep / terminal close)".
#
# Usage:
#   bash scripts/jintai/start-demo.sh
#
# What it does:
#   1. Detects whether port 8000 (backend) and 5175 (vite) already have
#      a listener. If yes, leaves them alone.
#   2. Starts whichever is missing in the background.
#   3. Health-checks both, then prints the URL to open in the browser.
#
# To stop (later):
#   bash scripts/jintai/start-demo.sh stop
#
# Notes:
#   - Uses SQLite (no docker / no PG). PG mode is `dev-backend.sh --pg`.
#   - Logs land in /tmp/jintai-demo-{backend,vite}.log
#   - PIDs in /tmp/jintai-demo-{backend,vite}.pid for later `stop`.

set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT/services/platform-api"
# Frontend lives in the sibling worktree when this script is run from the
# backend worktree (jintai-finance-reports). IMPORTANT: detect by Jintai-screen
# presence, not by `apps/win-web/` existence — the backend worktree has an
# OLDER `apps/win-web` (pre-jintai win-customer app) that would serve a
# stale bundle without the ?tab=jintai route, white-screening the user.
_has_jintai_screens() {
  [[ -f "$1/src/screens/jintai/JintaiDemoPage.tsx" ]]
}

WEB_DIR=""
for candidate in \
  "$ROOT/apps/win-web" \
  "$ROOT/../jintai-frontend-mode/apps/win-web" \
  "$ROOT/../jintai-frontend-backend-mode/apps/win-web" \
  ; do
  if _has_jintai_screens "$candidate"; then
    WEB_DIR=$(cd "$candidate" && pwd)
    break
  fi
done

if [[ -z "$WEB_DIR" ]]; then
  echo "ERR: cannot locate the jintai-aware apps/win-web."
  echo "     Need a checkout where src/screens/jintai/JintaiDemoPage.tsx exists."
  echo "     Tried:"
  echo "       $ROOT/apps/win-web"
  echo "       $ROOT/../jintai-frontend-mode/apps/win-web"
  exit 1
fi

BACKEND_PORT=8000
VITE_PORT=5175
BACKEND_PID_FILE=/tmp/jintai-demo-backend.pid
VITE_PID_FILE=/tmp/jintai-demo-vite.pid
BACKEND_LOG=/tmp/jintai-demo-backend.log
VITE_LOG=/tmp/jintai-demo-vite.log

_port_listening() {
  lsof -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1
}

_stop() {
  echo "==> stopping demo"
  for f in "$BACKEND_PID_FILE" "$VITE_PID_FILE"; do
    [[ -f "$f" ]] && pid=$(cat "$f") && [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid (from $f)" && rm -f "$f"
  done
  # Also catch anything still on those ports from before this run.
  for port in "$BACKEND_PORT" "$VITE_PORT"; do
    pid=$(_port_listening "$port")
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid on :$port"
  done
  echo "✓ done"
  exit 0
}

if [[ "${1:-}" == "stop" || "${1:-}" == "--stop" ]]; then
  _stop
fi

# Pre-flight
command -v npm >/dev/null 2>&1 || { echo "ERR: npm missing"; exit 1; }

# Find a python3 that can actually `import uvicorn`. macOS users frequently
# have multiple python3 binaries on PATH (system /usr/bin/python3, brew
# /usr/local/bin/python3, framework, venv, ...). The first one on PATH is
# often the bare system python with no third-party packages. Probe in
# preference order; stop at the first one with uvicorn importable. This
# fixes the round-29 regression where the script started a no-uvicorn
# python and 8000 was unreachable forever.
PY_BIN=""
for cand in \
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
    PY_BIN="$cand"
    break
  fi
done
if [[ -z "$PY_BIN" ]]; then
  echo "ERR: no python3 with uvicorn found."
  echo "     Install with: pip3 install uvicorn fastapi sqlalchemy aiosqlite"
  echo "     Or set: JINTAI_PYTHON=/path/to/python3 bash $0"
  exit 1
fi
echo "    python : $PY_BIN ($("$PY_BIN" --version 2>&1))"

echo "==> 锦泰 demo · start backend + vite"
echo "    backend: $BACKEND_DIR"
echo "    web    : $WEB_DIR"

# Backend
existing=$(_port_listening "$BACKEND_PORT")
if [[ -n "$existing" ]]; then
  echo "  backend already on :$BACKEND_PORT (pid=$existing) — leaving alone"
  echo "$existing" > "$BACKEND_PID_FILE"
else
  cd "$BACKEND_DIR"
  DATABASE_URL="sqlite+aiosqlite:///$(pwd)/jintai_dev_admin.db" \
    REDIS_URL="redis://localhost:6379" \
    COOKIE_SECRET="start-demo-cookie-secret-32-bytes-padding=" \
    "$PY_BIN" -m uvicorn dev_jintai_backend:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning \
      > "$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
  echo "  backend pid=$BACKEND_PID (log: $BACKEND_LOG)"
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
    echo "  npm install (one-time, ~30s)..."
    npm install --silent
  fi
  npm run dev -- --port "$VITE_PORT" --host 127.0.0.1 > "$VITE_LOG" 2>&1 &
  VITE_PID=$!
  echo "$VITE_PID" > "$VITE_PID_FILE"
  echo "  vite pid=$VITE_PID (log: $VITE_LOG)"
  cd "$ROOT"
fi

# Health check (≤8 sec wait each)
echo
echo "==> health check"
for i in $(seq 1 30); do
  curl -sS -m 1 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done
H=$(curl -sS -m 1 "http://127.0.0.1:$BACKEND_PORT/health" 2>&1)
if echo "$H" | grep -q '"status":"ok"'; then
  echo "  ✓ backend /health → $(echo "$H" | sed 's/.*"db":"\([^"]*\)".*/\1/')"
else
  echo "  ✗ backend NOT reachable: $H"
  echo "    see $BACKEND_LOG"
fi

for i in $(seq 1 30); do
  curl -sS -m 1 -I "http://127.0.0.1:$VITE_PORT/win/" >/dev/null 2>&1 && break
  sleep 0.5
done
if curl -sS -m 1 -I "http://127.0.0.1:$VITE_PORT/win/" 2>/dev/null | grep -q "200 OK"; then
  echo "  ✓ vite /win/ → 200 OK"
else
  echo "  ✗ vite NOT reachable"
  echo "    see $VITE_LOG"
fi

echo
echo "============================================================"
echo "  demo URL:"
echo "    http://127.0.0.1:$VITE_PORT/win/?tab=jintai"
echo
echo "  with backend overlay (?mode=backend) + inspector:"
echo "    http://127.0.0.1:$VITE_PORT/win/?tab=jintai&mode=backend&inspect=1"
echo
echo "  stop later:"
echo "    bash scripts/jintai/start-demo.sh stop"
echo "============================================================"
