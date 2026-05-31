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

# Round 13: Contract demo. Downstream customers are锂电/磁材/MLCC clients
# (匹配 round 4 jintai 业务场景), 金额是该客户类型常见单合同区间.
_CONTRACT_CUSTOMERS = [
    ("容百新能源科技股份有限公司", "300661"),
    ("横店集团东磁股份有限公司", "002056"),
    ("宁波东睦科技股份有限公司", "600114"),
    ("当升科技股份有限公司", "300073"),
]
_CONTRACT_PRODUCTS = [
    "刚玉莫来石承烧板 330×330×16mm",
    "氧化铝匣钵 300×220×100mm",
    "高纯氧化铝匣钵 (烧结 LiFePO4)",
    "镁橄榄石匣钵 200×200×80mm",
]


class DemoMockProvider:
    """Implements ExtractionProvider Protocol."""

    name = "demo-mock"

    def __init__(self, seed_extra: str = "") -> None:
        self._seed_extra = seed_extra

    async def extract(self, payload: ExtractionPayload) -> ProviderResult:
        seed = _derive_seed(payload.filename, payload.markdown, self._seed_extra)
        rng = random.Random(seed)

        # 按 filename 关键字 + extension 决定生成什么实体. Round 13: "合同"
        # 关键字现在路由到 Contract+Customer (之前错误地走 PR — 合同实体确实存在
        # 但 DemoMockProvider 漏了这条分支); "采购" 单独 → PR.
        lower = payload.filename.lower()
        entities: list[ProviderEntity] = []
        relationships: list[dict] = []
        if "合同" in payload.filename:
            customer = _gen_customer(rng, payload.filename)
            contract = _gen_contract(rng, payload.filename)
            entities = [customer, contract]
            relationships = [{
                "from_temp_id": customer.temp_id,
                "to_temp_id": contract.temp_id,
                "type": "Customer-has-Contract",
            }]
        elif "采购" in payload.filename:
            entities = [_gen_purchase_requisition(rng, payload.filename)]
        elif any(k in lower for k in (".xlsx", ".xls", "对账")):
            # Excel 通常是出库台账 / 对账表 → 出 IssueVoucher
            entities = [_gen_issue_voucher(rng, payload.filename)]
        else:
            entities = [_gen_issue_voucher(rng, payload.filename)]

        result = ProviderResult(
            entities=entities,
            relationships=relationships,
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


def _gen_customer(rng: random.Random, filename: str) -> ProviderEntity:
    """Customer entity for the contract counterparty. Round 13.

    The 4-char filename-hash suffix in `full_name` keeps demo re-uploads
    of similar contracts from colliding on the customers.full_name unique
    index (锦泰 customer demo data is sparse + uniqueness-protected).
    """
    name_zh, stock_code = rng.choice(_CONTRACT_CUSTOMERS)
    # Deterministic hash slice from filename so the SAME demo file always
    # produces the same Customer (re-uploads still idempotent for reviewers).
    suffix = hashlib.md5(filename.encode("utf-8")).hexdigest()[:4]
    full_name = f"{name_zh}-{suffix}"
    return ProviderEntity(
        entity_type="Customer",
        temp_id="customer-1",
        fields=[
            ProviderField(
                name="full_name", value=full_name,
                confidence=_jitter(rng, 0.96),
                source_excerpt=f"甲方: {full_name} (股票代码 {stock_code})",
                source_ref_id="chunk-1",
            ),
            ProviderField(
                name="short_name", value=name_zh.split("股份")[0],
                confidence=_jitter(rng, 0.85),
                source_excerpt=f"简称: {name_zh.split('股份')[0]}",
                source_ref_id="chunk-1",
            ),
        ],
    )


def _gen_contract(rng: random.Random, filename: str) -> ProviderEntity:
    """Contract entity (合同 PDF → contract head). Round 13.

    Fields mirror what ontology.HEADER_ALIASES['Contract'] expects so that
    confirm_writer maps them onto the Contract model 1-to-1 without
    additional rules. customer_id will be filled by the Customer-has-Contract
    relationship resolver in confirm_writer.
    """
    year = date.today().year
    contract_no_external = f"HT-{year}-{rng.randint(1000, 9999)}"
    contract_no_internal = f"JT{year % 100}-{rng.randint(100, 999):03d}"
    # 合同金额量级 (锦泰单合同 ~30-330 万元 季度量级)
    amount = rng.choice([320_000, 1_056_000, 3_276_000, 4_125_000, 1_575_000])
    signing_d = date.today()
    effective_d = signing_d
    expiry_d = date(year + 1, signing_d.month, signing_d.day)
    product = rng.choice(_CONTRACT_PRODUCTS)
    return ProviderEntity(
        entity_type="Contract",
        temp_id="contract-1",
        fields=[
            ProviderField(
                name="contract_no_external", value=contract_no_external,
                confidence=_jitter(rng, 0.96),
                source_excerpt=f"对方合同号: {contract_no_external}",
                source_ref_id="chunk-1",
            ),
            ProviderField(
                name="contract_no_internal", value=contract_no_internal,
                confidence=_jitter(rng, 0.88),
                source_excerpt=f"我方合同号: {contract_no_internal}",
                source_ref_id="chunk-2",
            ),
            ProviderField(
                name="amount_total", value=str(amount),
                confidence=_jitter(rng, 0.94),
                source_excerpt=f"合同总额: ¥{amount:,}.00 (人民币)  · 产品: {product}",
                source_ref_id="chunk-3",
            ),
            ProviderField(
                name="amount_currency", value="CNY",
                confidence=_jitter(rng, 0.99),
                source_excerpt="币种: 人民币 (CNY)",
                source_ref_id="chunk-3",
            ),
            ProviderField(
                name="signing_date", value=signing_d.isoformat(),
                confidence=_jitter(rng, 0.93),
                source_excerpt=f"签订日期: {signing_d.isoformat()}",
                source_ref_id="chunk-4",
            ),
            ProviderField(
                name="effective_date", value=effective_d.isoformat(),
                confidence=_jitter(rng, 0.89),
                source_excerpt=f"生效日期: {effective_d.isoformat()}",
                source_ref_id="chunk-4",
            ),
            ProviderField(
                name="expiry_date", value=expiry_d.isoformat(),
                confidence=_jitter(rng, 0.87),
                source_excerpt=f"到期日期: {expiry_d.isoformat()}",
                source_ref_id="chunk-4",
            ),
            ProviderField(
                name="payment_terms", value="30/60/10, 验收合格后 90 天结清",
                confidence=_jitter(rng, 0.82),
                source_excerpt="付款方式: 30/60/10,验收合格后 90 天结清",
                source_ref_id="chunk-5",
            ),
            ProviderField(
                name="status", value="active",
                confidence=_jitter(rng, 0.78),
                source_excerpt="合同状态: 履行中",
                source_ref_id="chunk-6",
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
