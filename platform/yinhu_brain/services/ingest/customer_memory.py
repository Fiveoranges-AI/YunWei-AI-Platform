"""Customer-memory extraction.

Given (customer, input_blob, modality) → returns
CustomerMemoryExtractionResult. Used by the universal ingest endpoint to
fill an inbox row's `extracted_payload` JSONB.

Modality-specific upstream:
  text_note               → text → LLM (text-only call)
  image (wechat / card)   → image content block → LLM (vision)
  contract pdf            → run existing contract extractor first; pass
                            the structured contract dict to LLM as
                            "contract_extracted" hint so memory items
                            are derived from it
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.config import settings
from yinhu_brain.models import Contact, Contract, Customer, Order
from yinhu_brain.services.ingest.customer_memory_schema import (
    CUSTOMER_MEMORY_TOOL_NAME,
    CustomerMemoryExtractionResult,
    customer_memory_tool,
)
from yinhu_brain.services.llm import call_claude, extract_tool_use_input
from yinhu_brain.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_image_to_markdown,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)

from yinhu_brain.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("customer_memory_extraction.md")


async def _format_customer_profile(
    session: AsyncSession, customer: Customer
) -> str:
    """Compact view of what we already know — so the LLM doesn't repeat it."""
    contacts = (
        await session.execute(
            select(Contact).where(Contact.customer_id == customer.id)
        )
    ).scalars().all()
    orders = (
        await session.execute(
            select(Order).where(Order.customer_id == customer.id)
        )
    ).scalars().all()
    contracts = (
        await session.execute(
            select(Contract).where(
                Contract.order_id.in_([o.id for o in orders] or [None])
            )
        )
    ).scalars().all()

    lines = [f"customer.full_name = {customer.full_name}"]
    if customer.short_name:
        lines.append(f"customer.short_name = {customer.short_name}")
    if customer.address:
        lines.append(f"customer.address = {customer.address}")
    if customer.tax_id:
        lines.append(f"customer.tax_id = {customer.tax_id}")
    if contacts:
        lines.append(f"\n已知联系人 ({len(contacts)}):")
        for c in contacts[:10]:
            bits = [c.name]
            if c.title:
                bits.append(c.title)
            if c.mobile:
                bits.append(c.mobile)
            elif c.phone:
                bits.append(c.phone)
            if c.email:
                bits.append(c.email)
            lines.append(f"  - {' / '.join(bits)} ({c.role.value})")
    if contracts:
        lines.append(f"\n已知合同 ({len(contracts)}):")
        for k in contracts[:10]:
            line = f"  - {k.contract_no_external or '(无合同号)'}"
            if k.signing_date:
                line += f", 签订 {k.signing_date}"
            line += f", {len(k.payment_milestones or [])} 阶段付款"
            lines.append(line)
    if orders:
        lines.append(f"\n已知订单 ({len(orders)}):")
        for o in orders[:10]:
            amt = (
                f"{o.amount_currency} {float(o.amount_total):,.2f}"
                if o.amount_total is not None else "?"
            )
            lines.append(f"  - {amt}, 交期 {o.delivery_promised_date or '?'}")
    return "\n".join(lines)


def _media_type(filename: str, content_type: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return content_type
    ext = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "image/jpeg")


async def extract_customer_memory(
    *,
    session: AsyncSession,
    customer: Customer,
    document_id,
    modality: str,
    text_content: str | None = None,
    image_bytes: bytes | None = None,
    image_filename: str | None = None,
    image_content_type: str | None = None,
) -> CustomerMemoryExtractionResult:
    """Run the LLM call against the appropriate input modality + tool, then
    Pydantic-validate the result. Caller wraps it into an inbox row."""

    profile_text = await _format_customer_profile(session, customer)

    input_content = text_content or "(see attached image)"
    ocr_warnings: list[str] = []
    if image_bytes:
        try:
            ocr_text = await parse_image_to_markdown(
                image_bytes,
                image_filename or "image.jpg",
                image_content_type,
            )
        except MistralOCRUnavailable as exc:
            ocr_text = ""
            ocr_warnings.append(f"Mistral OCR unavailable: {exc!s}")
            logger.warning("customer memory OCR failed for %s: %s", image_filename, exc)
        if ocr_text:
            input_content = (
                "图片已附在本次请求中。\n\n"
                "Mistral OCR 识别文本（markdown）：\n"
                f"{ocr_text}"
            )

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        customer_profile=profile_text,
        input_modality=modality,
        input_content=input_content[:30000],
    )

    if image_bytes:
        media_type = _media_type(image_filename or "image.jpg", image_content_type)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        content_blocks: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            },
            {"type": "text", "text": prompt},
        ]
        model = settings.model_vision
    else:
        content_blocks = [{"type": "text", "text": prompt}]
        model = settings.model_parse

    messages = [{"role": "user", "content": content_blocks}]

    response = await call_claude(
        messages,
        purpose="customer_memory_extraction",
        session=session,
        model=model,
        tools=[customer_memory_tool()],
        tool_choice={"type": "tool", "name": CUSTOMER_MEMORY_TOOL_NAME},
        # DeepSeek v4-pro emits a long `thinking` block before the tool call;
        # 4 k easily gets consumed by thinking alone, leaving no budget for
        # the actual tool_use args. Match contract.py's 8192 to give the
        # tool call enough room after thinking.
        max_tokens=8192,
        document_id=document_id,
    )
    tool_input = extract_tool_use_input(response, CUSTOMER_MEMORY_TOOL_NAME)
    result = CustomerMemoryExtractionResult.model_validate(tool_input)
    if ocr_warnings:
        result.parse_warnings = ocr_warnings + list(result.parse_warnings)
    return result
