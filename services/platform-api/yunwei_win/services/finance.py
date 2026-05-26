"""锦泰 财务三表 + 折旧 + 成本拆分聚合 service.

会企01 资产负债表 / 会企02 利润及利润分配表 / 会企03 现金流量表 从
底层 entities (invoices / payments / payables / stock_movements /
fixed_assets) 聚合, 加上 ``finance_period_opening_balances`` 的人工录入
期初, 拼成符合中国小企业会计准则的 JSON.

约定:
  * 单位元 (Numeric(18, 2)). 不出现"千元/万元".
  * 期 = YYYY-MM 字符串 (e.g. "2026-05"). period_bounds() 返回月初/月末日期.
  * 期初: 优先从 ``finance_period_opening_balances`` 取; 缺失则 0.
  * 期末: 期初 + 本期净变动 (按科目方向 debit/credit 加减).
  * 不做凭证 (journal entries); demo 阶段所有发生额从底层表算.
"""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    AccountClass,
    ChartOfAccount,
    DEFAULT_CHART_OF_ACCOUNTS,
    FixedAsset,
    FixedAssetStatus,
    Material,
    Payable,
    PayableStatus,
    PeriodOpeningBalance,
    PurchaseOrder,
    PurchaseOrderItem,
    StatementSection,
    StockMovement,
    StockMovementDirection,
    Supplier,
)


logger = logging.getLogger(__name__)


PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
ZERO = Decimal("0")
ZERO_2 = Decimal("0.00")
SMALL_BIZ_INCOME_TAX_RATE = Decimal("0.25")  # 小企业基础税率, 实际可享受减免
SURPLUS_RESERVE_RATE = Decimal("0.10")        # 法定盈余公积


def _q(value: Decimal | int | float | None) -> Decimal:
    """Quantize to 2 decimal places (元 + 分)."""
    if value is None:
        return ZERO_2
    return Decimal(value).quantize(Decimal("0.01"))


def period_bounds(period: str) -> tuple[date, date]:
    """'2026-05' → (date(2026,5,1), date(2026,5,31))."""
    m = PERIOD_RE.match(period)
    if not m:
        raise ValueError(f"invalid period {period!r}; expected YYYY-MM")
    year, month = int(m.group(1)), int(m.group(2))
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)


def _previous_period(period: str) -> str:
    y, mo = int(period[:4]), int(period[5:7])
    if mo == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{mo - 1:02d}"


# ============================== seed ====================================


async def ensure_chart_of_accounts_seeded(session: AsyncSession) -> int:
    """Insert DEFAULT_CHART_OF_ACCOUNTS rows if the table is empty.

    Returns the number of rows inserted (0 if already seeded). Idempotent —
    safe to call from any endpoint that needs the chart.
    """
    existing = (
        await session.execute(select(func.count()).select_from(ChartOfAccount))
    ).scalar_one()
    if existing > 0:
        return 0
    for code, name, klass, statement, key, normal, sort in DEFAULT_CHART_OF_ACCOUNTS:
        session.add(
            ChartOfAccount(
                account_code=code,
                account_name=name,
                account_class=klass,
                statement=statement,
                report_line_key=key,
                normal_balance=normal,
                sort_order=sort,
                created_by="system",
                updated_by="system",
            )
        )
    await session.flush()
    logger.info("finance.chart_of_accounts.seeded count=%d", len(DEFAULT_CHART_OF_ACCOUNTS))
    return len(DEFAULT_CHART_OF_ACCOUNTS)


# ============================== opening balance helpers ================


async def _opening_balances(
    session: AsyncSession, period: str,
) -> dict[str, Decimal]:
    """Return {account_code: opening_amount} for the given period."""
    rows = (
        await session.execute(
            select(PeriodOpeningBalance).where(PeriodOpeningBalance.period == period)
        )
    ).scalars().all()
    return {r.account_code: Decimal(r.opening_amount) for r in rows}


