"""Ontology-aware required-field map + column aliases for header detection.

Source of truth: the SQLAlchemy models under ``yunwei_win.models`` (task ①).

We intentionally derive the required set **dynamically** from the model
column metadata rather than hand-rolling a dict, so this file can't go
stale when task ① schema changes. ``test_parse_pipeline.py`` runs a
cross-check to guarantee the derivation matches expectations.

System-link FKs (``customer_id``, ``order_id``, ``contract_id``, etc.)
are filtered OUT of the user-visible required set because parsers
express those via ``relationships[]`` + ``temp_id`` rather than raw
UUIDs — they get satisfied by the relationship list, not by a field
value.

Header aliases let the Excel adapter map Chinese-or-English column
headers to canonical ontology field names. Keys are canonical field
names (lowercase), values are alias strings the user might write.
"""

from __future__ import annotations

from yunwei_win.models import (
    Contact,
    Contract,
    Customer,
    Invoice,
    Order,
    Payment,
    Product,
)
from yunwei_win.models.operations import OrderItem


# Entity → SQLAlchemy model mapping. OrderLine is the candidate JSON
# alias for OrderItem (task ① renamed it for clarity in the schema,
# but the product surface still calls them "order lines").
_ENTITY_MODELS = {
    "Customer": Customer,
    "Contact": Contact,
    "Contract": Contract,
    "Order": Order,
    "OrderLine": OrderItem,
    "Product": Product,
    "Invoice": Invoice,
    "Payment": Payment,
}


# System-link FK columns extracted entities express via relationships[],
# not via raw UUID fields. These are excluded from missing_required even
# when the underlying model marks them nullable=False.
_SYSTEM_LINK_COLUMNS = {
    "id",
    "customer_id",
    "order_id",
    "contract_id",
    "invoice_id",
    "payment_id",
    "product_id",
    "shipment_id",
    "next_action_id",
}


def required_fields(entity_type: str) -> set[str]:
    """User-visible required columns for an entity.

    "Required" means ``nullable=False`` AND no SQL/Python default. Columns
    that the ORM auto-fills (PKs with ``default=uuid4``, currency with
    ``default="CNY"``, enums with a default member, etc.) are excluded —
    the parser can omit them and the writeback layer still succeeds.

    Returns an empty set for unknown entity types (so a typo can't
    spuriously fill ``missing_required``).
    """
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        return set()
    out: set[str] = set()
    for col in model.__table__.columns:
        if col.name in _SYSTEM_LINK_COLUMNS:
            continue
        if col.nullable:
            continue
        if col.default is not None or col.server_default is not None:
            continue
        out.add(col.name)
    return out


def known_fields(entity_type: str) -> set[str]:
    model = _ENTITY_MODELS.get(entity_type)
    if model is None:
        return set()
    return {c.name for c in model.__table__.columns}


