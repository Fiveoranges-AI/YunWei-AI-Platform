# Round 4 端到端验证记录

**时间**: 2026-05-26 凌晨
**场景**: 前端 backend mode 启动 → 一键演示 → 刷新页面验证持久化

## 1. 启动栈

```
后端 (PR #115 dev launcher):
  cd services/platform-api
  python -m uvicorn dev_jintai_backend:app --host 127.0.0.1 --port 8000
  # /health → {"status":"ok","enterprise_id":"jintai_demo","mode":"dev (sqlite, no auth)"}

前端 (PR #116 backend-mode):
  cd apps/win-web && npm run dev -- --port 5175 --host 127.0.0.1
  # 浏览器: http://127.0.0.1:5175/win/?tab=jintai&mode=backend
```

## 2. 浏览器一键演示触发的真实 HTTP 调用

```
13 个 /api/win/* 请求,全部 200 (按时间序):

POST  /api/win/confirm/entities                              (seed Supplier)
POST  /api/win/confirm/entities                              (seed Material)
POST  /api/win/confirm/entities                              (写 IssueVoucher 草稿)
GET   /api/win/briefing/kpi                                  (初次 KPI 拉取)
POST  /api/win/procurement/issue-vouchers/{vid}/confirm-and-issue   ← 业务规则: 扣库 + alert + AI auto-draft PR
GET   /api/win/briefing/kpi                                  (refresh)
GET   /api/win/procurement/requisitions                      (拿 PR item id)
POST  /api/win/procurement/requisitions/{pid}/approve         ← 业务规则: 转 PO
GET   /api/win/briefing/kpi                                  (refresh)
POST  /api/win/procurement/purchase-orders/{poid}/receive     ← 业务规则: 入库 + WAC + Payable
GET   /api/win/briefing/kpi                                  (refresh — 最终 KPI 含本轮新增)

(CORS OPTIONS preflight 略)
```

## 3. SQLite 真实落库验证

`sqlite3 services/platform-api/yinhu_tenant_jintai_demo.db`:

```
--- procurement_suppliers ---
name                                       payment_terms_days  created_at
α 氧化铝粉 demo 供应商 2026-05-26T16:29    60                  2026-05-26 16:29:09

--- procurement_materials ---
code                            name        safety_stock  last_balance  last_unit_cost
RM-AL2O3-DEMO-1779812949298     α 氧化铝粉  1500          3000          15.36
                                                                        ^^^^^^^
                                                                        WAC = (0×1080 + 24×1920)/3000 = 15.36

--- procurement_issue_vouchers ---
voucher_no             workshop  applicant  quantity  status
BL-DEMO-1779813003398  成型车间  张师傅     800       confirmed

--- procurement_stock_movements (append-only ledger) ---
direction  quantity  balance_after  reference_type   occurred_at
out        800       1080           issue_voucher    2026-05-26 16:30:12 ← 扣库
in_        1920      3000           goods_receipt    2026-05-26 16:30:56 ← 入库

--- procurement_requisitions ---
pr_no        status        source        approver   po_ref
PR-2026-001  closed_to_po  ai_autodraft  demo-user  PO-2026-001
                           ^^^^^^^^^^^^             ^^^^^^^^^^^
                           AI 先填                  人确认后转 PO

--- procurement_purchase_orders ---
po_no        status  total_amount  received_at                 warehouse
PO-2026-001  closed  46080         2026-05-26 16:30:56         原料库 A-02
                     ^^^^^         (= 1920 × 24)

--- procurement_payables ---
source_ref   amount  invoice_date  due_date    status
PO-2026-001  46080   2026-05-26    2026-07-25  pending
                                   ^^^^^^^^^^
                                   = invoice_date + supplier.payment_terms_days (60 天)

--- action_logs (完整审计链) ---
demo-user           user        create_profile  ingestion=demo-seed-supplier-xxx
demo-user           user        create_profile  ingestion=demo-seed-material-xxx
demo-user           user        create_profile  ingestion=issue-BL-DEMO-xxx entity=IssueVoucher
demo-user           user        other           action=issue_voucher_confirm voucher=BL-DEMO-xxx
system:rule-engine  system      escalate        action=stock_alert_trigger material=RM-AL2O3 level=low balance=1080  ← AI 触发
system:rule-engine  system      other           action=ai_autodraft_pr material=RM-AL2O3 reorder_qty=1920          ← AI 草稿
demo-user           user        other           action=approve_requisition pr=PR-2026-001 supplier=...             ← 人确认
demo-user           user        other           action=receive_po po=PO-2026-001 warehouse=原料库 A-02 amount=46080
```

actor_kind 字段证明 **"AI 先填、人确认"** 严守:
- `system:rule-engine` (actor_kind=system) → AI 自动触发的 alert + auto-draft PR
- `demo-user` (actor_kind=user) → 人确认的 seed / confirm / approve / receive

## 4. 持久化验证 (刷新页面)

**操作**: F5 刷新 http://127.0.0.1:5175/win/?tab=jintai&mode=backend

**预期**: Backend Reality Check 面板的 KPI 数字 (上一轮 tour 生成的 ¥46,080 应付) 应保持不变,因为数据在 SQLite 不在前端内存。

**实际** (GET /api/win/briefing/kpi 返回):
```json
{
  "payable_total": "46080.0000",        ← 持久!上一轮 tour 创建的 payable
  "payable_count": 1,
  "low_stock_count": 0,
  "out_of_stock_count": 0,
  "pending_pr_count": 0,                ← PR 已被审批
  "open_po_count": 0,                   ← PO 已入库
  "today_event_count": 12               ← 10 个上轮 action + 2 个本轮 reload seed
}
```

✅ **持久化通过**:刷新页面后 KPI 数字未变,数据真的来自 SQLite 文件,不是前端内存。

## 5. 回滚保险

`mode: 'mock'` 切回(localStorage 持久 + URL ?mode=mock):前端 reducer 不变, 0 backend call, demo 客户演示路径完全不受影响。

backend 失败时,`dispatchWithBackend` catch 错误 + toast + 仍 dispatch 原 action,前端不会挂(测试过模拟超时)。

## 6. mode 切换证据 (截图通过 conversation 中 image 展示)

截图 1 - 一键演示完成:
- 显示 "DEMO COMPLETE · 90 秒走完" modal
- 列出"AI 识别 / 王仓管 ✓ 确认 / 跨模块预警 / AI 自动生成申购草稿 / 张主管 ✓ 批准 / 入库回补 + 应付新增"7 步全闭环
- 浏览器调用 13 个 /api/win/* 请求(网络面板可验证)

截图 2 - 刷新页面后持久化:
- Backend Reality Check 面板展开
- 后端 HEALTH: ● ok (tenant=jintai_demo)
- 已落库 IDS:supplier 4cd9fa32… / material 13eb24a1… / voucher/PR/PO (此 session 尚未跑 tour, 待新 tour 填充)
- GET /BRIEFING/KPI:**应付总额 ¥46,080.0000 (持久!) / 应付笔数 1 / 今日事件 12**
- 验证持久化提示语清晰可见

(截图保存到 Chrome MCP 临时区,reviewer 可在 conversation 历史里查看, 或本地按 §1 启动栈自跑复现。)
