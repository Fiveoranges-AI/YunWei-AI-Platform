"""OCR provider factory.

`get_ocr_provider` resolves the configured OCR provider. Pass `name` to
override the configured default (useful for tests). Unknown names raise
ValueError so the caller cannot silently fall through to a wrong provider.
"""

from __future__ import annotations

from yinhu_brain.config import settings

from .base import OcrProvider
from .mineru import MineruPreciseOcrProvider
from .mistral import MistralOcrProvider


def get_ocr_provider(name: str | None = None) -> OcrProvider:
    resolved = name if name is not None else settings.ocr_provider

    if resolved == "mistral":
        return MistralOcrProvider()
    if resolved == "mineru":
        return MineruPreciseOcrProvider()

    raise ValueError(f"unknown OCR provider: {resolved!r}")
