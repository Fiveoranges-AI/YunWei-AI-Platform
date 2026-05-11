"""Evidence collection — the single OCR/text-normalization step.

Pipeline step 1: take raw input (file bytes, camera capture, or pasted text)
and produce a `(Document row, ocr_text)` tuple. Every downstream extractor
(identity / commercial / ops) reads the same `ocr_text`, so OCR runs exactly
once per input regardless of how many extractors fire later.

This module deliberately does *not* call any LLM and does *not* make
extraction decisions — those are Planner's and the extractors' jobs.

Modality detection lives here because each modality has a different OCR
path:
- ``text``   → no OCR; the caller-supplied string is the text
- ``image``  → Mistral OCR ``parse_image_to_markdown``
- ``pdf``    → pypdf per-page text first; Mistral OCR fallback for scans
- ``office`` → Mistral OCR ``parse_document_to_markdown``

The Document row is created with ``processing_status=parsed`` and
``review_status=pending_review`` so a downstream orchestrator can decide
whether confirm needs human review.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from yinhu_brain.models import (
    Document,
    DocumentProcessingStatus,
    DocumentReviewStatus,
    DocumentType,
)
from yinhu_brain.config import settings
from yinhu_brain.services import pdf as pdf_utils
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.landingai_ade_client import (
    LandingAIUnavailable,
    parse_file_to_markdown,
)
from yinhu_brain.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_document_to_markdown,
    parse_image_to_markdown,
    parse_pdf_to_markdown,
)
from yinhu_brain.services.storage import store_upload

logger = logging.getLogger(__name__)


Modality = Literal["image", "pdf", "office", "text"]
SourceHint = Literal["file", "camera", "pasted_text"]


# ---------- public dataclass ----------------------------------------------


@dataclass
class Evidence:
    """Result of a single ingest collection pass.

    The Document row is already in the session (added + flushed) so any
    downstream code can immediately reference ``document.id`` for FK columns
    (e.g. ``llm_calls.document_id``, ``field_provenance.document_id``).
    """

    document_id: uuid.UUID
    document: Document
    ocr_text: str
    modality: Modality
    warnings: list[str] = field(default_factory=list)


# ---------- modality detection -------------------------------------------


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif"}
_PDF_EXTS = {".pdf"}
_OFFICE_EXTS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".odt"}

_TEXT_MIN_CHARS = 20  # below this strip()ed length, we add a warning but don't fail


def _detect_modality(
    *,
    text_content: str | None,
    content_type: str | None,
    filename: str | None,
    source_hint: SourceHint,
) -> Modality:
    """Decide the modality. Priority: text > image > pdf > office (fallback).

    Camera input often arrives without a filename or content_type — the
    ``source_hint`` is the tiebreaker that keeps a phone snapshot from
    routing into the office-document OCR endpoint.
    """
    if text_content is not None:
        return "text"

    ct = (content_type or "").lower().split(";", 1)[0].strip()
    ext = Path(filename or "").suffix.lower()

    if ct.startswith("image/") or ext in _IMAGE_EXTS:
        return "image"
    if ct == "application/pdf" or ext in _PDF_EXTS:
        return "pdf"
    if ext in _OFFICE_EXTS:
        return "office"
    # No filename / content_type signal — the caller's source_hint decides
    # whether to treat raw bytes as an image (camera capture) or a generic
    # office-style document.
    if source_hint == "camera":
        return "image"
    # last resort: send through the document_url OCR endpoint
    return "office"


def _default_filename(modality: Modality, source_hint: SourceHint) -> str:
    if modality == "text":
        return "note.txt"
    if source_hint == "camera":
        return "capture.jpg"
    if modality == "image":
        return "image.jpg"
    if modality == "pdf":
        return "document.pdf"
    return "document.bin"


def _default_ext(modality: Modality, source_hint: SourceHint) -> str:
    if modality == "text":
        return ".txt"
    if source_hint == "camera" or modality == "image":
        return ".jpg"
    if modality == "pdf":
        return ".pdf"
    return ".bin"


def _default_content_type(modality: Modality, source_hint: SourceHint) -> str | None:
    if modality == "text":
        return "text/plain"
    if source_hint == "camera" or modality == "image":
        return "image/jpeg"
    if modality == "pdf":
        return "application/pdf"
    return None


def _document_type_for(modality: Modality) -> DocumentType:
    """Pick a DocumentType enum for the row.

    The spec is explicit that we do NOT add new enum values here — Agent G
    may refine. The mapping is the loosest legal one:
    - text     → text_note
    - image    → business_card (used as the generic image bucket for now)
    - pdf/office → contract (used as the generic document bucket for now)
    """
    if modality == "text":
        return DocumentType.text_note
    if modality == "image":
        return DocumentType.business_card
    return DocumentType.contract


# ---------- main entrypoint ----------------------------------------------


async def collect_evidence(
    *,
    session: AsyncSession,
    file_bytes: bytes | None = None,
    original_filename: str | None = None,
    content_type: str | None = None,
    text_content: str | None = None,
    source_hint: SourceHint,
    uploader: str | None = None,
    progress: ProgressCallback | None = None,
) -> Evidence:
    """Collect evidence: store original, run OCR (or take text), insert Document.

    Exactly one of ``file_bytes`` or ``text_content`` must be supplied (text
    takes precedence if both arrive). Empty input on both raises ValueError —
    everything else returns an Evidence with a possibly-empty ``ocr_text``
    plus warnings explaining what went wrong.
    """
    # ----- 1. Validate input -----------------------------------------
    has_text = text_content is not None and text_content.strip()
    has_file = file_bytes is not None and len(file_bytes) > 0

    if not has_text and not has_file:
        raise ValueError("no input: must supply non-empty text_content or file_bytes")

    # ----- 2. Decide modality ----------------------------------------
    modality = _detect_modality(
        # When text_content is supplied (even partial) it's a text note, not a file.
        # We keep the literal None vs "" distinction so a deliberate empty-string
        # text_content still routes here rather than trying to OCR file bytes.
        text_content=text_content if has_text else None,
        content_type=content_type,
        filename=original_filename,
        source_hint=source_hint,
    )

    warnings: list[str] = []

    # ----- 3. Persist original bytes (text included) ------------------
    # We always store *something* so audit / replay can find the original
    # exactly as received.
    if modality == "text":
        # text path: encode to UTF-8 and store under .txt
        assert text_content is not None  # narrowed above via has_text
        payload_bytes = text_content.encode("utf-8")
        filename_for_store = original_filename or _default_filename(modality, source_hint)
        ext_default = _default_ext(modality, source_hint)
        ct_for_doc = content_type or _default_content_type(modality, source_hint)
    else:
        # file path
        assert file_bytes is not None  # narrowed above via has_file
        payload_bytes = file_bytes
        filename_for_store = original_filename or _default_filename(modality, source_hint)
        ext_default = _default_ext(modality, source_hint)
        ct_for_doc = content_type or _default_content_type(modality, source_hint)

    stored = store_upload(
        payload_bytes,
        filename_for_store,
        default_ext=ext_default,
    )
    await emit_progress(progress, "stored", "原始内容已保存，开始读取文本")

    # ----- 4. Compute ocr_text ---------------------------------------
    ocr_text = ""

    if modality == "text":
        assert text_content is not None
        ocr_text = text_content.strip()
    else:
        # When the LandingAI provider is selected, run Parse first. LandingAI
        # Parse handles image, PDF, and office in a single API call, replacing
        # the Mistral image/pdf/office paths. We fall through to Mistral only
        # when LandingAI is unavailable or returns empty markdown — Mistral
        # remains the working fallback until the rollout is verified.
        if settings.document_ai_provider == "landingai":
            await emit_progress(
                progress, "landingai_parse", "正在调用 LandingAI Parse 解析文档"
            )
            try:
                parsed = await parse_file_to_markdown(Path(stored.path))
                ocr_text = parsed.markdown or ""
                if parsed.metadata:
                    warnings.append(f"LandingAI Parse metadata: {parsed.metadata}")
            except LandingAIUnavailable as exc:
                msg = f"LandingAI parse unavailable: {exc!s}"
                warnings.append(msg)
                logger.warning(
                    "landingai parse failed for %s: %s", filename_for_store, exc
                )

        if not ocr_text and modality == "image":
            await emit_progress(progress, "ocr", "正在调用 Mistral OCR 识别图片")
            try:
                ocr_text = await parse_image_to_markdown(
                    payload_bytes,
                    filename_for_store,
                    ct_for_doc,
                )
            except MistralOCRUnavailable as exc:
                msg = f"Mistral OCR unavailable: {exc!s}"
                warnings.append(msg)
                logger.warning("evidence image OCR failed for %s: %s", filename_for_store, exc)

        elif not ocr_text and modality == "pdf":
            # Native text first; only fall back to Mistral OCR when pypdf came
            # up empty (scanned PDF). If the text layer exists we trust it —
            # double-OCR'ing is slow and can paper over native text with model
            # transcription errors.
            await emit_progress(progress, "ocr", "正在读取 PDF 文本")
            pages = pdf_utils.extract_text_with_pages(stored.path)
            native_text = pdf_utils.joined_text(pages)
            if native_text.strip():
                ocr_text = native_text
            else:
                await emit_progress(progress, "ocr", "扫描件无文本层，正在调用 Mistral OCR")
                try:
                    md = await parse_pdf_to_markdown(payload_bytes, filename_for_store)
                    if md.strip():
                        ocr_text = md
                except MistralOCRUnavailable as exc:
                    msg = f"Mistral OCR unavailable: {exc!s}"
                    warnings.append(msg)
                    logger.warning("evidence pdf OCR failed for %s: %s", filename_for_store, exc)

        elif not ocr_text:  # office (and the unknown-fallback bucket)
            await emit_progress(progress, "ocr", "正在调用 Mistral OCR 识别文档")
            try:
                md = await parse_document_to_markdown(
                    payload_bytes,
                    filename_for_store,
                    ct_for_doc,
                )
                ocr_text = md or ""
            except MistralOCRUnavailable as exc:
                msg = f"Mistral OCR unavailable: {exc!s}"
                warnings.append(msg)
                logger.warning("evidence office OCR failed for %s: %s", filename_for_store, exc)

    # ----- 5. Soft warning when text is too short --------------------
    stripped_len = len(ocr_text.strip())
    if stripped_len < _TEXT_MIN_CHARS:
        warnings.append(
            f"extracted text is too short ({stripped_len} chars); "
            "downstream extractors may not have enough signal"
        )

    # ----- 6. Insert Document row ------------------------------------
    doc = Document(
        type=_document_type_for(modality),
        file_url=stored.path,
        original_filename=filename_for_store,
        content_type=ct_for_doc,
        file_sha256=stored.sha256,
        file_size_bytes=stored.size,
        ocr_text=ocr_text,
        uploader=uploader,
        processing_status=DocumentProcessingStatus.parsed,
        review_status=DocumentReviewStatus.pending_review,
        parse_warnings=list(warnings),
    )
    session.add(doc)
    await session.flush()

    return Evidence(
        document_id=doc.id,
        document=doc,
        ocr_text=ocr_text,
        modality=modality,
        warnings=warnings,
    )
