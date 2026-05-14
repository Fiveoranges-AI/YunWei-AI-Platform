"""Deterministic entity resolution proposals for vNext ingest.

After extraction normalization, every row in ``NormalizedExtraction``
might be a brand-new entity, a duplicate of an existing tenant row, or
an ambiguous candidate. This module walks the rows table-by-table and
applies hard-coded match rules to produce a row-level
``create | update | link_existing | ignore`` proposal that ReviewDraft
materializes into the wizard, and confirm writeback uses to fill
``system_link`` FK fields.

First-version scope:

  customers   strong: exact tax_id, then normalized full_name
  contacts    strong: mobile / email within selected customer
              weak:   name within selected customer
  contracts   strong: contract_no_external within selected customer
  invoices    strong: invoice_no within selected customer
  orders      weak:   selected customer + amount_total + delivery date
              (no strong rule — catalog has no external order number)

LLMs never produce ``customer_id`` (system_link), so the customer scope
is sourced from either ``selected_customer_id`` (passed by the caller)
or the customer row this extraction itself strong-matches first.

Out of scope (intentionally deferred):
  * Fuzzy/semantic matching — keep it deterministic so behavior is
    predictable and reviewable.
  * Multi-tenant deduplication — every session is already scoped to one
    tenant DB by the request middleware.
  * External-key strong match for orders — first add the column to the
    catalog/ORM (later task), then turn it on.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models.company_data import Invoice
from yunwei_win.models.contact import Contact
from yunwei_win.models.contract import Contract
from yunwei_win.models.customer import Customer
from yunwei_win.models.order import Order
from yunwei_win.services.schema_ingest.extraction_normalize import (
    NormalizedExtraction,
    NormalizedRow,
)

MatchLevel = Literal["strong", "weak", "none"]
ProposedOperation = Literal["create", "update", "link_existing", "ignore"]


class EntityCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: UUID
    label: str
    match_level: MatchLevel
    match_keys: list[str] = Field(default_factory=list)
    confidence: float | None = None
    reason: str | None = None


class EntityResolutionRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_name: str
    client_row_id: str
    proposed_operation: ProposedOperation
    selected_entity_id: UUID | None = None
    confidence: float | None = None
    match_level: MatchLevel = "none"
    match_keys: list[str] = Field(default_factory=list)
    reason: str | None = None
    candidates: list[EntityCandidate] = Field(default_factory=list)


class EntityResolutionProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    rows: list[EntityResolutionRow] = Field(default_factory=list)


# Tables we run rules for. Anything else gets a default-create proposal
# so ReviewDraft can still show it but nothing tries to match.
_FIRST_VERSION_TABLES = ("customers", "contacts", "contracts", "invoices", "orders")


async def propose_entity_resolution(
    *,
    session: AsyncSession,
    extraction: NormalizedExtraction,
    selected_customer_id: UUID | None = None,
) -> EntityResolutionProposal:
    """Build create/update/link proposals for every row in ``extraction``.

    Customers are resolved first because a strong customer match becomes
    the implicit ``selected_customer_id`` for the rest of the document
    (contacts, contracts, invoices, orders). The caller may also pin a
    customer explicitly via ``selected_customer_id``.
    """

    rows: list[EntityResolutionRow] = []
    implicit_customer_id = selected_customer_id

    for row in extraction.tables.get("customers", []):
        result = await _resolve_customer(session, row)
        rows.append(result)
        if (
            implicit_customer_id is None
            and result.proposed_operation == "update"
            and result.selected_entity_id is not None
        ):
            implicit_customer_id = result.selected_entity_id

    for table_name, table_rows in extraction.tables.items():
        if table_name == "customers":
            continue
        for row in table_rows:
            if table_name == "contacts":
                rows.append(await _resolve_contact(session, row, implicit_customer_id))
            elif table_name == "contracts":
                rows.append(await _resolve_contract(session, row, implicit_customer_id))
            elif table_name == "invoices":
                rows.append(await _resolve_invoice(session, row, implicit_customer_id))
            elif table_name == "orders":
                rows.append(await _resolve_order(session, row, implicit_customer_id))
            else:
                rows.append(_default_create(table_name, row))

    return EntityResolutionProposal(rows=rows)


# ---------------------------------------------------------------------------
# Per-table resolvers
# ---------------------------------------------------------------------------


async def _resolve_customer(
    session: AsyncSession, row: NormalizedRow
) -> EntityResolutionRow:
    full_name = _str_value(row, "full_name")
    tax_id = _str_value(row, "tax_id")

    if tax_id:
        stmt = select(Customer).where(Customer.tax_id == tax_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return _strong_match_row(
                table_name="customers",
                client_row_id=row.client_row_id,
                entity=existing,
                label=existing.full_name,
                match_keys=["tax_id"],
                reason=f"existing customer matched by tax_id={tax_id!r}",
            )

    if full_name:
        normalized = _normalize_company_name(full_name)
        if normalized:
            stmt = select(Customer)
            for customer in (await session.execute(stmt)).scalars().all():
                if _normalize_company_name(customer.full_name) == normalized:
                    return _strong_match_row(
                        table_name="customers",
                        client_row_id=row.client_row_id,
                        entity=customer,
                        label=customer.full_name,
                        match_keys=["full_name"],
                        reason=(
                            f"existing customer matched by normalized "
                            f"full_name={full_name!r}"
                        ),
                    )

    return _default_create("customers", row)


async def _resolve_contact(
    session: AsyncSession,
    row: NormalizedRow,
    customer_id: UUID | None,
) -> EntityResolutionRow:
    name = _str_value(row, "name")
    mobile = _str_value(row, "mobile")
    email = _str_value(row, "email")

    if customer_id and mobile:
        existing = (
            await session.execute(
                select(Contact).where(
                    Contact.customer_id == customer_id,
                    Contact.mobile == mobile,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _strong_match_row(
                table_name="contacts",
                client_row_id=row.client_row_id,
                entity=existing,
                label=existing.name or "(无名)",
                match_keys=["mobile"],
                reason=f"existing contact matched by mobile within selected customer",
            )

    if customer_id and email:
        existing = (
            await session.execute(
                select(Contact).where(
                    Contact.customer_id == customer_id,
                    Contact.email == email,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _strong_match_row(
                table_name="contacts",
                client_row_id=row.client_row_id,
                entity=existing,
                label=existing.name or "(无名)",
                match_keys=["email"],
                reason=f"existing contact matched by email within selected customer",
            )

    if customer_id and name:
        existing = (
            await session.execute(
                select(Contact).where(
                    Contact.customer_id == customer_id,
                    Contact.name == name,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return EntityResolutionRow(
                table_name="contacts",
                client_row_id=row.client_row_id,
                proposed_operation="create",
                match_level="weak",
                match_keys=["name"],
                reason=(
                    "existing contact with same name within selected "
                    "customer — defaulting to create with candidate"
                ),
                candidates=[
                    EntityCandidate(
                        entity_id=existing.id,
                        label=existing.name,
                        match_level="weak",
                        match_keys=["name"],
                    )
                ],
            )

    return _default_create("contacts", row)


async def _resolve_contract(
    session: AsyncSession,
    row: NormalizedRow,
    customer_id: UUID | None,
) -> EntityResolutionRow:
    no_external = _str_value(row, "contract_no_external")
    if customer_id and no_external:
        existing = (
            await session.execute(
                select(Contract).where(
                    Contract.customer_id == customer_id,
                    Contract.contract_no_external == no_external,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _strong_match_row(
                table_name="contracts",
                client_row_id=row.client_row_id,
                entity=existing,
                label=existing.contract_no_external or "(无合同号)",
                match_keys=["contract_no_external", "customer_id"],
                reason="existing contract matched by external number within customer",
            )

    return _default_create("contracts", row)


async def _resolve_invoice(
    session: AsyncSession,
    row: NormalizedRow,
    customer_id: UUID | None,
) -> EntityResolutionRow:
    invoice_no = _str_value(row, "invoice_no")
    if customer_id and invoice_no:
        existing = (
            await session.execute(
                select(Invoice).where(
                    Invoice.customer_id == customer_id,
                    Invoice.invoice_no == invoice_no,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return _strong_match_row(
                table_name="invoices",
                client_row_id=row.client_row_id,
                entity=existing,
                label=existing.invoice_no or "(无发票号)",
                match_keys=["invoice_no", "customer_id"],
                reason="existing invoice matched by invoice_no within customer",
            )

    return _default_create("invoices", row)


async def _resolve_order(
    session: AsyncSession,
    row: NormalizedRow,
    customer_id: UUID | None,
) -> EntityResolutionRow:
    """Orders only get a weak match: same customer + amount + delivery date.

    The catalog has no external order number column yet, so we never
    strong-match. When all three signals line up, we expose the existing
    order as a candidate but still default to create so the reviewer can
    decide consciously.
    """

    if customer_id is None:
        return _default_create("orders", row)

    amount = _to_decimal(_str_value(row, "amount_total"))
    delivery_date = _to_date(_str_value(row, "delivery_promised_date"))
    if amount is None or delivery_date is None:
        return _default_create("orders", row)

    existing = (
        await session.execute(
            select(Order).where(
                Order.customer_id == customer_id,
                Order.amount_total == amount,
                Order.delivery_promised_date == delivery_date,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return _default_create("orders", row)

    return EntityResolutionRow(
        table_name="orders",
        client_row_id=row.client_row_id,
        proposed_operation="create",
        match_level="weak",
        match_keys=["customer_id", "amount_total", "delivery_promised_date"],
        reason=(
            "existing order with same customer / amount / delivery date — "
            "defaulting to create with candidate"
        ),
        candidates=[
            EntityCandidate(
                entity_id=existing.id,
                label=f"order {existing.id}",
                match_level="weak",
                match_keys=["customer_id", "amount_total", "delivery_promised_date"],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strong_match_row(
    *,
    table_name: str,
    client_row_id: str,
    entity: Any,
    label: str,
    match_keys: list[str],
    reason: str | None,
) -> EntityResolutionRow:
    return EntityResolutionRow(
        table_name=table_name,
        client_row_id=client_row_id,
        proposed_operation="update",
        selected_entity_id=entity.id,
        match_level="strong",
        match_keys=match_keys,
        reason=reason,
        candidates=[
            EntityCandidate(
                entity_id=entity.id,
                label=label,
                match_level="strong",
                match_keys=match_keys,
            )
        ],
    )


def _default_create(table_name: str, row: NormalizedRow) -> EntityResolutionRow:
    return EntityResolutionRow(
        table_name=table_name,
        client_row_id=row.client_row_id,
        proposed_operation="create",
        match_level="none",
        match_keys=[],
        reason=None,
        candidates=[],
    )


def _str_value(row: NormalizedRow, field_name: str) -> str | None:
    field = row.fields.get(field_name)
    if field is None:
        return None
    value = field.value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_WHITESPACE_RE = re.compile(r"[\s　]+")


def _normalize_company_name(name: str) -> str:
    return _WHITESPACE_RE.sub("", name).strip().lower()


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(value: str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
