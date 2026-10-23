"""光天 demo 种子数据 — 复刻前端 ``screens/guangtian/data.ts`` 的 8 个 SKU +
开账库存 + 3 张客户订单, 让 backend 模式打开就有真数据.

幂等: 已有 SKU 则跳过. 由 dev launcher 启动钩子调用, 或测试直接调用.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from yunwei_win.models import (
    GuangtianCustomerOrder,
    GuangtianCustomerOrderItem,
    GuangtianMovementOp,
    GuangtianMovementRefType,
    GuangtianOrderLevel,
    GuangtianSku,
    GuangtianSkuKind,
    GuangtianStockMovement,
    GuangtianStockStatus,
)

SEED_ACTOR = "seed"
_SEED_AT = datetime(2026, 5, 19, 9, 0, tzinfo=timezone.utc)

# code, name, spec, category, unit, location, stock, safety, kind, anomaly
_SKUS: list[tuple] = [
    ("JT-HLZ-230-114-65", "高铝砖（标准型）", "230×114×65 mm", "高铝砖", "块", "A-03", 4280, 2000, GuangtianSkuKind.finished, False),
    ("JT-MLS-M70", "莫来石砖", "M70 等级 230×114×65", "莫来石砖", "块", "A-05", 320, 800, GuangtianSkuKind.finished, False),
    ("JT-JZL-JC16", "浇注料", "JC-16 标准型 25kg/袋", "浇注料", "袋", "B-02", 0, 200, GuangtianSkuKind.finished, False),
    ("JT-GZB-AL80", "刚玉砖", "AL80 等级 230×114×65", "刚玉砖", "块", "C-01", 1850, 1500, GuangtianSkuKind.finished, True),
    ("JT-HLZ-T3-150", "高铝砖（T3 异型）", "T3 异型 150×75 mm", "高铝砖", "块", "A-04", 6800, 1500, GuangtianSkuKind.finished, False),
    ("JT-MLS-MS65", "莫来石轻质砖", "MS-65 轻质保温", "莫来石砖", "块", "A-06", 95, 0, GuangtianSkuKind.finished, False),
    ("JT-JZL-JC18-LR", "低水泥浇注料", "JC-18 低水泥 25kg/袋", "浇注料", "袋", "B-03", 540, 300, GuangtianSkuKind.finished, False),
    ("JT-GZB-AL90", "高纯刚玉砖", "AL90 等级 230×114×65", "刚玉砖", "块", "C-02", 78, 200, GuangtianSkuKind.finished, False),
]

# order_no, customer, delivery (note), level, total_value, ai_suggestion,
#   items=[(sku_code, needed)]
_ORDERS: list[tuple] = [
    (
        "SO-20260519-001", "江苏宏泰工程有限公司", date(2026, 5, 22), "周五，2 天后",
        GuangtianOrderLevel.urgent, Decimal("38600"),
        "JC-16 已缺货、M70 低库存，建议立即排产或与客户协商分批交付",
        [("JT-JZL-JC16", 200), ("JT-MLS-M70", 600)],
    ),
    (
        "SO-20260519-002", "江苏宏泰工程有限公司", date(2026, 5, 24), "周日",
        GuangtianOrderLevel.low, Decimal("6200"), "库存充足，可全发",
        [("JT-JZL-JC18-LR", 300)],
    ),
    (
        "SO-20260519-003", "常州新材科技有限公司", date(2026, 5, 23), "周六，3 天后",
        GuangtianOrderLevel.high, Decimal("62400"),
        "AL90 缺口 72，建议补产；高铝砖与 AL80 可发",
        [("JT-GZB-AL90", 150), ("JT-HLZ-230-114-65", 1000), ("JT-GZB-AL80", 500)],
    ),
]


async def seed_guangtian_demo(engine: AsyncEngine) -> bool:
    """写入 demo 种子. 返回 True=已写入, False=已存在跳过."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            existing = (await session.execute(select(GuangtianSku.id).limit(1))).first()
            if existing is not None:
                return False
            code_to_id: dict[str, GuangtianSku] = {}
            for (code, name, spec, cat, unit, loc, stock, safety, kind, anomaly) in _SKUS:
                bal = Decimal(stock)
                sku = GuangtianSku(
                    code=code, name=name, spec=spec, category=cat, unit=unit,
                    location=loc, kind=kind, safety_stock=Decimal(safety),
                    last_balance=bal,
                    status_override=GuangtianStockStatus.anomaly if anomaly else None,
                    last_in_at=date(2026, 5, 17),
                    human_verified=True, verified_by=SEED_ACTOR,
                    created_by=SEED_ACTOR, updated_by=SEED_ACTOR,
                )
                session.add(sku)
                await session.flush()
                code_to_id[code] = sku
                if bal > 0:
                    session.add(GuangtianStockMovement(
                        sku_id=sku.id, op=GuangtianMovementOp.inbound, quantity=bal,
                        balance_before=Decimal("0"), balance_after=bal,
                        reference_type=GuangtianMovementRefType.opening,
                        reference_no=f"OPEN-{code}", operator=SEED_ACTOR,
                        occurred_at=_SEED_AT, confidence=100, confirmed=True,
                        note="期初建账", source_type="opening", extracted_by="seed",
                        created_by=SEED_ACTOR, updated_by=SEED_ACTOR,
                    ))
            for (ono, cust, ddate, dnote, level, value, ai_sugg, items) in _ORDERS:
                order = GuangtianCustomerOrder(
                    order_no=ono, customer=cust, delivery_date=ddate, delivery_note=dnote,
                    level=level, total_value=value, ai_suggestion=ai_sugg,
                    human_verified=True, verified_by=SEED_ACTOR,
                    created_by=SEED_ACTOR, updated_by=SEED_ACTOR,
                )
                session.add(order)
                await session.flush()
                for i, (sku_code, needed) in enumerate(items):
                    sku = code_to_id.get(sku_code)
                    session.add(GuangtianCustomerOrderItem(
                        order_id=order.id, sku_id=sku.id if sku else None,
                        needed=Decimal(needed), unit=sku.unit if sku else None,
                        sort_order=i, human_verified=True, verified_by=SEED_ACTOR,
                        created_by=SEED_ACTOR, updated_by=SEED_ACTOR,
                    ))
        return True
