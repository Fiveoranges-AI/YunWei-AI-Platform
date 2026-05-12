"""Tests for the OCR provider factory.

The project autouse fixture wants Postgres + Redis; we override with a no-op
because these tests don't touch any DB.
"""

from __future__ import annotations

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from yinhu_brain.config import settings
from yinhu_brain.services.ocr.factory import get_ocr_provider
from yinhu_brain.services.ocr.mineru import MineruPreciseOcrProvider
from yinhu_brain.services.ocr.mistral import MistralOcrProvider


def test_get_ocr_provider_defaults_to_mistral(monkeypatch):
    from yinhu_brain.services.ocr import factory

    monkeypatch.setattr(factory.settings, "ocr_provider", "mistral")

    provider = get_ocr_provider()

    assert isinstance(provider, MistralOcrProvider)


def test_get_ocr_provider_can_select_mineru(monkeypatch):
    from yinhu_brain.services.ocr import factory

    monkeypatch.setattr(factory.settings, "ocr_provider", "mineru")

    provider = get_ocr_provider()

    assert isinstance(provider, MineruPreciseOcrProvider)


def test_get_ocr_provider_rejects_unknown_value():
    with pytest.raises(ValueError, match="unknown OCR provider"):
        get_ocr_provider("not-real")


def test_extractor_provider_default_is_landingai():
    assert settings.extractor_provider == "landingai"
