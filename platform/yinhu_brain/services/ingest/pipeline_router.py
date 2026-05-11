from __future__ import annotations

import re
from typing import Literal

from yinhu_brain.services.ingest.landingai_schemas.registry import PipelineName
from yinhu_brain.services.ingest.unified_schemas import PipelineRoutePlan, PipelineSelection


_RULES: dict[PipelineName, list[tuple[re.Pattern[str], float]]] = {
    "identity": [
        (re.compile(r"(甲方|买方|客户|联系人|电话|手机|邮箱|统一社会信用代码|有限公司|股份|集团)"), 0.35),
        (re.compile(r"1[3-9]\d{9}"), 0.35),
        (re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+"), 0.35),
    ],
    "contract_order": [
        (re.compile(r"(合同编号|合同号|订单号|采购订单|销售订单|报价单|\bPO\b)", re.I), 0.35),
        (re.compile(r"(总金额|单价|数量|付款方式|预付|尾款|交货|交期)"), 0.35),
        (re.compile(r"(甲方|乙方|供方|需方)"), 0.2),
    ],
    "finance": [
        (re.compile(r"(发票号码|发票代码|增值税|价税合计|开票日期|对账单|回款|收款|银行流水)"), 0.45),
        (re.compile(r"(开户行|账号|交易流水|未付金额|应收|账期)"), 0.3),
    ],
    "logistics": [
        (re.compile(r"(送货单|发货单|签收|物流|运单|快递|仓库|库存|批次|到货|出库|入库)"), 0.45),
        (re.compile(r"(收货人|签收人|运输|承运|库存数量)"), 0.25),
    ],
    "manufacturing_requirement": [
        (re.compile(r"(规格书|技术要求|技术参数|材质|型号|牌号|质量标准|验收标准|包装要求|安全库存|MOQ|最小起订量)"), 0.45),
        (re.compile(r"(月用量|交期要求|提前期|备货|生产任务)"), 0.25),
    ],
    "commitment_task_risk": [
        (re.compile(r"(承诺|答应|确认|跟进|催|安排|下周|本周|月底|投诉|不满|质量问题|延期|风险|偏好|决策人)"), 0.35),
        (re.compile(r"([:：]\d\d|微信|聊天|消息|会议纪要|邮件)"), 0.25),
    ],
}

# Activation thresholds tuned so each pipeline can fire on a single strong
# pattern hit. ``contract_order``/``logistics``/``manufacturing_requirement``
# stay slightly higher to avoid false positives on documents that only mention
# one peripheral keyword.
_THRESHOLDS: dict[PipelineName, float] = {
    "identity": 0.35,
    "contract_order": 0.55,
    "finance": 0.45,
    "logistics": 0.55,
    "manufacturing_requirement": 0.55,
    "commitment_task_risk": 0.35,
}


def _score(text: str, patterns: list[tuple[re.Pattern[str], float]]) -> float:
    score = 0.0
    for pattern, weight in patterns:
        if pattern.search(text):
            score += weight
    return min(round(score, 3), 1.0)


async def route_pipelines(
    *,
    markdown: str,
    modality: Literal["image", "pdf", "office", "text"],
    source_hint: Literal["file", "camera", "pasted_text"],
) -> PipelineRoutePlan:
    text = markdown or ""
    scores = {name: _score(text, rules) for name, rules in _RULES.items()}

    selected = [
        PipelineSelection(name=name, confidence=score, reason="heuristic match")
        for name, score in scores.items()
        if score >= _THRESHOLDS[name]
    ]

    if any(x.name != "identity" for x in selected) and scores["identity"] >= 0.25:
        if not any(x.name == "identity" for x in selected):
            selected.insert(
                0,
                PipelineSelection(
                    name="identity",
                    confidence=scores["identity"],
                    reason="customer identity likely present alongside business evidence",
                ),
            )

    selected.sort(key=lambda x: (x.name != "identity", -x.confidence, x.name))
    selected = selected[:3]

    if not selected and text.strip():
        selected = [
            PipelineSelection(
                name="commitment_task_risk",
                confidence=0.3,
                reason="fallback memory extraction for unclassified customer evidence",
            )
        ]

    non_identity = [x for x in selected if x.name != "identity"]
    primary = non_identity[0].name if non_identity else (selected[0].name if selected else None)

    rejected = [
        PipelineSelection(name=name, confidence=score, reason="below activation threshold")
        for name, score in scores.items()
        if name not in {x.name for x in selected}
    ]

    return PipelineRoutePlan(
        primary_pipeline=primary,
        selected_pipelines=selected,
        rejected_pipelines=rejected,
        document_summary=text.strip()[:300],
        needs_human_review=len(selected) > 2 or any(x.confidence < 0.6 for x in selected),
    )
