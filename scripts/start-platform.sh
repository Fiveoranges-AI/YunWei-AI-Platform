#!/usr/bin/env bash
# 一键跑通 锦泰 + 光天 两个 demo (同一个前端, 两个后端并行).
#
#   锦泰后端  dev_jintai_backend     → :8000  (tenant jintai_demo)
#   光天后端  dev_guangtian_backend  → :8001  (tenant guangtian_demo)
#   统一前端  guangtian-frontend     → :5175  (带 jintai + guangtian 两 tab)
#             前端用 VITE_JINTAI_BACKEND / VITE_GUANGTIAN_BACKEND 分别指向两后端,
#             所以 ?tab=jintai&mode=backend 打 :8000, ?tab=guangtian&mode=backend 打 :8001.
#
# Usage:
#   bash scripts/start-platform.sh           # 启动两者 (默认 127.0.0.1, 仅本机)
#   bash scripts/start-platform.sh --public  # vite 绑 0.0.0.0 (Tailscale/LAN 对端可看)
#   bash scripts/start-platform.sh stop      # 停止
#
# --public 安全: vite 绑 0.0.0.0 → Tailscale 对端 + 同网段 LAN 都能访问;
# 后端仍只在 127.0.0.1 不暴露 (demo 默认 mock 模式无后端调用)。演示完 stop。
#
# Notes:
#   - 纯 SQLite, 无 docker/PG. 失败看 /tmp/platform-{jintai,guangtian,vite}.log
#   - 光天后端尚未进 main (PR #122), 脚本会 probe guangtian-backend worktree.
#   - Override: $JINTAI_BACKEND_DIR / $GUANGTIAN_BACKEND_DIR / $DEMO_WEB_DIR / $JINTAI_PYTHON.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JINTAI_PORT=8000
GUANGTIAN_PORT=8001
VITE_PORT=5175

J_PID=/tmp/platform-jintai.pid
G_PID=/tmp/platform-guangtian.pid
V_PID=/tmp/platform-vite.pid
J_LOG=/tmp/platform-jintai.log
G_LOG=/tmp/platform-guangtian.log
V_LOG=/tmp/platform-vite.log

_listening() { lsof -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }

