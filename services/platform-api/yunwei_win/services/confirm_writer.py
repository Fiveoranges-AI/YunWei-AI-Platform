"""Confirm-writer for the candidate JSON → ontology row commit path.

P0 task ③: take a CandidateJSON (from task ② parse pipeline) that a human
has confirmed (with optional per-field edits) and persist it into the
customer-operations ontology tables built by task ①.

Every row written here is stamped:

  * ``human_verified=True``
  * ``verified_by`` / ``verified_at`` from the calling user / now()
  * ``source_type`` / ``source_ref`` / ``source_span`` passed through from
    the candidate so the row remembers which file/cell it came from
  * row ``confidence`` = the model's original value (per-field
    ``was_edited=True`` causes that field's confidence pointer to drop;
    we store the *minimum* surviving field confidence as the row-level
    seed, with the row marked human-verified)
  * ``created_by`` / ``updated_by`` = actor

After each entity write, one ``ActionLog`` row is appended (one per
ingestion + entity_type+target) summarising the action.

The writer is **deliberately not transactional across entities** —
callers (the confirm endpoint) wrap the whole batch in a single
``async with session.begin()`` so a single failed row aborts the lot.

Out of scope here:
  * parsing — that's task ②.
  * dedup detection — the candidate carries ``warnings`` and the UI
    resolves "merge vs new"; the writer only honours an explicit
    ``existing_entity_id`` decision the caller passes in.
  * permissions — the per-tenant DB boundary handles isolation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    ActionLog,
    ActionTargetType,
    Contact,
    ContactRole,
    Contract,
    Customer,
    Invoice,
    NextActionType,
    Order,
    OrderItem,
    Payment,
    Product,
)


logger = logging.getLogger(__name__)


# Entity-type → SQLAlchemy model. Stable contract surfaced in the
# error message when an unknown entity_type is submitted.
_ENTITY_MODEL: dict[str, type] = {
    "Customer": Customer,
    "Contact": Contact,
    "Contract": Contract,
    "Order": Order,
    "OrderLine": OrderItem,
    "OrderItem": OrderItem,
    "Product": Product,
    "Invoice": Invoice,
    "Payment": Payment,
}

_ENTITY_TARGET: dict[str, ActionTargetType] = {
    "Customer": ActionTargetType.customer,
    "Contact": ActionTargetType.contact,
    "Contract": ActionTargetType.contract,
    "Order": ActionTargetType.order,
    "OrderLine": ActionTargetType.order,
    "OrderItem": ActionTargetType.order,
    "Product": ActionTargetType.other,
    "Invoice": ActionTargetType.invoice,
    "Payment": ActionTargetType.payment,
}

# Fields the candidate JSON may carry but the ORM models drive via FK
# resolution from ``relationships[]``. Reject if the candidate tries to
# set them directly — the FK comes from the relationship resolver.
_SYSTEM_LINK_COLUMNS = {
    "customer_id",
    "order_id",
    "contract_id",
    "invoice_id",
    "payment_id",
    "product_id",
    "shipment_id",
}


# Special role mapping for Contact role enum.
_CONTACT_ROLE_LOOKUP = {r.value: r for r in ContactRole}


@dataclass
class ConfirmedField:
    """One confirmed field on an entity."""

    name: str
    value: Any
    confidence: float | None = None
    was_edited: bool = False
    source_span: dict[str, Any] | None = None


@dataclass
class ConfirmedEntity:
    """One human-confirmed entity from the candidate JSON."""

    entity_type: str
    temp_id: str
    fields: list[ConfirmedField] = field(default_factory=list)
    # If the user picked "associate with existing X" in the duplicate-warning
    # dialog, the row is *not* re-created — but child relationships still
    # resolve to this id. Mutually exclusive with insertion.
    existing_entity_id: uuid.UUID | None = None


@dataclass
class ConfirmedRelationship:
    from_temp_id: str
    to_temp_id: str
    type: str  # e.g. "Customer-has-Contact", "Order-has-OrderLine"


@dataclass
class ConfirmRequest:
    """Input bundle passed to ``confirm_candidate``."""

    ingestion_id: str
    source_type: str
    source_ref: str
    actor: str  # platform user id / display name
    entities: list[ConfirmedEntity] = field(default_factory=list)
    relationships: list[ConfirmedRelationship] = field(default_factory=list)


@dataclass
class WrittenEntity:
    """Outcome record for one entity in the confirm batch."""

    temp_id: str
    entity_type: str
    entity_id: uuid.UUID
    created: bool  # False if existing_entity_id was passed
    human_verified: bool
    verified_by: str
    field_count: int
    edited_field_count: int


@dataclass
class ConfirmResult:
    """Aggregate result of one confirm request."""

    written: list[WrittenEntity] = field(default_factory=list)
    action_log_ids: list[uuid.UUID] = field(default_factory=list)


# ---- relationship resolution -----------------------------------------


_PARENT_FK_BY_RELATIONSHIP: dict[str, tuple[str, str]] = {
    # "from"-temp_id row gets a FK column pointing at "to"-temp_id row.
    # The mapping below is read as: when relationship.type matches the
    # key, the *child* side is `child_entity` and the parent's id is
    # written into the column `child_fk` on the child row.
    "Customer-has-Contact":   ("Contact", "customer_id"),
    "Customer-has-Order":     ("Order", "customer_id"),
    "Customer-has-Contract":  ("Contract", "customer_id"),
    "Customer-has-Invoice":   ("Invoice", "customer_id"),
    "Customer-has-Payment":   ("Payment", "customer_id"),
    "Order-has-OrderLine":    ("OrderLine", "order_id"),
    "Order-has-OrderItem":    ("OrderItem", "order_id"),
    "Order-has-Invoice":      ("Invoice", "order_id"),
    "Contract-has-Order":     ("Order", "contract_id"),
    "OrderLine-has-Product":  ("OrderLine", "product_id"),
    "OrderItem-has-Product":  ("OrderItem", "product_id"),
    "Invoice-has-Payment":    ("Payment", "invoice_id"),
}


# ---- value coercion --------------------------------------------------


def _coerce_value(model: type, attr: str, value: Any) -> Any:
    """Coerce candidate JSON values into the column's native Python type.

    Strings come back from the LLM / spreadsheet adapter for date and
    numeric columns; the ORM would otherwise reject them. We keep the
    surface area small (Date / Numeric / Boolean / Enum) — anything else
    is passed through unchanged.
    """
    if value is None or value == "":
        return None
    col = getattr(model, attr, None)
    if col is None:
        return value
    pytype = getattr(getattr(col, "type", None), "python_type", None)
    try:
        if pytype is None:
            return value
        if pytype is Decimal and not isinstance(value, Decimal):
            return Decimal(str(value))
        if pytype is int and not isinstance(value, int):
            return int(str(value).strip())
        if pytype is float and not isinstance(value, float):
            return float(str(value).strip())
        if pytype is bool and not isinstance(value, bool):
            return str(value).strip().lower() in ("1", "true", "yes", "y", "是", "true ")
        if pytype is date and not isinstance(value, date):
            return _parse_date(value)
        if pytype is datetime and not isinstance(value, datetime):
            return _parse_datetime(value)
    except (ValueError, InvalidOperation, TypeError):
        # Surface as a typed error so the API layer can return 400.
        raise ConfirmFieldError(
            f"cannot coerce field {attr!r} value {value!r} to {pytype.__name__}"
        )
    # Contact.role enum coercion: candidate JSON sends the string label.
    if model is Contact and attr == "role":
        if isinstance(value, ContactRole):
            return value
        v = str(value).strip().lower()
        if v in _CONTACT_ROLE_LOOKUP:
            return _CONTACT_ROLE_LOOKUP[v]
        return ContactRole.other
    return value


def _parse_date(value: Any) -> date:
    s = str(value).strip().replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
    # Accept "2026-05-21" / "2026-5-21" / "2026-05-21T00:00:00"
    if "T" in s:
        s = s.split("T", 1)[0]
    parts = s.split("-")
    if len(parts) != 3:
        raise ValueError(s)
    y, m, d = (int(p) for p in parts)
    return date(y, m, d)


def _parse_datetime(value: Any) -> datetime:
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


class ConfirmFieldError(ValueError):
    """Raised when a confirmed value can't be coerced to its column type."""


