"""Confirm step for the unified ``/auto`` ingest pipeline.

After ``auto_ingest`` produces a ``UnifiedDraft`` and the user reviews it
in the frontend, this module persists the user-reviewed payload to the
canonical entity tables:

- ``customers`` — INSERT or UPDATE (per-entity decision: ``new`` vs ``merge``)
- ``contacts`` — INSERT or UPDATE per slot (same convention as customer)
- ``orders`` + ``contracts`` — always INSERT, mirrors the legacy /contract
  confirm flow (one document → one order + contract)
- Customer-memory tables (events / commitments / tasks / risk_signals /
  memory_items) — append-only INSERT, bound to the resolved customer

This module is the equivalent of ``commit_contract_extraction`` from the
legacy contract pipeline — it shares the same decision-aware semantics for
customer + contact resolution, then layers the ops-side fan-out on top.

Constraints copied from the legacy commit logic:
- ``customer.full_name`` is required when *any* downstream entity wants to
  attach (order, contract, contacts, ops rows). Without a customer name we
  can't merge or create the parent row, so we raise a clear error rather
  than persist orphan rows.
- ``Document.review_status = confirmed`` is set as the very last step so a
  partial failure leaves the row in ``pending_review`` for retry.
- ``Document.assigned_customer_id`` is set to the resolved customer so the
  document can be traced back from the customer profile UI.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.models import (
    CommitmentDirection,
    CommitmentStatus,
    Contact,
    ContactRole,
    Contract,
    Customer,
    CustomerCommitment,
    CustomerEvent,
    CustomerEventType,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    DocumentReviewStatus,
    MemoryKind,
    Order,
    RiskKind,
    RiskSeverity,
    RiskStatus,
    TaskPriority,
    TaskStatus,
)
from yinhu_brain.services.ingest.provenance import write_provenance
from yinhu_brain.services.ingest.schemas import ContractExtractionResult
from yinhu_brain.services.ingest.unified_schemas import AutoConfirmRequest

logger = logging.getLogger(__name__)


# Same threshold the contract pipeline uses for review-flag computation.
_REVIEW_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class AutoConfirmResult:
    """Bundle returned by ``commit_auto_extraction``.

    Order/contract IDs are optional because the user might confirm an
    identity-only or ops-only draft (no commercial dimension). Customer ID
    is also optional in the rare case the draft has neither a customer nor
    any rows that need a customer parent (currently impossible because we
    require a customer for ops rows — but kept Optional so the dataclass
    handles future "memory-only without customer" use cases gracefully).
    """

    document_id: uuid.UUID
    customer_id: uuid.UUID | None
    contact_ids: list[uuid.UUID] = field(default_factory=list)
    order_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    event_ids: list[uuid.UUID] = field(default_factory=list)
    commitment_ids: list[uuid.UUID] = field(default_factory=list)
    task_ids: list[uuid.UUID] = field(default_factory=list)
    risk_signal_ids: list[uuid.UUID] = field(default_factory=list)
    memory_item_ids: list[uuid.UUID] = field(default_factory=list)
    confidence_overall: float = 0.0
    warnings: list[str] = field(default_factory=list)
    needs_review_fields: list[str] = field(default_factory=list)


# ---------- helpers (copied from inbox.py to keep modules independent) ---


def _enum_or_default(enum_cls, raw: Any, default):
    """Coerce a string-or-enum into an enum; fall back to ``default`` on miss.

    Borrowed from ``api/customer_profile/inbox.py`` so the customer-memory
    fan-out shares the same tolerance: LLM emits "other" or our enum value
    enum.value-string, anything else gracefully falls back.
    """
    if raw is None:
        return default
    if isinstance(raw, enum_cls):
        return raw
    try:
        return enum_cls(raw)
    except (ValueError, TypeError):
        if hasattr(raw, "value"):
            try:
                return enum_cls(raw.value)
            except (ValueError, TypeError):
                return default
        return default


def _parse_dt(raw: Any) -> datetime | None:
    """ISO datetime parser tolerant of trailing ``Z`` and naive strings."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_date(raw: Any) -> date | None:
    """ISO date parser; tolerates ``2026-05-10T12:00:00`` by truncating."""
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw[:10]).date()
        except ValueError:
            return None
    return raw


