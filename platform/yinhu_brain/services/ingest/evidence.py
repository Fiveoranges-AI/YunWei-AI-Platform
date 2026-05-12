"""Evidence collection — the single OCR/text-normalization step.

Pipeline step 1: take raw input (file bytes, camera capture, or pasted text)
and produce a `(Document row, ocr_text)` tuple. Every downstream extractor
(identity / commercial / ops) reads the same `ocr_text`, so OCR runs exactly
once per input regardless of how many extractors fire later.

This module deliberately does *not* call any LLM and does *not* make
extraction decisions — those are Planner's and the extractors' jobs.

Modality detection lives here so the orchestrator can choose between
the text bypass and the configured OCR provider:
- ``text``   → no OCR; the caller-supplied string is the ``ocr_text``
- ``image`` / ``pdf`` / ``office`` → ``get_ocr_provider().parse(OcrInput(...))``;
  the provider owns modality-specific branching (native PDF text, scanned
  fallback, document_url, etc.)

The Document row is created with ``processing_status=parsed`` and
``review_status=pending_review`` so a downstream orchestrator can decide
whether confirm needs human review.
"""

from __future__ import annotations

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
from yinhu_brain.services.ingest.progress import ProgressCallback, emit_progress
from yinhu_brain.services.ocr import OcrInput, OcrResult, get_ocr_provider
from yinhu_brain.services.storage import (
    open_for_read,
    store_upload,
)


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


@dataclass
class PreStoredFile:
    """Descriptor for an upload the caller already persisted to storage.

    The async ``/jobs`` API stages files via ``store_upload`` before
    enqueueing the worker. Passing the resulting descriptor here skips the
    duplicate ``store_upload`` call inside ``collect_evidence`` while
    keeping the Document row in sync with whatever the API wrote.
    """

    path: str
    sha256: str
    size: int
    original_filename: str
    content_type: str | None = None


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
    pre_stored: PreStoredFile | None = None,
) -> Evidence:
    """Collect evidence: store original, run OCR (or take text), insert Document.

    Exactly one of ``file_bytes`` / ``text_content`` / ``pre_stored`` must be
    supplied (text takes precedence if both arrive). ``pre_stored`` indicates
    the caller already persisted the bytes via ``store_upload`` and only wants
    the OCR / Document steps to run. Empty input on all paths raises
    ValueError — everything else returns an Evidence with a possibly-empty
    ``ocr_text`` plus warnings explaining what went wrong.
    """
    # ----- 1. Validate input -----------------------------------------
    has_text = text_content is not None and text_content.strip()
    has_file = file_bytes is not None and len(file_bytes) > 0
    has_pre = pre_stored is not None

    if not has_text and not has_file and not has_pre:
        raise ValueError(
            "no input: must supply non-empty text_content, file_bytes, or pre_stored"
        )

    # If the caller pre-stored the file, surface the descriptor's metadata
    # into the local vars so modality detection and the Document row see
    # the same filename / content_type the original upload had.
    effective_filename = original_filename
    effective_content_type = content_type
    if has_pre:
        assert pre_stored is not None
        effective_filename = effective_filename or pre_stored.original_filename
        effective_content_type = effective_content_type or pre_stored.content_type

    # ----- 2. Decide modality ----------------------------------------
    modality = _detect_modality(
        # When text_content is supplied (even partial) it's a text note, not a file.
        # We keep the literal None vs "" distinction so a deliberate empty-string
        # text_content still routes here rather than trying to OCR file bytes.
        text_content=text_content if has_text else None,
        content_type=effective_content_type,
        filename=effective_filename,
        source_hint=source_hint,
    )

    warnings: list[str] = []

    # ----- 3. Persist original bytes (text included) ------------------
    # We always store *something* so audit / replay can find the original
    # exactly as received. Pre-stored callers (e.g. the /jobs worker) skip
    # the store_upload round-trip but still need ``payload_bytes`` for OCR
    # paths that take raw bytes (image / office / scanned PDF).
    if modality == "text":
        # text path: encode to UTF-8 and store under .txt
        assert text_content is not None  # narrowed above via has_text
        payload_bytes = text_content.encode("utf-8")
        filename_for_store = effective_filename or _default_filename(modality, source_hint)
        ext_default = _default_ext(modality, source_hint)
        ct_for_doc = effective_content_type or _default_content_type(modality, source_hint)
        stored_path = None
        stored_sha = None
        stored_size = None
    elif has_pre:
        # pre-stored path: file already on disk; rehydrate bytes only if the
        # modality's OCR step needs them.
        assert pre_stored is not None
        filename_for_store = effective_filename or _default_filename(modality, source_hint)
        ext_default = _default_ext(modality, source_hint)
        ct_for_doc = effective_content_type or _default_content_type(modality, source_hint)
        stored_path = pre_stored.path
        stored_sha = pre_stored.sha256
        stored_size = pre_stored.size
        needs_bytes = modality in ("image", "office") or (
            modality == "pdf" and not file_bytes
        )
        if file_bytes:
            payload_bytes = file_bytes
        elif needs_bytes:
            try:
                payload_bytes = open_for_read(pre_stored.path)
            except FileNotFoundError as exc:
                raise ValueError(
                    f"pre_stored file not found: {pre_stored.path}"
                ) from exc
        else:
            # PDF native-text path reads the file directly via pypdf; no need
            # to load bytes here.
            payload_bytes = b""
    else:
        # file path
        assert file_bytes is not None  # narrowed above via has_file
        payload_bytes = file_bytes
        filename_for_store = effective_filename or _default_filename(modality, source_hint)
        ext_default = _default_ext(modality, source_hint)
        ct_for_doc = effective_content_type or _default_content_type(modality, source_hint)
        stored_path = None
        stored_sha = None
        stored_size = None

    if has_pre and modality != "text":
        # No store_upload needed — the API already wrote the file.
        await emit_progress(progress, "stored", "复用已上传文件，开始读取文本")
    else:
        stored = store_upload(
            payload_bytes,
            filename_for_store,
            default_ext=ext_default,
        )
        stored_path = stored.path
        stored_sha = stored.sha256
        stored_size = stored.size
        await emit_progress(progress, "stored", "原始内容已保存，开始读取文本")

    # ----- 4. Compute ocr_text ---------------------------------------
    ocr_text = ""

    if modality == "text":
        # Text bypass: no OCR provider is invoked. The pasted string IS the
        # ``ocr_text`` (stripped) — downstream extractors read the same field
        # regardless of input modality.
        assert text_content is not None
        ocr_text = text_content.strip()
    else:
        if modality == "image":
            await emit_progress(progress, "ocr", "正在识别图片文本")
        elif modality == "pdf":
            await emit_progress(progress, "ocr", "正在读取 PDF 文本")
        else:
            await emit_progress(progress, "ocr", "正在识别文档文本")

        # ``source_hint`` in ``OcrInput`` is narrower than the orchestrator's
        # ("pasted_text" is impossible here because we already bypassed text).
        provider_hint = "camera" if source_hint == "camera" else "file"
        ocr_result: OcrResult = await get_ocr_provider().parse(
            OcrInput(
                file_bytes=payload_bytes,
                stored_path=stored_path,
                filename=filename_for_store,
                content_type=ct_for_doc,
                modality=modality,
                source_hint=provider_hint,
            )
        )
        ocr_text = ocr_result.markdown or ""
        warnings.extend(ocr_result.warnings)

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
        file_url=stored_path,
        original_filename=filename_for_store,
        content_type=ct_for_doc,
        file_sha256=stored_sha,
        file_size_bytes=stored_size,
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
