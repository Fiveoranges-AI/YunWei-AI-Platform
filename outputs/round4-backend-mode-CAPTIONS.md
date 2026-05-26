# Round 4 — 前端 backend mode 端到端验证截图

落盘位置: `/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21/`

| # | 文件 | 大小 | 内容 |
|---|---|---|---|
| 1 | `round4-backend-mode-panel-persistence.png` | 277 KB · 1700×1100 | 整页 + 右上角 Backend Reality Check 面板;`mode=backend&inspect=1` URL 触发面板自动展开 |
| 2 | `round4-backend-mode-panel-zoom.png` | 67 KB · 460×740 | (从 #1 裁出) 面板特写,KPI 数字清晰可读 |
| 3 | `round4-backend-mode-demo-complete.png` | 363 KB · 1700×1100 | DEMO COMPLETE modal — 一键演示 7 步闭环完成态;`mode=backend&jumpToEnd=1` URL 跳转 |

## 拍摄方式

完全命令行(可复现):
```bash
# 服务先起
bash scripts/jintai/dev-backend.sh          # 后端 127.0.0.1:8000 (依赖 PR #115)
cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1   # 前端

# 截图 1+3 (用 macOS Chrome headless)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21"

"$CHROME" --headless=new --disable-gpu --window-size=1700,1100 --virtual-time-budget=8000 \
  --screenshot="$DIR/round4-backend-mode-panel-persistence.png" \
  "http://127.0.0.1:5175/win/?tab=jintai&mode=backend&inspect=1"

"$CHROME" --headless=new --disable-gpu --window-size=1700,1100 --virtual-time-budget=8000 \
  --screenshot="$DIR/round4-backend-mode-demo-complete.png" \
  "http://127.0.0.1:5175/win/?tab=jintai&mode=backend&jumpToEnd=1"

# 截图 2 (裁出面板)
sips -c 740 460 --cropOffset 0 1240 \
  "$DIR/round4-backend-mode-panel-persistence.png" \
  --out "$DIR/round4-backend-mode-panel-zoom.png"
```

## 关键证据 — 跨进程持久化

截图 2 中:**应付总额 ¥46,080.0000 / 应付笔数 1 / 今日事件 14**。

这些数字源自:Chrome MCP 浏览器(用户的常驻 Chrome profile)在 round 4 端到端验证里跑完 90 秒 tour,生成的真实落库数据 → 写到 `services/platform-api/yinhu_tenant_jintai_demo.db`。

截图本身由 **headless Chrome (全新 ephemeral profile,无 localStorage,无 cookie)** 拍摄。两个 profile 完全独立,KPI 数字仍一致 — 证明数据真在 SQLite 文件,跟前端 mock 无关。

## URL debug 参数 (PR #116 round 4 截图修补)

新加 2 个 URL 参数(仅用于截图/调试,生产 demo 路径行为 0 影响):
- `?inspect=1`(或 `?inspectPanel=1`)— `JintaiBackendModePanel` 默认展开
- `?jumpToEnd=1`— `JintaiProvider` 挂载后立即 `dispatch TOUR_SET_STEP(TOUR_TOTAL+1)`,显示 DEMO COMPLETE modal

两参数都 opt-in,默认 demo 行为不变。
