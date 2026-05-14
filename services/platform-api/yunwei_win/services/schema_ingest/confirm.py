"""Confirm reviewed ReviewDraft cells into company data tables.

Confirm receives:
  - the server-stored ``DocumentExtraction`` (canonical draft, source of truth);
  - the client's optional echoed draft + cell-level patches.

Behavior:
  1. Load the canonical draft from ``DocumentExtraction.review_draft``.
  2. If the client supplied ``request.review_draft`` only cross-check its
     ``extraction_id`` matches the URL path — its tables/rows are ignored.
  3. Apply patches onto the server draft (patches targeting missing
     tables/rows/cells are silently skipped).
  4. Validate catalog ↔ ORM parity for every table being written.
  5. Validate every non-rejected cell against the catalog ``data_type``.
  6. If a non-rejected required cell is empty, return ``invalid_cells``
     without writing.
  7. Otherwise write tables in dependency phases (parents -> children),
     emit ``FieldProvenance`` for each confirmed non-empty cell, and flip
     the extraction / document / job status to ``confirmed``.

The current implementation intentionally skips fuzzy merge: if a row carries ``entity_id`` we
update; otherwise we create. Child rows inherit FK substitutions from
``client_row_id -> uuid`` mapping built within this confirm.
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
from yunwei_win.services.schema_ingest.schemas import (
    ConfirmExtractionRequest,
    ConfirmExtractionResponse,
    ReviewCell,
    ReviewDraft,
    ReviewRow,
    ReviewTable,
)

logger = logging.getLogger(__name__)


# table_name -> (Model, EntityType-for-provenance)
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


# Tables written before others to satisfy FK ordering. Phases run sequentially
# so a child created in phase 2 can reference a parent inserted in phase 1.
WRITE_PHASES: list[list[str]] = [
    ["customers", "products"],
    ["contacts", "orders", "contracts", "invoices", "shipments", "product_requirements"],
    ["contract_payment_milestones", "invoice_items", "shipment_items", "payments"],
    ["customer_journal_items", "customer_tasks"],
]


# FK auto-resolve map lives in ``fk_links.py`` so the materializer and the
# writeback path stay in sync.


async def confirm_review_draft(
    *,
    session: AsyncSession,
    extraction_id: UUID,
    request: ConfirmExtractionRequest,
    confirmed_by: str | None,
) -> ConfirmExtractionResponse:
    """Validate + write back the reviewed draft. See module docstring.

    Returns ``ConfirmExtractionResponse``; the caller (API endpoint) raises
    HTTPException(400) when ``invalid_cells`` is non-empty.
    """

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

    # If the client echoed a draft, cross-check its extraction_id only;
    # we do not trust its structure.
    if request.review_draft is not None:
        if request.review_draft.extraction_id != extraction_id:
            raise HTTPException(
                status_code=400,
                detail="review_draft.extraction_id does not match URL extraction_id",
            )

    # The linked IngestJob must not already be in a terminal state.
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

    # Catalog is the source of truth for required/data_type.
    await ensure_default_company_schema(session)
    catalog = await get_company_schema(session)
    catalog_by_table: dict[str, dict[str, dict[str, Any]]] = {}
    for t in catalog.get("tables") or []:
        catalog_by_table[t["table_name"]] = {
            f["field_name"]: f for f in t.get("fields") or []
        }

    # Source of truth: the DB-stored ReviewDraft. Patches mutate this draft
    # in place; the client's echoed draft is intentionally not consulted for
    # structure.
    server_draft = ReviewDraft.model_validate(extraction.review_draft)
    _apply_patches(server_draft, request.patches)

    # Validate catalog ↔ ORM parity for each table referenced in the draft
    # *before* writing anything. Either direction failing is a 400.
    invalid_cells = _check_orm_parity(server_draft, catalog_by_table)

    # Validate every non-rejected cell against the catalog data_type.
    invalid_cells.extend(_validate_draft(server_draft, catalog_by_table))
    if invalid_cells:
        return ConfirmExtractionResponse(
            extraction_id=extraction_id,
            document_id=extraction.document_id,
            status="pending_review",
            invalid_cells=invalid_cells,
        )

    # Index rows by table_name for ordered writeback.
    rows_by_table: dict[str, list[ReviewRow]] = {}
    for t in server_draft.tables:
        rows_by_table.setdefault(t.table_name, []).extend(t.rows)

    written: dict[str, list[UUID]] = {}
    row_uuid_map: dict[tuple[str, str], UUID] = {}

    for phase in WRITE_PHASES:
        for table_name in phase:
            rows = rows_by_table.get(table_name)
            if not rows:
                continue
            field_map = catalog_by_table.get(table_name)
            if field_map is None:
                continue
            for row in rows:
                # Skip rows where every non-rejected cell is empty AND the row
                # is a fresh insert — empty placeholder rows for array tables.
                if row.entity_id is None and _row_is_empty(row):
                    continue
                row_uuid = await _persist_row(
                    session=session,
                    table_name=table_name,
                    row=row,
                    field_map=field_map,
                    row_uuid_map=row_uuid_map,
                    document_id=extraction.document_id,
                )
                if row_uuid is None:
                    continue
                row_uuid_map[(table_name, row.client_row_id)] = row_uuid
                written.setdefault(table_name, []).append(row_uuid)

    # Mark all the surrounding metadata confirmed.
    now = datetime.now(timezone.utc)
    extraction.status = DocumentExtractionStatus.confirmed
    extraction.confirmed_by = confirmed_by
    extraction.confirmed_at = now
    extraction.review_draft = server_draft.model_dump(mode="json")

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


# ---- draft merging / patching ----------------------------------------


def _apply_patches(draft: ReviewDraft, patches) -> None:
    """Apply one patch at a time, looking up table+row+cell in-place."""

    if not patches:
        return
    table_index: dict[str, ReviewTable] = {t.table_name: t for t in draft.tables}
    for patch in patches:
        table = table_index.get(patch.table_name)
        if table is None:
            continue
        row = _find_row(table, patch.client_row_id)
        if row is None:
            continue
        if patch.entity_id is not None:
            row.entity_id = patch.entity_id
        if patch.operation is not None:
            row.operation = patch.operation
        cell = _find_cell(row, patch.field_name)
        if cell is None:
            continue
        if patch.value is not None or (patch.status is not None and patch.status != cell.status):
            old_value = cell.value
            if patch.value is not None:
                cell.value = patch.value
                cell.display_value = str(patch.value)
                if patch.status is None and patch.value != old_value:
                    cell.status = "edited"
                    cell.source = "edited"
        if patch.status is not None:
            cell.status = patch.status  # type: ignore[assignment]
            if patch.status == "edited" and cell.source not in ("edited",):
                cell.source = "edited"


def _find_row(table: ReviewTable, client_row_id: str) -> ReviewRow | None:
    for row in table.rows:
        if row.client_row_id == client_row_id:
            return row
    return None


def _find_cell(row: ReviewRow, field_name: str) -> ReviewCell | None:
    for cell in row.cells:
        if cell.field_name == field_name:
            return cell
    return None


# ---- validation ------------------------------------------------------


def _check_orm_parity(
    draft: ReviewDraft,
    catalog_by_table: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Fail loudly when catalog cells and ORM columns are out of sync.

    Two directions:

    1. **catalog_field_has_no_orm_destination**: a non-rejected, non-empty cell
       names a field the SQLAlchemy model has no column for. Without this
       guard ``setattr(entity, field_name, value)`` would silently drop the
       value (the old behavior).
    2. **orm_requires_field_missing_from_catalog**: a NOT-NULL ORM column with
       no server-side or Python-side default is neither provided by the
       catalog nor by ``FK_FIELD_PARENTS``. Without this guard the eventual
       ``flush`` would raise ``IntegrityError`` mid-write.
    """

    # A FK column counts as satisfiable from the auto-fill map only when the
    # parent table is also being written in this confirm — otherwise the
    # eventual flush hits IntegrityError.
    tables_being_written = {t.table_name for t in draft.tables}

    invalid: list[dict[str, Any]] = []
    for table in draft.tables:
        model_pair = TABLE_MODEL.get(table.table_name)
        if model_pair is None:
            continue
        model, _ = model_pair
        orm_columns = set(model.__table__.columns.keys())
        catalog_fields = set(catalog_by_table.get(table.table_name, {}).keys())

        for row in table.rows:
            if row.operation == "create" and row.entity_id is None and _row_is_empty(row):
                # Reviewer left an empty placeholder; we'd skip this row at
                # write time, so don't fire parity errors against it.
                continue

            # Direction 1: catalog cell -> ORM column.
            for cell in row.cells:
                if cell.status == "rejected":
                    continue
                if _value_is_empty(cell.value):
                    continue
                if cell.field_name not in orm_columns:
                    invalid.append({
                        "table_name": table.table_name,
                        "client_row_id": row.client_row_id,
                        "field_name": cell.field_name,
                        "reason": "catalog_field_has_no_orm_destination",
                    })

            # Direction 2: ORM NOT NULL column -> catalog field / FK / context.
            for column in model.__table__.columns:
                if not _column_must_be_supplied(column):
                    continue
                name = column.name
                if name in catalog_fields:
                    continue
                parent_table = FK_FIELD_PARENTS.get(name)
                if parent_table is not None and parent_table in tables_being_written:
                    continue
                invalid.append({
                    "table_name": table.table_name,
                    "client_row_id": row.client_row_id,
                    "field_name": name,
                    "reason": "orm_requires_field_missing_from_catalog",
                })
    return invalid


