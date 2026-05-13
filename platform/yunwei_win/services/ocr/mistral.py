"""Mistral OCR provider.

Wraps the existing ``mistral_ocr_client`` helpers behind the ``OcrProvider``
contract so the ingest orchestrator does not branch per modality. Behavior
mirrors what used to live inline in ``evidence.py``:

- ``image``  → ``parse_image_to_markdown``
- ``pdf``    → native text via ``pdf_utils`` first; Mistral OCR fallback for
               scanned PDFs (no text layer)
- ``office`` (and any other modality this provider sees) → ``parse_document_to_markdown``

`MistralOCRUnavailable` is converted into a warning on ``OcrResult`` rather
than re-raised so the orchestrator can still create a ``Document`` row with
the warning attached — same behavior the inline code previously had.
"""

from __future__ import annotations

import logging

from yunwei_win.services import pdf as pdf_utils
from yunwei_win.services.mistral_ocr_client import (
    MistralOCRUnavailable,
    parse_document_to_markdown,
    parse_image_to_markdown,
    parse_pdf_to_markdown,
)
from yunwei_win.services.storage import materialize_to_local, open_for_read

from .base import OcrInput, OcrProvider, OcrResult

logger = logging.getLogger(__name__)


class MistralOcrProvider(OcrProvider):
    async def parse(self, input: OcrInput) -> OcrResult:
        if input.modality == "image":
            return await self._parse_image(input)
        if input.modality == "pdf":
            return await self._parse_pdf(input)
        # ``office`` and any fallback modality go through the document_url
        # endpoint, matching the previous ``else`` branch in evidence.py.
        return await self._parse_office(input)

    async def _parse_image(self, input: OcrInput) -> OcrResult:
        try:
            markdown = await parse_image_to_markdown(
                input.file_bytes,
                input.filename,
                input.content_type,
            )
            return OcrResult(markdown=markdown or "", provider="mistral")
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral image OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])

    async def _parse_pdf(self, input: OcrInput) -> OcrResult:
        # Native text first; only fall back to Mistral OCR when pypdf came
        # up empty (scanned PDF). If the text layer exists we trust it —
        # double-OCR'ing is slow and can paper over native text with model
        # transcription errors.
        local_pdf = materialize_to_local(input.stored_path)
        pages = pdf_utils.extract_text_with_pages(str(local_pdf))
        native_text = pdf_utils.joined_text(pages)
        if native_text.strip():
            return OcrResult(
                markdown=native_text,
                provider="mistral",
                metadata={"pdf_text_source": "native"},
            )

        # Pre-stored callers may have skipped the byte-load when the native
        # text path was expected to succeed; load on demand for the OCR
        # fallback so we don't penalize the happy path.
        ocr_bytes = input.file_bytes
        if not ocr_bytes and input.stored_path:
            try:
                ocr_bytes = open_for_read(input.stored_path)
            except FileNotFoundError as exc:
                msg = f"pre_stored pdf missing on fallback: {exc!s}"
                return OcrResult(markdown="", provider="mistral", warnings=[msg])

        try:
            markdown = await parse_pdf_to_markdown(ocr_bytes, input.filename)
            return OcrResult(
                markdown=markdown or "",
                provider="mistral",
                metadata={"pdf_text_source": "mistral_ocr"},
            )
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral pdf OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])

    async def _parse_office(self, input: OcrInput) -> OcrResult:
        try:
            markdown = await parse_document_to_markdown(
                input.file_bytes,
                input.filename,
                input.content_type,
            )
            return OcrResult(markdown=markdown or "", provider="mistral")
        except MistralOCRUnavailable as exc:
            msg = f"Mistral OCR unavailable: {exc!s}"
            logger.warning("mistral office OCR failed for %s: %s", input.filename, exc)
            return OcrResult(markdown="", provider="mistral", warnings=[msg])
