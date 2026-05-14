"""GET / POST /api/win/company-schema —— 公司 schema 目录对外接口。

挂载位置: ``yunwei_win.routes`` 把这个 router 注册进根 router，根 router 再
被 ``platform_app.main`` 挂在 ``/api/win``。所以最终 path 是:

- ``GET  /api/win/company-schema``
- ``POST /api/win/company-schema/change-proposals``
- ``POST /api/win/company-schema/change-proposals/{proposal_id}/approve``
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.services.company_schema import (
    approve_schema_change_proposal,
    create_schema_change_proposal,
    get_company_schema,
)

router = APIRouter(prefix="/company-schema")


@router.get("")
async def read_company_schema(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await get_company_schema(session)


@router.post("/change-proposals")
async def post_change_proposal(
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        return await create_schema_change_proposal(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/change-proposals/{proposal_id}/approve")
async def approve_change_proposal(
    proposal_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    reviewer = (payload or {}).get("reviewed_by") if isinstance(payload, dict) else None
    try:
        return await approve_schema_change_proposal(session, proposal_id, reviewer)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
