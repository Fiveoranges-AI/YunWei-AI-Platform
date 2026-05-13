"""WeChat screenshot ingest.

Single Claude vision call → list of structured ChatMessages + business-relevant
extracted_entities + summary. Stored as Document (type=chat_log, raw_llm_response
holds the structured payload). No new tables — the Q&A path reads
``documents.raw_llm_response`` directly when answering chat-related questions.
"""

from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.models import Document, DocumentType
from yunwei_win.services.ingest.schemas import (
    WECHAT_TOOL_NAME,
    WeChatExtraction,
    wechat_tool,
)
from yunwei_win.config import settings
from yunwei_win.services.llm import call_claude, extract_tool_use_input
from yunwei_win.services.ingest.progress import ProgressCallback, emit_progress
from yunwei_win.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_image_to_markdown,
)
from yunwei_win.services.storage import store_upload

logger = logging.getLogger(__name__)

from yunwei_win.services.prompts import find_prompt

_PROMPT_PATH = find_prompt("wechat_screenshot_extraction.md")


@dataclass
class WeChatIngestResult:
    document_id: uuid.UUID
    message_count: int
    extracted_entity_count: int
    summary: str | None
    confidence_overall: float
    warnings: list[str] = field(default_factory=list)


def _media_type(filename: str, content_type: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return content_type
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


async def ingest_wechat_screenshot(
    *,
    session: AsyncSession,
    image_bytes: bytes,
    original_filename: str,
    content_type: str | None = None,
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
) -> WeChatIngestResult:
    file_path, sha, size = store_upload(
        image_bytes, original_filename, default_ext=".jpg"
    )
    await emit_progress(progress, "stored", "原始图片已保存，开始 OCR")

    doc = Document(
        type=DocumentType.chat_log,
        file_url=file_path,
        original_filename=original_filename,
        content_type=content_type,
        file_sha256=sha,
        file_size_bytes=size,
        uploader=uploader,
    )
    session.add(doc)
    await session.flush()

    media_type = _media_type(original_filename, content_type)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    ocr_text = ""
    ocr_warnings: list[str] = []
    await emit_progress(progress, "ocr", "正在调用 Mistral OCR 识别截图文字")
    try:
        ocr_text = await parse_image_to_markdown(
            image_bytes,
            original_filename,
            content_type,
        )
    except MistralOCRUnavailable as exc:
        ocr_warnings.append(f"Mistral OCR unavailable: {exc!s}")
        logger.warning("wechat screenshot OCR failed for %s: %s", original_filename, exc)
    if ocr_text:
        doc.ocr_text = ocr_text
        prompt = (
            prompt
            + "\n\n## Mistral OCR 识别文本\n"
            + "下面是 OCR 从截图中识别出的 markdown 文本。请结合图片和 OCR，优先用图片判断消息方向和顺序，"
              "用 OCR 辅助核对每条消息原文。\n\n"
            + ocr_text[:12000]
        )
    await session.flush()

    await emit_progress(progress, "extract", "OCR 完成，AI 正在抽取聊天内容")
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]
    response = await call_claude(
        messages,
        purpose="wechat_extraction",
        session=session,
        model=settings.model_vision,
        tools=[wechat_tool()],
        tool_choice={"type": "tool", "name": WECHAT_TOOL_NAME},
        max_tokens=4096,
        document_id=doc.id,
    )
    tool_input = extract_tool_use_input(response, WECHAT_TOOL_NAME)
    doc.raw_llm_response = tool_input
    await session.flush()

    result = WeChatExtraction.model_validate(tool_input)
    await emit_progress(progress, "persist", "正在保存截图解析结果")
    doc.parse_warnings = ocr_warnings + list(result.parse_warnings)
    await session.flush()

    return WeChatIngestResult(
        document_id=doc.id,
        message_count=len(result.messages),
        extracted_entity_count=len(result.extracted_entities),
        summary=result.summary,
        confidence_overall=result.confidence_overall,
        warnings=ocr_warnings + list(result.parse_warnings),
    )