class ConfirmRelationshipError(ValueError):
    """Raised when a relationship can't be resolved (unknown temp_id, etc.)."""


# ---- main entry ------------------------------------------------------


async def confirm_candidate(
    request: ConfirmRequest,
    session: AsyncSession,
) -> ConfirmResult:
    """Persist a confirmed candidate batch.

    Caller MUST wrap this in ``async with session.begin()`` so the whole
    batch is one transaction. On any error the caller's enclosing
    transaction rolls back — we don't open / close one here so the API
    handler can do its own commit / rollback.
    """
    if not request.entities:
        raise ValueError("confirm_candidate called with no entities")

    verified_at = datetime.now(tz=timezone.utc)
    actor = request.actor or "unknown"

    # Pre-build per-entity rows so we can resolve relationships before
    # flushing. We add to the session in two passes: first parents
    # (Customer / Contract / Product), then children that depend on
    # them (Order / Contact / Invoice / Payment / OrderItem). Inside a
    # generation we ``session.add()`` everything, ``flush()``, and the
    # generated UUIDs become available for the next pass.

    # 1. Build entity skeleton: kwargs + edited-field count.
    prepared: dict[str, _Prepared] = {}
    for ent in request.entities:
        if ent.entity_type not in _ENTITY_MODEL:
            raise ValueError(f"unknown entity_type {ent.entity_type!r}")
        if ent.existing_entity_id is not None:
            # User picked "associate existing" — don't insert, just
            # resolve temp_id → id for downstream relationships. Skip
            # writeback but DO emit an ActionLog ("reconcile" target).
            prepared[ent.temp_id] = _Prepared(
                entity=ent,
                model=_ENTITY_MODEL[ent.entity_type],
                kwargs={},
                row=None,
                resolved_id=ent.existing_entity_id,
                edited_count=sum(1 for f in ent.fields if f.was_edited),
            )
            continue
        model = _ENTITY_MODEL[ent.entity_type]
        kwargs: dict[str, Any] = {}
        edited_count = 0
        for f in ent.fields:
            if f.name in _SYSTEM_LINK_COLUMNS:
                # FK comes from relationships[], not field overrides.
                continue
            if not hasattr(model, f.name):
                # Unknown column — silently drop. Candidate JSON may carry
                # auxiliary fields (display labels etc.) that the ontology
                # doesn't materialise.
                continue
            kwargs[f.name] = _coerce_value(model, f.name, f.value)
            if f.was_edited:
                edited_count += 1
        prepared[ent.temp_id] = _Prepared(
            entity=ent,
            model=model,
            kwargs=kwargs,
            row=None,
            resolved_id=None,
            edited_count=edited_count,
        )

    # 2. Resolve relationships → FK assignments.
    for rel in request.relationships:
        spec = _PARENT_FK_BY_RELATIONSHIP.get(rel.type)
        if spec is None:
            # Unknown relationship type — surfaced as a warning, not an error,
            # because the candidate adapter may produce richer relationship
            # types that don't have a direct FK home (Customer-has-Risk etc.).
            logger.warning(
                "confirm_writer.unhandled_relationship type=%s from=%s to=%s",
                rel.type, rel.from_temp_id, rel.to_temp_id,
            )
            continue
        child_entity_type, child_fk = spec
        # The pair (from, to) defines which side is the parent. The mapping's
        # "child_entity_type" tells us whether `from_temp_id` is the parent
        # or `to_temp_id` is the parent.
        # Convention: relationship "Customer-has-Contact" means
        # from=Customer (parent), to=Contact (child).
        parent_temp_id = rel.from_temp_id
        child_temp_id = rel.to_temp_id
        if child_temp_id not in prepared:
            raise ConfirmRelationshipError(
                f"relationship {rel.type!r} references unknown child temp_id "
                f"{child_temp_id!r}"
            )
        child = prepared[child_temp_id]
        if child.entity.entity_type not in (child_entity_type, _normalise_child(child_entity_type)):
            raise ConfirmRelationshipError(
                f"relationship {rel.type!r} expected child to be "
                f"{child_entity_type}, got {child.entity.entity_type}"
            )
        # Stash parent_temp_id so we can resolve to a real UUID after flush.
        child.pending_parent_fk = (child_fk, parent_temp_id)

    # 3. Flush in dependency order: things with no parent first.
    order = _topological_order(prepared)

    result = ConfirmResult()

    for temp_id in order:
        prep = prepared[temp_id]
        if prep.resolved_id is not None:
            # existing-entity branch: nothing to write. Emit ActionLog below.
            written = WrittenEntity(
                temp_id=temp_id,
                entity_type=prep.entity.entity_type,
                entity_id=prep.resolved_id,
                created=False,
                human_verified=True,
                verified_by=actor,
                field_count=len(prep.entity.fields),
                edited_field_count=prep.edited_count,
            )
            result.written.append(written)
            log_id = await _emit_action_log(
                session=session,
                ingestion_id=request.ingestion_id,
                entity=prep.entity,
                entity_id=prep.resolved_id,
                action=NextActionType.reconcile,
                actor=actor,
                edited_count=prep.edited_count,
                verified_at=verified_at,
            )
            result.action_log_ids.append(log_id)
            continue

        # Resolve pending FK if any.
        if prep.pending_parent_fk is not None:
            col, parent_temp = prep.pending_parent_fk
            parent_prep = prepared.get(parent_temp)
            if parent_prep is None:
                raise ConfirmRelationshipError(
                    f"unknown parent temp_id {parent_temp!r}"
                )
            parent_id = parent_prep.resolved_id
            if parent_id is None:
                raise ConfirmRelationshipError(
                    f"parent {parent_temp!r} not yet flushed when resolving "
                    f"FK for {temp_id!r} — topological order bug?"
                )
            prep.kwargs[col] = parent_id

        # Stamp audit fields. row_confidence = min surviving field confidence
        # (so the row remembers it's AI-seeded even though it's human-verified).
        surviving = [
            f.confidence
            for f in prep.entity.fields
            if not f.was_edited and f.confidence is not None
        ]
        row_confidence = min(surviving) if surviving else None

        stamped = {
            "human_verified": True,
            "verified_by": actor,
            "verified_at": verified_at,
            "source_type": request.source_type,
            "source_ref": request.source_ref,
            "source_span": _aggregate_source_spans(prep.entity),
            "extracted_by": "llm",
            "created_by": actor,
            "updated_by": actor,
        }
        if row_confidence is not None and hasattr(prep.model, "confidence"):
            stamped["confidence"] = Decimal(str(round(row_confidence, 2)))

        # Only set columns that exist on the model.
        for k, v in stamped.items():
            if hasattr(prep.model, k):
                prep.kwargs[k] = v

        row = prep.model(**prep.kwargs)
        session.add(row)
        await session.flush()
        prep.row = row
        prep.resolved_id = row.id

        written = WrittenEntity(
            temp_id=temp_id,
            entity_type=prep.entity.entity_type,
            entity_id=row.id,
            created=True,
            human_verified=True,
            verified_by=actor,
            field_count=len(prep.entity.fields),
            edited_field_count=prep.edited_count,
        )
        result.written.append(written)
        log_id = await _emit_action_log(
            session=session,
            ingestion_id=request.ingestion_id,
            entity=prep.entity,
            entity_id=row.id,
            action=NextActionType.create_profile,
            actor=actor,
            edited_count=prep.edited_count,
            verified_at=verified_at,
        )
        result.action_log_ids.append(log_id)

    return result


