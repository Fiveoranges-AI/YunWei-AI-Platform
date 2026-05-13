"""Natural-language Q&A.

V1 strategy: KB dump + single Claude call with tool_use citations. No vector
search yet — small DB (50-200 customers, 100-500 contracts) fits in 30K-char
context budget. When DB grows we'll add a retrieval pre-stage.

Flow:
1. Load all customers (+ orders + contracts), recent chat_log Documents
2. Format into a structured text block with [customer:UUID]/[contract:UUID]/[document:UUID] anchors
3. Hand to Claude (Opus) with `submit_qa_answer` tool forced
4. Return {answer, citations, confidence, no_relevant_info}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import Contract, Customer, Document, DocumentType, Order
from yunwei_win.config import settings
from yunwei_win.services.ingest.schemas import QA_TOOL_NAME, qa_tool
from yunwei_win.services.llm import call_claude, extract_tool_use_input

logger = logging.getLogger(__name__)

from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("qa.md")

# Hard cap so we never blow context. Claude Opus 1M+ but we keep prompt < 30K
# chars for cost / latency.
_MAX_KB_CHARS = 30000


def _format_milestone(m: dict[str, Any]) -> str:
    pct = int(round(m.get("ratio", 0) * 100))
    pieces = [f"{m.get('name','?')} {pct}%"]
    if m.get("trigger_event"):
        pieces.append(f"@{m['trigger_event']}")
    if m.get("trigger_offset_days") is not None:
        pieces.append(f"+{m['trigger_offset_days']}d")
    return " ".join(pieces)


def _customer_block(c: Customer, orders: list[Order], contracts: list[Contract]) -> str:
    lines = [f"[customer:{c.id}] {c.full_name}"]
    if c.short_name:
        lines.append(f"  短名: {c.short_name}")
    if c.address:
        lines.append(f"  地址: {c.address}")

    for o in orders:
        amt = (
            f"{o.amount_currency} {float(o.amount_total):,.2f}"
            if o.amount_total is not None else "?"
        )
        delivery = (
            o.delivery_promised_date.isoformat()
            if o.delivery_promised_date else "?"
        )
        line = f"  [order:{o.id}] 总额 {amt}, 交期 {delivery}"
        if o.description:
            line += f", 内容: {o.description[:80]}"
        lines.append(line)

    for k in contracts:
        lines.append(f"  [contract:{k.id}] 合同号 {k.contract_no_external or '?'}")
        if k.signing_date:
            lines.append(f"    签订: {k.signing_date.isoformat()}")
        if k.payment_milestones:
            ms = " | ".join(_format_milestone(m) for m in k.payment_milestones)
            lines.append(f"    付款: {ms}")
        if k.delivery_terms:
            lines.append(f"    交付: {k.delivery_terms[:200]}")
        if k.confidence_overall is not None:
            lines.append(f"    解析自评 confidence: {k.confidence_overall:.2f}")

    return "\n".join(lines)


def _chat_block(d: Document) -> str:
    payload = d.raw_llm_response or {}
    title = payload.get("conversation_title") or "(无标题)"
    summary = payload.get("summary") or ""
    msg_count = len(payload.get("messages") or [])
    extracted = payload.get("extracted_entities") or []

    lines = [f"[document:{d.id}] chat_log [{title}] ({msg_count} 条消息) — {summary}"]
    if extracted:
        for ent in extracted[:10]:
            kind = ent.get("kind", "?")
            value = ent.get("value", "")
            lines.append(f"  - {kind}: {value}")
    return "\n".join(lines)


async def build_kb(session: AsyncSession) -> str:
    customers = (
        await session.execute(select(Customer).order_by(Customer.created_at.desc()))
    ).scalars().all()

    blocks: list[str] = []
    for c in customers:
        orders = (
            await session.execute(select(Order).where(Order.customer_id == c.id))
        ).scalars().all()
        contracts = (
            await session.execute(
                select(Contract).where(
                    Contract.order_id.in_([o.id for o in orders] or [None])
                )
            )
        ).scalars().all()
        blocks.append(_customer_block(c, list(orders), list(contracts)))

    chats = (
        await session.execute(
            select(Document)
            .where(Document.type == DocumentType.chat_log)
            .order_by(Document.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    if chats:
        blocks.append("--- 聊天记录 ---")
        for d in chats:
            blocks.append(_chat_block(d))

    if not blocks:
        return "(知识库为空，还没上传任何合同 / 文档。)"

    kb = "\n\n".join(blocks)
    if len(kb) > _MAX_KB_CHARS:
        # Trim oldest customers (kept newest first via ORDER BY)
        kb = kb[:_MAX_KB_CHARS] + "\n\n[...truncated due to context budget...]"
    return kb


async def answer_question(
    session: AsyncSession, question: str
) -> dict[str, Any]:
    kb = await build_kb(session)
    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        kb=kb, question=question
    )
    messages = [{"role": "user", "content": prompt}]
    response = await call_claude(
        messages,
        purpose="qa",
        session=session,
        model=settings.model_qa,
        tools=[qa_tool()],
        tool_choice={"type": "tool", "name": QA_TOOL_NAME},
        max_tokens=2000,
    )
    return extract_tool_use_input(response, QA_TOOL_NAME)
