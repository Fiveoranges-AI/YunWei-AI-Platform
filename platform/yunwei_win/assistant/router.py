"""POST /api/win/assistant/chat — shared assistant endpoint.

Mounted by ``yunwei_win`` under ``/api/win/assistant``. The middleware in
``platform_app.main`` has already attached ``request.state.auth_context``
for every ``/api/win/*`` request, so we read enterprise scope from there
and refuse to honour any tenant ID supplied in the request body.

Pro/Max enterprises with an ``assistant`` runtime binding are forwarded
to their dedicated runtime via :mod:`yunwei_win.assistant.dedicated`;
everyone else (trial / lite, or Pro without a binding, or a binding
flagged ``unhealthy``) goes through the shared QA service. A dedicated
runtime hiccup falls back transparently so a runtime outage never leaves
Pro users without an answer.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_app import runtime_registry
from platform_app.entitlements import entitlements_for
from yunwei_win.assistant.dedicated import (
    DedicatedRuntimeError,
    ask_dedicated_runtime,
)
from yunwei_win.assistant.service import answer_shared_assistant
from yunwei_win.db import get_session
from yunwei_win.services.llm import LLMCallFailed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant")


class AssistantChatRequest(BaseModel):
    """Client-supplied chat payload.

    Note: ``enterprise_id`` is deliberately **not** a field here. Tenant
    scope must come from the server-side ``AuthContext``; accepting it
    from the body would let any logged-in user impersonate another
    enterprise's data. ``extra="ignore"`` makes such fields a no-op
    instead of an error so legacy clients don't break.
    """

    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1, max_length=2000)
    customer_id: str | None = None


@router.post("/chat")
async def chat(
    payload: AssistantChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ctx = getattr(request.state, "auth_context", None)
    if ctx is None:
        # Belt-and-braces: middleware should have rejected this already,
        # but if /api/win/assistant ever moves we want a hard failure.
        raise HTTPException(
            status_code=401,
            detail={"error": "not_logged_in", "message": "请登录"},
        )
    ent = entitlements_for(ctx)
    if not ent.can_use_shared_assistant:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "assistant_not_enabled",
                "message": "当前套餐未开通问答",
            },
        )

    # Pro/Max: try the dedicated per-tenant runtime first. On any
    # transport / 5xx failure we fall back to the shared assistant so a
    # runtime hiccup never leaves Pro users without an answer. The
    # runtime endpoint URL stays server-side — the SPA never sees it.
    if ent.can_use_dedicated_runtime:
        runtime = runtime_registry.get_runtime_for(
            ctx.enterprise_id, "assistant"
        )
        if runtime is not None and runtime.health != "unhealthy":
            try:
                return await ask_dedicated_runtime(
                    runtime.endpoint_url,
                    question=payload.question,
                    customer_id=payload.customer_id,
                    user_id=ctx.user_id,
                )
            except DedicatedRuntimeError:
                # Log without the endpoint URL to keep infra details
                # out of error-tracking dashboards that ship to vendors.
                logger.warning(
                    "dedicated runtime unavailable for enterprise=%s, "
                    "falling back to shared assistant",
                    ctx.enterprise_id,
                )

    try:
        result = await answer_shared_assistant(
            session, payload.question, customer_id=payload.customer_id
        )
    except ValueError as exc:
        # _parse_customer_id rejects non-UUID, non-"all" inputs.
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_customer_id", "message": str(exc)},
        ) from exc
    except LLMCallFailed as exc:
        logger.exception("shared assistant LLM call failed")
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc

    await session.commit()
    return result
