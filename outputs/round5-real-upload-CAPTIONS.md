# Round 5 — 真实文档上传 → AI 抽取 → 人工确认 → 落库 截图

落盘位置: `/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21/`

| # | 文件 | 大小 | 内容 |
|---|---|---|---|
| 1a | `round5-real-upload-1-fields.png` | 297 KB · 1700×1300 | 整页 — backend mode AI 收件箱;上传 .xlsx 示例后渲染候选字段卡片(8 字段 + 置信度色码) |
| 1b | `round5-real-upload-1-zoom.png` | 134 KB · 1450×750 | (从 1a 裁出) 卡片特写,8 字段 + 置信度 chips(96/95/95/91/94/98 绿 / 83 黄 / 92 绿)清晰可读 |
| 2a | `round5-real-upload-2-edited.png` | 298 KB · 1700×1300 | 整页 — 已编辑两个字段(workshop / quantity);蓝色背景 + ✎ 标记编辑过 |
| 2b | `round5-real-upload-2-zoom.png` | 135 KB · 1450×750 | (从 2a 裁出) 卡片特写,workshop=成型车间 / quantity=1500 高亮编辑标 |
| 3 | `round5-real-upload-3-accepted.png` | 351 KB · 1700×1300 | 整页 — 采纳后 "✓ 已写入 IssueVoucher (id=...); 主线触发: 库存 380 kg · 缺料预警 · auto-draft PR-..." 绿色提示框 + 右上 Backend Reality Check 面板显示真实 KPI |

## 拍摄方式 (完全命令行,可复现)

```bash
# 服务先起
rm -f services/platform-api/yinhu_tenant_jintai_demo.db    # 重置 SQLite 让 KPI 数字可预测
bash scripts/jintai/dev-backend.sh                          # 后端 127.0.0.1:8000
cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1   # 前端

# 3 张截图 (用 PR #116 加的 ?previewUpload= debug 参数让 headless Chrome 自动跑通各状态)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="/Users/kobeli/Documents/Yinhu Project/outputs/jintai-demo-iter21"

# #1: 上传后,字段卡 + 置信度 (previewUpload=fields)
"$CHROME" --headless=new --disable-gpu --window-size=1700,1300 --virtual-time-budget=15000 \
  --screenshot="$DIR/round5-real-upload-1-fields.png" \
  "http://127.0.0.1:5175/win/?tab=jintai&mode=backend&previewUpload=fields#inbox"

# #2: 编辑两个字段后 (previewUpload=edited 自动 setS({...edits:{quantity:1500,workshop:成型车间}}))
"$CHROME" ... --screenshot="$DIR/round5-real-upload-2-edited.png" \
  "http://...&previewUpload=edited#inbox"

# #3: 采纳后 + Backend Reality Check 面板展开 (previewUpload=accepted + inspect=1)
"$CHROME" ... --virtual-time-budget=20000 --screenshot="$DIR/round5-real-upload-3-accepted.png" \
  "http://...&previewUpload=accepted&inspect=1#inbox"

# 裁特写 (sips)
sips -c 750 1450 --cropOffset 130 80 \
  "$DIR/round5-real-upload-1-fields.png" --out "$DIR/round5-real-upload-1-zoom.png"
sips -c 750 1450 --cropOffset 130 80 \
  "$DIR/round5-real-upload-2-edited.png" --out "$DIR/round5-real-upload-2-zoom.png"
```

## 关键证据

**截图 1 (字段卡)**:
- 头部 "✨ AI 抽取了 8 个字段(整体置信度 93.0%) · 实体类型: IssueVoucher · provider: demo-mock · 文件 供应商对账.xlsx (6.8 KB)"
- 黄色警告框 "⚠ DemoMockProvider — 当前 deployment 没配 ANTHROPIC_API_KEY..."
- 8 字段表格,置信度颜色编码:
  - ≥90%:绿色 (voucher_no 96, workshop 95, applicant 95, material_name_hint 91, quantity 94, unit 98, issued_date 92)
  - 70-90%:黄色 (purpose 83)
  - <70%:红色 (本批次最低 83% 未触发)

**截图 2 (编辑状态)**:
- quantity 改为 1500 (从 1200),workshop 改为"成型车间" (从"烧结车间")
- 编辑过的行 background 变蓝,label 标 "✎" (例如 "quantity ✎")
- 其它行保持原状

**截图 3 (采纳后)**:
- 上传 panel 转为绿色 "✓ 已写入 IssueVoucher (id=93ca5be9...);主线触发: 库存 380.0000 kg · 缺料预警 · auto-draft PR-2026-002"
- 右上角 Backend Reality Check 面板展开,显示 KPI:
  - 应付总额 ¥46,080.0000 (round 4 历史)
  - 应付笔数 1
  - **低库存 SKU 1** ← 新!主线触发
  - **待审批 PR 1** ← 新!auto-draft
  - 今日事件 20 (新增了 5 条:upload + confirm + issue + alert + autodraft)

## 后端 API 调用证据 (GET /briefing/kpi)

```json
{
  "payable_total": "46080.0000",
  "payable_count": 1,
  "low_stock_count": 1,     // 主线触发:material balance 1880-1500=380 < safety 1500
  "pending_pr_count": 1,    // auto-draft PR-2026-002
  "today_event_count": 20   // 上传 + confirm + 业务规则 ActionLog 链
}
```

## SQLite 验证

```bash
sqlite3 services/platform-api/yinhu_tenant_jintai_demo.db <<'EOF'
SELECT voucher_no, workshop, applicant, quantity, status
  FROM procurement_issue_vouchers ORDER BY created_at DESC LIMIT 1;
-- BL-2026-018  成型车间  王师傅  1500  confirmed    ← 编辑过的 quantity=1500 真落库

SELECT actor, action_type, substr(input_summary, 1, 80)
  FROM action_logs ORDER BY executed_at DESC LIMIT 5;
-- demo-user        other  action=receive_po po=...  
-- system:rule-eng  other  action=ai_autodraft_pr material=... reorder_qty=...
-- system:rule-eng  escalate action=stock_alert_trigger ...
-- demo-user        other  action=issue_voucher_confirm voucher=BL-2026-018...
-- demo-user  create_profile  ingestion=upload-confirm-... entity=IssueVoucher...

SELECT level, balance_at_trigger FROM procurement_stock_alerts ORDER BY triggered_at DESC LIMIT 1;
-- low   380.0000

SELECT pr_no, source, status FROM procurement_requisitions ORDER BY created_at DESC LIMIT 1;
-- PR-2026-002  ai_autodraft  pending_approval
EOF
```

完整链路:上传 .xlsx → parse_pipeline + DemoMockProvider → 候选字段 + 置信度 → 客户编辑 quantity 1200→1500 → 采纳 (was_edited=True confidence=None,审计真实) → confirm_writer 写 IssueVoucher (id=93ca5be9...) → POST /procurement/issue-vouchers/{id}/confirm-and-issue → stock movement 出 1500 → balance 380 < safety 1500 → StockAlert(low) → ai_autodraft_requisition → PR-2026-002 待审批。

## URL debug 参数 (PR #116 round 5 截图修补)

新加 3 个 opt-in 参数(仅截图/调试,生产 demo 路径行为 0 影响):
- `?previewUpload=fields` — JintaiRealUploadPanel 自动 fetch .xlsx 示例并 upload,停在 candidate 状态
- `?previewUpload=edited` — 同上 + 自动 setS 加 edits {quantity:1500, workshop:成型车间}
- `?previewUpload=accepted` — 同上 + 自动 click accept,跑完整 confirm → 主线链
