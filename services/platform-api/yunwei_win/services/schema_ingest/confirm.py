"""Confirm a vNext ReviewDraft into the tenant business tables.

Contract (call from API only; lock + version must already be held):

  1. load extraction; status must be ``pending_review``;
  2. ``assert_valid_review_lock(lock_token, base_version)`` — stale tokens or
     stale versions are 409s before we touch any business row;
  3. validate the server-stored ``review_draft`` against the active catalog
     for catalog/ORM parity, missing required cells, and primitive type;
  4. walk rows by table in dependency phases (customers/products →
     children → grandchildren); the row's ``row_decision.operation`` drives
     create / update / link_existing / ignore;
  5. ``system_link`` FK columns are filled from a ``row_uuid_map`` that
     tracks parents written or linked in this same confirm — never from
     extractor cells;
  6. AI null / missing cells never overwrite an existing DB value; only an
     explicit ``edited`` cell with ``explicit_clear=True`` clears a column;
  7. each persisted field emits a ``FieldProvenance`` row carrying
     ``parse_id``, ``extraction_id``, source refs, and the user-facing
     ``review_action`` (ai / edited / default / linked / system);
  8. on success flip the extraction to ``confirmed``, release the review
     lock, mark the linked Document/IngestJob, and commit the whole batch
     in one transaction.

If validation produces ``invalid_cells`` the caller receives a response
with those cells and no business rows are written.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import (
    Contact,
    Contract,
    Customer,
    Document,
    DocumentReviewStatus,
    EntityType,
    FieldProvenance,
    IngestJob,
    IngestJobStatus,
    Order,
)
from yunwei_win.models.company_data import (
    ContractPaymentMilestone,
    CustomerJournalItem,
    Invoice,
    InvoiceItem,
    Payment,
    Product,
    ProductRequirement,
    Shipment,
    ShipmentItem,
)
from yunwei_win.models.customer_memory import CustomerTask
from yunwei_win.models.document_extraction import (
    DocumentExtraction,
    DocumentExtractionStatus,
)
from yunwei_win.services.company_schema import (
    ensure_default_company_schema,
    get_company_schema,
)
from yunwei_win.services.schema_ingest.fk_links import FK_FIELD_PARENTS
from yunwei_win.services.schema_ingest.review_lock import (
    assert_valid_review_lock,
    release_review_lock,
)
from yunwei_win.services.schema_ingest.schemas import (
    ConfirmExtractionRequest,
    ConfirmExtractionResponse,
    ReviewCell,
    ReviewDraft,
    ReviewRow,
    ReviewRowDecision,
    ReviewTable,
)

logger = logging.getLogger(__name__)


# table_name -> (Model, EntityType for provenance)
TABLE_MODEL: dict[str, tuple[type, EntityType]] = {
    "customers": (Customer, EntityType.customer),
    "contacts": (Contact, EntityType.contact),
    "orders": (Order, EntityType.order),
    "contracts": (Contract, EntityType.contract),
    "contract_payment_milestones": (
        ContractPaymentMilestone,
        EntityType.contract_payment_milestone,
    ),
    "products": (Product, EntityType.product),
    "product_requirements": (ProductRequirement, EntityType.product_requirement),
    "invoices": (Invoice, EntityType.invoice),
    "invoice_items": (InvoiceItem, EntityType.invoice_item),
    "payments": (Payment, EntityType.payment),
    "shipments": (Shipment, EntityType.shipment),
    "shipment_items": (ShipmentItem, EntityType.shipment_item),
    "customer_journal_items": (CustomerJournalItem, EntityType.customer_journal_item),
    "customer_tasks": (CustomerTask, EntityType.customer_task),
}


# Parents before children before grandchildren. Phases run sequentially so a
# child created in phase 2 can find its parent UUID in row_uuid_map.
WRITE_PHASES: list[list[str]] = [
    ["customers", "products"],
    [
        "contacts",
        "orders",
        "contracts",
        "invoices",
        "shipments",
        "product_requirements",
    ],
    [
        "contract_payment_milestones",
        "invoice_items",
        "shipment_items",
        "payments",
    ],
    ["customer_journal_items", "customer_tasks"],
]


_HIDDEN_FIELD_ROLES = {"system_link", "audit"}
_AUDIT_DOCUMENT_FIELDS = {"document_id", "source_document_id"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def confirm_review_draft(
    *,
    session: AsyncSession,
    extraction_id: UUID,
    request: ConfirmExtractionRequest,
    confirmed_by: str | None,
) -> ConfirmExtractionResponse:
    extraction = (
        await session.execute(
            select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
        )
    ).scalar_one_or_none()
    if extraction is None:
        raise HTTPException(status_code=404, detail="extraction not found")
    if extraction.status != DocumentExtractionStatus.pending_review:
        raise HTTPException(
            status_code=409,
            detail=f"extraction is {extraction.status.value}, not pending_review",
        )

    if request.lock_token is None or request.base_version is None:
        raise HTTPException(
            status_code=400, detail="lock_token and base_version are required"
        )
    assert_valid_review_lock(
        extraction,
        lock_token=request.lock_token,
        base_version=request.base_version,
    )

    job = (
        await session.execute(
            select(IngestJob).where(IngestJob.extraction_id == extraction_id)
        )
    ).scalar_one_or_none()
    if job is not None and job.status in (
        IngestJobStatus.confirmed,
        IngestJobStatus.failed,
        IngestJobStatus.canceled,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"linked ingest job is {job.status.value}",
        )

    await ensure_default_company_schema(session)
    catalog = await get_company_schema(session)
    catalog_by_table: dict[str, dict[str, dict[str, Any]]] = {
        t["table_name"]: {f["field_name"]: f for f in t.get("fields") or []}
        for t in catalog.get("tables") or []
    }

    if extraction.review_draft is None:
        raise HTTPException(status_code=409, detail="review_draft missing on extraction")
    server_draft = ReviewDraft.model_validate(extraction.review_draft)

    invalid_cells = _validate_draft(server_draft, catalog_by_table)
    if invalid_cells:
        return ConfirmExtractionResponse(
            extraction_id=extraction_id,
            document_id=extraction.document_id,
            status="pending_review",
            invalid_cells=invalid_cells,
        )

    rows_by_table: dict[str, list[tuple[ReviewTable, ReviewRow]]] = {}
    for t in server_draft.tables:
        rows_by_table.setdefault(t.table_name, []).extend((t, r) for r in t.rows)

    written: dict[str, list[UUID]] = {}
    row_uuid_map: dict[tuple[str, str], UUID] = {}

    for phase in WRITE_PHASES:
        for table_name in phase:
            pairs = rows_by_table.get(table_name)
            if not pairs:
                continue
            field_map = catalog_by_table.get(table_name)
            if field_map is None:
                continue
            for _table_meta, row in pairs:
                outcome = await _process_row(
                    session=session,
                    table_name=table_name,
                    row=row,
                    field_map=field_map,
                    row_uuid_map=row_uuid_map,
                    extraction=extraction,
                )
                if outcome is None:
                    continue
                row_uuid, was_written = outcome
                row_uuid_map[(table_name, row.client_row_id)] = row_uuid
                if was_written:
                    written.setdefault(table_name, []).append(row_uuid)

    now = datetime.now(timezone.utc)
    extraction.status = DocumentExtractionStatus.confirmed
    extraction.confirmed_by = confirmed_by
    extraction.confirmed_at = now
    extraction.review_draft = server_draft.model_dump(mode="json")
    release_review_lock(extraction)

    doc = (
        await session.execute(
            select(Document).where(Document.id == extraction.document_id)
        )
    ).scalar_one_or_none()
    if doc is not None:
        doc.review_status = DocumentReviewStatus.confirmed

    if job is not None:
        job.status = IngestJobStatus.confirmed
        job.finished_at = now

    await session.commit()

    return ConfirmExtractionResponse(
        extraction_id=extraction_id,
        document_id=extraction.document_id,
        status="confirmed",
        written_rows=written,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _row_operation(row: ReviewRow) -> str:
    if row.row_decision is not None:
        return row.row_decision.operation
    return row.operation or "create"


def _validate_draft(
    draft: ReviewDraft,
    catalog_by_table: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Catalog/ORM parity + required + primitive type validation.

    Rows with ``operation in {ignore, link_existing}`` skip cell validation —
    ``ignore`` rows never write, and ``link_existing`` rows attach an existing
    entity ID without touching cell values.
    """

    invalid: list[dict[str, Any]] = []
    for table in draft.tables:
        model_pair = TABLE_MODEL.get(table.table_name)
        if model_pair is None:
            continue
        model, _ = model_pair
        orm_columns = set(model.__table__.columns.keys())
        field_map = catalog_by_table.get(table.table_name, {})

        for row in table.rows:
            operation = _row_operation(row)
            if operation in {"ignore", "link_existing"}:
                continue
            if not row.is_writable and operation not in {"create", "update"}:
                continue

            for cell in row.cells:
                if cell.status == "rejected":
                    continue
                if _value_is_empty(cell.value):
                    spec = field_map.get(cell.field_name)
                    if (
                        spec is not None
                        and bool(spec.get("required"))
                        and operation == "create"
                        and _system_link_satisfied(
                            cell.field_name, table.table_name
                        )
                        is False
                    ):
                        invalid.append({
                            "table_name": table.table_name,
                            "client_row_id": row.client_row_id,
                            "field_name": cell.field_name,
                            "reason": "missing_required",
                        })
                    continue
                # Non-empty review cells must point at a real ORM column.
                if cell.field_name not in orm_columns:
                    invalid.append({
                        "table_name": table.table_name,
                        "client_row_id": row.client_row_id,
                        "field_name": cell.field_name,
                        "reason": "catalog_field_has_no_orm_destination",
                    })
                    continue
                spec = field_map.get(cell.field_name)
                if spec is None:
                    continue
                if not _value_matches_type(spec, cell.value):
                    invalid.append({
                        "table_name": table.table_name,
                        "client_row_id": row.client_row_id,
                        "field_name": cell.field_name,
                        "reason": "invalid_value",
                    })
    return invalid