async def _accounts_by_section(
    session: AsyncSession, section: StatementSection,
) -> list[ChartOfAccount]:
    return (
        await session.execute(
            select(ChartOfAccount)
            .where(ChartOfAccount.statement == section)
            .order_by(ChartOfAccount.sort_order)
        )
    ).scalars().all()


# ============================== aggregations from entities ============


async def _inventory_value(session: AsyncSession) -> Decimal:
    """Sum(material.last_balance × material.last_unit_cost)."""
    rows = (
        await session.execute(
            select(Material.last_balance, Material.last_unit_cost).where(
                Material.is_deleted == False
            )
        )
    ).all()
    total = ZERO
    for balance, cost in rows:
        total += Decimal(balance) * Decimal(cost)
    return _q(total)


async def _accounts_payable_outstanding(
    session: AsyncSession, as_of: date | None = None,
) -> Decimal:
    """Sum(payables.amount - paid_amount) where status != paid (and invoice on or before as_of)."""
    stmt = select(Payable.amount, Payable.paid_amount, Payable.invoice_date).where(
        Payable.status != PayableStatus.paid, Payable.is_deleted == False,
    )
    if as_of is not None:
        stmt = stmt.where(Payable.invoice_date <= as_of)
    rows = (await session.execute(stmt)).all()
    total = ZERO
    for amount, paid, _inv in rows:
        total += Decimal(amount) - Decimal(paid)
    return _q(total)


async def _fixed_assets_summary(
    session: AsyncSession, as_of: date,
) -> tuple[Decimal, Decimal]:
    """Return (original_cost_total, accumulated_depreciation_total) for assets
    acquired ≤ as_of and active or disposed_after as_of."""
    rows = (
        await session.execute(
            select(FixedAsset).where(
                FixedAsset.acquired_date <= as_of,
                FixedAsset.is_deleted == False,
            )
        )
    ).scalars().all()
    original_total = ZERO
    accum_total = ZERO
    for asset in rows:
        if asset.status == FixedAssetStatus.disposed and asset.disposed_date and asset.disposed_date <= as_of:
            continue
        original_total += Decimal(asset.original_cost)
        monthly = monthly_depreciation(asset)
        months_through = months_depreciated(asset, as_of)
        max_depreciable = Decimal(asset.original_cost) - Decimal(asset.salvage_value)
        accum = min(monthly * months_through, max_depreciable)
        accum_total += accum
    return _q(original_total), _q(accum_total)


def monthly_depreciation(asset: FixedAsset) -> Decimal:
    if asset.useful_life_months <= 0:
        return ZERO
    depreciable = Decimal(asset.original_cost) - Decimal(asset.salvage_value)
    return depreciable / Decimal(asset.useful_life_months)


def months_depreciated(asset: FixedAsset, as_of: date) -> int:
    """Number of full months between acquired_date and as_of (inclusive of as_of's month)."""
    if as_of < asset.acquired_date:
        return 0
    years = as_of.year - asset.acquired_date.year
    months = as_of.month - asset.acquired_date.month
    total = years * 12 + months
    if as_of.day >= asset.acquired_date.day:
        total += 1
    if total < 0:
        return 0
    return total


# ============================== invoices/payments aggregations =========
# These rely on the customer-ontology Invoice/Payment models from P0 task ①
# (yunwei_win/models/company_data.py). For demo purposes we aggregate amounts;
# if those tables are empty the rows simply return 0.


async def _revenue_in_period(session: AsyncSession, start: date, end: date) -> Decimal:
    from yunwei_win.models import Invoice

    rows = (
        await session.execute(
            select(Invoice.amount_total).where(
                Invoice.issue_date >= start,
                Invoice.issue_date <= end,
                Invoice.is_deleted == False,
            )
        )
    ).all()
    total = ZERO
    for (amount,) in rows:
        if amount is not None:
            total += Decimal(amount)
    return _q(total)