_stop() {
  echo "==> stopping platform"
  for f in "$J_PID" "$G_PID" "$V_PID"; do
    [[ -f "$f" ]] && pid=$(cat "$f") && [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid ($f)" && rm -f "$f"
  done
  for port in "$JINTAI_PORT" "$GUANGTIAN_PORT" "$VITE_PORT"; do
    pid=$(_listening "$port"); [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && echo "  killed pid=$pid on :$port"
  done
  echo "✓ done"; exit 0
}
[[ "${1:-}" == "stop" || "${1:-}" == "--stop" ]] && _stop

# --public: bind vite to 0.0.0.0 so a Tailscale / LAN peer can open the demo.
# Backends stay on 127.0.0.1 (NOT exposed). The demo default is mock mode →
# no backend calls, so a remote viewer sees the full demo without the backends.
# (?mode=backend stays local-only by design; remote backend-mode would need a
# vite proxy — see scripts/README.md.)
VITE_HOST="127.0.0.1"
if [[ "${1:-}" == "--public" ]]; then
  VITE_HOST="0.0.0.0"
fi

command -v npm >/dev/null 2>&1 || { echo "ERR: npm missing"; exit 1; }

# --- python with uvicorn (round-25 probe) ---
PY_BIN=""
for cand in \
  "${JINTAI_PYTHON:-}" "$(command -v python3 2>/dev/null)" \
  /usr/local/bin/python3 /opt/homebrew/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 ; do
  [[ -z "$cand" || ! -x "$cand" ]] && continue
  if "$cand" -c "import uvicorn" >/dev/null 2>&1; then PY_BIN="$cand"; break; fi
done
[[ -z "$PY_BIN" ]] && { echo "ERR: no python3 with uvicorn (set \$JINTAI_PYTHON)"; exit 1; }

# --- locate the two backend dirs ---
_probe() { # $1 = filename, rest = candidate dirs ; echoes first dir containing it
  local want="$1"; shift
  for d in "$@"; do [[ -n "$d" && -f "$d/$want" ]] && { (cd "$d" && pwd); return 0; }; done
  return 1
}
J_DIR=$(_probe dev_jintai_backend.py "${JINTAI_BACKEND_DIR:-}" "$ROOT/services/platform-api" "$ROOT/../jintai-finance-reports/services/platform-api") \
  || { echo "ERR: dev_jintai_backend.py not found (set \$JINTAI_BACKEND_DIR)"; exit 1; }
G_DIR=$(_probe dev_guangtian_backend.py "${GUANGTIAN_BACKEND_DIR:-}" "$ROOT/services/platform-api" "$ROOT/../guangtian-backend/services/platform-api") \
  || { echo "ERR: dev_guangtian_backend.py not found — 光天后端未进 main, 需 guangtian-backend worktree (或 set \$GUANGTIAN_BACKEND_DIR)"; exit 1; }
WEB_DIR=$(_probe src/screens/guangtian/GuangtianDemoPage.tsx "${DEMO_WEB_DIR:-}" "$ROOT/apps/win-web" "$ROOT/../guangtian-frontend/apps/win-web" "$ROOT/../guangtian-frontend-v2/apps/win-web") \
  || { echo "ERR: guangtian-aware apps/win-web not found (set \$DEMO_WEB_DIR)"; exit 1; }

echo "    python   : $PY_BIN ($("$PY_BIN" --version 2>&1))"
echo "    jintai   : $J_DIR → :$JINTAI_PORT"
echo "    guangtian: $G_DIR → :$GUANGTIAN_PORT"
echo "    web      : $WEB_DIR → :$VITE_PORT"

_start_backend() { # $1=dir $2=module $3=port $4=dbfile $5=pidfile $6=log
  local existing; existing=$(_listening "$3")
  if [[ -n "$existing" ]]; then echo "  $2 already on :$3 (pid=$existing)"; echo "$existing" > "$5"; return; fi
  ( cd "$1" && DATABASE_URL="sqlite+aiosqlite:///$(pwd)/$4" REDIS_URL="redis://localhost:6379" \
      COOKIE_SECRET="start-demo-cookie-secret-32-bytes-padding=" \
      "$PY_BIN" -m uvicorn "$2:app" --host 127.0.0.1 --port "$3" --log-level warning > "$6" 2>&1 & echo $! > "$5" )
  echo "  $2 pid=$(cat "$5") → :$3 (log: $6)"
}

echo "==> start backends"
_start_backend "$J_DIR" dev_jintai_backend    "$JINTAI_PORT"    platform_jintai_admin.db    "$J_PID" "$J_LOG"
_start_backend "$G_DIR" dev_guangtian_backend "$GUANGTIAN_PORT" platform_guangtian_admin.db "$G_PID" "$G_LOG"

echo "==> start unified vite"
existing=$(_listening "$VITE_PORT")
if [[ -n "$existing" ]]; then
  echo "  vite already on :$VITE_PORT (pid=$existing)"; echo "$existing" > "$V_PID"
else
  cd "$WEB_DIR"
  [[ -d node_modules ]] || { echo "  npm install (one-time)..."; npm install --silent; }
  VITE_JINTAI_BACKEND="http://127.0.0.1:$JINTAI_PORT/api/win" \
    VITE_GUANGTIAN_BACKEND="http://127.0.0.1:$GUANGTIAN_PORT/api/win" \
    npm run dev -- --port "$VITE_PORT" --host "$VITE_HOST" > "$V_LOG" 2>&1 &
  echo "$!" > "$V_PID"; echo "  vite pid=$(cat "$V_PID") → $VITE_HOST:$VITE_PORT (log: $V_LOG)"
  cd "$ROOT"
fi

echo; echo "==> health check"
for port in "$JINTAI_PORT" "$GUANGTIAN_PORT"; do
  for i in $(seq 1 30); do curl -sS -m1 "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break; sleep 0.5; done
  H=$(curl -sS -m1 "http://127.0.0.1:$port/health" 2>&1)
  echo "$H" | grep -q '"status":"ok"' && echo "  ✓ :$port /health → $(echo "$H" | sed 's/.*enterprise_id":"\([^"]*\)".*/\1/')" || echo "  ✗ :$port NOT reachable: $H"
done
for i in $(seq 1 30); do curl -sS -m1 -I "http://127.0.0.1:$VITE_PORT/win/" >/dev/null 2>&1 && break; sleep 0.5; done
curl -sS -m1 -I "http://127.0.0.1:$VITE_PORT/win/" 2>/dev/null | grep -q "200 OK" && echo "  ✓ vite /win/ → 200 OK" || echo "  ✗ vite NOT reachable (see $V_LOG)"

echo
echo "============================================================"
if [[ "$VITE_HOST" == "0.0.0.0" ]]; then
  TS_IP=$(command -v tailscale >/dev/null 2>&1 && tailscale ip -4 2>/dev/null | head -1)
  LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
  HOST_FOR_URL="${TS_IP:-${LAN_IP:-<this-mac-ip>}}"
  echo "  ⚠ PUBLIC 模式: vite 绑 0.0.0.0 — Tailscale 对端 + 同网段 LAN 都能访问。"
  echo "    后端仍只在 127.0.0.1(不暴露)。演示完务必 stop。"
  echo
  echo "  赵博士打开(默认 mock 模式,无需后端):"
  echo "    锦泰 : http://$HOST_FOR_URL:$VITE_PORT/win/?tab=jintai"
  echo "    光天 : http://$HOST_FOR_URL:$VITE_PORT/win/?tab=guangtian"
  [[ -n "$TS_IP" ]] && echo "    (Tailscale IP: $TS_IP)" || echo "    (未检测到 tailscale; 上面用 LAN IP)"
else
  echo "  锦泰 : http://127.0.0.1:$VITE_PORT/win/?tab=jintai"
  echo "         http://127.0.0.1:$VITE_PORT/win/?tab=jintai&mode=backend&inspect=1"
  echo "  光天 : http://127.0.0.1:$VITE_PORT/win/?tab=guangtian"
  echo "         http://127.0.0.1:$VITE_PORT/win/?tab=guangtian&mode=backend&inspect=1"
  echo "  公开(给 Tailscale 对端看): bash scripts/start-platform.sh --public"
fi
echo "  stop : bash scripts/start-platform.sh stop"
echo "============================================================"
