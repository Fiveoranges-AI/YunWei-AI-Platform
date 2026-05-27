"""DemoMockProvider — 当 ANTHROPIC_API_KEY 缺失时的 fallback provider.

锦泰 demo 阶段, 客户可能在无 LLM key 的环境跑前端 backend mode 演示
(开发机 / 客户笔记本 / CI). MockProvider (tests 用) 需要测试代码硬塞 result,
不适合 ad-hoc demo. 此 DemoMockProvider 看 filename + content size 派生 seed,
出 "看着像真的" IssueVoucher / Material / Supplier 候选, 让 demo 接得上 round 4
主线 (confirm → 扣库 → alert → auto-draft PR → ...).

ActionLog 会标 provider_name='demo-mock' 让审计透明 — 客户能区分真 LLM 抽取
和 demo mock.

Deterministic: 同一文件每次 demo 出同一候选(seed=md5(filename+size)),便于
reviewer 复现.
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import date, datetime
from pathlib import Path

from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ExtractionProvider,
    ProviderEntity,
    ProviderField,
    ProviderResult,
)


logger = logging.getLogger(__name__)


# 来自 round 4 demo 主线常量
_WORKSHOPS = ["成型车间", "烧结车间", "包装车间"]
_APPLICANTS = ["张师傅", "李师傅", "王师傅", "刘工"]
_MATERIALS = [
    ("α 氧化铝粉", "CT3000SG · 5N 级"),
    ("莫来石骨料", "3-5 mm · M70"),
    ("电熔白刚玉 W18", "刚玉骨料 · 0.5-2 mm"),
    ("磷酸二氢铝", "工业级 ≥ 99%"),
]
_PURPOSES = [
    "BL-2026-018 容百二供 NCM 高镍配料",
    "ZC-2026-015 锂电承烧板 NCM811",
    "MLCC-2026-007 多层陶瓷电容基板",
]


class DemoMockProvider:
    """Implements ExtractionProvider Protocol."""

    name = "demo-mock"

    def __init__(self, seed_extra: str = "") -> None:
        self._seed_extra = seed_extra

    async def extract(self, payload: ExtractionPayload) -> ProviderResult:
        seed = _derive_seed(payload.filename, payload.markdown, self._seed_extra)
        rng = random.Random(seed)

        # 按 filename 关键字 + extension 决定生成什么实体
        lower = payload.filename.lower()
        if any(k in payload.filename for k in ("合同", "采购")):
            entities = [_gen_purchase_requisition(rng, payload.filename)]
        elif any(k in lower for k in (".xlsx", ".xls", "对账")):
            # Excel 通常是出库台账 / 对账表 → 出 IssueVoucher
            entities = [_gen_issue_voucher(rng, payload.filename)]
        else:
            entities = [_gen_issue_voucher(rng, payload.filename)]

        result = ProviderResult(
            entities=entities,
            relationships=[],
            warnings=[
                "demo-mock provider used (no LLM key configured); fields derived "
                "from filename hash + size — deterministic but not real AI extraction"
            ],
            provider_name="demo-mock",
        )
        logger.info(
            "demo_mock_provider.extract filename=%s seed=%s entities=%d",
            payload.filename, seed[:8], len(entities),
        )
        return result


def _derive_seed(filename: str, markdown: str, extra: str = "") -> str:
    h = hashlib.md5()
    h.update(filename.encode("utf-8"))
    h.update(str(len(markdown)).encode("utf-8"))
    h.update(extra.encode("utf-8"))
    return h.hexdigest()


def _gen_issue_voucher(rng: random.Random, filename: str) -> ProviderEntity:
    """IssueVoucher entity. Material_id 留空 (前端选 / 后端按 name 解析)."""
    voucher_no_seq = rng.randint(1, 9999)
    workshop = rng.choice(_WORKSHOPS)
    applicant = rng.choice(_APPLICANTS)
    material_name, material_spec = rng.choice(_MATERIALS)
    qty = rng.choice([400, 500, 600, 800, 1000, 1200, 1500])
    purpose = rng.choice(_PURPOSES)
    today = date.today()
    return ProviderEntity(
        entity_type="IssueVoucher",
        temp_id="iv-1",
        fields=[
            ProviderField(
                name="voucher_no",
                value=f"BL-{today.year}-{voucher_no_seq:03d}",
                confidence=_jitter(rng, 0.96),
                source_excerpt=f"领料单号: BL-{today.year}-{voucher_no_seq:03d}",
                source_ref_id=f"chunk-1",
            ),
            ProviderField(
                name="workshop", value=workshop,
                confidence=_jitter(rng, 0.97),
                source_excerpt=f"申请车间: {workshop}",
                source_ref_id="chunk-2",
            ),
            ProviderField(
                name="applicant", value=applicant,
                confidence=_jitter(rng, 0.93),
                source_excerpt=f"领用人: {applicant}",
                source_ref_id="chunk-3",
            ),
            # material_name 是 hint, 前端 / 后端 entity resolution 拿来匹配 Material.id
            ProviderField(
                name="material_name_hint", value=material_name,
                confidence=_jitter(rng, 0.91),
                source_excerpt=f"物料: {material_name} ({material_spec})",
                source_ref_id="chunk-4",
            ),
            ProviderField(
                name="quantity", value=str(qty),
                confidence=_jitter(rng, 0.94),
                source_excerpt=f"数量: {qty} kg",
                source_ref_id="chunk-5",
            ),
            ProviderField(
                name="unit", value="kg",
                confidence=_jitter(rng, 0.99),
                source_excerpt="单位: kg",
                source_ref_id="chunk-5",
            ),
            ProviderField(
                name="purpose", value=purpose,
                confidence=_jitter(rng, 0.84),
                source_excerpt=f"用途: {purpose}",
                source_ref_id="chunk-6",
            ),
            ProviderField(
                name="issued_date", value=today.isoformat(),
                confidence=_jitter(rng, 0.92),
                source_excerpt=f"领用日期: {today.isoformat()}",
                source_ref_id="chunk-7",
            ),
        ],
    )


def _gen_purchase_requisition(rng: random.Random, filename: str) -> ProviderEntity:
    """PurchaseRequisition entity (合同 / 采购单 → PR head)."""
    pr_no = f"PR-{date.today().year}-{rng.randint(100, 999):03d}"
    workshop = rng.choice(_WORKSHOPS)
    applicant = rng.choice(_APPLICANTS)
    return ProviderEntity(
        entity_type="PurchaseRequisition",
        temp_id="pr-1",
        fields=[
            ProviderField(
                name="pr_no", value=pr_no,
                confidence=_jitter(rng, 0.95),
                source_excerpt=f"申购单号: {pr_no}",
                source_ref_id="chunk-1",
            ),
            ProviderField(
                name="dept", value=workshop,
                confidence=_jitter(rng, 0.93),
                source_excerpt=f"申购部门: {workshop}",
                source_ref_id="chunk-2",
            ),
            ProviderField(
                name="applicant", value=applicant,
                confidence=_jitter(rng, 0.91),
                source_excerpt=f"申请人: {applicant}",
                source_ref_id="chunk-3",
            ),
            ProviderField(
                name="apply_date", value=date.today().isoformat(),
                confidence=_jitter(rng, 0.97),
                source_excerpt=f"申购日期: {date.today().isoformat()}",
                source_ref_id="chunk-4",
            ),
        ],
    )


def _jitter(rng: random.Random, base: float) -> float:
    """加 ±2% 抖动,模拟真实 LLM 置信度的细微差异 (e.g. 0.93→0.928)."""
    delta = (rng.random() - 0.5) * 0.04
    v = base + delta
    return round(max(0.5, min(0.99, v)), 3)


# Type-check that the class satisfies the Protocol
_: ExtractionProvider = DemoMockProvider()  # pragma: no cover
