"""光天 · 老板问数 — 自然语言查询 (DemoMock NLU over real data).

P2 决策 D3: 先用确定性规则匹配 + 真实库存数据回答, 返回前端 ``AnswerBlock`` 形状
(conclusion / evidence / risk / actions / links). 跑通端到端不依赖 LLM / API key.
后续可换 Claude (529 重试 ≤3), 接口不变.

意图识别用关键词命中, 数据全部来自当前 tenant 真实表 — 不是写死的 mock 答案.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    GuangtianReplenishment,
    GuangtianReplenishStatus,
    GuangtianSku,
    GuangtianStockAlert,
)
from yunwei_win.services.guangtian import open_order_gap_by_sku


def _block(conclusion: str, evidence: list[dict], risk: str, actions: list[str], links: list[dict]) -> dict:
    return {
        "conclusion": conclusion,
        "evidence": evidence,
        "risk": risk,
        "actions": actions,
        "links": links,
        "engine": "demo-mock",  # 标注非 LLM, 诚实
    }


async def answer_inventory_question(*, session: AsyncSession, question: str) -> dict:
    q = (question or "").strip()
    skus = (await session.execute(select(GuangtianSku).where(GuangtianSku.is_deleted.is_(False)))).scalars().all()
    gaps = await open_order_gap_by_sku(session)

    low = [s for s in skus if Decimal(s.safety_stock) > 0 and 0 < Decimal(s.last_balance) < Decimal(s.safety_stock)]
    out = [s for s in skus if Decimal(s.last_balance) <= 0]

    # 意图: 明天优先生产什么 / 优先排产
    if any(k in q for k in ("优先生产", "优先排产", "先生产", "排产", "明天")):
        # 优先级: 已缺货 > 有订单缺口 > 低库存
        ranked = sorted(
            [s for s in skus if s.id in gaps or s in out or s in low],
            key=lambda s: (
                0 if s in out else (1 if s.id in gaps else 2),
                -float(gaps.get(s.id, 0)),
            ),
        )[:5]
        if not ranked:
            return _block("当前无缺货/缺口 SKU, 无需紧急排产", [], "info", ["维持现有计划"], [])
        top = ranked[0]
        gap = gaps.get(top.id, Decimal("0"))
        return _block(
            f"建议优先生产 {top.name}({top.code}): 现库存 {top.last_balance}, "
            f"安全线 {top.safety_stock}" + (f", 未满足订单缺口 {gap}" if gap > 0 else ""),
            [
                {"label": "已缺货 SKU", "count": len(out)},
                {"label": "有订单缺口 SKU", "count": len(gaps)},
                {"label": "低库存 SKU", "count": len(low)},
            ],
            "high" if (out or gaps) else "medium",
            [f"优先排产 {top.code} {top.name}", "去 AI 补产建议生成补产单"],
            [{"label": "查看补产建议", "target": "replenish"}, {"label": "查看缺货预警", "target": "shortage"}],
        )

    # 意图: 缺货 / 已缺货
    if any(k in q for k in ("缺货", "断货", "没货", "缺口")):
        names = "、".join(f"{s.code}" for s in out[:5]) or "无"
        return _block(
            f"当前已缺货 {len(out)} 个 SKU: {names}; 另有 {len(gaps)} 个 SKU 存在未满足订单缺口",
            [{"label": "已缺货", "count": len(out)}, {"label": "订单缺口", "count": len(gaps)}],
            "urgent" if out else ("high" if gaps else "info"),
            ["生成补产建议", "联系客户协商交期"],
            [{"label": "缺货预警", "target": "shortage"}, {"label": "补产建议", "target": "replenish"}],
        )

    # 意图: 低库存 / 安全库存
    if any(k in q for k in ("低库存", "安全库存", "预警")):
        names = "、".join(f"{s.code}({s.last_balance}/{s.safety_stock})" for s in low[:5]) or "无"
        return _block(
            f"低于安全库存的 SKU 共 {len(low)} 个: {names}",
            [{"label": "低库存", "count": len(low)}, {"label": "已缺货", "count": len(out)}],
            "high" if low else "info",
            ["生成补产建议补至安全线"],
            [{"label": "SKU 台账", "target": "sku"}, {"label": "补产建议", "target": "replenish"}],
        )

    # 意图: 补产建议
    if any(k in q for k in ("补产", "补货", "生产计划")):
        pending = (
            await session.execute(
                select(GuangtianReplenishment).where(
                    GuangtianReplenishment.status == GuangtianReplenishStatus.suggested
                )
            )
        ).scalars().all()
        total = sum((Decimal(r.suggest_qty) for r in pending), Decimal("0"))
        return _block(
            f"当前有 {len(pending)} 条待处理补产建议, 合计建议补产 {total} 单位",
            [{"label": "待处理建议", "count": len(pending)}],
            "high" if pending else "info",
            ["逐条采纳并挂工艺组", "或一键生成本周补产计划"],
            [{"label": "AI 补产建议", "target": "replenish"}],
        )

    # fallback: 总览
    open_alerts = (
        await session.execute(select(GuangtianStockAlert).where(GuangtianStockAlert.resolved_at.is_(None)))
    ).scalars().all()
    return _block(
        f"库存总览: 共 {len(skus)} 个 SKU 在册, 低库存 {len(low)} 个, 已缺货 {len(out)} 个, "
        f"未解除预警 {len(open_alerts)} 条",
        [
            {"label": "SKU 总数", "count": len(skus)},
            {"label": "低库存", "count": len(low)},
            {"label": "已缺货", "count": len(out)},
            {"label": "未解除预警", "count": len(open_alerts)},
        ],
        "medium" if (low or out) else "info",
        ["可问: 明天优先生产什么 / 哪些缺货 / 补产建议"],
        [{"label": "工作台", "target": "report"}],
    )
