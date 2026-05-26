#!/usr/bin/env bash
# 锦泰 demo 前端 backend-mode 用的轻量后端启动脚本.
#
# 跳过 platform 认证 / Redis,SQLite 落盘 ~ 5 秒可重置.
# CORS allow 127.0.0.1:5175 (Vite dev server 默认端口).
#
# Usage:
#   bash scripts/jintai/dev-backend.sh
#   # 默认监听 127.0.0.1:8000;前端 fetch base = http://127.0.0.1:8000/api/win
#
#   # 自定端口:
#   PORT=8001 bash scripts/jintai/dev-backend.sh
#
#   # 重置 demo DB (删两个 sqlite 文件):
#   rm -f services/platform-api/jintai_dev_admin.db services/platform-api/yinhu_tenant_jintai_demo.db
#
# Dependencies: python3.11+, uvicorn, fastapi, sqlalchemy[asyncio], aiosqlite (已在 yunwei_win 现有依赖里).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PA_DIR="$ROOT/services/platform-api"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

cd "$PA_DIR"

if ! command -v uvicorn >/dev/null 2>&1; then
  if ! python3 -c "import uvicorn" >/dev/null 2>&1; then
    echo "uvicorn not found. pip install uvicorn" >&2
    exit 1
  fi
fi

echo "==> Starting 锦泰 demo dev backend"
echo "    host:    $HOST"
echo "    port:    $PORT"
echo "    db:      $PA_DIR/jintai_dev_admin.db (admin) + yinhu_tenant_jintai_demo.db (tenant)"
echo "    health:  http://$HOST:$PORT/health"
echo "    api:     http://$HOST:$PORT/api/win/{procurement,finance,briefing,confirm}/*"
echo "    docs:    http://$HOST:$PORT/docs"
echo
echo "前端 (Vite, http://127.0.0.1:5175) 加 ?mode=backend 或 toggle 切换;CORS 已配."
echo "按 Ctrl-C 停."
echo

exec python3 -m uvicorn dev_jintai_backend:app --host "$HOST" --port "$PORT" --reload
