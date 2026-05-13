"""POST /api/win/ask — natural-language Q&A."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.db import get_session
from yunwei_win.services.llm import LLMCallFailed
from yunwei_win.services.qa import answer_question

logger = logging.getLogger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/ask")
async def ask(
    payload: AskRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        result = await answer_question(session, payload.question)
    except LLMCallFailed as exc:
        logger.exception("ask LLM call failed")
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc

    await session.commit()  # commit the llm_calls audit row
    return result
