"""Catalog 服务 —— 读取 / 种子 / 改 schema 元数据。

调用方:
- ``GET /api/win/company-schema``: ``get_company_schema``。
- Schema proposal API: ``create_schema_change_proposal`` /
  ``approve_schema_change_proposal``。
- ReviewDraft materializer（Agent B 写）: 也直接调 ``get_company_schema``。

幂等性:
- ``ensure_default_company_schema`` 用 ``(table_name, version=1)`` 作为 dedupe
  key。已存在的表不会被覆盖；列表里新增表会被补进去。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from yunwei_win.models.company_schema import (
    CompanySchemaField,
    CompanySchemaTable,
    SchemaChangeProposal,
)
from yunwei_win.services.company_schema.default_catalog import DEFAULT_COMPANY_SCHEMA


_VALID_PROPOSAL_TYPES = {"add_table", "add_field", "alter_field", "deactivate_field"}


async def ensure_default_company_schema(session: AsyncSession) -> None:
    """种子默认 schema。已存在 ``(table_name, version=1)`` 的表不动。

    幂等：可在每次 GET 前安全调用。
    """

    existing_names = set(
        (await session.execute(
            select(CompanySchemaTable.table_name).where(CompanySchemaTable.version == 1)
        )).scalars()
    )

    for table_idx, spec in enumerate(DEFAULT_COMPANY_SCHEMA):
        if spec["table_name"] in existing_names:
            continue
        table_is_array = bool(spec.get("is_array", False))
        table = CompanySchemaTable(
            table_name=spec["table_name"],
            label=spec["label"],
            purpose=spec.get("purpose"),
            category=spec["category"],
            version=1,
            is_active=True,
            sort_order=table_idx,
        )
        session.add(table)
        await session.flush()  # 拿到 table.id

        for field_idx, field_spec in enumerate(spec.get("fields", [])):
            session.add(
                CompanySchemaField(
                    table_id=table.id,
                    field_name=field_spec["field_name"],
                    label=field_spec["label"],
                    data_type=field_spec["data_type"],
                    required=bool(field_spec.get("required", False)),
                    # 数组型字段标记：要么字段自己声明 is_array，要么继承自表的
                    # ``is_array`` 标记（让整张数组表的每个字段都带这个旗标，
                    # 方便 ReviewDraft 拼装时偷懒查任何一列就知道）。
                    is_array=bool(field_spec.get("is_array", table_is_array)),
                    enum_values=field_spec.get("enum_values"),
                    default_value=field_spec.get("default_value"),
                    description=field_spec.get("description"),
                    extraction_hint=field_spec.get("extraction_hint"),
                    validation=field_spec.get("validation"),
                    sort_order=field_spec.get("sort_order", field_idx),
                    is_active=True,
                )
            )
        await session.flush()

    await session.commit()


def _field_to_dict(f: CompanySchemaField) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "field_name": f.field_name,
        "label": f.label,
        "data_type": f.data_type,
        "required": bool(f.required),
        "is_array": bool(f.is_array),
        "enum_values": f.enum_values,
        "default_value": f.default_value,
        "description": f.description,
        "extraction_hint": f.extraction_hint,
        "validation": f.validation,
        "sort_order": f.sort_order,
        "is_active": bool(f.is_active),
    }


def _table_to_dict(t: CompanySchemaTable) -> dict[str, Any]:
    active_fields = [f for f in t.fields if f.is_active]
    active_fields.sort(key=lambda f: (f.sort_order, f.field_name))
    return {
        "id": str(t.id),
        "table_name": t.table_name,
        "label": t.label,
        "purpose": t.purpose,
        "category": t.category,
        "version": t.version,
        "is_active": bool(t.is_active),
        "sort_order": t.sort_order,
        "fields": [_field_to_dict(f) for f in active_fields],
    }


async def get_company_schema(session: AsyncSession) -> dict[str, Any]:
    """返回当前租户的完整 catalog，已种子化。"""

    await ensure_default_company_schema(session)

    result = await session.execute(
        select(CompanySchemaTable)
        .where(CompanySchemaTable.is_active.is_(True))
        .options(selectinload(CompanySchemaTable.fields))
        .order_by(CompanySchemaTable.sort_order, CompanySchemaTable.table_name)
    )
    tables = result.scalars().all()
    return {"tables": [_table_to_dict(t) for t in tables]}


def _proposal_to_dict(p: SchemaChangeProposal) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "source_document_id": str(p.source_document_id) if p.source_document_id else None,
        "source_extraction_id": str(p.source_extraction_id) if p.source_extraction_id else None,
        "proposal_type": p.proposal_type,
        "table_name": p.table_name,
        "field_name": p.field_name,
        "proposed_payload": p.proposed_payload,
        "reason": p.reason,
        "status": p.status,
        "created_by": p.created_by,
        "reviewed_by": p.reviewed_by,
        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


async def create_schema_change_proposal(
    session: AsyncSession, payload: dict[str, Any]
) -> dict[str, Any]:
    """新建一条 pending 提案。"""

    proposal_type = payload.get("proposal_type")
    if proposal_type not in _VALID_PROPOSAL_TYPES:
        raise ValueError(
            f"invalid proposal_type {proposal_type!r}; "
            f"expected one of {sorted(_VALID_PROPOSAL_TYPES)}"
        )

    proposal = SchemaChangeProposal(
        source_document_id=_coerce_uuid(payload.get("source_document_id")),
        source_extraction_id=_coerce_uuid(payload.get("source_extraction_id")),
        proposal_type=proposal_type,
        table_name=payload.get("table_name"),
        field_name=payload.get("field_name"),
        proposed_payload=payload.get("proposed_payload") or {},
        reason=payload.get("reason"),
        status="pending",
        created_by=payload.get("created_by"),
    )
    session.add(proposal)
    await session.commit()
    await session.refresh(proposal)
    return _proposal_to_dict(proposal)


def _coerce_uuid(raw: Any) -> UUID | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


async def approve_schema_change_proposal(
    session: AsyncSession,
    proposal_id: UUID,
    reviewer: str | None = None,
) -> dict[str, Any]:
    """审批通过 —— 当前只实现 ``add_field``。其它类型暂时只改状态。"""

    proposal = (
        await session.execute(
            select(SchemaChangeProposal).where(SchemaChangeProposal.id == proposal_id)
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise LookupError(f"proposal {proposal_id} not found")

    if proposal.proposal_type == "add_field":
        await _apply_add_field(session, proposal)

    proposal.status = "applied"
    proposal.reviewed_by = reviewer
    proposal.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(proposal)
    return _proposal_to_dict(proposal)


async def _apply_add_field(session: AsyncSession, proposal: SchemaChangeProposal) -> None:
    if not proposal.table_name or not proposal.field_name:
        return

    table = (
        await session.execute(
            select(CompanySchemaTable)
            .where(
                CompanySchemaTable.table_name == proposal.table_name,
                CompanySchemaTable.version == 1,
            )
            .options(selectinload(CompanySchemaTable.fields))
        )
    ).scalar_one_or_none()
    if table is None:
        return

    if any(f.field_name == proposal.field_name for f in table.fields):
        # 同名字段已存在，幂等返回。
        return

    payload = proposal.proposed_payload or {}
    next_sort = max((f.sort_order for f in table.fields), default=-1) + 1

    session.add(
        CompanySchemaField(
            table_id=table.id,
            field_name=proposal.field_name,
            label=payload.get("label", proposal.field_name),
            data_type=payload.get("data_type", "text"),
            required=bool(payload.get("required", False)),
            is_array=bool(payload.get("is_array", False)),
            enum_values=payload.get("enum_values"),
            default_value=payload.get("default_value"),
            description=payload.get("description"),
            extraction_hint=payload.get("extraction_hint"),
            validation=payload.get("validation"),
            sort_order=payload.get("sort_order", next_sort),
            is_active=True,
        )
    )
    await session.flush()
