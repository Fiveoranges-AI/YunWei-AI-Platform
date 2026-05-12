"""Extractor provider factory.

`get_extractor_provider` resolves the configured extractor provider. Pass
`name` to override the configured default (useful for tests). Unknown names
raise ValueError so the caller cannot silently fall through to a wrong
provider.
"""

from __future__ import annotations

from yinhu_brain.config import settings

from .base import ExtractorProvider
from .deepseek import DeepSeekSchemaExtractorProvider
from .landingai import LandingAIExtractorProvider


def get_extractor_provider(name: str | None = None) -> ExtractorProvider:
    resolved = name if name is not None else settings.extractor_provider

    if resolved == "landingai":
        return LandingAIExtractorProvider()
    if resolved == "deepseek":
        return DeepSeekSchemaExtractorProvider()

    raise ValueError(f"unknown extractor provider: {resolved!r}")
