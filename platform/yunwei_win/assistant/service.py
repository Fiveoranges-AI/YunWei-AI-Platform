"""Routing layer between the shared assistant endpoint and existing Q&A.

``answer_shared_assistant`` is the single entry point: it dispatches to
the cross-customer KB helper or the per-customer KB helper depending on
``customer_id``. We deliberately reuse the existing functions instead of
re-implementing knowledge-base construction here — Task 5 only adds an
endpoint, not a new prompt or retrieval strategy.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.api.customer_profile.ask import answer_customer_question
from yunwei_win.services.qa import answer_question


def _parse_customer_id(raw: str | None) -> UUID | None:
    """Return a UUID for single-customer scope, or None for shared scope.

    ``None`` and the sentinel ``"all"`` both mean "cross-customer". Any
    other non-UUID value is rejected with ``ValueError`` so the router
    can map it to a 400.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s or s.lower() == "all":
        return None
    return UUID(s)


async def answer_shared_assistant(
    session: AsyncSession,
    question: str,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Dispatch a shared-assistant question.

    - ``customer_id`` is None / "all" → cross-customer KB via
      :func:`yunwei_win.services.qa.answer_question`.
    - ``customer_id`` is a UUID string → single-customer KB via
      :func:`yunwei_win.api.customer_profile.ask.answer_customer_question`.

    Returns the front-end-compatible shape::

        {"answer": str, "citations": [...], "confidence": float,
         "no_relevant_info": bool}
    """
    target = _parse_customer_id(customer_id)
    if target is None:
        return await answer_question(session, question)
    return await answer_customer_question(session, target, question)
