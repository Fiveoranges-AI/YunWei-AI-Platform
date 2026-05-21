"""Confirm-card API — candidate JSON → ontology writeback.

Mounted under ``/api/win/confirm``. Powers the P0 task ③ frontend cards:
the user confirms (and optionally edits) parsed entities, this endpoint
writes them into the per-tenant Postgres with full audit stamps and
emits an ActionLog row per entity.

Endpoints:

  * ``POST /confirm/entities``  — write confirmed candidate to ontology.

The request body is a thin Pydantic wrapper around the
``ConfirmRequest`` dataclass from ``services.confirm_writer``. The
writer raises ``ConfirmFieldError`` / ``ConfirmRelationshipError`` which
this handler maps to 400.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.services.confirm_writer import (
    ConfirmFieldError,
    ConfirmRelationshipError,
    ConfirmRequest,
    ConfirmedEntity,
    ConfirmedField,
    ConfirmedRelationship,
    confirm_candidate,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/confirm")


# ---- request / response shapes ---------------------------------------


class ConfirmFieldIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    value: Any | None = None
    confidence: float | None = None
    was_edited: bool = False
    source_span: dict[str, Any] | None = None


class ConfirmEntityIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_type: str
    temp_id: str
    fields: list[ConfirmFieldIn] = Field(default_factory=list)
    # If the user resolved a duplicate warning by associating with an
    # existing row, the id goes here; the writer skips re-creation.
    existing_entity_id: UUID | None = None


class ConfirmRelationshipIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    from_temp_id: str
    to_temp_id: str
    type: str


class ConfirmEntitiesRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ingestion_id: str
    source_type: str
    source_ref: str = ""
    entities: list[ConfirmEntityIn] = Field(default_factory=list)
    relationships: list[ConfirmRelationshipIn] = Field(default_factory=list)


class WrittenEntityOut(BaseModel):
    temp_id: str
    entity_type: str
    entity_id: UUID
    created: bool
    human_verified: bool
    verified_by: str
    field_count: int
    edited_field_count: int


class ConfirmEntitiesResponse(BaseModel):
    written: list[WrittenEntityOut]
    action_log_ids: list[UUID]


# ---- handler --------------------------------------------------------


def _actor_from_request(request: Request) -> str:
    """Best-effort actor identity for the audit stamp.

    Platform middleware sets ``request.state.user`` (a TypedDict with
    ``id``/``username``) on authenticated requests. In dev / tests an
    override may set just ``request.state.actor`` as a string. Falls
    back to ``"unknown"`` so the writer never sees an empty value.
    """
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, str) and actor:
        return actor
    user = getattr(request.state, "user", None)
    if isinstance(user, dict):
        for key in ("id", "username", "display_name"):
            val = user.get(key)
            if isinstance(val, str) and val:
                return val
    return "unknown"


@router.post("/entities", response_model=ConfirmEntitiesResponse)
async def confirm_entities(
    request: Request,
    payload: ConfirmEntitiesRequest,
    session: AsyncSession = Depends(get_session),
) -> ConfirmEntitiesResponse:
    """Write a human-confirmed candidate batch into the ontology tables."""

    if not payload.entities:
        raise HTTPException(status_code=400, detail="entities is empty")

    actor = _actor_from_request(request)

    confirm_req = ConfirmRequest(
        ingestion_id=payload.ingestion_id,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        actor=actor,
        entities=[
            ConfirmedEntity(
                entity_type=e.entity_type,
                temp_id=e.temp_id,
                fields=[
                    ConfirmedField(
                        name=f.name,
                        value=f.value,
                        confidence=f.confidence,
                        was_edited=f.was_edited,
                        source_span=f.source_span,
                    )
                    for f in e.fields
                ],
                existing_entity_id=e.existing_entity_id,
            )
            for e in payload.entities
        ],
        relationships=[
            ConfirmedRelationship(
                from_temp_id=r.from_temp_id,
                to_temp_id=r.to_temp_id,
                type=r.type,
            )
            for r in payload.relationships
        ],
    )

    try:
        async with session.begin():
            result = await confirm_candidate(confirm_req, session)
    except ConfirmFieldError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ConfirmRelationshipError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.info(
        "confirm.entities.done ingestion=%s actor=%s written=%d action_logs=%d",
        payload.ingestion_id, actor, len(result.written), len(result.action_log_ids),
    )

    return ConfirmEntitiesResponse(
        written=[
            WrittenEntityOut(
                temp_id=w.temp_id,
                entity_type=w.entity_type,
                entity_id=w.entity_id,
                created=w.created,
                human_verified=w.human_verified,
                verified_by=w.verified_by,
                field_count=w.field_count,
                edited_field_count=w.edited_field_count,
            )
            for w in result.written
        ],
        action_log_ids=result.action_log_ids,
    )
