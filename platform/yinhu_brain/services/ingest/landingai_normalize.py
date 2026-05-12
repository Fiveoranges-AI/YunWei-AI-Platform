"""Project LandingAI per-pipeline extracts onto a single `UnifiedDraft`.

LandingAI returns one JSON object per schema (identity / contract_order /
finance / logistics / manufacturing_requirement / commitment_task_risk).
The downstream review form binds to a `UnifiedDraft`, so this module
folds those independent extracts into the legacy customer / contacts /
order / contract / ops shape.

Design notes:

- Field names diverge between LandingAI schemas and our legacy DB schema
  (`contract_number` vs `contract_no_external`, `total_amount` vs
  `amount_total`). We map them here rather than touching either side.
- LandingAI's `contacts[].role` enum is broader than the legacy
  `ContactRoleEx`. Unknown roles collapse to `buyer` (these contacts are
  always Party A / buyer-side per the schema descriptions).
- Real LandingAI extractions are sparse — every accessor goes through
  `dict.get(...) or {}` so missing keys don't crash the normalizer.
"""

from __future__ import annotations

from typing import Any

from yinhu_brain.services.ingest.schemas import (
    ContactExtraction,
    ContractExtraction,
    CustomerExtraction,
    OrderExtraction,
    PaymentMilestone,
)
from yinhu_brain.services.ingest.unified_schemas import (
    PipelineExtractResult,
    UnifiedDraft,
)


def _int_or_none(v: Any) -> int | None:
    """Best-effort int coercion. Used for fields LandingAI declares as string
    (e.g. ``trigger_offset_days``) but our DB models type as ``int | None``.

    - ``None`` / empty / blank string → ``None``
    - ``int`` / ``float`` → ``int(value)``
    - ``"90"`` / ``"90天"`` / ``"  90 "`` → ``90``
    - Anything else unparseable → ``None`` (don't crash the ingest)
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        try:
            return int(v)
        except (OverflowError, ValueError):
            return None
    if isinstance(v, str):
        cleaned = v.strip().replace("天", "").replace(" ", "")
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return None
    return None


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = (
            v.replace(",", "")
            .replace("，", "")
            .replace("¥", "")
            .replace("￥", "")
            .replace("元", "")
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _ratio(v: Any) -> float:
    n = _num(v)
    if n is None:
        return 0.0
    return n / 100.0 if n > 1.0 else n


def _normalize_role(raw: Any) -> str:
    """Map LandingAI schema's role enum onto the legacy ContactRoleEx.

    LandingAI emits `primary_business / procurement / payment / legal /
    delivery / acceptance / invoice / other`. The downstream DB enum is
    `seller / buyer / delivery / acceptance / invoice / other`. The
    pass-through values map verbatim; anything else (`primary_business`,
    `procurement`, `payment`, `legal`) is a buyer-side functional role
    so it collapses to `buyer`.
    """
    if raw in {"delivery", "acceptance", "invoice", "other"}:
        return raw
    return "buyer"


def normalize_pipeline_results(results: list[PipelineExtractResult]) -> UnifiedDraft:
    """Fold each `PipelineExtractResult` onto a single `UnifiedDraft`.

    The first pipeline that yields a customer wins (identity and
    contract_order both emit one — they should agree, but if they don't
    we keep the first to avoid silent overwrites).
    """

    draft = UnifiedDraft(pipeline_results=results)
    warnings: list[str] = []

    for result in results:
        data = result.extraction or {}
        warnings.extend(result.warnings)
        warnings.extend(data.get("extraction_warnings") or [])

        # customer — first non-empty wins
        customer = data.get("customer") or {}
        if customer and draft.customer is None:
            draft.customer = CustomerExtraction.model_validate(
                {
                    "full_name": customer.get("full_name"),
                    "short_name": customer.get("short_name"),
                    "address": customer.get("address"),
                    "tax_id": customer.get("tax_id"),
                }
            )

        if result.name in {"identity", "contract_order"}:
            contacts = data.get("contacts") or []
            for c in contacts:
                draft.contacts.append(
                    ContactExtraction.model_validate(
                        {
                            "name": c.get("name"),
                            "title": c.get("title"),
                            "phone": c.get("phone"),
                            "mobile": c.get("mobile"),
                            "email": c.get("email"),
                            "role": _normalize_role(c.get("role")),
                            "address": c.get("address"),
                        }
                    )
                )

        if result.name == "contract_order":
            contract = data.get("contract") or {}
            order = data.get("order") or {}
            milestones = (
                data.get("payment_milestones")
                or contract.get("payment_milestones")
                or []
            )
            draft.contract = ContractExtraction.model_validate(
                {
                    "contract_no_external": contract.get("contract_number")
                    or contract.get("contract_no_external"),
                    "payment_milestones": [
                        PaymentMilestone.model_validate(
                            {
                                "name": m.get("name"),
                                "ratio": _ratio(m.get("ratio")),
                                "trigger_event": m.get("trigger_event") or "other",
                                "trigger_offset_days": _int_or_none(
                                    m.get("trigger_offset_days")
                                ),
                                "raw_text": m.get("raw_text"),
                            }
                        )
                        for m in milestones
                    ],
                    "delivery_terms": contract.get("delivery_terms"),
                    "penalty_terms": contract.get("penalty_terms"),
                    "signing_date": contract.get("signing_date"),
                    "effective_date": contract.get("effective_date"),
                    "expiry_date": contract.get("expiry_date"),
                }
            )
            draft.order = OrderExtraction.model_validate(
                {
                    "amount_total": order.get("total_amount")
                    or order.get("amount_total"),
                    "amount_currency": order.get("currency")
                    or order.get("amount_currency")
                    or contract.get("currency")
                    or "CNY",
                    "delivery_promised_date": order.get("delivery_promised_date"),
                    "delivery_address": order.get("delivery_address"),
                    "description": order.get("summary") or order.get("description"),
                }
            )

        if result.name == "commitment_task_risk":
            draft.summary = data.get("summary") or draft.summary
            draft.events = data.get("events") or []
            draft.commitments = data.get("commitments") or []
            draft.tasks = data.get("tasks") or []
            draft.risk_signals = data.get("risk_signals") or []
            draft.memory_items = data.get("memory_items") or []

    draft.warnings = warnings
    draft.confidence_overall = 0.8 if any(r.extraction for r in results) else 0.3
    return draft