def _column_must_be_supplied(column: Any) -> bool:
    """A NOT NULL column with no default that the caller must supply.

    Primary keys and columns with a server-side or Python-side default are
    excluded — the DB or SQLAlchemy fills them in.
    """

    if column.nullable:
        return False
    if column.primary_key:
        return False
    if column.server_default is not None:
        return False
    if column.default is not None:
        return False
    return True


def _validate_draft(
    draft: ReviewDraft,
    catalog_by_table: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Walk every row/cell and collect ``invalid_cells`` entries.

    Empty required non-rejected cells -> ``missing_required``.
    Non-coercible values -> ``invalid_value``.
    Empty placeholder rows for array tables (no required field, entity_id
    null) are skipped — the reviewer chose not to add a row.
    """

    invalid: list[dict[str, Any]] = []
    for table in draft.tables:
        field_map = catalog_by_table.get(table.table_name)
        if field_map is None:
            continue
        for row in table.rows:
            row_is_create = row.operation == "create" and row.entity_id is None
            row_empty = _row_is_empty(row)
            row_has_required = _row_has_required(row, field_map)
            # Skip a row only when there's nothing the user needs to provide.
            # An empty create-row with NO required fields is a discard signal.
            if row_is_create and row_empty and not row_has_required:
                continue
            for cell in row.cells:
                if cell.status == "rejected":
                    continue
                field_spec = field_map.get(cell.field_name)
                if field_spec is None:
                    continue
                value_is_empty = _value_is_empty(cell.value)
                if value_is_empty:
                    if bool(field_spec.get("required")) and row_is_create:
                        # FK fields are filled by writeback from a same-
                        # confirm parent. The check is structural — based
                        # on FK_FIELD_PARENTS + parent rows in the draft —
                        # not the cell's ``source`` mark (which the
                        # materializer sets for UI but may be absent in
                        # drafts created before that change).
                        if (
                            cell.field_name in FK_FIELD_PARENTS
                            and _draft_has_writeable_parent(draft, cell.field_name)
                        ):
                            continue
                        invalid.append({
                            "table_name": table.table_name,
                            "client_row_id": row.client_row_id,
                            "field_name": cell.field_name,
                            "reason": "missing_required",
                        })
                    continue
                ok = _validate_value(field_spec, cell.value)
                if not ok:
                    invalid.append({
                        "table_name": table.table_name,
                        "client_row_id": row.client_row_id,
                        "field_name": cell.field_name,
                        "reason": "invalid_value",
                    })
    return invalid


def _row_has_required(
    row: ReviewRow, field_map: dict[str, dict[str, Any]]
) -> bool:
    """Whether the row has any catalog-required field in its cells."""

    for cell in row.cells:
        spec = field_map.get(cell.field_name)
        if spec is None:
            continue
        if bool(spec.get("required")):
            return True
    return False


def _draft_has_writeable_parent(draft: ReviewDraft, fk_field_name: str) -> bool:
    """True when an FK cell can rely on a same-confirm parent at writeback.

    Mirrors the runtime decision in ``_persist_row`` / ``_lookup_single_parent``:
    a parent row will be written when (a) it has an ``entity_id`` (update path)
    or (b) at least one non-rejected cell has a value (fresh insert). Rows
    with every cell rejected are not written and do not satisfy the link.
    """

    parent_table = FK_FIELD_PARENTS.get(fk_field_name)
    if parent_table is None:
        return False
    for t in draft.tables:
        if t.table_name != parent_table:
            continue
        for row in t.rows:
            if row.entity_id is not None:
                return True
            if not _row_is_empty(row):
                return True
    return False


def _row_is_empty(row: ReviewRow) -> bool:
    """A row is "empty" if every non-rejected cell has no value."""

    for cell in row.cells:
        if cell.status == "rejected":
            continue
        if not _value_is_empty(cell.value):
            return False
    return True


def _value_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _validate_value(field_spec: dict[str, Any], value: Any) -> bool:
    """Return True if ``value`` is coercible to ``data_type``."""

    data_type = (field_spec.get("data_type") or "text").lower()
    try:
        if data_type == "text":
            return isinstance(value, (str, int, float)) or value is None
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
            if isinstance(value, (int, float, Decimal)):
                return True
            Decimal(str(value))
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
                # Allow floats like "10.0" only when they're integral.
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


# ---- coercion --------------------------------------------------------


def _coerce_value(field_spec: dict[str, Any], value: Any) -> Any:
    """Coerce a validated cell value to the storable type."""

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
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
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
    # text / enum / json fall through unchanged.
    return value


# ---- writeback -------------------------------------------------------


async def _persist_row(
    *,
    session: AsyncSession,
    table_name: str,
    row: ReviewRow,
    field_map: dict[str, dict[str, Any]],
    row_uuid_map: dict[tuple[str, str], UUID],
    document_id: UUID,
) -> UUID | None:
    """Create or update a single row + emit provenance.

    Cells with ``status="rejected"`` or empty value are skipped.
    Returns the row UUID written (or None when nothing to do).
    """

    model_pair = TABLE_MODEL.get(table_name)
    if model_pair is None:
        logger.warning("schema confirm: unknown table %r, skipping", table_name)
        return None
    model, entity_type = model_pair

    cell_values: dict[str, Any] = {}
    provenance_cells: list[ReviewCell] = []
    for cell in row.cells:
        if cell.status == "rejected":
            continue
        value = cell.value
        # Auto-fill FK if empty + we have a same-confirm sibling mapping.
        if _value_is_empty(value) and cell.field_name in FK_FIELD_PARENTS:
            parent_table = FK_FIELD_PARENTS[cell.field_name]
            value = _lookup_single_parent(row_uuid_map, parent_table)
        if _value_is_empty(value):
            continue
        field_spec = field_map.get(cell.field_name)
        if field_spec is None:
            continue
        try:
            coerced = _coerce_value(field_spec, value)
        except (ValueError, InvalidOperation, TypeError) as exc:
            logger.warning(
                "schema confirm: skipping %s.%s due to coercion error %s",
                table_name, cell.field_name, exc,
            )
            continue
        cell_values[cell.field_name] = coerced
        provenance_cells.append(cell)

    # Upsert the row. The ORM parity precondition guarantees every
    # ``cell_values`` key has a matching column on the model, so we set
    # attributes directly without a silent ``hasattr`` skip.
    if row.entity_id is not None:
        entity = (
            await session.execute(select(model).where(model.id == row.entity_id))
        ).scalar_one_or_none()
        if entity is None:
            # ``entity_id`` set but row missing — treat as create.
            entity = model()
            entity.id = row.entity_id  # respect client-chosen id
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

    await session.flush()
    row_uuid: UUID = entity.id  # type: ignore[attr-defined]

    for cell in provenance_cells:
        await _write_provenance(
            session=session,
            document_id=document_id,
            entity_type=entity_type,
            entity_id=row_uuid,
            cell=cell,
        )

    return row_uuid


def _lookup_single_parent(
    row_uuid_map: dict[tuple[str, str], UUID], parent_table: str
) -> UUID | None:
    """If exactly one row of ``parent_table`` was written in this confirm,
    return its uuid so child rows can inherit the FK. None otherwise."""

    matches = [v for (t, _r), v in row_uuid_map.items() if t == parent_table]
    if len(matches) == 1:
        return matches[0]
    return None


async def _write_provenance(
    *,
    session: AsyncSession,
    document_id: UUID,
    entity_type: EntityType,
    entity_id: UUID,
    cell: ReviewCell,
) -> None:
    """Insert a FieldProvenance row keyed by (document, entity, field).

    Skipped silently when the cell has no evidence AND wasn't user-edited —
    nothing useful to record. Sqlite has no upsert primitive so we look up
    + update in place to satisfy the UNIQUE constraint.
    """

    has_evidence = cell.evidence is not None
    edited_by_user = cell.source == "edited"
    if not (has_evidence or edited_by_user):
        return

    existing = (
        await session.execute(
            select(FieldProvenance).where(
                FieldProvenance.document_id == document_id,
                FieldProvenance.entity_type == entity_type,
                FieldProvenance.entity_id == entity_id,
                FieldProvenance.field_name == cell.field_name,
            )
        )
    ).scalar_one_or_none()
    payload = {
        "value": cell.value,
        "source_page": cell.evidence.page if cell.evidence else None,
        "source_excerpt": cell.evidence.excerpt if cell.evidence else None,
        "confidence": cell.confidence,
        "excerpt_match": None,
        "extracted_by": cell.source,
    }
    if existing is None:
        session.add(
            FieldProvenance(
                document_id=document_id,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=cell.field_name,
                **payload,
            )
        )
    else:
        for k, v in payload.items():
            setattr(existing, k, v)