# Excel header → canonical field name. The Excel adapter scans the
# header row and matches case-insensitively against alias substrings;
# the first canonical hit wins. Keep aliases short and distinctive so
# accidental substring matches (e.g. "name" inside "company name") fall
# through to a more specific entry first — order within the same value
# tuple doesn't matter for matching, but more-specific entries (e.g.
# "tax_id" → "纳税人识别号") should be listed before less-specific ones
# in the same entity to win when a row has both.
HEADER_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "Customer": {
        "full_name": ("客户名称", "客户全称", "公司名称", "公司全称", "买方", "甲方", "customer", "customer name", "company"),
        "short_name": ("客户简称", "简称", "short name"),
        "tax_id": ("纳税人识别号", "税号", "统一社会信用代码", "信用代码", "tax id", "tax_id", "uscc"),
        "address": ("地址", "公司地址", "address"),
        "industry": ("行业", "industry"),
    },
    "Contact": {
        "name": ("联系人", "联系人姓名", "对接人", "contact", "contact name"),
        "phone": ("电话", "座机", "phone"),
        "mobile": ("手机", "手机号", "mobile"),
        "email": ("邮箱", "email", "e-mail"),
        "title": ("职位", "title"),
        "wechat_id": ("微信", "微信号", "wechat"),
    },
    "Order": {
        "order_no": ("订单号", "订单编号", "po号", "po", "order no", "order number"),
        "order_date": ("订单日期", "下单日期", "下单时间", "order date"),
        "amount_total": ("订单金额", "订单总额", "总金额", "金额", "amount", "total amount"),
        "amount_currency": ("币种", "货币", "currency"),
        "delivery_promised_date": ("交期", "约定交期", "交付日期", "delivery date"),
        "delivery_address": ("交货地址", "收货地址", "delivery address"),
        "status": ("订单状态", "状态", "status"),
    },
    "OrderLine": {
        "description": ("产品名称", "品名", "货品名称", "物料名称", "description", "product"),
        "specification": ("规格", "型号", "规格型号", "specification", "spec"),
        "quantity": ("数量", "件数", "qty", "quantity"),
        "unit": ("单位", "计量单位", "unit"),
        "unit_price": ("单价", "unit price", "price"),
        "amount": ("行金额", "小计", "行小计", "subtotal", "line total"),
    },
    "Contract": {
        "contract_no_external": ("合同号", "合同编号", "对方合同号", "contract no"),
        "contract_no_internal": ("内部合同号", "内部编号"),
        "amount_total": ("合同金额", "合同总额"),
        "amount_currency": ("币种", "currency"),
        "signing_date": ("签订日期", "签约日期", "signing date"),
        "effective_date": ("生效日期", "起始日期", "effective date"),
        "expiry_date": ("到期日期", "失效日期", "expiry date"),
        "payment_terms": ("账期", "付款条件", "付款方式", "payment terms"),
    },
    "Invoice": {
        "invoice_no": ("发票号", "发票号码", "invoice no", "invoice number"),
        "issue_date": ("开票日期", "开票时间", "invoice date"),
        "amount_total": ("发票金额", "开票金额", "invoice amount"),
        "tax_amount": ("税额", "税款", "tax amount"),
        "buyer_tax_id": ("购方税号", "客户税号", "buyer tax id"),
    },
    "Payment": {
        "payment_date": ("回款日期", "收款日期", "到账日期", "payment date"),
        "amount": ("回款金额", "收款金额", "金额", "amount"),
        "amount_due": ("应收金额", "应收款", "due amount"),
        "method": ("回款方式", "付款方式", "method"),
        "reference_no": ("流水号", "凭证号", "reference no"),
        "due_date": ("到期日期", "应收日期", "due date"),
    },
    "Product": {
        "name": ("产品名称", "品名", "name", "product name"),
        "sku": ("sku", "物料编码", "产品编号"),
        "specification": ("规格", "specification"),
        "unit": ("单位", "unit"),
    },
}


def find_canonical_field(entity_type: str, header_text: str) -> str | None:
    """Resolve a free-text Excel header to a canonical field name.

    Match strategy:
      1. exact case-insensitive equality against any alias → confidence "high".
      2. case-insensitive substring containment → confidence "medium".
      3. miss → ``None``; caller may treat as positional fallback.

    Returns ``None`` if no alias matches.
    """
    if not header_text:
        return None
    aliases = HEADER_ALIASES.get(entity_type, {})
    needle = header_text.strip().lower()

    for field_name, alts in aliases.items():
        for alt in alts:
            if needle == alt.lower():
                return field_name

    for field_name, alts in aliases.items():
        for alt in alts:
            a = alt.lower()
            if a in needle or needle in a:
                return field_name

    return None


def header_match_confidence(entity_type: str, header_text: str) -> float:
    """Return the confidence multiplier for a header match.

    Exact alias → 1.0. Substring → 0.85. Miss → 0.0 (caller should
    treat as positional / unmatched).
    """
    if not header_text:
        return 0.0
    aliases = HEADER_ALIASES.get(entity_type, {})
    needle = header_text.strip().lower()
    for alts in aliases.values():
        for alt in alts:
            if needle == alt.lower():
                return 1.0
    for alts in aliases.values():
        for alt in alts:
            a = alt.lower()
            if a in needle or needle in a:
                return 0.85
    return 0.0