# ---- internals -------------------------------------------------------


@dataclass
class _Prepared:
    entity: ConfirmedEntity
    model: type
    kwargs: dict[str, Any]
    row: Any
    resolved_id: uuid.UUID | None
    edited_count: int
    pending_parent_fk: tuple[str, str] | None = None


def _normalise_child(name: str) -> str:
    if name == "OrderLine":
        return "OrderItem"
    if name == "OrderItem":
        return "OrderLine"
    return name


def _topological_order(prepared: dict[str, _Prepared]) -> list[str]:
    """Return temp_ids in parent → child order.

    Builds a DAG from each prepared entity's ``pending_parent_fk`` and
    runs a Kahn topo sort. Cycles raise.
    """
    parents: dict[str, set[str]] = {tid: set() for tid in prepared}
    for tid, prep in prepared.items():
        if prep.pending_parent_fk is not None:
            _, parent_temp = prep.pending_parent_fk
            if parent_temp in prepared:
                parents[tid].add(parent_temp)
    ordered: list[str] = []
    remaining = dict(parents)
    while remaining:
        ready = [t for t, ps in remaining.items() if not ps]
        if not ready:
            raise ConfirmRelationshipError(
                f"relationship cycle: {list(remaining.keys())!r}"
            )
        ready.sort()  # deterministic
        for t in ready:
            ordered.append(t)
            del remaining[t]
            for ps in remaining.values():
                ps.discard(t)
    return ordered


