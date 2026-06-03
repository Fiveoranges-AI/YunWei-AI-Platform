# Round 7 — Postgres 模式 + production readiness 截图

落盘位置: `/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21/`

| # | 文件 | 大小 | 内容 |
|---|---|---|---|
| 1 | `round7-pg-mode-panel.png` | 360 KB · 1900×1300 | 整页 (经营日报 tab + 右上 Backend Reality Check 展开,health.db = `postgres (dev-stack)`) |
| 1.zoom | `round7-pg-mode-panel-zoom.png` | 73 KB · 460×700 | 面板特写:**db=postgres (dev-stack)** badge 清晰可读,tenant=jintai_demo,5 个 IDs 已落库 |
| 2 | `round7-pg-mode-briefing.png` | 326 KB · 1900×1400 | 经营日报 tab full page · backend overlay 拉 /briefing/kpi(PG 后端数字)+ ActionLog 列表(actor_kind 区分) |
| 3 | `round7-pg-mode-finance.png` | 406 KB · 1900×1400 | 财务 tab · 会企 01 资产负债表(PG 后端拉)+ mock UI 对照 |

## 复现命令

```bash
# 1. 起 Postgres + Redis dev stack
docker compose -f infra/local/dev-stack.yml up -d

# 2. backend --pg 模式
bash scripts/jintai/dev-backend.sh --pg                # 监听 :8000, DATABASE_URL=postgres@:5433

# 3. (可选) full-demo.sh 让 backend 有数据
BASE=http://127.0.0.1:8000/api/win bash scripts/jintai/full-demo.sh

# 4. 前端
cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1

# 5. 截图 (用 PR #114/#116 已有的 ?inspect=1 调试参数)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21"
"$CHROME" --headless=new --disable-gpu --window-size=1900,1300 --virtual-time-budget=10000 \
  --screenshot="$DIR/round7-pg-mode-panel.png" \
  "http://127.0.0.1:5175/win/?tab=jintai&mode=backend&inspect=1#briefing"
sips -c 700 460 --cropOffset 0 1440 "$DIR/round7-pg-mode-panel.png" --out "$DIR/round7-pg-mode-panel-zoom.png"
```

## 核心证据

**Backend Reality Check 面板首行从 round 4 的 `● ok (tenant=jintai_demo)` 升级为**:
```
● ok (tenant=jintai_demo · db=postgres (dev-stack))
```

— 让 reviewer 一眼区分 SQLite (单机 demo) vs Postgres (生产 like)。`/health` endpoint 也同步返回 `{"db":"postgres (dev-stack)"}` 让 curl 验证清楚。

## clean-room smoke 一键证明 (scripts/jintai/smoke-clean.sh)

```
==============================================================
smoke-clean.sh 总结: 9 passed, 0 failed (1 frontend skipped)
==============================================================
  PASS: data volume removed              (docker compose down -v)
  PASS: PG @ 5433 ready                  (postgres:16 healthcheck)
  PASS: Redis @ 6380 ready
  PASS: backend /health → postgres       (dev-backend.sh --pg)
  PASS: full-demo.sh 完整跑通            (主线 15 步 + 三表 + KPI)
  PASS: payable_total=¥46,080 (PO 入库后)  (会企01 应付账款)
  PASS: balance-sheet 返回 7 个资产行
  PASS: /parse/upload → provider=demo-mock, entity_type=IssueVoucher
  PASS: pytest: 42 passed                (jintai-* 关键测试)
  SKIP: frontend Vite (跨 worktree node_modules 不在)

✅ smoke PASS — 全闭环 clean-room 可复现
```

CTO 早上一行命令 `bash scripts/jintai/smoke-clean.sh` 就能从 0 状态(干净 docker volume)证明端到端可复现。
