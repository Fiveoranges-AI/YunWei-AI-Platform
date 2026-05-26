"""锦泰财务模块 — 会企01/02/03 三表 + 固定资产折旧.

最小可用的中国小企业会计准则映射:
  * ``finance_chart_of_accounts`` — 科目主表(账号代码 / 名称 / 类别 /
    报表归属 / 报表行键). demo 给一组 seed 常用科目;后续业务方可扩.
  * ``finance_period_opening_balances`` — 每个会计期间的科目期初余额
    (人工录入). 期末 = 期初 + 自动聚合的本期发生额.
  * ``finance_fixed_assets`` — 固定资产卡片. 直线折旧:
    monthly = (original_cost − salvage_value) / useful_life_months.

不建凭证表 (journal entries):demo 阶段所有发生额从底层 entities
(invoices / payments / payables / stock_movements) 聚合.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Date,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from yunwei_win.db import Base
from yunwei_win.models._base import TimestampMixin
from yunwei_win.models._mixins import (
    HumanVerificationMixin,
    OwnershipMixin,
    RowAuditMixin,
    RowProvenanceMixin,
    SoftDeleteMixin,
)


# ============================== enums =====================================


class AccountClass(str, enum.Enum):
    asset = "asset"
    liability = "liability"
    equity = "equity"
    revenue = "revenue"
    expense = "expense"


class StatementSection(str, enum.Enum):
    balance_sheet = "balance_sheet"     # 会企01 资产负债表
    pnl = "pnl"                         # 会企02 利润及利润分配表
    cashflow = "cashflow"               # 会企03 现金流量表


class NormalBalance(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class FixedAssetCategory(str, enum.Enum):
    machinery = "machinery"           # 机器设备
    office = "office"                 # 办公设备
    vehicle = "vehicle"               # 运输工具
    building = "building"             # 房屋建筑物
    other = "other"


class FixedAssetStatus(str, enum.Enum):
    active = "active"
    disposed = "disposed"


# ============================== tables ====================================


class ChartOfAccount(
    Base,
    TimestampMixin,
    RowAuditMixin,
):
    """会计科目主表. 简化版,只装报表用的字段.

    ``report_line_key`` 是稳定字符串(snake_case),会企报表 service 按这个 key
    挑出对应科目并聚合;比如 ``accounts_payable`` 在会企01 资产负债表 ``流动负债``
    分类下出 ``应付账款`` 行.
    """

    __tablename__ = "finance_chart_of_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_class: Mapped[AccountClass] = mapped_column(
        SQLEnum(AccountClass, name="finance_account_class"), nullable=False, index=True,
    )
    statement: Mapped[StatementSection] = mapped_column(
        SQLEnum(StatementSection, name="finance_statement_section"), nullable=False, index=True,
    )
    report_line_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    normal_balance: Mapped[NormalBalance] = mapped_column(
        SQLEnum(NormalBalance, name="finance_normal_balance"), nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PeriodOpeningBalance(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
):
    """每期每科目的期初余额(人工录入或上期结转).

    ``period`` 用 ``YYYY-MM`` 字符串. ``opening_amount`` 单位元.
    报表 service 默认从这里取期初,叠加聚合发生额得期末.
    """

    __tablename__ = "finance_period_opening_balances"
    __table_args__ = (
        UniqueConstraint("period", "account_code", name="uq_period_opening_balance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    account_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FixedAsset(
    Base,
    TimestampMixin,
    RowProvenanceMixin,
    HumanVerificationMixin,
    RowAuditMixin,
    OwnershipMixin,
    SoftDeleteMixin,
):
    """固定资产卡片. 直线折旧(``计提折旧 = (原值 − 残值) / 月数``)."""

    __tablename__ = "finance_fixed_assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[FixedAssetCategory] = mapped_column(
        SQLEnum(FixedAssetCategory, name="finance_fixed_asset_category"),
        nullable=False, default=FixedAssetCategory.other,
    )
    acquired_date: Mapped[date] = mapped_column(Date, nullable=False)
    original_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    useful_life_months: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[FixedAssetStatus] = mapped_column(
        SQLEnum(FixedAssetStatus, name="finance_fixed_asset_status"),
        nullable=False, default=FixedAssetStatus.active,
    )
    disposed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ============================== seed data ===============================


# 最小可用科目表 (demo + 锦泰主线必备 ~15 个科目). 业务方扩展时往这里加.
# 字段: (account_code, account_name, account_class, statement, report_line_key, normal_balance, sort_order)
DEFAULT_CHART_OF_ACCOUNTS: list[tuple] = [
    # 资产 (balance_sheet, debit)
    ("1001", "库存现金",           AccountClass.asset,     StatementSection.balance_sheet, "monetary_funds",         NormalBalance.debit,  1),
    ("1002", "银行存款",           AccountClass.asset,     StatementSection.balance_sheet, "monetary_funds",         NormalBalance.debit,  2),
    ("1122", "应收账款",           AccountClass.asset,     StatementSection.balance_sheet, "accounts_receivable",    NormalBalance.debit,  3),
    ("1405", "库存商品",           AccountClass.asset,     StatementSection.balance_sheet, "inventory",              NormalBalance.debit,  4),
    ("1601", "固定资产",           AccountClass.asset,     StatementSection.balance_sheet, "fixed_assets",           NormalBalance.debit,  5),
    ("1602", "累计折旧",           AccountClass.asset,     StatementSection.balance_sheet, "accumulated_depreciation", NormalBalance.credit, 6),
    # 负债 (balance_sheet, credit)
    ("2001", "短期借款",           AccountClass.liability, StatementSection.balance_sheet, "short_term_loan",        NormalBalance.credit, 10),
    ("2202", "应付账款",           AccountClass.liability, StatementSection.balance_sheet, "accounts_payable",       NormalBalance.credit, 11),
    # 所有者权益 (balance_sheet, credit)
    ("4001", "实收资本",           AccountClass.equity,    StatementSection.balance_sheet, "paid_in_capital",        NormalBalance.credit, 20),
    ("4104", "未分配利润",         AccountClass.equity,    StatementSection.balance_sheet, "retained_earnings",      NormalBalance.credit, 21),
    # 损益 (pnl)
    ("6001", "主营业务收入",       AccountClass.revenue,   StatementSection.pnl,           "operating_revenue",      NormalBalance.credit, 30),
    ("6401", "主营业务成本",       AccountClass.expense,   StatementSection.pnl,           "operating_cost",         NormalBalance.debit,  31),
    ("6601", "销售费用",           AccountClass.expense,   StatementSection.pnl,           "selling_expense",        NormalBalance.debit,  32),
    ("6602", "管理费用",           AccountClass.expense,   StatementSection.pnl,           "admin_expense",          NormalBalance.debit,  33),
    ("6603", "财务费用",           AccountClass.expense,   StatementSection.pnl,           "finance_expense",        NormalBalance.debit,  34),
]
