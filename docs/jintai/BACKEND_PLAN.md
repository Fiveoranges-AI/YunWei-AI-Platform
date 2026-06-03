# 锦泰耐火材料 · 后端开发计划

**作者**: Claude (autonomous overnight, 2026-05-26)
**目标**: 把锦泰前端 demo (`apps/win-web/src/screens/jintai/`) 的 5 步主线从内存 mock 升级成后端真实落库 API。
**老板早上 5 分钟扫这一份就能 review 整体方案。**

> **更新 (round 2, 凌晨)**: 老板追加授权 "你为我做最佳判断 然后执行",已:
> 1. 把 PR #114 末尾 7 项决策全部拍板 (5 ✅ / 2 ⏸),写到 PR description 顶部
> 2. 推进 P1 财务三表 / 进销存台账 / 折旧 / 成本拆分 (新 PR `feat/jintai-finance-reports`,base 于 #114)
> 3. P2.b auto-draft 升级(近 3 月用量 + supplier 自动绑 + unit_price 回填)
> 4. P2.a BOM (配料单) explode API
> 5. WAC 加权平均成本(Material 加 `last_unit_cost`,receive PO 自动更新)
>
> Round 2 决策 / 文件 / 测试详见 `outputs/JINTAI_BACKEND_ROUND2_REPORT.md`。
> 本文件 §10-12 是 round 2 的增量章节。

---

## 1. 决策摘要 (Why-and-What, 不读代码也能懂)

| # | 决策 | 选定 | 拒绝项 | 原因 |
|---|---|---|---|---|
| D1 | 分支策略 | 基于 `feat/p0-integration-verify` (PR #113) 开 `feat/jintai-backend-mainline`,worktree 隔离 | base on main | 复用已有 `confirm_writer + ActionLog + FieldProvenance + Mixin`,不重复造轮子;P0 trilogy 4 个 OPEN PR 还没 merge,这条 stack 自然延伸 |
| D2 | 采购/库存 schema 位置 | 新建 `yunwei_win/models/procurement.py`,**不**复用现有 `order.py` | 复用 `order.py` | 现有 `orders` 是销售侧(客户→订单);锦泰主线是采购侧(供应商→采购订单),语义完全不同 |
| D3 | confirm 写入路径 | 扩展 `confirm_writer._ENTITY_MODEL/_PARENT_FK_BY_RELATIONSHIP` 字典 | 另起一套 procurement_writer | 老板红线:"confirm 写入路径必须经过 confirm_writer + ActionLog + FieldProvenance,不允许绕过"。mixin-based audit 字段对新 model 透明可用 |
| D4 | 业务规则副作用 | confirm 是纯写入;副作用(扣库存/触发预警/AI auto-draft PR)放在 `services/procurement.py`,**API handler 在 confirm 后调一次** | 在 confirm_writer 里 hook | confirm_writer 单一职责更易测;procurement service 的输入是已落库的 entity,可独立单测 |
| D5 | 拆 PR | 单个 PR `feat/jintai-backend-mainline`(P0 主线全部),P1 财务报表如时间允许再开第二个 PR `feat/jintai-finance-reports` 栈在上面 | 拆成 schema/api/rules/tests 4 个 PR | 这些层之间耦合紧,4 个 PR 串行 review 比 1 个 PR 横切 review 更慢;mainline 主线必须一起 review 才有意义 |
| D6 | Migration 风格 | 沿用 `_run_lightweight_tenant_migrations` (idempotent `ALTER ... ADD COLUMN IF NOT EXISTS`),新表加进 `ensure_schema_ingest_tables` | 引入 Alembic | 红线之一 |
| D7 | 测试基座 | 每个新测试文件 override `_clean_state` 为 no-op,用 in-memory SQLite + `Base.metadata.create_all`,httpx.AsyncClient/ASGITransport,**不依赖** postgres + redis | 写 postgres 集成测试 | 复用 `test_confirm_cards.py` 已经验证的 pattern,本地 + CI 都能跑 |
| D8 | Supplier / Material 建模 | 独立的 ref 表,不是 string 列 | 把 supplier_name / material_name 当字符串放进 PR/PO | 应付账期(D9)依赖 supplier.payment_terms_days;库存余额必须按 material 聚合;FK 比 string 干净 |
| D9 | 应付账期 | 入库时按 supplier.payment_terms_days 计算 due_date(默认 60 天) | 客户端传 due_date | demo 前端写死 `"2026-07-24"`,但后端应该按规则算 |
| D10 | AI auto-draft PR 的 source_type | `source_type="ai_autodraft"` + `extracted_by="llm:rule-engine"` + `human_verified=False`;`approve_pr` API 是首次设 `human_verified=True` | 直接当 human_verified=True | 体现"AI 先填、人确认"的核心。 张主管点 approve 才算签字 |
| D11 | 不动前端 | 后端 API 跑通 + curl + 集成测试即可,前端切"后端模式"留明早老板验收 | 同步改前端 | 红线 |
| D12 | 财务三表 (P1) | 时间允许才做。从 invoices / payments / payables / fixed_assets 聚合,只读 API | 写入式财务系统 | 财务三表是出账物,不该用 AI 直接落账;只读聚合保安全 |

---

## 2. 数据模型 (新增 9 张表)

全部放进 `yunwei_win/models/procurement.py`,全部使用同一套 Mixin:
`TimestampMixin + RowProvenanceMixin + HumanVerificationMixin + RowAuditMixin + OwnershipMixin + SoftDeleteMixin`(`StockMovement` 和 `StockAlert` 不挂 HumanVerificationMixin/SoftDeleteMixin,见下)。

```
Supplier                    供应商 ref 表
  id, name (unique), payment_terms_days (default 60), contact_phone, notes

Material                    物料 ref 表
  id, code (unique), name, spec, unit, kind (raw|wip|finished),
  safety_stock (numeric), last_balance (numeric, denormalized 加速 KPI), 
  notes

StockMovement               库存流水 (append-only ledger)
  id, material_id (FK), direction (in|out|init), quantity (numeric),
  balance_after (numeric),
  reference_type (issue_voucher|goods_receipt|opening|adjustment),
  reference_id (UUID, polymorphic),
  occurred_at (timestamp),
  + RowProvenance + RowAudit  (不挂 HumanVerification / SoftDelete: 流水append-only)

IssueVoucher                领料单 (出库单 head)
  id, voucher_no (unique), workshop, applicant, material_id (FK),
  quantity (numeric), unit, purpose, issued_date,
  status (draft|confirmed|cancelled),
  + 全套 Mixin

PurchaseRequisition         申购单 head
  id, pr_no (unique), dept, applicant, apply_date, supplier_id (FK, 可空),
  status (draft|pending_approval|approved|rejected|closed_to_po),
  source (manual|ai_autodraft), source_note (Text),
  approver, approved_at, po_ref (string of po_no for traceability),
  + 全套 Mixin

PurchaseRequisitionItem     申购单 line
  id, pr_id (FK CASCADE), material_id (FK), quantity, unit, arrive_date,
  unit_price, amount, note,
  + 全套 Mixin

PurchaseOrder               采购订单 head
  id, po_no (unique), supplier_id (FK), from_pr_id (FK, 可空),
  status (open|in_transit|closed|cancelled),
  delivery_date, total_amount, currency (default CNY),
  warehouse (入库时填), received_at,
  + 全套 Mixin

PurchaseOrderItem           采购订单 line
  id, po_id (FK CASCADE), material_id (FK), quantity, unit,
  unit_price, amount,
  + 全套 Mixin

GoodsReceipt                入库单 (1:1 with PO for demo simplicity)
  id, receipt_no, po_id (FK), warehouse, received_at, received_by,
  + RowProvenance + HumanVerification + RowAudit

Payable                     应付账款
  id, supplier_id (FK), source_type (po|manual), source_ref (po_no string),
  source_po_id (FK 可空), amount, paid_amount (default 0),
  invoice_date, due_date, status (pending|partial|paid|overdue),
  + 全套 Mixin

StockAlert                  缺料预警
  id, material_id (FK), level (low|out),
  balance_at_trigger, safety_stock_at_trigger,
  triggered_at, resolved_at (nullable),
  triggered_by (issue_voucher_id 字符串/UUID),
  + RowAudit (不挂 HumanVerification — alert 不是 entity, 是事件)
```

**新枚举** (放进 `yunwei_win/enums.py`):
```
StockMovementDirection: in / out / init / adjustment
IssueVoucherStatus: draft / confirmed / cancelled
PurchaseRequisitionStatus: draft / pending_approval / approved / rejected / closed_to_po
PurchaseRequisitionSource: manual / ai_autodraft
PurchaseOrderStatus: open / in_transit / closed / cancelled
PayableStatus: pending / partial / paid / overdue
StockAlertLevel: low / out
```

**ActionTargetType 扩展**:加 `material / issue_voucher / requisition / purchase_order / goods_receipt / payable / stock_alert`(向后兼容,只新增不动)。

---

## 3. API 列表 (10 个端点)

全部挂在 `/api/win/` 下,沿用现有 `routes.py` 注册模式。

| Method | Path | 说明 | 写入路径 |
|---|---|---|---|
| POST | `/confirm/entities` | (已有,扩展) 现支持新的 entity_type: Supplier / Material / IssueVoucher / PurchaseRequisition / PurchaseOrder | confirm_writer |
| POST | `/procurement/issue-vouchers/{id}/confirm-and-issue` | 领料单已被 confirm 入库后,调此触发库存扣减 + 预警 + AI auto-draft PR(等价于前端 demo 的 CONFIRM_INBOX 副作用部分) | 业务规则 service |
| POST | `/procurement/requisitions/{id}/approve` | 张主管批准 PR → 设 human_verified=True,自动创建 PO(等价于 APPROVE_PR) | 业务规则 service |
| POST | `/procurement/requisitions/{id}/reject` | 驳回 PR | 业务规则 service |
| POST | `/procurement/purchase-orders/{id}/receive` | PO 入库 → 写 GoodsReceipt + 库存增加 + 自动新增 Payable | 业务规则 service |
| GET | `/procurement/materials` | 物料列表 + 当前余额 + warning level | 只读聚合 |
| GET | `/procurement/requisitions?status=pending_approval` | PR 列表 | 只读聚合 |
| GET | `/procurement/purchase-orders?status=...` | PO 列表 | 只读聚合 |
| GET | `/procurement/payables?aging=overdue|due_soon|future` | 应付台账 | 只读聚合 |
| GET | `/briefing/kpi` | 经营日报 KPI:本月应付总额 / 低库存 SKU 数 / 在途 PO 数 / 待审批 PR 数 / 今日要事 | 只读聚合 |

**P1 (时间允许)**:
| GET | `/finance/balance-sheet?period=2026-05` | 会企01 资产负债表 |
| GET | `/finance/pnl-distribution?period=2026-05` | 会企02 利润及利润分配表 |
| GET | `/finance/cashflow?period=2026-05` | 会企03 现金流量表 |

---

## 4. 业务规则 (主线 5 步,backend 视角)

```
Step 1+2  上传领料单照片 → /confirm/entities 写 IssueVoucher 草稿 (现有路径)
                                ↓
Step 3   POST /procurement/issue-vouchers/{id}/confirm-and-issue
            │
            ├─ 1. set IssueVoucher.status = 'confirmed' (idempotent guard)
            ├─ 2. INSERT StockMovement(direction='out', qty=-issue.qty,
            │        reference_type='issue_voucher', reference_id=issue.id)
            ├─ 3. UPDATE Material.last_balance -= issue.qty
            ├─ 4. IF Material.last_balance < Material.safety_stock:
            │        INSERT StockAlert(level='low', ...)
            │        INSERT ActionLog(action_type='other', actor='system:rule-engine')
            │        ↓ AI auto-draft PR (规则版):
            │        INSERT PurchaseRequisition(source='ai_autodraft', 
            │              status='pending_approval', human_verified=False,
            │              source_note='AI 检测到 {material} 跌破安全线...')
            │        + PurchaseRequisitionItem (qty = reorder_qty 默认 = safety_stock × 2 - balance)
            │        INSERT ActionLog(action_type='other', 
            │              actor='system:rule-engine', kind='system')
            └─ return { stock_alert: ..., auto_drafted_pr: ... }

Step 4   POST /procurement/requisitions/{id}/approve
            │
            ├─ guard: status == 'pending_approval'
            ├─ UPDATE PR: status='closed_to_po', human_verified=True, 
            │             verified_by=actor, approved_at=now, approver=actor
            ├─ INSERT PurchaseOrder (status='open', from_pr_id=pr.id,
            │           supplier_id=pr.supplier_id, total_amount=sum(items))
            ├─ INSERT PurchaseOrderItem rows from PR items
            ├─ UPDATE PR.po_ref = new_po.po_no
            ├─ INSERT ActionLog (action_type='other', actor=actor, kind='user')
            └─ return { purchase_order: ... }

Step 5   POST /procurement/purchase-orders/{id}/receive
            │
            ├─ guard: status in ('open', 'in_transit')
            ├─ UPDATE PO: status='closed', warehouse=payload.warehouse, received_at=now
            ├─ INSERT GoodsReceipt
            ├─ FOR each PO item:
            │     INSERT StockMovement(direction='in', qty=+item.qty,
            │           reference_type='goods_receipt', reference_id=receipt.id)
            │     UPDATE Material.last_balance += item.qty
            │     IF Material.last_balance >= Material.safety_stock:
            │         UPDATE StockAlert: resolved_at = now
            ├─ INSERT Payable (supplier_id=PO.supplier_id, amount=PO.total_amount,
            │           invoice_date=today, 
            │           due_date=today + supplier.payment_terms_days)
            ├─ INSERT ActionLog
            └─ return { receipt: ..., payable: ... }

Step 6   GET /briefing/kpi    (经营日报,实时反映)
            return {
              payable_total: SUM(payables.amount - paid_amount) WHERE status != 'paid',
              payable_overdue: SUM(...) WHERE due_date < today,
              low_stock_count: COUNT(materials) WHERE last_balance < safety_stock,
              pending_pr_count: COUNT(prs) WHERE status='pending_approval',
              open_po_count: COUNT(pos) WHERE status IN ('open', 'in_transit'),
              today_events: [近 24h 的 ActionLog 摘要],
            }
```

---

## 5. 测试策略

| 层 | 文件 | 覆盖 |
|---|---|---|
| Unit | `tests/test_procurement_models.py` | Model 字段、enum、Mixin 落到 SQLite 没冲突,Base.metadata.create_all OK |
| Unit | `tests/test_procurement_rules.py` | issue-and-confirm 触发库存扣减 / 低库存 → alert / auto-draft PR;approve → PO;receive → 库存增加 + payable + due_date;边界:idempotent, 高安全库存不预警 |
| Confirm | `tests/test_confirm_procurement.py` | 扩展后的 confirm_writer 能写 Supplier / Material / IssueVoucher / PR(含 items via relationships)|
| API | `tests/test_procurement_api.py` | 全部 10 个端点 happy path,httpx.AsyncClient,SQLite |
| KPI | `tests/test_briefing_kpi.py` | KPI 聚合数字正确 |
| **E2E** | `tests/test_jintai_mainline_e2e.py` | **端到端 happy path**: 上传 → confirm → issue → 库存 -800 → alert → auto-draft PR → approve → PO → receive → 库存 +4000 → payable +¥96000 → KPI 反映 |
| P1 | `tests/test_finance_reports.py` | 三表聚合数字与底层 entity 一致 |

测试基座沿用 `test_confirm_cards.py` pattern:
- `_clean_state` override 为 no-op
- in-memory SQLite + `Base.metadata.create_all`
- `httpx.AsyncClient(ASGITransport(app=app))`

**红线**: `pytest backend/` 全绿(已 skip 的 11 个 PEP 701 syntax error 不算)。新增 ≥ 50 个测试函数。

---

## 6. 分支与 PR 计划

| Branch | Base | PR 标题 | 状态 |
|---|---|---|---|
| `feat/jintai-backend-mainline` | `feat/p0-integration-verify` | feat(jintai-backend): 采购/库存主线 — schema + 业务规则 + API + E2E | draft / do-not-merge |
| `feat/jintai-finance-reports` (如果时间允许) | `feat/jintai-backend-mainline` | feat(jintai-backend): 财务三表 P1 — balance-sheet / pnl / cashflow 只读聚合 | draft / do-not-merge |

每个 PR description 4 段:
1. **Summary** (3 bullets: 做了什么 / 为什么 / 不做什么)
2. **Test plan** (checklist)
3. **风险与回滚** (新建表无破坏性 / 全部 do-not-merge / 回滚只需 revert)
4. **明早 CTO review checklist** (确认决策 / 接入前端的 wiring 任务)

---

## 7. 取舍清单 (老板 review 时重点看的)

✅ **做了**:
- 完整数据模型 (9 张新表) + 扩展现有 ontology 枚举
- 业务规则全链 (confirm → 扣库存 → 预警 → AI auto-draft → approve → PO → receive → payable → KPI)
- 必走 confirm_writer + ActionLog 路径
- 测试基座 + 端到端 happy path

⚠️  **简化了**:
- AI auto-draft PR 用规则引擎 (按近 N 月平均用量 = safety_stock × 2 - balance),没真正调 LLM (P2 留给后续)
- BOM / 配料单 / 跨模块工序 (P2,不在本次 scope)
- 折旧 / 成本拆分 (P2 不实现,前端 demo 直接显示固定数,等真有制造数据再算)
- 财务三表只读聚合,**不支持冲销 / 调账 / 期末结转** (财务系统专业活,demo 不碰)

❌ **没做** (留给老板拍板):
- 前端 wire-up: 把 store.tsx 的 reducer 切到 API 调用(避免半夜动 demo)
- LLM 真调 (auto-draft PR 现在是规则版,真版需 prompts.py 加 schema-aware prompt)
- 财务三表期末结转算法
- BOM 配料联动

---

## 8. 风险登记

| 风险 | 缓解 |
|---|---|
| 测试需要 postgres + redis,本地可能没装 | 每个新文件 override `_clean_state`,sqlite-only 跑通 |
| confirm_writer 扩展破坏现有 OrderLine 等映射 | 只新增 `_ENTITY_MODEL` 字典 key,不动旧 key;test_confirm_cards.py 当回归 |
| 新增 mixin 列在已存在 tenant DB 没字段 → ORM 查询炸 | 沿用 `_run_lightweight_tenant_migrations` 增量 ALTER,首次访问自动补齐 |
| 业务规则在 confirm 之后调,中间 API 调用失败 → 数据半路 | API handler 把"业务规则副作用"也包进 `session.begin()` |
| Material.last_balance 反范式 → 跟 StockMovement 不一致 | 每次写 StockMovement 必须算并写 last_balance,单元测试断言一致 |

---

## 9. 落地次序 (今晚的执行 checklist)

```
✅ Phase 0  discovery (done)
✅ Phase 1  写本文 BACKEND_PLAN.md (done) 
□ Phase 2.1 enums + models + lightweight migrations
□ Phase 2.2 扩展 confirm_writer 字典 + 测试
□ Phase 2.3 procurement service (业务规则)
□ Phase 2.4 procurement API + briefing API
□ Phase 2.5 E2E mainline 测试
□ Phase 2.6 pytest 全绿 verify
□ Phase 3   (P1 财务三表 — 时间允许)
□ Phase 4   scripts/jintai/mainline-demo.sh
□ Phase 5   commit / push / 开 PR (do-not-merge)
□ Phase 6   outputs/JINTAI_BACKEND_REPORT.md
```

**预算**: Phase 2 是大头,占今晚 70% 时间。E2E 测试是 gate,必须通过才能收尾。

---

## 10. Round 2 (老板追加授权后) — 决策落地

老板凌晨原话:"你为我做最佳判断 然后执行"。Claude 拍板了原本 7 项待决策,继续推进 P1 + P2,详见 `outputs/JINTAI_BACKEND_ROUND2_REPORT.md`。决策汇总:

| 议题 | 决策 | 落地代码 |
|---|---|---|
| 分支策略 | ✅ 保持 base #113 | 本 PR base 在 #114 |
| AI auto-draft 公式 | ✅ 升级到近 3 月用量 + safety fallback | `services/procurement.py::_compute_reorder_recommendation` |
| Supplier/Material 入库 | ⏸ 走 confirm 不变 | 无 |
| 应付账期 60 天 | ✅ 保持 | 无 |
| auto-draft 自动绑 supplier | ✅ 升级 | `_last_supplier_for_material` / `_last_unit_price_for_material` |
| ActionTargetType 扩展 | ⏸ 仍延后 | 无 |
| 财务三表 自研 vs Kingdee | ✅ 自研最小聚合 | `models/finance.py` + `services/finance.py` + `api/finance.py` |

---

## 11. Round 2 新增数据 / API

**5 张新表**:
- `finance_chart_of_accounts` (科目主表,15 个常用 seed)
- `finance_period_opening_balances` (每期每科目期初余额)
- `finance_fixed_assets` (固定资产卡片 + 直线折旧)
- `procurement_bills_of_materials` (BOM head)
- `procurement_bill_of_materials_lines` (BOM line)

**Material 加 1 列** `last_unit_cost` (Numeric 18,4,WAC 自动更新)

**9 个新 API**:
```
GET  /finance/balance-sheet?period=YYYY-MM      (会企01)
GET  /finance/pnl-distribution?period=YYYY-MM   (会企02)
GET  /finance/cashflow?period=YYYY-MM           (会企03)
GET  /finance/depreciation?period=YYYY-MM
GET  /finance/cost-breakdown?period=YYYY-MM
GET  /finance/chart-of-accounts
GET  /procurement/inventory-ledger?material_id=&period=
GET  /procurement/boms[?status=]
GET  /procurement/boms/{id}
POST /procurement/boms/{id}/explode  (按 batch_quantity 爆开)
```

**业务规则升级**:
- `receive_purchase_order` → WAC 自动更新 material.last_unit_cost
- `_ai_autodraft_requisition` → 用近 3 月用量 + 最近 supplier + 最近 unit_price
- BOM `explode` → 算每料 required vs balance + shortage + available 标记

---

## 12. Round 2 测试

```
$ pytest tests/test_jintai_bom.py tests/test_jintai_finance_reports.py \
         tests/test_jintai_mainline_e2e.py tests/test_procurement_api_listings.py \
         tests/test_confirm_cards.py tests/test_ontology_schema.py \
         tests/test_p0_end_to_end.py tests/test_parse_pipeline.py \
         tests/test_ontology_migration_cycle.py -q
56 passed in 2.74s
```

- 11 finance reports tests (含 WAC, auto-draft 升级, 3 月用量推荐)
- 5 BOM tests (含 explode + scrap_rate + confirm_writer 走 BOM)
- 9 既有 round 1 测试 (mainline e2e + listings) 不破
- 31 既有 ontology / parse / confirm 测试 不破