async def _cash_received_in_period(session: AsyncSession, start: date, end: date) -> Decimal:
    from yunwei_win.models import Payment

    rows = (
        await session.execute(
            select(Payment.amount).where(
                Payment.payment_date >= start,
                Payment.payment_date <= end,
                Payment.is_deleted == False,
            )
        )
    ).all()
    total = ZERO
    for (amount,) in rows:
        if amount is not None:
            total += Decimal(amount)
    return _q(total)


async def _cogs_in_period(session: AsyncSession, start: date, end: date) -> Decimal:
    """Cost of goods sold = sum(stock_movements.out × material.last_unit_cost in period).

    Simplification: uses *current* last_unit_cost (WAC), not the cost at
    movement time. Refined version would snapshot unit cost per movement.
    """
    rows = (
        await session.execute(
            select(StockMovement.quantity, StockMovement.material_id).where(
                StockMovement.direction == StockMovementDirection.out,
                StockMovement.occurred_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
                StockMovement.occurred_at < datetime.combine(end, time.max, tzinfo=timezone.utc),
            )
        )
    ).all()
    if not rows:
        return ZERO_2
    material_ids = {mid for _, mid in rows}
    materials = (
        await session.execute(select(Material).where(Material.id.in_(material_ids)))
    ).scalars().all()
    cost_by_material = {m.id: Decimal(m.last_unit_cost) for m in materials}
    total = ZERO
    for qty, mid in rows:
        total += Decimal(qty) * cost_by_material.get(mid, ZERO)
    return _q(total)


async def _payables_paid_in_period(session: AsyncSession, start: date, end: date) -> Decimal:
    """Outflow for procurement — payables that moved to paid/partial in period.

    Simplification: we don't track payable_payment events yet, so this is
    approximated as zero unless a Payable transitioned with paid_amount > 0.
    In a future iteration we'd add PayablePayment events.
    """
    # No event log yet; placeholder. demo will surface 0 unless seeded.
    return ZERO_2


async def _po_amount_received_in_period(session: AsyncSession, start: date, end: date) -> Decimal:
    """Sum(PO.total_amount) for POs received within the period."""
    rows = (
        await session.execute(
            select(PurchaseOrder.total_amount).where(
                PurchaseOrder.received_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
                PurchaseOrder.received_at < datetime.combine(end, time.max, tzinfo=timezone.utc),
            )
        )
    ).all()
    total = ZERO
    for (amount,) in rows:
        if amount is not None:
            total += Decimal(amount)
    return _q(total)


# ============================== report builders ========================


@dataclass
class ReportRow:
    line: str
    name: str
    code: str | None
    amount: Decimal
    opening: Decimal | None = None
    ending: Decimal | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"line": self.line, "name": self.name, "amount": str(_q(self.amount))}
        if self.code is not None:
            d["code"] = self.code
        if self.opening is not None:
            d["opening"] = str(_q(self.opening))
        if self.ending is not None:
            d["ending"] = str(_q(self.ending))
        if self.note is not None:
            d["note"] = self.note
        return d


