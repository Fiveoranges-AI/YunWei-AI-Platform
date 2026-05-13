"""Mistral Document AI OCR client.

The OCR API returns page-level markdown for PDFs and images. We call it with
base64 data URLs so uploaded customer files do not need to be made public.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from yunwei_win.config import settings

logger = logging.getLogger(__name__)


class MistralOCRUnavailable(Exception):
    """Mistral OCR is not configured or the upstream request failed."""


@dataclass
class OCRMarkdown:
    markdown: str
    payload: dict[str, Any]


def _media_type(filename: str, content_type: str | None, default: str) -> str:
    if content_type:
        return content_type
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(ext, default)


def _data_url(data: bytes, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def _markdown_from_payload(payload: dict[str, Any]) -> str:
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return ""
    chunks: list[str] = []
    for page in sorted(pages, key=lambda p: p.get("index", 0) if isinstance(p, dict) else 0):
        if not isinstance(page, dict):
            continue
        md = page.get("markdown")
        if isinstance(md, str) and md.strip():
            index = page.get("index")
            label = f"\n\n<!-- page {index} -->\n" if index is not None else "\n\n"
            chunks.append(label + md.strip())
    return "\n\n".join(chunks).strip()


async def _ocr(document: dict[str, Any], *, table_format: str | None) -> OCRMarkdown:
    token = settings.mistral_api_key.strip()
    if not token:
        return OCRMarkdown(markdown="", payload={})

    base_url = settings.mistral_base_url.strip().rstrip("/")
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(settings.mistral_ocr_timeout_seconds),
        write=120.0,
        pool=10.0,
    )
    payload: dict[str, Any] = {
        "model": settings.mistral_ocr_model,
        "document": document,
        "include_image_base64": False,
    }
    if table_format:
        payload["table_format"] = table_format

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            resp = await client.post(
                "/v1/ocr",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise MistralOCRUnavailable(f"mistral ocr unreachable: {exc!r}") from exc

    if resp.status_code >= 500:
        raise MistralOCRUnavailable(
            f"mistral ocr 5xx {resp.status_code}: {resp.text[:300]}"
        )
    if resp.status_code >= 400:
        raise MistralOCRUnavailable(
            f"mistral ocr 4xx {resp.status_code}: {resp.text[:300]}"
        )

    try:
        body = resp.json()
    except Exception as exc:
        raise MistralOCRUnavailable(
            f"mistral ocr non-JSON response: {resp.text[:200]}"
        ) from exc

    markdown = _markdown_from_payload(body)
    return OCRMarkdown(markdown=markdown, payload=body)


async def parse_document_to_markdown(
    document_bytes: bytes,
    filename: str = "doc.pdf",
    content_type: str | None = None,
) -> str:
    media_type = _media_type(filename, content_type, "application/octet-stream")
    result = await _ocr(
        {
            "type": "document_url",
            "document_url": _data_url(document_bytes, media_type),
        },
        table_format="markdown",
    )
    if result.markdown:
        logger.info("mistral ocr parsed document %s: %d chars", filename, len(result.markdown))
    return result.markdown


async def parse_pdf_to_markdown(pdf_bytes: bytes, filename: str = "doc.pdf") -> str:
    return await parse_document_to_markdown(
        pdf_bytes,
        filename,
        "application/pdf",
    )


async def parse_image_to_markdown(
    image_bytes: bytes,
    filename: str = "image.jpg",
    content_type: str | None = None,
) -> str:
    media_type = _media_type(filename, content_type, "image/jpeg")
    result = await _ocr(
        {
            "type": "image_url",
            "image_url": _data_url(image_bytes, media_type),
        },
        table_format=None,
    )
    if result.markdown:
        logger.info("mistral ocr parsed image %s: %d chars", filename, len(result.markdown))
    return result.markdown