def _system_link_satisfied(field_name: str, _table_name: str) -> bool:
    """``True`` when an empty visible cell is OK because confirm will fill it.

    With vNext, ``system_link`` columns are filtered out of review cells, so
    they never appear here. Audit fields like ``document_id`` are also
    filtered out. This guard is only relevant if a legacy draft still has
    one of those names visible — treat them as system-supplied so we don't
    raise a missing_required for fields the model can never produce.
    """

    return field_name in FK_FIELD_PARENTS or field_name in _AUDIT_DOCUMENT_FIELDS


def _value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _to_decimal(value: Any) -> Decimal:
    """Coerce OCR-style numeric strings to Decimal.

    Handles ``"90%"`` → ``Decimal("0.9")`` (per-hundred convention used by
    catalog ratio/rate fields) and thousands separators
    (``"30,000.00"`` → ``Decimal("30000.00")``). Raises
    ``InvalidOperation`` / ``ValueError`` on garbage so callers can branch
    on the exception just like a bare ``Decimal(str(value))``.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise InvalidOperation("bool is not a decimal")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    if s.endswith("%"):
        return Decimal(s[:-1].replace(",", "").strip()) / Decimal(100)
    return Decimal(s.replace(",", ""))


def _value_matches_type(field_spec: dict[str, Any], value: Any) -> bool:
    data_type = (field_spec.get("data_type") or "text").lower()
    try:
        if data_type == "text":
            return isinstance(value, (str, int, float))
        if data_type == "uuid":
            UUID(str(value))
            return True
        if data_type == "date":
            if isinstance(value, date):
                return True
            datetime.strptime(str(value), "%Y-%m-%d")
            return True
        if data_type == "datetime":
            if isinstance(value, datetime):
                return True
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return True
        if data_type == "decimal":
            _to_decimal(value)
            return True
        if data_type == "integer":
            if isinstance(value, bool):
                return False
            if isinstance(value, int):
                return True
            s = str(value)
            try:
                int(s)
                return True
            except ValueError:
                return float(s).is_integer()
        if data_type == "boolean":
            if isinstance(value, bool):
                return True
            if isinstance(value, (int, float)):
                return value in (0, 1)
            return str(value).lower() in ("true", "false", "0", "1")
        if data_type == "enum":
            enum_values = field_spec.get("enum_values") or []
            if not enum_values:
                return True
            return value in enum_values
        if data_type == "json":
            return True
        return True
    except (ValueError, InvalidOperation, TypeError):
        return False


def _coerce_value(field_spec: dict[str, Any], value: Any) -> Any:
    if value is None:
        return None
    data_type = (field_spec.get("data_type") or "text").lower()
    if data_type == "uuid":
        return UUID(str(value)) if not isinstance(value, UUID) else value
    if data_type == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    if data_type == "datetime":
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if data_type == "decimal":
        return _to_decimal(value)
    if data_type == "integer":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        return int(float(str(value)))
    if data_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).lower() in ("true", "1")
    return value


# ---------------------------------------------------------------------------
# Row processing
# ---------------------------------------------------------------------------


async def _process_row(
    *,
    session: AsyncSession,
    table_name: str,
    row: ReviewRow,
    field_map: dict[str, dict[str, Any]],
    row_uuid_map: dict[tuple[str, str], UUID],
    extraction: DocumentExtraction,
) -> tuple[UUID, bool] | None:
    """Apply one row's decision. Returns (entity_id, was_written) or None.

    - ``ignore`` and non-writable rows without an explicit decision return None.
    - ``link_existing`` returns (selected_entity_id, False) so row_uuid_map
      can feed child FK auto-fills without creating a duplicate parent.
    - ``create`` / ``update`` actually write business rows + provenance.
    """

    decision: ReviewRowDecision | None = row.row_decision
    operation = decision.operation if decision is not None else (row.operation or "create")

    if operation == "ignore":
        return None
    if not row.is_writable and operation not in {"create", "update", "link_existing"}:
        return None

    if operation == "link_existing":
        target_id = (
            decision.selected_entity_id
            if decision is not None
            else None
        ) or row.entity_id
        if target_id is None:
            logger.warning(
                "confirm: link_existing for %s.%s without selected_entity_id",
                table_name,
                row.client_row_id,
            )
            return None
        return target_id, False

    if operation == "update":
        existing_id = (
            decision.selected_entity_id
            if decision is not None
            else None
        ) or row.entity_id
        if existing_id is None:
            logger.warning(
                "confirm: update for %s.%s without selected_entity_id",
                table_name,
                row.client_row_id,
            )
            return None
        entity_id = await _write_row(
            session=session,
            table_name=table_name,
            row=row,
            field_map=field_map,
            row_uuid_map=row_uuid_map,
            extraction=extraction,
            existing_id=existing_id,
            is_update=True,
        )
        return (entity_id, True) if entity_id is not None else None

    # default: create
    entity_id = await _write_row(
        session=session,
        table_name=table_name,
        row=row,
        field_map=field_map,
        row_uuid_map=row_uuid_map,
        extraction=extraction,
        existing_id=row.entity_id,
        is_update=False,
    )
    return (entity_id, True) if entity_id is not None else None


async def _write_row(
    *,
    session: AsyncSession,
    table_name: str,
    row: ReviewRow,
    field_map: dict[str, dict[str, Any]],
    row_uuid_map: dict[tuple[str, str], UUID],
    extraction: DocumentExtraction,
    existing_id: UUID | None,
    is_update: bool,
) -> UUID | None:
    model_pair = TABLE_MODEL.get(table_name)
    if model_pair is None:
        return None
    model, entity_type = model_pair
    orm_columns = set(model.__table__.columns.keys())

    cell_values: dict[str, Any] = {}
    provenance_cells: list[tuple[ReviewCell, Any]] = []

    for cell in row.cells:
        if cell.status == "rejected":
            continue
        spec = field_map.get(cell.field_name)
        if spec is None:
            continue
        if cell.field_name not in orm_columns:
            continue
        value_is_empty = _value_is_empty(cell.value)

        if value_is_empty:
            # An explicit user-driven clear is the only way to overwrite a
            # column with NULL; otherwise leave the DB value alone.
            if (
                is_update
                and cell.source == "edited"
                and cell.explicit_clear
                and cell.status != "missing"
            ):
                cell_values[cell.field_name] = None
                provenance_cells.append((cell, None))
            continue

        if cell.source == "default" and is_update:
            # Defaults only apply on create, never overwrite live data.
            continue

        try:
            coerced = _coerce_value(spec, cell.value)
        except (ValueError, InvalidOperation, TypeError):
            continue
        cell_values[cell.field_name] = coerced
        provenance_cells.append((cell, coerced))

    # Fill system_link FK columns from parents written or linked earlier in
    # this confirm. These never come from extractor cells.
    system_fk_writes: dict[str, UUID] = {}
    for fk_name, parent_table in FK_FIELD_PARENTS.items():
        if fk_name not in orm_columns:
            continue
        if fk_name in cell_values:
            continue
        if parent_table == "documents":
            continue  # handled separately below
        parent_uuid = _lookup_single_parent(row_uuid_map, parent_table)
        if parent_uuid is None:
            continue
        system_fk_writes[fk_name] = parent_uuid
        cell_values[fk_name] = parent_uuid

    # Audit document_id / source_document_id come from the extraction itself.
    audit_writes: dict[str, UUID] = {}
    for audit_name in _AUDIT_DOCUMENT_FIELDS:
        if audit_name not in orm_columns:
            continue
        if audit_name in cell_values:
            continue
        cell_values[audit_name] = extraction.document_id
        audit_writes[audit_name] = extraction.document_id

    if existing_id is not None:
        entity = (
            await session.execute(select(model).where(model.id == existing_id))
        ).scalar_one_or_none()
        if entity is None and is_update:
            # Update target vanished — treat as create with the chosen id.
            entity = model()
            entity.id = existing_id
            for k, v in cell_values.items():
                setattr(entity, k, v)
            session.add(entity)
        elif entity is None:
            entity = model()
            entity.id = existing_id
            for k, v in cell_values.items():
                setattr(entity, k, v)
            session.add(entity)
        else:
            for k, v in cell_values.items():
                setattr(entity, k, v)
    else:
        entity = model()
        for k, v in cell_values.items():
            setattr(entity, k, v)
        session.add(entity)

    try:
        await session.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "confirm: flush failed for %s row %s: %s", table_name, row.client_row_id, exc
        )
        raise

    row_uuid: UUID = entity.id  # type: ignore[attr-defined]

    for cell, coerced in provenance_cells:
        await _write_provenance(
            session=session,
            extraction=extraction,
            entity_type=entity_type,
            entity_id=row_uuid,
            field_name=cell.field_name,
            value=coerced,
            review_action=_review_action_for(cell),
            source_refs=[ref.model_dump() for ref in cell.source_refs],
            confidence=cell.confidence,
        )

    for fk_name, parent_uuid in system_fk_writes.items():
        await _write_provenance(
            session=session,
            extraction=extraction,
            entity_type=entity_type,
            entity_id=row_uuid,
            field_name=fk_name,
            value=str(parent_uuid),
            review_action="linked",
            source_refs=[],
            confidence=None,
        )

    for audit_name, audit_value in audit_writes.items():
        await _write_provenance(
            session=session,
            extraction=extraction,
            entity_type=entity_type,
            entity_id=row_uuid,
            field_name=audit_name,
            value=str(audit_value),
            review_action="system",
            source_refs=[],
            confidence=None,
        )

    return row_uuid


def _review_action_for(cell: ReviewCell) -> str:
    source = cell.source
    if source == "ai":
        return "ai"
    if source == "edited":
        return "edited"
    if source == "default":
        return "default"
    if source == "linked":
        return "linked"
    return "system"


def _lookup_single_parent(
    row_uuid_map: dict[tuple[str, str], UUID], parent_table: str
) -> UUID | None:
    matches = [v for (t, _r), v in row_uuid_map.items() if t == parent_table]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


async def _write_provenance(
    *,
    session: AsyncSession,
    extraction: DocumentExtraction,
    entity_type: EntityType,
    entity_id: UUID,
    field_name: str,
    value: Any,
    review_action: str,
    source_refs: list[Any],
    confidence: float | None,
) -> None:
    payload = {
        "value": _provenance_value(value),
        "parse_id": extraction.parse_id,
        "extraction_id": extraction.id,
        "source_page": None,
        "source_excerpt": _first_excerpt(source_refs),
        "confidence": confidence,
        "excerpt_match": None,
        "extracted_by": review_action,
        "source_refs": source_refs,
        "review_action": review_action,
    }
    existing = (
        await session.execute(
            select(FieldProvenance).where(
                FieldProvenance.document_id == extraction.document_id,
                FieldProvenance.entity_type == entity_type,
                FieldProvenance.entity_id == entity_id,
                FieldProvenance.field_name == field_name,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            FieldProvenance(
                document_id=extraction.document_id,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                **payload,
            )
        )
    else:
        for k, v in payload.items():
            setattr(existing, k, v)


def _provenance_value(value: Any) -> Any:
    if isinstance(value, (UUID, Decimal, date, datetime)):
        return str(value)
    return value


def _first_excerpt(source_refs: list[Any]) -> str | None:
    for ref in source_refs:
        if isinstance(ref, dict):
            excerpt = ref.get("excerpt")
            if isinstance(excerpt, str) and excerpt:
                return excerpt
    return None
