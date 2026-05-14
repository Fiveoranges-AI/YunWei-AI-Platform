"""Physical file type detection for vNext ingest.

Maps ``(filename, content_type, source_hint)`` to the source-type label
and the parser/extractor provider pair that should handle it. Purely
physical — no business-semantic guesses. Pasted text is a hard
short-circuit so the same uploader endpoint can carry both real files
and pasted snippets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

SourceType = Literal["pdf", "image", "pptx", "text", "docx", "spreadsheet"]
ParserProvider = Literal["landingai", "text", "docx", "spreadsheet"]
ExtractorProvider = Literal["landingai", "deepseek"]


@dataclass(frozen=True)
class DetectedSourceType:
    source_type: SourceType
    parser_provider: ParserProvider
    extractor_provider: ExtractorProvider


_TEXT_EXTS = {".txt", ".md", ".markdown"}
_TEXT_MIMES = {"text/plain", "text/markdown"}

_SPREADSHEET_EXTS = {".xlsx", ".xls", ".csv"}
_SPREADSHEET_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
}

_DOCX_EXTS = {".docx"}
_DOCX_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_PPTX_EXTS = {".pptx"}
_PPTX_MIMES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_PDF_EXTS = {".pdf"}
_PDF_MIMES = {"application/pdf"}


def detect_source_type(
    *,
    filename: str | None,
    content_type: str | None,
    source_hint: str | None,
) -> DetectedSourceType:
    """Resolve the physical source type and provider pair for an upload.

    ``source_hint == "pasted_text"`` always wins because the pasted-text
    uploader fabricates a ``.txt`` filename and a ``text/plain`` MIME
    that we should treat as authoritative for the text path.
    """

    if source_hint == "pasted_text":
        return DetectedSourceType("text", "text", "deepseek")

    ext = _ext(filename)
    ct = (content_type or "").lower().strip()

    if ext in _TEXT_EXTS or ct in _TEXT_MIMES:
        return DetectedSourceType("text", "text", "deepseek")

    if ext in _SPREADSHEET_EXTS or ct in _SPREADSHEET_MIMES:
        return DetectedSourceType("spreadsheet", "spreadsheet", "deepseek")

    if ext in _DOCX_EXTS or ct in _DOCX_MIMES:
        return DetectedSourceType("docx", "docx", "deepseek")

    if ext in _PPTX_EXTS or ct in _PPTX_MIMES:
        return DetectedSourceType("pptx", "landingai", "landingai")

    if ct.startswith("image/"):
        return DetectedSourceType("image", "landingai", "landingai")

    if ext in _PDF_EXTS or ct in _PDF_MIMES:
        return DetectedSourceType("pdf", "landingai", "landingai")

    raise ValueError(
        f"unsupported file type: filename={filename!r} content_type={content_type!r}"
    )


def _ext(filename: str | None) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower()
