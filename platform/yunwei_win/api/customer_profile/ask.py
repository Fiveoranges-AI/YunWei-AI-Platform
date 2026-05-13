"""POST /api/customers/{id}/ask — customer-scoped natural-language Q&A.

Loads only the target customer's KB (contacts, contracts, orders, events,
commitments, tasks, risks, memory, documents), hands it to Claude with a
forced ``submit_customer_ask_answer`` tool, and returns the structured
answer + citations. Prompt template lives in ``prompts/customer_ask.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.config import settings
from yunwei_win.db import get_session
from yunwei_win.models import (
    CommitmentStatus,
    Contact,
    Contract,
    Customer,
    CustomerCommitment,
    CustomerEvent,
    CustomerMemoryItem,
    CustomerRiskSignal,
    CustomerTask,
    Document,
    Order,
    RiskStatus,
    TaskStatus,
)
from yunwei_win.schemas.customer import (
    CustomerAskCitation,
    CustomerAskRequest,
    CustomerAskResponse,
)
from yunwei_win.services.llm import LLMCallFailed, call_claude, extract_tool_use_input

from yunwei_win.api.customer_profile._helpers import load_customer

logger = logging.getLogger(__name__)
router = APIRouter()


from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("customer_ask.md")
_TOOL_NAME = "submit_customer_ask_answer"
_KB_CHAR_BUDGET = 30_000


def _ask_tool() -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": "Submit a structured customer-scoped Q&A answer with citations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_type": {"type": "string"},
                            "target_id": {"type": "string"},
                            "snippet": {"type": ["string", "null"]},
                        },
                        "required": ["target_type", "target_id"],
                    },
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "no_relevant_info": {"type": "boolean"},
            },
            "required": ["answer", "confidence"],
        },
    }


async def _build_customer_kb(
    session: AsyncSession, customer: Customer
) -> str:
    """Compact text representation of a single customer's KB."""
    lines: list[str] = [f"[customer:{customer.id}] {customer.full_name}"]
    if customer.short_name:
        lines.append(f"  短名: {customer.short_name}")
    if customer.address:
        lines.append(f"  地址: {customer.address}")

    async def _scalars(stmt):
        return (await session.execute(stmt)).scalars().all()

    contacts = await _scalars(
        select(Contact).where(Contact.customer_id == customer.id)
    )
    if contacts:
        lines.append("\n联系人:")
        for c in contacts:
            bits = [f"[contact:{c.id}]", c.name, c.role.value]
            if c.title:
                bits.append(c.title)
            if c.mobile:
                bits.append(c.mobile)
            elif c.phone:
                bits.append(c.phone)
            if c.email:
                bits.append(c.email)
            lines.append("  " + " ".join(bits))

    orders = await _scalars(
        select(Order).where(Order.customer_id == customer.id)
    )
    contracts = []
    if orders:
        contracts = await _scalars(
            select(Contract).where(
                Contract.order_id.in_([o.id for o in orders])
            )
        )
    if contracts:
        lines.append("\n合同:")
        for k in contracts:
            line = f"  [contract:{k.id}] 合同号 {k.contract_no_external or '?'}"
            if k.signing_date:
                line += f", 签订 {k.signing_date}"
            lines.append(line)
            if k.payment_milestones:
                ms = " | ".join(
                    f"{m.get('name','?')} {int(round(m.get('ratio',0)*100))}% "
                    f"@{m.get('trigger_event','?')}"
                    for m in k.payment_milestones
                )
                lines.append(f"    付款: {ms}")
    if orders:
        lines.append("\n订单:")
        for o in orders:
            amt = (
                f"{o.amount_currency} {float(o.amount_total):,.2f}"
                if o.amount_total is not None else "?"
            )
            lines.append(
                f"  [order:{o.id}] {amt}, 交期 {o.delivery_promised_date or '?'}"
            )

    events = await _scalars(
        select(CustomerEvent)
        .where(CustomerEvent.customer_id == customer.id)
        .order_by(
            CustomerEvent.occurred_at.desc().nullslast(),
            CustomerEvent.created_at.desc(),
        )
        .limit(40)
    )
    if events:
        lines.append("\n客户动态:")
        for e in events:
            ts = (e.occurred_at or e.created_at).date().isoformat()
            lines.append(
                f"  [event:{e.id}] {ts} {e.event_type.value}: {e.title}"
            )

    commits = await _scalars(
        select(CustomerCommitment).where(
            CustomerCommitment.customer_id == customer.id,
            CustomerCommitment.status == CommitmentStatus.open,
        )
    )
    if commits:
        lines.append("\n未完成承诺:")
        for c in commits:
            due = c.due_date.isoformat() if c.due_date else "?"
            lines.append(
                f"  [commitment:{c.id}] {c.direction.value} | due {due}: {c.summary}"
            )

    tasks = await _scalars(
        select(CustomerTask).where(
            CustomerTask.customer_id == customer.id,
            CustomerTask.status.in_([TaskStatus.open, TaskStatus.in_progress]),
        )
    )
    if tasks:
        lines.append("\n待办:")
        for t in tasks:
            due = t.due_date.isoformat() if t.due_date else "?"
            lines.append(
                f"  [task:{t.id}] {t.priority.value} | due {due}: {t.title}"
            )

    risks = await _scalars(
        select(CustomerRiskSignal).where(
            CustomerRiskSignal.customer_id == customer.id,
            CustomerRiskSignal.status == RiskStatus.open,
        )
    )
    if risks:
        lines.append("\n风险线索:")
        for r in risks:
            lines.append(
                f"  [risk:{r.id}] {r.severity.value}/{r.kind.value}: {r.summary}"
            )

    mems = await _scalars(
        select(CustomerMemoryItem)
        .where(CustomerMemoryItem.customer_id == customer.id)
        .order_by(CustomerMemoryItem.created_at.desc())
        .limit(40)
    )
    if mems:
        lines.append("\n长期记忆:")
        for m in mems:
            lines.append(f"  [memory:{m.id}] {m.kind.value}: {m.content}")

    docs = await _scalars(
        select(Document)
        .where(Document.assigned_customer_id == customer.id)
        .order_by(Document.created_at.desc())
        .limit(20)
    )
    if docs:
        lines.append("\n相关文档:")
        for d in docs:
            lines.append(
                f"  [document:{d.id}] {d.type.value} {d.original_filename}"
            )

    return "\n".join(lines)[:_KB_CHAR_BUDGET]


@router.post(
    "/{customer_id}/ask", response_model=CustomerAskResponse
)
async def customer_ask(
    customer_id: UUID,
    payload: CustomerAskRequest,
    session: AsyncSession = Depends(get_session),
) -> CustomerAskResponse:
    cust = await load_customer(session, customer_id)
    kb = await _build_customer_kb(session, cust)

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        kb=kb, question=payload.question
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        response = await call_claude(
            messages,
            purpose="customer_ask",
            session=session,
            model=settings.model_qa,
            tools=[_ask_tool()],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            max_tokens=2000,
        )
    except LLMCallFailed as exc:
        raise HTTPException(502, f"upstream LLM error: {exc!s}") from exc
    finally:
        await session.commit()

    tool_input = extract_tool_use_input(response, _TOOL_NAME)

    citations: list[CustomerAskCitation] = []
    for c in tool_input.get("citations") or []:
        try:
            citations.append(CustomerAskCitation.model_validate(c))
        except Exception:
            continue

    return CustomerAskResponse(
        answer=tool_input.get("answer", ""),
        citations=citations,
        confidence=float(tool_input.get("confidence", 0.5)),
        no_relevant_info=bool(tool_input.get("no_relevant_info", False)),
    )