async def compute_balance_sheet(period: str, session: AsyncSession) -> dict[str, Any]:
    """会企01 资产负债表. 期初取 PeriodOpeningBalance, 期末由发生额倒推或聚合.

    Demo simplification: 期末值优先用底层 entities 实时聚合 (应付/存货/固定资产);
    期初取 opening_balances 表 (人工录入). 现金/应收/借款类没有 entity 源的科目,
    期末 = 期初 (因为 demo 没有现金交易明细).
    """
    await ensure_chart_of_accounts_seeded(session)
    _start, end = period_bounds(period)
    openings = await _opening_balances(session, period)
    accounts = await _accounts_by_section(session, StatementSection.balance_sheet)

    # 实时计算的科目期末值
    inventory_value = await _inventory_value(session)
    ap_outstanding = await _accounts_payable_outstanding(session, as_of=end)
    fa_original, fa_accum = await _fixed_assets_summary(session, as_of=end)

    # 计算本期净利润 (用于未分配利润期末)
    pnl = await compute_pnl(period, session, seed_only=False)
    net_profit_period = Decimal(pnl["net_profit_period"])

    # 期末 by report_line_key
    ending_by_key: dict[str, Decimal] = {}
    notes_by_key: dict[str, str] = {}

    def _set(key: str, value: Decimal, note: str | None = None) -> None:
        ending_by_key[key] = ending_by_key.get(key, ZERO) + value
        if note:
            notes_by_key[key] = note

    # 货币资金 / 应收 / 借款: 期末 = 期初 (no event source for demo).
    # 存货: 实时
    # 应付: 实时
    # 固定资产 / 累计折旧: 实时
    # 实收资本: 期末 = 期初
    # 未分配利润: 期末 = 期初 + 本期净利润 - 本期分配 (盈余公积 etc. 在 PNL 里算)
    retained_period_change = Decimal(pnl["retained_earnings_change_period"])

    assets_rows: list[ReportRow] = []
    liabilities_rows: list[ReportRow] = []
    equity_rows: list[ReportRow] = []
    asset_total_opening = ZERO
    asset_total_ending = ZERO
    liab_total_opening = ZERO
    liab_total_ending = ZERO
    equity_total_opening = ZERO
    equity_total_ending = ZERO

    for acc in accounts:
        op = openings.get(acc.account_code, ZERO)
        key = acc.report_line_key
        if key == "inventory":
            ending = inventory_value
            notes_by_key.setdefault(key, "= sum(material.last_balance × last_unit_cost)")
        elif key == "accounts_payable":
            ending = ap_outstanding
            notes_by_key.setdefault(key, "= sum(payables outstanding @ as_of)")
        elif key == "fixed_assets":
            ending = fa_original
            notes_by_key.setdefault(key, "= sum(fixed_assets.original_cost @ as_of)")
        elif key == "accumulated_depreciation":
            ending = fa_accum
            notes_by_key.setdefault(key, "= sum(monthly_dep × months_through @ as_of)")
        elif key == "retained_earnings":
            ending = op + retained_period_change
            notes_by_key.setdefault(key, "= opening + 本期未分配利润增量")
        else:
            ending = op
        row = ReportRow(
            line=str(acc.sort_order),
            name=acc.account_name,
            code=acc.account_code,
            amount=ending,
            opening=op,
            ending=ending,
            note=notes_by_key.get(key),
        )
        if acc.account_class == AccountClass.asset:
            assets_rows.append(row)
            asset_total_opening += op
            asset_total_ending += ending if key != "accumulated_depreciation" else -ending
        elif acc.account_class == AccountClass.liability:
            liabilities_rows.append(row)
            liab_total_opening += op
            liab_total_ending += ending
        elif acc.account_class == AccountClass.equity:
            equity_rows.append(row)
            equity_total_opening += op
            equity_total_ending += ending

    # Subtotal rows
    assets_rows.append(ReportRow("subtotal", "资产总计", None,
                                  asset_total_ending, asset_total_opening, asset_total_ending,
                                  note="累计折旧已抵减"))
    liabilities_rows.append(ReportRow("subtotal", "负债合计", None,
                                       liab_total_ending, liab_total_opening, liab_total_ending))
    equity_rows.append(ReportRow("subtotal", "所有者权益合计", None,
                                  equity_total_ending, equity_total_opening, equity_total_ending))

    return {
        "statement": "会企01 资产负债表",
        "period": period,
        "as_of_date": end.isoformat(),
        "currency": "CNY",
        "unit": "元",
        "assets": [r.to_dict() for r in assets_rows],
        "liabilities": [r.to_dict() for r in liabilities_rows],
        "equity": [r.to_dict() for r in equity_rows],
        "totals": {
            "assets": str(_q(asset_total_ending)),
            "liabilities_plus_equity": str(_q(liab_total_ending + equity_total_ending)),
            "balanced": _q(asset_total_ending) == _q(liab_total_ending + equity_total_ending),
        },
    }


