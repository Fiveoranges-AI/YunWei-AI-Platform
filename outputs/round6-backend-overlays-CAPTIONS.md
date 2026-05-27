# Round 6 — 全 tab backend overlay 截图

落盘位置: `/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21/`

每张全页 + zoom 特写两份(zoom 把顶部 backend overlay 区拍清楚)。

| # | tab | 全页 | zoom (overlay 特写) | 内容 |
|---|---|---|---|---|
| 1 | 财务 · 会企01 资产负债表 | `round6-finance-balance-sheet.png` (413 KB · 1900×1400) | `round6-finance-balance-sheet-zoom.png` (178 KB · 1700×600) | `GET /finance/balance-sheet?period=2026-05` · 3 列(资产/负债/所有者权益)期初+期末 · 借贷平衡断言(本截图 demo seed 含未对账固定资产,显示 "⚠ 不平衡" — feature 本身在工作) |
| 2 | 经营日报 KPI | `round6-briefing-kpi.png` (325 KB) | `round6-briefing-kpi-zoom.png` (167 KB · 1700×600) | `GET /briefing/kpi` · 6 KPI 卡片(应付总额/应付逾期/低库存/缺货/待审 PR/未结 PO) + 最近 24h ActionLog 列表(actor_kind 区分"AI"/"人") |
| 3 | 采购 · 申购/订单/应付 | `round6-purchase-payables.png` (319 KB) | `round6-purchase-payables-zoom.png` (169 KB · 1700×600) | `GET /procurement/{requisitions,purchase-orders,payables}` · 3 列列表 · status badge 色码(pending_approval/closed/overdue/due_soon) |
| 4 | 生产 · D 配料单 | `round6-production-bom.png` (322 KB) | `round6-production-bom-zoom.png` (203 KB · 1700×800) | `GET /procurement/boms?status=active` + `POST /boms/{id}/explode` 实时缺料分析 · "✓ 库存全够 — 可开批" 或 "⚠ 有缺料 — 主线已 auto-draft PR" |

## 拍摄方式 (完全命令行,可复现)

```bash
# 服务起 (依赖 PR #115)
bash scripts/jintai/dev-backend.sh                              # 后端 127.0.0.1:8000
cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1  # 前端

# Round 6 seed:补 FixedAsset + BOM + period openings(让 4 张截图都有内容)
# (见 round 6 commit message)

# 4 张全页 + zoom (用 PR #116 已有的 ?productionSubtab=D debug 参数让 BOM tab 可命中)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21"

for combo in \
  "finance-balance-sheet:#finance" \
  "briefing-kpi:#briefing" \
  "purchase-payables:#purchase" \
  "production-bom:#production&productionSubtab=D"
do
  IFS=: read name hash <<< "$combo"
  "$CHROME" --headless=new --disable-gpu --window-size=1900,1400 --virtual-time-budget=10000 \
    --screenshot="$DIR/round6-$name.png" \
    "http://127.0.0.1:5175/win/?tab=jintai&mode=backend$hash"
done

# zoom 裁顶部 overlay 特写
sips -c 600 1700 --cropOffset 130 80 "$DIR/round6-finance-balance-sheet.png" --out "$DIR/round6-finance-balance-sheet-zoom.png"
sips -c 600 1700 --cropOffset 130 80 "$DIR/round6-briefing-kpi.png" --out "$DIR/round6-briefing-kpi-zoom.png"
sips -c 600 1700 --cropOffset 130 80 "$DIR/round6-purchase-payables.png" --out "$DIR/round6-purchase-payables-zoom.png"
sips -c 800 1700 --cropOffset 130 80 "$DIR/round6-production-bom.png" --out "$DIR/round6-production-bom-zoom.png"
```

## 核心证据

每张 zoom 截图顶部都有标准 overlay chrome:
```
✨ backend live data  GET /api/win/...  · 拉取于 HH:MM:SS  [↻ 刷新]
```

证明 4 个 tab 的关键数字真的从 SQLite 拉(而不是 mock 写死的)。**刷新页面 → 拉取时间变,数字保持(因为数据在后端)**。

## mock 路径 0 影响

每张全页截图都能看到:overlay 在顶部展示真 backend 数字 → 下方 mock UI 完全保留原状(资产负债表 / KPI 卡片 / 申购单 / 配料单 mock 内容仍可见)。**mock 模式切换** (`?mode=mock` 或 chip 切回) **整段 overlay return null,demo 客户路径 100% 不变**。

## Backend overlay 设计

每个 overlay 都是 backend-mode-only 组件,统一住 `apps/win-web/src/screens/jintai/JintaiBackendOverlays.tsx` (约 530 行):
- `JintaiFinanceBackendOverlay({ activeTab })` — 5 sub-tab 路由到对应 _Finance* 子组件
- `JintaiBriefingBackendOverlay()` — KPI + ActionLog
- `JintaiPurchaseBackendOverlay()` — 3 列并发 query (PR / PO / 应付)
- `JintaiProductionBomBackendOverlay()` — list BOMs + 每个 explode 一次

每个 overlay 用 `useBackendQuery` hook (~30 行,`state/useBackendQuery.ts`):
- loading / error / data 三态
- 30s stale-while-revalidate (KPI 高频默认;finance 报表 visit 时拉)
- enabled gate (mode !== "backend" 时 skip,不浪费请求)
- run-id 防 race (旧请求结果不覆盖新)
