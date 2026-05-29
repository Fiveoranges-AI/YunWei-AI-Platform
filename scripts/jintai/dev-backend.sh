#!/usr/bin/env bash
# 锦泰 demo 前端 backend-mode 用的轻量后端启动脚本.
#
# 默认 SQLite (零依赖, 5 秒可重置):
#   bash scripts/jintai/dev-backend.sh
#
# Round 7: --pg flag 用 Postgres 替代 SQLite (需先 docker compose up dev-stack):
#   docker compose -f infra/local/dev-stack.yml up -d
#   bash scripts/jintai/dev-backend.sh --pg
#
# 跳过 platform 认证 / Redis (注入固定 enterprise_id=jintai_demo).
# CORS allow 127.0.0.1:5175 (Vite dev server 默认端口).
#
# Env / flags:
#   --pg                 → 用 Postgres @ 127.0.0.1:5433 (dev-stack.yml)
#   HOST=127.0.0.1       → 监听地址 (default)
#   PORT=8000            → 监听端口 (default)
#
# 重置 demo DB:
#   SQLite mode:  rm -f services/platform-api/yinhu_tenant_jintai_demo.db
#   PG mode:      docker compose -f infra/local/dev-stack.yml down -v && up -d

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PA_DIR="$ROOT/services/platform-api"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
USE_PG=0

for arg in "$@"; do
  case "$arg" in
    --pg|--postgres)
      USE_PG=1
      ;;
    -h|--help)
      sed -n '2,25p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

cd "$PA_DIR"

if ! python3 -c "import uvicorn" >/dev/null 2>&1; then
  echo "uvicorn not installed. pip install uvicorn" >&2
  exit 1
fi

if [[ "$USE_PG" -eq 1 ]]; then
  # PG mode: connect to dev-stack postgres on 5433
  export DATABASE_URL="postgresql://postgres:test@localhost:5433/test"
  export REDIS_URL="redis://localhost:6380"
  DB_LABEL="Postgres @ localhost:5433/test (per-tenant DB: tenant_jintai_demo)"
  # Pre-flight: PG reachable?
  if ! python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('localhost',5433))" 2>/dev/null; then
    echo "ERROR: Postgres @ localhost:5433 unreachable." >&2
    echo "       Run: docker compose -f infra/local/dev-stack.yml up -d" >&2
    exit 3
  fi
else
  DB_LABEL="SQLite @ $PA_DIR/yinhu_tenant_jintai_demo.db"
fi

echo "==> Starting 锦泰 demo dev backend"
echo "    host:    $HOST"
echo "    port:    $PORT"
echo "    db:      $DB_LABEL"
echo "    health:  http://$HOST:$PORT/health"
echo "    api:     http://$HOST:$PORT/api/win/{procurement,finance,briefing,confirm,parse,bom}/*"
echo "    docs:    http://$HOST:$PORT/docs"
echo
echo "前端 (Vite, http://127.0.0.1:5175) 加 ?mode=backend 或 toggle 切换;CORS 已配."
echo "按 Ctrl-C 停."
echo

exec python3 -m uvicorn dev_jintai_backend:app --host "$HOST" --port "$PORT" --reload