async def compute_pnl(
    period: str, session: AsyncSession, *, seed_only: bool = False,
) -> dict[str, Any]:
    """会企02 利润及利润分配表.

    seed_only=True 时跳过 ensure_chart_of_accounts_seeded (避免 balance_sheet 调用时
    递归 flush).
    """
    if not seed_only:
        await ensure_chart_of_accounts_seeded(session)
    start, end = period_bounds(period)

    revenue = await _revenue_in_period(session, start, end)
    cogs = await _cogs_in_period(session, start, end)
    openings = await _opening_balances(session, period)
    selling = openings.get("6601", ZERO)
    admin = openings.get("6602", ZERO)
    finance_expense = openings.get("6603", ZERO)

    operating_profit = revenue - cogs - selling - admin - finance_expense
    profit_total = operating_profit  # 无其他业务利润 / 营业外
    income_tax = (profit_total * SMALL_BIZ_INCOME_TAX_RATE) if profit_total > 0 else ZERO
    net_profit = profit_total - income_tax
    surplus_reserve = (net_profit * SURPLUS_RESERVE_RATE) if net_profit > 0 else ZERO
    dividends = ZERO
    retained_change = net_profit - surplus_reserve - dividends

    rows = [
        ReportRow("1",  "一、营业收入",        "6001", revenue),
        ReportRow("2",  "  减:营业成本",      "6401", cogs),
        ReportRow("3",  "  减:销售费用",      "6601", selling),
        ReportRow("4",  "  减:管理费用",      "6602", admin),
        ReportRow("5",  "  减:财务费用",      "6603", finance_expense),
        ReportRow("6",  "二、营业利润",        None,   operating_profit),
        ReportRow("7",  "三、利润总额",        None,   profit_total),
        ReportRow("8",  "  减:所得税费用",    None,   income_tax,
                  note=f"按 {SMALL_BIZ_INCOME_TAX_RATE * 100}% 计 (小企业基础税率, 实际可享受减免)"),
        ReportRow("9",  "四、净利润",          None,   net_profit),
        ReportRow("10", "  加:年初未分配利润",None,   openings.get("4104", ZERO)),
        ReportRow("11", "五、可供分配的利润",  None,   net_profit + openings.get("4104", ZERO)),
        ReportRow("12", "  减:提取盈余公积",  None,   surplus_reserve,
                  note=f"按净利润 {SURPLUS_RESERVE_RATE * 100}% 法定提取"),
        ReportRow("13", "  减:应付投资人利润",None,   dividends),
        ReportRow("14", "六、未分配利润 (期末)", "4104", openings.get("4104", ZERO) + retained_change),
    ]

    return {
        "statement": "会企02 利润及利润分配表",
        "period": period,
        "currency": "CNY",
        "unit": "元",
        "rows": [r.to_dict() for r in rows],
        "net_profit_period": str(_q(net_profit)),
        "retained_earnings_change_period": str(_q(retained_change)),
        "totals": {
            "revenue": str(_q(revenue)),
            "operating_profit": str(_q(operating_profit)),
            "net_profit": str(_q(net_profit)),
        },
    }


