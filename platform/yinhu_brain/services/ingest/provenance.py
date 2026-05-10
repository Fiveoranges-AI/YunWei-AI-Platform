"""Write field_provenance rows from a ContractExtractionResult.

Walks `result.field_provenance` (flat list of {path, source_page, source_excerpt}),
resolves each path to a (entity_type, entity_id, value, confidence) tuple, then
upserts a FieldProvenance row. Also runs a substring-match check: if
`source_excerpt` is not found in the document's ocr_text, the row is flagged
`excerpt_match=False`, confidence is reduced by 0.2, and a parse warning is added.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.models import EntityType, FieldProvenance
from yinhu_brain.services.ingest.schemas import (
    ContractExtractionResult,
    FieldProvenanceEntry,
)


_INDEX_RE = re.compile(r"\[(\d+)\]")


def _resolve_path(result: ContractExtractionResult, path: str) -> Any:
    """Walk dotted path with optional [N] indices on a Pydantic tree."""
    obj: Any = result
    parts = path.split(".")
    for part in parts:
        m = _INDEX_RE.search(part)
        if m:
            attr = part[: m.start()]
            idx = int(m.group(1))
            obj = getattr(obj, attr, None)
            if obj is None:
                return None
            try:
                obj = obj[idx]
            except (IndexError, TypeError):
                return None
        else:
            obj = getattr(obj, part, None)
            if obj is None:
                return None
    return obj


def _entity_for_path(
    path: str,
    *,
    customer_id: uuid.UUID,
    order_id: uuid.UUID,
    contract_id: uuid.UUID,
    contact_ids: list[uuid.UUID | None],
) -> tuple[EntityType, uuid.UUID] | None:
    """Return (entity_type, id) or None if the path doesn't resolve.

    `contact_ids` is positional and may contain None placeholders for contacts
    we filtered out (e.g. nameless ones). A None at the index means "the LLM
    saw this slot but we chose not to persist it" — the caller should drop
    those provenance rows silently rather than warning.
    """
    if path.startswith("customer."):
        return EntityType.customer, customer_id
    if path.startswith("order."):
        return EntityType.order, order_id
    if path.startswith("contract."):
        return EntityType.contract, contract_id
    if path.startswith("contacts["):
        m = _INDEX_RE.search(path.split(".")[0])
        if not m:
            return None
        idx = int(m.group(1))
        if idx >= len(contact_ids):
            return None
        cid = contact_ids[idx]
        if cid is None:  # contact at this slot was filtered out — silent drop
            return None
        return EntityType.contact, cid
    return None


def _normalize_for_match(s: str) -> str:
    """Normalize whitespace for substring matching — pypdf often inserts random spaces."""
    return re.sub(r"\s+", "", s)


def _value_to_jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "value"):  # Enum
        return v.value
    if isinstance(v, list):
        return [_value_to_jsonable(x) for x in v]
    if hasattr(v, "model_dump"):
        return v.model_dump(mode="json")
    return str(v)


async def write_provenance(
    *,
    session: AsyncSession,
    document_id: uuid.UUID,
    result: ContractExtractionResult,
    customer_id: uuid.UUID,
    order_id: uuid.UUID,
    contract_id: uuid.UUID,
    contact_ids: list[uuid.UUID | None],
    ocr_text: str,
    extracted_by: str,
) -> list[str]:
    """Insert provenance rows. Returns list of warnings (excerpt mismatches).

    `contact_ids` may contain None placeholders for contacts we filtered out;
    provenance rows pointing at those slots are dropped silently.
    """
    warnings: list[str] = []
    ocr_normalized = _normalize_for_match(ocr_text or "")

    for entry in result.field_provenance:
        target = _entity_for_path(
            entry.path,
            customer_id=customer_id,
            order_id=order_id,
            contract_id=contract_id,
            contact_ids=contact_ids,
        )
        if target is None:
            # Two cases lump together here:
            #   (a) genuinely unknown prefix → noise worth flagging
            #   (b) contacts[N] where slot N was filtered (None placeholder)
            # Distinguish by re-checking the path; (b) is the boring case.
            if entry.path.startswith("contacts["):
                continue  # contact filtered, no warning
            warnings.append(f"unknown entity prefix in path: {entry.path}")
            continue
        entity_type, entity_id = target

        value = _resolve_path(result, entry.path)
        confidence = result.field_confidence.get(entry.path)

        excerpt_match: bool | None = None
        if entry.source_excerpt:
            excerpt_norm = _normalize_for_match(entry.source_excerpt)
            excerpt_match = excerpt_norm in ocr_normalized
            if not excerpt_match:
                if confidence is not None:
                    confidence = max(0.0, confidence - 0.2)
                warnings.append(
                    f"source_excerpt for {entry.path!r} not found in OCR text "
                    f"(possibly LLM hallucination or vision-only content)"
                )

        await upsert_field_provenance(
            session,
            document_id=document_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=entry.path,
            value=_value_to_jsonable(value),
            source_page=entry.source_page,
            source_excerpt=entry.source_excerpt,
            confidence=confidence,
            excerpt_match=excerpt_match,
            extracted_by=extracted_by,
        )

    return warnings


async def upsert_field_provenance(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    field_name: str,
    value: Any,
    source_page: int | None,
    source_excerpt: str | None,
    confidence: float | None,
    excerpt_match: bool | None,
    extracted_by: str | None,
) -> None:
    """Insert-or-update a FieldProvenance row keyed by the unique tuple
    (document_id, entity_type, entity_id, field_name). Portable across
    Postgres and SQLite."""
    existing = (
        await session.execute(
            select(FieldProvenance).where(
                FieldProvenance.document_id == document_id,
                FieldProvenance.entity_type == entity_type,
                FieldProvenance.entity_id == entity_id,
                FieldProvenance.field_name == field_name,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(FieldProvenance(
            document_id=document_id,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            value=value,
            source_page=source_page,
            source_excerpt=source_excerpt,
            confidence=confidence,
            excerpt_match=excerpt_match,
            extracted_by=extracted_by,
        ))
    else:
        existing.value = value
        existing.source_page = source_page
        existing.source_excerpt = source_excerpt
        existing.confidence = confidence
        existing.excerpt_match = excerpt_match
        existing.extracted_by = extracted_by
