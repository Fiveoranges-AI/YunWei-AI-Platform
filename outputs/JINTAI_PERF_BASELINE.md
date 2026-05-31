# 锦泰 后端 endpoint 性能基线 (Round 12)

**生成**: 2026-05-27 · **环境**: macOS / Python 3.11 / SQLite file (single process)
**目的**: round 9 SELF_AUDIT P3 性能 backlog;给 CTO 一个具体 latency 数字,**不是**优化目标

---

## 方法

1. 起 `dev_jintai_backend:app` (uvicorn, SQLite file)
2. `BASE=http://127.0.0.1:8000/api/win bash scripts/jintai/full-demo.sh` 跑完整 15 步 happy path,seed 完整数据 (supplier, material, voucher, PR, PO, payable, stock movement, fixed asset)
3. 每个 GET endpoint 连打 10 次,记录 best / avg / worst (curl `%{time_total}`,毫秒)
4. parse/upload POST 连打 3 次 (单文件 5KB JPG, DemoMockProvider 路径)

**没测**: PG service container 模式(等 CI 真跑就有数);并发负载;真 ClaudeProvider (无 API key)

---

## 结果

### GET endpoints (10 hits each)

| endpoint | best | avg | worst | response size |
|---|---:|---:|---:|---:|
| `/briefing/kpi` | 1.7 ms | **2.3 ms** | 4.2 ms | 3.1 KB |
| `/finance/balance-sheet?period=YYYY-MM` | 2.7 ms | **3.0 ms** | 3.3 ms | 1.8 KB |
| `/finance/pnl-distribution?period=YYYY-MM` | 1.7 ms | **1.9 ms** | 2.2 ms | 1.4 KB |
| `/finance/cashflow?period=YYYY-MM` | 1.5 ms | **1.6 ms** | 1.8 ms | 1.7 KB |
| `/finance/depreciation?period=YYYY-MM` | 0.8 ms | **0.8 ms** | 1.0 ms | 0.2 KB |
| `/finance/cost-breakdown?period=YYYY-MM` | 1.3 ms | **1.5 ms** | 1.8 ms | 0.5 KB |
| `/procurement/inventory-ledger` | 0.5 ms | **0.5 ms** | 0.7 ms | 0.2 KB |
| `/procurement/requisitions` | 1.0 ms | **1.1 ms** | 1.4 ms | 0.8 KB |
| `/procurement/purchase-orders` | 1.0 ms | **1.0 ms** | 1.2 ms | 0.5 KB |
| `/procurement/payables` | 0.7 ms | **0.9 ms** | 1.0 ms | 0.3 KB |
| `/procurement/materials` | 0.7 ms | **0.8 ms** | 1.1 ms | 0.2 KB |
| `/finance/chart-of-accounts` (首次 seed) | 2.0 ms | — | — | 3.4 KB |

### POST endpoints (3 hits each)

| endpoint | latencies | HTTP |
|---|---|---|
| `POST /parse/upload` (5KB JPG, demo-mock) | 4 / 2 / 2 ms | 200 |

### Full-demo 15 步整体

来自 CI `API smoke (PG + dev_jintai_backend)` job (`run 26494075586`): **end-to-end full-demo.sh 完成 52 秒** (包含 uvicorn 启动 + 等待健康 + 15 步 curl)。

---

## 结论

**没有需要优化的 endpoint**。

- 所有 GET 都 < 5 ms p99
- 最重的 `/briefing/kpi` (fan-out 到 6 个子查询计算应付/低库存/待审 PR 等) 也只 2.3 ms 平均
- `/finance/balance-sheet` 跑全套科目聚合 + 折旧闭环只 3 ms
- POST `/parse/upload` (DemoMockProvider 路径) 2-4 ms (mock 不调 LLM)

**P3 backlog status (round 9 SELF_AUDIT 留的)**:
- ~~"如有 >1s 的, 看能不能优化或加 index"~~ — 无 >1s,无需 index

**注意事项 (期望 prod 数字会变的方向)**:
1. **PG vs SQLite**: PG 网络 round-trip 通常 ~1ms,会让 baseline 翻 2-3x. 但仍 <20ms,远低于 user-perceived "卡" 阈值 (~200ms)
2. **真数据规模**: 现在是 1 supplier / 1 material / 1 voucher / 1 PR / 1 PO / 1 payable. 100 倍数据 → finance 聚合可能从 3ms → 30ms (linear scan). 锦泰单工厂一年级别没问题, 多工厂 / 多年要看
3. **真 ClaudeProvider**: parse/upload 用 vision LLM → 3-15 秒. 已加 LLMCallFailed → 502 处理 (round 11 fix)
4. **并发**: 没测. round 9 P0-4 fix 加了原子条件 UPDATE,理论 PG 下 row lock 串行化几个并发请求,worst case 是排队等 lock 释放

**何时重测**:
- PG mode 上 prod 后,跑同一脚本
- 任何 finance/balance-sheet 改了聚合逻辑后 (容易引入 N+1)
- 真数据涨到 1000+ entity 后

---

## 复现

```bash
# 起 backend
cd services/platform-api
rm -f jintai_dev_admin.db yinhu_tenant_jintai_demo.db
python3 -m uvicorn dev_jintai_backend:app --host 127.0.0.1 --port 8000 \
  > /tmp/perf-backend.log 2>&1 &
sleep 2 && curl -sS http://127.0.0.1:8000/health

# seed
BASE=http://127.0.0.1:8000/api/win bash scripts/jintai/full-demo.sh

# time GET endpoints (best/avg/worst over 10 hits)
PERIOD=$(date -u +%Y-%m)
BASE=http://127.0.0.1:8000/api/win
for ep in /briefing/kpi /finance/balance-sheet?period=$PERIOD ... ; do
    times=()
    for i in $(seq 1 10); do
      times+=($(curl -sS -o /dev/null -w "%{time_total}" "$BASE$ep"))
    done
    echo "${times[@]}" | python3 -c "
import sys
ts = [float(x)*1000 for x in sys.stdin.read().split()]
print(f'{min(ts):.1f}/{sum(ts)/len(ts):.1f}/{max(ts):.1f} ms')
"
done

# stop backend
kill %1
```
