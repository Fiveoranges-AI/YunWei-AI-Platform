"""PDF utilities used by the contract ingest pipeline.

Three things:
- extract_text_with_pages: pypdf text per page so provenance can record source_page
- pdf_to_base64: encode whole file for Claude vision
- is_scanned: heuristic so the pipeline knows to lean harder on vision
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageText:
    page_num: int          # 1-indexed for human-friendly provenance
    text: str


def extract_text_with_pages(pdf_path: str | Path) -> list[PageText]:
    """Return per-page text (1-indexed). Empty pages keep their slot."""
    from pypdf import PdfReader

    p = Path(pdf_path)
    reader = PdfReader(BytesIO(p.read_bytes()))
    pages: list[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("pdf page %d extract failed: %s", i, exc)
            text = ""
        pages.append(PageText(page_num=i, text=text))
    return pages


def joined_text(pages: list[PageText]) -> str:
    """Join all page text with page-number markers — useful as a hint to the LLM."""
    out: list[str] = []
    for p in pages:
        if p.text.strip():
            out.append(f"[page {p.page_num}]\n{p.text}")
    return "\n\n".join(out)


def pdf_to_base64(pdf_path: str | Path) -> str:
    """Whole-file base64 for Anthropic `document` content blocks."""
    return base64.b64encode(Path(pdf_path).read_bytes()).decode("ascii")


def is_scanned(pages: list[PageText], threshold: int = 50) -> bool:
    """Roughly: <50 chars total of pypdf-extractable text → treat as scanned."""
    total = sum(len(p.text.strip()) for p in pages)
    return total < threshold