def _first_nonempty(*candidates: Any) -> str:
    """Return the first non-empty candidate after stripping; ``""`` if all empty."""
    for c in candidates:
        s = (c or "").strip().split("\n", 1)[0]
        if s:
            return s
    return ""


def _value_or_none(v: Any) -> Any:
    """Coerce Pydantic enum values into their canonical ``.value`` form for
    the ops-row writer; ints/strings/None fall through unchanged.
    """
    if v is None:
        return None
    if hasattr(v, "value"):
        return v.value
    return v


# ---------- main entrypoint ----------------------------------------------


async def commit_auto_extraction(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    request: AutoConfirmRequest,
) -> AutoConfirmResult:
    """Persist a user-reviewed ``UnifiedDraft`` to canonical entity tables.

    Sequence:
      1. Validate the document — must exist, must not already be confirmed.
      2. Resolve the customer (new vs merge) — required when any downstream
         row (contacts, order, contract, ops) wants to attach.
      3. Resolve each contact slot (new vs merge); skip nameless slots.
      4. INSERT order + contract if present.
      5. Append-only INSERT for events / commitments / tasks / risk_signals
         / memory_items, bound to the resolved customer + document.
      6. Write field_provenance via the legacy ``write_provenance`` helper
         (path resolution shares the schema, so identity + commercial paths
         resolve cleanly; ops paths are dropped silently).
      7. Stamp Document.review_status = confirmed + assigned_customer_id.
    """
    doc = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError(f"document {document_id} not found")
    if doc.review_status == DocumentReviewStatus.confirmed:
        raise ValueError(f"document {document_id} already confirmed")

    has_downstream_rows = (
        request.order is not None
        or request.contract is not None
        or len(request.contacts) > 0
        or len(request.events) > 0
        or len(request.commitments) > 0
        or len(request.tasks) > 0
        or len(request.risk_signals) > 0
        or len(request.memory_items) > 0
    )

    # ----- 2. Customer resolution -----------------------------------
    customer: Customer | None = None
    if request.customer is not None:
        cust_final = request.customer.final
        if not (cust_final.full_name and cust_final.full_name.strip()):
            doc.parse_error = (
                "customer name not extracted (likely OCR failure)"
            )
            await session.flush()
            raise ValueError(
                "customer name is required; OCR likely failed on the buyer/甲方 region"
            )

        if request.customer.mode == "merge":
            if request.customer.existing_id is None:
                raise ValueError("customer.mode=merge requires existing_id")
            customer = (
                await session.execute(
                    select(Customer).where(
                        Customer.id == request.customer.existing_id
                    )
                )
            ).scalar_one_or_none()
            if customer is None:
                raise ValueError(
                    f"customer {request.customer.existing_id} not found"
                )
            customer.full_name = cust_final.full_name.strip()
            customer.short_name = cust_final.short_name
            customer.address = cust_final.address
            customer.tax_id = cust_final.tax_id
        else:
            customer = Customer(
                full_name=cust_final.full_name.strip(),
                short_name=cust_final.short_name,
                address=cust_final.address,
                tax_id=cust_final.tax_id,
            )
            session.add(customer)
        await session.flush()
    elif has_downstream_rows:
        # Without a customer, ops/order/contract/contacts have nowhere to
        # attach. Surface the error rather than silently dropping rows.
        raise ValueError(
            "customer is required when contacts / order / contract / "
            "events / commitments / tasks / risk_signals / memory_items "
            "are present"
        )

    # ----- 3. Contacts ---------------------------------------------
    contact_slots: list[uuid.UUID | None] = []
    contact_ids: list[uuid.UUID] = []
    skipped_contacts = 0
    if customer is not None:
        for decision in request.contacts:
            c_final = decision.final
            if not (c_final.name and c_final.name.strip()):
                skipped_contacts += 1
                contact_slots.append(None)
                continue
            try:
                role = ContactRole(c_final.role.value)
            except ValueError:
                role = ContactRole.other
            if decision.mode == "merge":
                if decision.existing_id is None:
                    raise ValueError("contact.mode=merge requires existing_id")
                ct = (
                    await session.execute(
                        select(Contact).where(Contact.id == decision.existing_id)
                    )
                ).scalar_one_or_none()
                if ct is None:
                    raise ValueError(
                        f"contact {decision.existing_id} not found"
                    )
                ct.customer_id = customer.id
                ct.name = c_final.name.strip()
                ct.title = c_final.title
                ct.phone = c_final.phone
                ct.mobile = c_final.mobile
                ct.email = c_final.email
                ct.role = role
                ct.address = c_final.address
            else:
                ct = Contact(
                    customer_id=customer.id,
                    name=c_final.name.strip(),
                    title=c_final.title,
                    phone=c_final.phone,
                    mobile=c_final.mobile,
                    email=c_final.email,
                    role=role,
                    address=c_final.address,
                )
                session.add(ct)
            await session.flush()
            contact_slots.append(ct.id)
            contact_ids.append(ct.id)

    # ----- 4. Order + Contract -------------------------------------
    order_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    order_obj: Order | None = None
    contract_obj: Contract | None = None
    if customer is not None and request.order is not None:
        order_obj = Order(
            customer_id=customer.id,
            amount_total=request.order.amount_total,
            amount_currency=request.order.amount_currency,
            delivery_promised_date=request.order.delivery_promised_date,
            delivery_address=request.order.delivery_address,
            description=request.order.description,
        )
        session.add(order_obj)
        await session.flush()
        order_id = order_obj.id

    if order_obj is not None and request.contract is not None:
        milestone_dicts: list[dict] = []
        for i, m in enumerate(request.contract.payment_milestones):
            d = m.model_dump(mode="json")
            if not d.get("name"):
                d["name"] = f"阶段{i + 1}"
            milestone_dicts.append(d)

        contract_obj = Contract(
            order_id=order_obj.id,
            contract_no_external=request.contract.contract_no_external,
            contract_no_internal=Path(doc.original_filename or "").stem or None,
            payment_milestones=milestone_dicts,
            delivery_terms=request.contract.delivery_terms,
            penalty_terms=request.contract.penalty_terms,
            signing_date=request.contract.signing_date,
            effective_date=request.contract.effective_date,
            expiry_date=request.contract.expiry_date,
            confidence_overall=request.confidence_overall,
        )
        session.add(contract_obj)
        await session.flush()
        contract_id = contract_obj.id

    # ----- 5. Ops rows --------------------------------------------
    event_ids: list[uuid.UUID] = []
    commitment_ids: list[uuid.UUID] = []
    task_ids: list[uuid.UUID] = []
    risk_signal_ids: list[uuid.UUID] = []
    memory_item_ids: list[uuid.UUID] = []

    if customer is not None:
        for ev in request.events:
            title = _first_nonempty(ev.title, ev.description, ev.raw_excerpt)
            if not title:
                continue
            row = CustomerEvent(
                customer_id=customer.id,
                document_id=doc.id,
                occurred_at=_parse_dt(ev.occurred_at),
                event_type=_enum_or_default(
                    CustomerEventType,
                    _value_or_none(ev.event_type),
                    CustomerEventType.other,
                ),
                title=title[:500],
                description=ev.description,
                raw_excerpt=ev.raw_excerpt,
                confidence=ev.confidence,
            )
            session.add(row)
            await session.flush()
            event_ids.append(row.id)

        for cm in request.commitments:
            if not (cm.summary and cm.summary.strip()):
                continue
            row = CustomerCommitment(
                customer_id=customer.id,
                document_id=doc.id,
                direction=_enum_or_default(
                    CommitmentDirection,
                    _value_or_none(cm.direction),
                    CommitmentDirection.mutual,
                ),
                summary=cm.summary[:500],
                description=cm.description,
                due_date=_parse_date(cm.due_date),
                status=CommitmentStatus.open,
                raw_excerpt=cm.raw_excerpt,
                confidence=cm.confidence,
            )
            session.add(row)
            await session.flush()
            commitment_ids.append(row.id)

        for tk in request.tasks:
            title = _first_nonempty(tk.title, tk.description, tk.raw_excerpt)
            if not title:
                continue
            row = CustomerTask(
                customer_id=customer.id,
                document_id=doc.id,
                title=title[:500],
                description=tk.description,
                assignee=tk.assignee,
                due_date=_parse_date(tk.due_date),
                priority=_enum_or_default(
                    TaskPriority,
                    _value_or_none(tk.priority),
                    TaskPriority.normal,
                ),
                status=TaskStatus.open,
                raw_excerpt=tk.raw_excerpt,
            )
            session.add(row)
            await session.flush()
            task_ids.append(row.id)

        for r in request.risk_signals:
            if not (r.summary and r.summary.strip()):
                continue
            row = CustomerRiskSignal(
                customer_id=customer.id,
                document_id=doc.id,
                severity=_enum_or_default(
                    RiskSeverity,
                    _value_or_none(r.severity),
                    RiskSeverity.medium,
                ),
                kind=_enum_or_default(
                    RiskKind,
                    _value_or_none(r.kind),
                    RiskKind.other,
                ),
                summary=r.summary[:500],
                description=r.description,
                status=RiskStatus.open,
                raw_excerpt=r.raw_excerpt,
                confidence=r.confidence,
            )
            session.add(row)
            await session.flush()
            risk_signal_ids.append(row.id)

        for m in request.memory_items:
            if not (m.content and m.content.strip()):
                continue
            row = CustomerMemoryItem(
                customer_id=customer.id,
                document_id=doc.id,
                kind=_enum_or_default(
                    MemoryKind,
                    _value_or_none(m.kind),
                    MemoryKind.context,
                ),
                content=m.content,
                raw_excerpt=m.raw_excerpt,
                confidence=m.confidence,
            )
            session.add(row)
            await session.flush()
            memory_item_ids.append(row.id)

    # ----- 6. Provenance -----------------------------------------
    excerpt_warnings: list[str] = []
    if (
        customer is not None
        and order_obj is not None
        and contract_obj is not None
        and request.field_provenance
    ):
        # write_provenance walks paths against ContractExtractionResult; we
        # synthesize one from the confirm payload (treating missing pieces
        # as fully-null instances so path resolution doesn't crash). Ops
        # paths (events[].title, commitments[].summary, ...) don't share a
        # prefix with customer/order/contract/contacts so write_provenance
        # silently drops them — that's fine, ops rows already carry their
        # own ``raw_excerpt`` for traceability.
        result_view = ContractExtractionResult(
            customer=request.customer.final if request.customer else None,
            contacts=[c.final for c in request.contacts],
            order=request.order,
            contract=request.contract,
            field_provenance=request.field_provenance,
            confidence_overall=request.confidence_overall,
            field_confidence={},
            parse_warnings=request.parse_warnings,
        )
        excerpt_warnings = await write_provenance(
            session=session,
            document_id=doc.id,
            result=result_view,
            customer_id=customer.id,
            order_id=order_obj.id,
            contract_id=contract_obj.id,
            contact_ids=contact_slots,
            ocr_text=doc.ocr_text or "",
            extracted_by=settings.model_parse,
        )

    # ----- 7. Document audit + warnings --------------------------
    base_warnings = list(doc.parse_warnings or [])
    payload_warnings = list(request.parse_warnings)
    all_warnings = base_warnings + payload_warnings + excerpt_warnings
    if skipped_contacts:
        all_warnings.append(
            f"{skipped_contacts} contact(s) skipped — name field came back null"
        )

    doc.parse_warnings = all_warnings
    doc.review_status = DocumentReviewStatus.confirmed
    if customer is not None:
        doc.assigned_customer_id = customer.id
    await session.flush()

    needs_review_fields: list[str] = []
    if request.confidence_overall < _REVIEW_CONFIDENCE_THRESHOLD:
        needs_review_fields.append("confidence_overall")

    return AutoConfirmResult(
        document_id=doc.id,
        customer_id=customer.id if customer is not None else None,
        contact_ids=contact_ids,
        order_id=order_id,
        contract_id=contract_id,
        event_ids=event_ids,
        commitment_ids=commitment_ids,
        task_ids=task_ids,
        risk_signal_ids=risk_signal_ids,
        memory_item_ids=memory_item_ids,
        confidence_overall=request.confidence_overall,
        warnings=all_warnings,
        needs_review_fields=needs_review_fields,
    )
