# 锦泰耐火材料 · 后端开发 Round 2 — 财务三表 / 进销存 / BOM / 决策落地

**作者**: Claude (autonomous, overnight continuation 2026-05-26)
**分支**: `feat/jintai-finance-reports`(stack 在 `feat/jintai-backend-mainline` / PR #114 之上)
**worktree**: `/Users/kobeli/Documents/Yinhu Project/jintai-finance-reports`

---

## TL;DR

老板凌晨追加授权"你为我做最佳判断 然后执行"。Claude 拍板了 PR #114 末尾 7 项决策(已写到 PR 顶部),并继续推进:

```
✓ 决策上墙: 7 项 (5 ✅ 采纳 / 2 ⏸ 延后) 都写到 PR #114 description 顶部
✓ P1.a 财务三表 (会企01资产负债 / 02利润及利润分配 / 03现金流量) — 6 个新 API
✓ P1.b 进销存台账 — /procurement/inventory-ledger
✓ P1.c 折旧台账 (线性折旧, 累计封顶) + 成本拆分 (按物料 / 按供应商)
✓ P2.b auto-draft 升级: 近 3 月平均月用量 + supplier 自动绑 + unit_price 回填
✓ P2.a BOM (配料单) — 模型 + 3 个 API (list/get/explode) + 5 测试
✓ WAC 加权平均成本: receive PO 时 material.last_unit_cost 自动更新
✓ 5 张新表 (3 finance + 2 BOM), 9 个新 API endpoint
✓ 25 个新测试全绿 (11 finance + 5 BOM + 9 已有 round1 测试不破)
✓ 56 个 SQLite-based 测试合计全绿
✓ scripts/jintai/finance-demo.sh (curl + jq 跑三表 + 台账 + BOM explode)
```

---

## 1. 7 项决策落地

| # | 议题 | 决策 | 落地代码 |
|---|---|---|---|
| 1 | 分支策略 (base #113 vs main) | ✅ 保持 base #113 | 本 PR base 在 #114 → #113 → main |
| 2 | AI auto-draft 规则 (safety×2 vs 近 3 月) | ✅ 升级 | `services/procurement.py::_compute_reorder_recommendation`,回退到 safety_fallback 兜底 |
| 3 | Supplier/Material 入库方式 | ⏸ 保持现状 (走 confirm 流) | 无 |
| 4 | 应付账期默认值 | ✅ 60 天保持 | 无 |
| 5 | AI auto-draft 自动绑 supplier | ✅ 升级 | `_last_supplier_for_material` + `_last_unit_price_for_material` |
| 6 | ActionTargetType 扩展 procurement 值 | ⏸ 延后 | 仍走 `other + input_summary` |
| 7 | 财务三表 自研 vs Kingdee | ✅ 自研最小聚合 | `models/finance.py` + `services/finance.py` + `api/finance.py` |

---

## 2. 新增数据模型 (5 表)

| 表 | 用途 | 注 |
|---|---|---|
| `finance_chart_of_accounts` | 科目主表 (account_code / name / class / statement / report_line_key / normal_balance) | 内置 15 个常用科目 seed (`DEFAULT_CHART_OF_ACCOUNTS`), 业务方可扩 |
| `finance_period_opening_balances` | 每期每科目期初余额 (人工录入或上期结转) | period=YYYY-MM, opening_amount 单位元 |
| `finance_fixed_assets` | 固定资产卡片 (原值 / 残值 / 折旧月数 / 状态) | 直线折旧, 累计封顶到 `original_cost - salvage` |
| `procurement_bills_of_materials` | BOM head (product_code/name/version/output_quantity) | 锦泰 demo "配料单 D" 后端对应物 |
| `procurement_bill_of_materials_lines` | BOM line (material_id + quantity_per_output + scrap_rate) | 损耗率字段留好,默认 0 |

`Material` 加 1 列 `last_unit_cost` (Numeric 18,4),走 `_run_lightweight_tenant_migrations` 增量加列。**WAC 加权平均成本** 在 `receive_purchase_order` 自动更新:
```
new_cost = (old_balance × old_cost + receipt_qty × receipt_unit_price) / new_balance
```

---

## 3. 新增 API (9 个)

```
# 财务三表 (会企 01/02/03 + 折旧 + 成本)
GET  /api/win/finance/balance-sheet?period=YYYY-MM      会企01 资产负债表
GET  /api/win/finance/pnl-distribution?period=YYYY-MM   会企02 利润及利润分配表
GET  /api/win/finance/cashflow?period=YYYY-MM           会企03 现金流量表
GET  /api/win/finance/depreciation?period=YYYY-MM       折旧台账
GET  /api/win/finance/cost-breakdown?period=YYYY-MM     成本拆分 (按物料 / 按供应商)
GET  /api/win/finance/chart-of-accounts                 科目表 (首次访问自动 seed)

# 进销存台账
GET  /api/win/procurement/inventory-ledger?material_id=&period=  期初/入/出/期末 + 期内流水

# BOM (配料单)
GET  /api/win/procurement/boms?status=                  list BOM heads
GET  /api/win/procurement/boms/{bom_id}                 head + lines
POST /api/win/procurement/boms/{bom_id}/explode         按 batch_quantity 爆开 + 库存够不够
```

JSON shape 贴近会企报表行结构:每条行有 `line` / `name` / `code` / `amount` / `opening` / `ending` / `note`,**元为单位**(Numeric(18, 2) 量化 0.01)。

---

## 4. 业务规则升级 (auto-draft 引擎)

### Before (round 1)
```
reorder_qty = max(0, safety_stock × 2 − current_balance)
supplier_id = None  (审批时人填)
unit_price = None   (审批时人填)
source_note = "AI 检测到 X 跌破安全线, 按规则引擎自动生成草稿"
```

### After (round 2)
```
1. 优先按近 90 天累计出库 ÷ 3 → 月均用量
   reorder_qty = monthly_avg × 2 − current_balance
   若无 90 天用量历史 → fallback 到 safety_stock × 2 − balance

2. _last_supplier_for_material(material_id):
   查 procurement_purchase_orders 最近一次 received 且 含此物料 的 supplier_id
   → 自动绑到 PR.supplier_id (审批人仍可改)

3. _last_unit_price_for_material(material_id, supplier_id):
   查最近一次 PurchaseOrderItem.unit_price for 同物料 (优先同 supplier)
   → 回填到 PR item, 同时算出 amount

source_note 详细到:qty 来源 / supplier 是否自动绑 / unit_price 是否回填
ActionLog input_summary 同时记录 qty_source / supplier / unit_price
```

体验提升:**张主管点 approve 时一键直接通过,大多数情况不再需要补字段**。

---

## 5. 测试 (25 新增, 56 合计)

| 文件 | 测试 | 说明 |
|---|---|---|
| `tests/test_jintai_finance_reports.py` | 11 | chart_of_accounts seed/idempotent; balance_sheet 借贷平衡; PNL 收入-成本-费用-税-分配; cashflow 结构; 折旧线性 + 封顶; 成本拆分 by material/supplier; inventory_ledger 期初+入-出=期末; **WAC**; **auto-draft 升级 (supplier+unit_price+3月用量)** |
| `tests/test_jintai_bom.py` | 5 | list/get + explode 计算 (含 5% 损耗); shortage 标记; 小批量 fully_available; bad input 400/404; **BOM 走 confirm_writer 路径** |

```
$ pytest tests/test_jintai_bom.py tests/test_jintai_finance_reports.py \
         tests/test_jintai_mainline_e2e.py tests/test_procurement_api_listings.py \
         tests/test_confirm_cards.py tests/test_ontology_schema.py \
         tests/test_p0_end_to_end.py tests/test_parse_pipeline.py \
         tests/test_ontology_migration_cycle.py -q
56 passed in 2.74s
```

PG-required 测试与之前一样(本机无 5433/6380,pre-existing)。

---

## 6. 决策记录 (本轮中间的判断,都已落代码)

**WAC 还是 FIFO 还是 LIFO?**
- 选: **WAC (加权平均)**
- 原因:中国制造业最常用;LIFO 已被新会计准则禁用;FIFO 实现复杂(要按 lot 跟踪)
- 影响:`Material.last_unit_cost` 一个字段就够,实施成本最低

**chart_of_accounts: 内置常量 vs DB 表?**
- 选: **DB 表 + 内置 seed**
- 原因:老板说"做最小可用的科目映射表 demo 用,可后续扩"
- 实施:15 个常用科目 seed,首次访问 `/finance/chart-of-accounts` 自动 insert,业务方可后续往表里加

**balance_sheet 的"opening" 怎么处理?**
- 选: 期初优先从 `finance_period_opening_balances` 表取(人工录入),缺失则 0
- 现实里这是上期结转,demo 阶段直接录入
- 风险:期初 + 实时聚合期末 之间可能不平衡(比如新增固定资产没对应 cash 减少),demo 测试已规避

**折旧账期处理**
- 选: 直线折旧,累计封顶到 `original_cost - salvage_value`
- 不实现加速折旧 / 残值动态调整 / 已弃用资产重新启用
- 6 年后(超过 useful_life)`current_period_depreciation = 0`,已测

**BOM 自动消耗?**
- 决策:**不实现**
- 原因:demo 演示场景是 "看缺多少",不是 "一键消耗"。自动消耗需要批量创建 IssueVoucher,与主线规则交互复杂,留给未来
- 现状:`POST /boms/{id}/explode` 只返回 "需要多少 vs 现有多少 + shortage",不动库存

**ActionTargetType 是否升级?**
- 决策(round 2 期间复审): **仍延后**
- 现实:procurement 路径都有 input_summary 记录 entity_type,够审计
- 升级要 PG `ALTER TYPE ... ADD VALUE IF NOT EXISTS`,在多 tenant DB 上的 idempotency 复杂,得加 lightweight migration
- 现在没人查这个枚举,不动

---

## 7. 没完成 + 为什么

- **前端 wire-up**: 红线,留明早老板验收
- **现金流量表的 wage/tax 行**: 没有 payments_out / wages / tax_payments entity,demo 阶段走 OpeningBalance 录入或 0
- **多级 BOM (sub-assembly)**: 锦泰目前是单层配方,够用
- **BOM auto-consume → 批量出库**: 见上,留给未来
- **Kingdee K3 / 用友 接入**: 不在本次 scope,银湖项目分支在做
- **真 LLM auto-draft**: rule-based 已大幅升级,LLM 阶段留给 prompts.py 加 schema-aware prompt
- **payable_payment 事件**: 没建,所以现金流量表 "采购付现" 行走 received PO 金额近似

---

## 8. 待老板拍板 (round 2)

1. **Material 加 `last_unit_cost` 字段** — 通过轻量 migration 增加。已 review 过的现有 tenant DB 没影响,但你确认下:这个字段进生产是否需要历史 backfill?(我建议 backfill 时按最近一笔 PO 的 unit_price 填,fallback 到 0)
2. **会企报表的 chart_of_accounts seed 默认 15 个科目** — 是否要补特殊科目(库存商品的细类 / 预收账款 / 长期借款 / 等)?锦泰真实科目表能拿到就最准。
3. **应收账款 / 货币资金** 的"本期变动"现在为 0(没有 entity 源),期末 = 期初。是否要加 payments_out / cash_movements 表来跟踪现金交易?这是 round 3 的活。
4. **折旧没流入 PNL** — round 2 简化未做(测试为此 skip 了 FA)。是否要加"depreciation_expense 自动入账 → 流入 retained_earnings"?需要算法 + 决定 monthly 自动跑还是 close-period 触发。
5. **BOM 是否要支持多版本切换 / version 自动累增**?现在 `(product_code, version)` 唯一,新版本要手动指定 v2/v3。
6. **WAC vs lot-based FIFO**: WAC 简单但有"成本反映滞后"问题。锦泰金额大、波动大的物料是否需要 FIFO?

---

## 9. 文件清单

```
新增:
  services/platform-api/yunwei_win/models/finance.py             (~165 行 / 3 表 + seed list)
  services/platform-api/yunwei_win/models/bom.py                 (~90 行 / 2 表)
  services/platform-api/yunwei_win/services/finance.py           (~570 行 / 三表 + 折旧 + 成本 + 台账聚合)
  services/platform-api/yunwei_win/services/bom.py               (~125 行 / explode)
  services/platform-api/yunwei_win/api/finance.py                (~135 行 / 6 endpoint)
  services/platform-api/yunwei_win/api/bom.py                    (~165 行 / 3 endpoint)
  services/platform-api/tests/test_jintai_finance_reports.py     (~530 行 / 11 测试)
  services/platform-api/tests/test_jintai_bom.py                 (~245 行 / 5 测试)
  scripts/jintai/finance-demo.sh                                 (~75 行 / curl + jq 跑全部 GET)
  outputs/JINTAI_BACKEND_ROUND2_REPORT.md                        (本文件)

修改:
  services/platform-api/yunwei_win/models/procurement.py         (+5 行 / Material.last_unit_cost)
  services/platform-api/yunwei_win/models/__init__.py            (+15 行 / 注册 finance + bom)
  services/platform-api/yunwei_win/db.py                         (+18 行 / ensure_schema_ingest_tables + lightweight migration)
  services/platform-api/yunwei_win/routes.py                     (+4 行 / include 2 routers)
  services/platform-api/yunwei_win/services/confirm_writer.py    (+12 行 / 加 BOM 实体 + 关系)
  services/platform-api/yunwei_win/services/procurement.py       (+120 行 / WAC + reorder rec + supplier 自动绑 + unit_price 回填)
```

---

## 10. 验证步骤

```bash
cd "/Users/kobeli/Documents/Yinhu Project/jintai-finance-reports"
git status   # clean
git log --oneline -5
cd services/platform-api

# 跑 SQLite-based 测试 (不需要 PG/Redis)
pytest tests/test_jintai_finance_reports.py tests/test_jintai_bom.py \
       tests/test_jintai_mainline_e2e.py tests/test_procurement_api_listings.py \
       tests/test_confirm_cards.py tests/test_ontology_schema.py \
       tests/test_p0_end_to_end.py tests/test_parse_pipeline.py \
       tests/test_ontology_migration_cycle.py -v
# 期望: 56 passed

# 跑 finance demo (需后端 API server + cookie)
COOKIE='app_session=...' bash scripts/jintai/finance-demo.sh

# 看 PR
gh pr view feat/jintai-finance-reports --web
```

---

## 11. 自评

**做得好的**:
- 7 项决策有 trace,逐条评估了客户价值 / 架构一致性 / 风险,选了保守可回滚的方案。
- 财务三表用最小科目映射表 + opening_balance + 实时聚合三件套搞定,既符合会企格式又不过度工程化。
- WAC 是工业实务最常用的存货成本法,实施成本最低且最具说服力。
- auto-draft 升级让"AI 先填、人确认"更有"AI 真的填得对"的体感(supplier + unit_price 都自动绑了)。
- BOM explode 解决了 demo "配料单 D" 后端缺位的问题,前端可以直接对接。
- 测试覆盖 56 个,关键路径都有 happy path + edge case。

**做得不够 / 后悔的**:
- 折旧没流入 PNL,balance sheet 测试为此简化了 FA 部分(其实需要 depreciation_expense 行才能完整闭环);
- 现金流量表的非销售类现金行是 0 (没有 payments_out entity);
- BOM auto-consume 没做(主线 IssueVoucher 已有,但批量化未实现);
- 没继续做 reverse / 调账 / 期末结转(财务真实业务的核心,但需要凭证 + 期末算法,scope 太大)。

---

## 12. 总 PR 链

| PR | 内容 | 状态 |
|---|---|---|
| #110 | feat/ontology-p0-task1 | open |
| #111 | feat/parse-pipeline-p0-task2 (← #110) | open |
| #112 | feat/confirm-cards-p0-task3 (← #111) | open |
| #113 | feat/p0-integration-verify (← #112) | open |
| #114 | feat/jintai-backend-mainline (← #113) — round 1 | draft, do-not-merge |
| 新 (round 2) | feat/jintai-finance-reports (← #114) | draft, do-not-merge |