async def compute_cashflow(period: str, session: AsyncSession) -> dict[str, Any]:
    """会企03 现金流量表. demo 阶段许多行无 entity 源, 走 OpeningBalance 或 0."""
    await ensure_chart_of_accounts_seeded(session)
    start, end = period_bounds(period)
    openings = await _opening_balances(session, period)

    # 经营活动
    cash_in_sales = await _cash_received_in_period(session, start, end)
    cash_in_other = openings.get("cf_op_other_in", ZERO)
    cash_out_purchase = await _po_amount_received_in_period(session, start, end)
    cash_out_wages = openings.get("cf_op_wages", ZERO)
    cash_out_tax = openings.get("cf_op_tax", ZERO)
    cash_out_other = openings.get("cf_op_other_out", ZERO)
    operating_in_total = cash_in_sales + cash_in_other
    operating_out_total = cash_out_purchase + cash_out_wages + cash_out_tax + cash_out_other
    operating_net = operating_in_total - operating_out_total

    # 投资活动
    fa_purchases = ZERO
    new_assets = (
        await session.execute(
            select(FixedAsset).where(
                FixedAsset.acquired_date >= start,
                FixedAsset.acquired_date <= end,
            )
        )
    ).scalars().all()
    for a in new_assets:
        fa_purchases += Decimal(a.original_cost)
    investing_net = ZERO - fa_purchases

    # 筹资活动 (无 entity 源, 走 opening)
    financing_in = openings.get("cf_fin_in", ZERO)
    financing_out = openings.get("cf_fin_out", ZERO)
    financing_net = financing_in - financing_out

    net_increase = operating_net + investing_net + financing_net
    cash_opening = openings.get("1001", ZERO) + openings.get("1002", ZERO)
    cash_ending = cash_opening + net_increase

    operating_rows = [
        ReportRow("op-1", "销售商品、提供劳务收到的现金",      None, cash_in_sales),
        ReportRow("op-2", "收到的其他与经营活动有关的现金",    None, cash_in_other),
        ReportRow("op-in", "  经营活动现金流入小计",            None, operating_in_total),
        ReportRow("op-3", "购买商品、接受劳务支付的现金",      None, cash_out_purchase),
        ReportRow("op-4", "支付给职工以及为职工支付的现金",    None, cash_out_wages),
        ReportRow("op-5", "支付的各项税费",                      None, cash_out_tax),
        ReportRow("op-6", "支付的其他与经营活动有关的现金",    None, cash_out_other),
        ReportRow("op-out", "  经营活动现金流出小计",            None, operating_out_total),
        ReportRow("op-net", "经营活动产生的现金流量净额",        None, operating_net),
    ]
    investing_rows = [
        ReportRow("inv-1", "购建固定资产、无形资产支付的现金",  None, fa_purchases),
        ReportRow("inv-net", "投资活动产生的现金流量净额",        None, investing_net),
    ]
    financing_rows = [
        ReportRow("fin-1", "吸收投资、借款收到的现金",             None, financing_in),
        ReportRow("fin-2", "偿还债务、分配股利支付的现金",         None, financing_out),
        ReportRow("fin-net", "筹资活动产生的现金流量净额",          None, financing_net),
    ]
    summary_rows = [
        ReportRow("sum-1", "五、现金及现金等价物净增加额",  None, net_increase),
        ReportRow("sum-2", "  加:期初现金及现金等价物余额",None, cash_opening),
        ReportRow("sum-3", "六、期末现金及现金等价物余额",  None, cash_ending),
    ]

    return {
        "statement": "会企03 现金流量表",
        "period": period,
        "currency": "CNY",
        "unit": "元",
        "operating": [r.to_dict() for r in operating_rows],
        "investing": [r.to_dict() for r in investing_rows],
        "financing": [r.to_dict() for r in financing_rows],
        "summary": [r.to_dict() for r in summary_rows],
        "totals": {
            "operating_net": str(_q(operating_net)),
            "investing_net": str(_q(investing_net)),
            "financing_net": str(_q(financing_net)),
            "net_increase": str(_q(net_increase)),
            "cash_ending": str(_q(cash_ending)),
        },
    }


# ============================== depreciation schedule ==================