def _aggregate_source_spans(entity: ConfirmedEntity) -> dict[str, Any] | None:
    """Build the row-level source_span pointer.

    The row gets a compact JSON ``{fields: {<field>: <span>}}`` so a list
    view doesn't need to join field_provenance for every cell. The first
    field with a populated span becomes the "primary" span for
    deep-link previews.
    """
    fields = {}
    primary = None
    for f in entity.fields:
        if not f.source_span:
            continue
        fields[f.name] = f.source_span
        if primary is None:
            primary = f.source_span
    if not fields:
        return None
    return {"primary": primary, "fields": fields}


async def _emit_action_log(
    *,
    session: AsyncSession,
    ingestion_id: str,
    entity: ConfirmedEntity,
    entity_id: uuid.UUID,
    action: NextActionType,
    actor: str,
    edited_count: int,
    verified_at: datetime,
) -> uuid.UUID:
    """Append one ActionLog row for a confirmed entity write."""

    target = _ENTITY_TARGET.get(entity.entity_type, ActionTargetType.other)
    edited_fields = [f.name for f in entity.fields if f.was_edited]
    input_summary = (
        f"ingestion={ingestion_id} entity={entity.entity_type} temp={entity.temp_id} "
        f"fields={len(entity.fields)} edited={edited_count}"
    )
    if edited_fields:
        input_summary += " edited_fields=" + ",".join(sorted(edited_fields))
    log = ActionLog(
        target_entity_type=target,
        target_entity_id=entity_id,
        action_type=action,
        actor=actor,
        actor_kind="user",
        input_summary=input_summary,
        output_summary=f"created entity_id={entity_id}",
        executed_at=verified_at,
        succeeded=True,
        created_by=actor,
        updated_by=actor,
    )
    session.add(log)
    await session.flush()
    return log.id