async def compute_depreciation_schedule(period: str, session: AsyncSession) -> dict[str, Any]:
    """折旧台账. 每个 active fixed asset 一行, 含原值/累计折旧/本期折旧/净值."""
    _start, end = period_bounds(period)
    rows = (
        await session.execute(
            select(FixedAsset).where(
                FixedAsset.acquired_date <= end,
                FixedAsset.is_deleted == False,
            )
            .order_by(FixedAsset.asset_no)
        )
    ).scalars().all()

    out_rows: list[dict[str, Any]] = []
    total_original = ZERO
    total_accum = ZERO
    total_period = ZERO
    total_net = ZERO

    for asset in rows:
        if asset.status == FixedAssetStatus.disposed and asset.disposed_date and asset.disposed_date <= end:
            continue
        monthly = monthly_depreciation(asset)
        months_through = months_depreciated(asset, end)
        max_depreciable = Decimal(asset.original_cost) - Decimal(asset.salvage_value)
        accum_uncapped = monthly * months_through
        accum = min(accum_uncapped, max_depreciable)
        net_value = Decimal(asset.original_cost) - accum

        # 本期折旧 = 当月可计提
        if asset.acquired_date > end:
            period_dep = ZERO
        elif months_through == 0:
            period_dep = ZERO
        else:
            # 如果累计已封顶, 本期 = 0
            prev_months = max(0, months_through - 1)
            prev_accum = min(monthly * prev_months, max_depreciable)
            period_dep = accum - prev_accum
            if period_dep < 0:
                period_dep = ZERO

        out_rows.append({
            "asset_no": asset.asset_no,
            "name": asset.name,
            "category": asset.category.value,
            "acquired_date": asset.acquired_date.isoformat(),
            "original_cost": str(_q(asset.original_cost)),
            "salvage_value": str(_q(asset.salvage_value)),
            "useful_life_months": asset.useful_life_months,
            "monthly_depreciation": str(_q(monthly)),
            "months_depreciated_through_period": months_through,
            "accumulated_depreciation": str(_q(accum)),
            "current_period_depreciation": str(_q(period_dep)),
            "net_book_value": str(_q(net_value)),
            "status": asset.status.value,
        })
        total_original += Decimal(asset.original_cost)
        total_accum += accum
        total_period += period_dep
        total_net += net_value

    return {
        "period": period,
        "as_of_date": end.isoformat(),
        "currency": "CNY",
        "unit": "元",
        "rows": out_rows,
        "totals": {
            "original_cost": str(_q(total_original)),
            "accumulated_depreciation": str(_q(total_accum)),
            "current_period_depreciation": str(_q(total_period)),
            "net_book_value": str(_q(total_net)),
        },
    }


# ============================== cost breakdown =========================


async def compute_cost_breakdown(period: str, session: AsyncSession) -> dict[str, Any]:
    """成本拆分: 按 material 聚合本期出库金额 (qty × last_unit_cost) +
    按 supplier 聚合本期 PO 金额."""
    start, end = period_bounds(period)
    start_ts = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_ts = datetime.combine(end, time.max, tzinfo=timezone.utc)

    # 按物料 (基于 stock_movements outbound × last_unit_cost)
    out_rows = (
        await session.execute(
            select(
                StockMovement.material_id,
                func.sum(StockMovement.quantity).label("qty"),
            ).where(
                StockMovement.direction == StockMovementDirection.out,
                StockMovement.occurred_at >= start_ts,
                StockMovement.occurred_at <= end_ts,
            ).group_by(StockMovement.material_id)
        )
    ).all()
    materials = {}
    if out_rows:
        mids = [mid for mid, _ in out_rows]
        rows = (await session.execute(select(Material).where(Material.id.in_(mids)))).scalars().all()
        materials = {m.id: m for m in rows}
    by_material: list[dict[str, Any]] = []
    cogs_total = ZERO
    for mid, qty in out_rows:
        m = materials.get(mid)
        if m is None:
            continue
        amount = Decimal(qty) * Decimal(m.last_unit_cost)
        cogs_total += amount
        by_material.append({
            "material_id": str(m.id),
            "code": m.code,
            "name": m.name,
            "unit": m.unit,
            "consumed_qty": str(_q(qty)),
            "unit_cost": str(_q(m.last_unit_cost)),
            "cost_amount": str(_q(amount)),
        })
    by_material.sort(key=lambda r: Decimal(r["cost_amount"]), reverse=True)

    # 按供应商 (基于本期 received PO)
    sup_rows = (
        await session.execute(
            select(
                PurchaseOrder.supplier_id,
                func.sum(PurchaseOrder.total_amount).label("amount"),
                func.count(PurchaseOrder.id).label("po_count"),
            ).where(
                PurchaseOrder.received_at >= start_ts,
                PurchaseOrder.received_at <= end_ts,
            ).group_by(PurchaseOrder.supplier_id)
        )
    ).all()
    suppliers = {}
    if sup_rows:
        sids = [sid for sid, _, _ in sup_rows]
        rows = (await session.execute(select(Supplier).where(Supplier.id.in_(sids)))).scalars().all()
        suppliers = {s.id: s for s in rows}
    by_supplier: list[dict[str, Any]] = []
    procurement_total = ZERO
    for sid, amount, po_count in sup_rows:
        s = suppliers.get(sid)
        if s is None:
            continue
        procurement_total += Decimal(amount or 0)
        by_supplier.append({
            "supplier_id": str(s.id),
            "name": s.name,
            "po_count": int(po_count),
            "received_amount": str(_q(amount or 0)),
        })
    by_supplier.sort(key=lambda r: Decimal(r["received_amount"]), reverse=True)

    return {
        "period": period,
        "currency": "CNY",
        "unit": "元",
        "by_material": by_material,
        "by_supplier": by_supplier,
        "totals": {
            "cogs_from_material_consumption": str(_q(cogs_total)),
            "procurement_received": str(_q(procurement_total)),
        },
    }


# ============================== 进销存台账 (inventory ledger) ============


async def compute_inventory_ledger(
    *, material_id, period: str, session: AsyncSession,
) -> dict[str, Any]:
    """进销存台账: 期初 / 入 / 出 / 期末 + 期内流水明细."""
    import uuid as _uuid
    if not isinstance(material_id, _uuid.UUID):
        material_id = _uuid.UUID(str(material_id))
    start, end = period_bounds(period)
    start_ts = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_ts = datetime.combine(end, time.max, tzinfo=timezone.utc)

    material = await session.get(Material, material_id)
    if material is None:
        raise ValueError(f"material {material_id} not found")

    # opening = balance_after of last movement strictly before start_ts; if none, 0.
    prior = (
        await session.execute(
            select(StockMovement).where(
                StockMovement.material_id == material_id,
                StockMovement.occurred_at < start_ts,
            ).order_by(StockMovement.occurred_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    opening_balance = Decimal(prior.balance_after) if prior else ZERO

    period_movements = (
        await session.execute(
            select(StockMovement).where(
                StockMovement.material_id == material_id,
                StockMovement.occurred_at >= start_ts,
                StockMovement.occurred_at <= end_ts,
            ).order_by(StockMovement.occurred_at)
        )
    ).scalars().all()

    in_qty = ZERO
    out_qty = ZERO
    movements_out: list[dict[str, Any]] = []
    for m in period_movements:
        if m.direction == StockMovementDirection.in_:
            in_qty += Decimal(m.quantity)
        elif m.direction == StockMovementDirection.out:
            out_qty += Decimal(m.quantity)
        movements_out.append({
            "id": str(m.id),
            "occurred_at": m.occurred_at.isoformat(),
            "direction": m.direction.value,
            "quantity": str(_q(m.quantity)),
            "balance_after": str(_q(m.balance_after)),
            "reference_type": m.reference_type.value,
            "reference_id": str(m.reference_id) if m.reference_id else None,
            "source_ref": m.source_ref,
        })

    ending_balance = opening_balance + in_qty - out_qty

    return {
        "material_id": str(material.id),
        "code": material.code,
        "name": material.name,
        "unit": material.unit,
        "period": period,
        "opening_balance": str(_q(opening_balance)),
        "in_qty": str(_q(in_qty)),
        "out_qty": str(_q(out_qty)),
        "ending_balance": str(_q(ending_balance)),
        "unit_cost": str(_q(material.last_unit_cost)),
        "ending_value": str(_q(ending_balance * Decimal(material.last_unit_cost))),
        "movements": movements_out,
    }
