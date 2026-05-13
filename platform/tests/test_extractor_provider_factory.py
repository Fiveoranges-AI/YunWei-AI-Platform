"""Tests for the extractor provider factory.

Mirrors `test_ocr_provider_factory.py`. The project autouse fixture wants
Postgres + Redis; we override with a no-op because these tests don't touch
any DB.
"""

from __future__ import annotations

import pytest


# Override the project-level autouse fixture so we don't need Postgres.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004 — yield-only no-op replacement fixture
    yield


from pydantic import ValidationError

from yunwei_win.config import Settings, settings
from yunwei_win.services.ingest.extractors.providers.deepseek import (
    DeepSeekSchemaExtractorProvider,
)
from yunwei_win.services.ingest.extractors.providers.factory import (
    get_extractor_provider,
)
from yunwei_win.services.ingest.extractors.providers.landingai import (
    LandingAIExtractorProvider,
)


def test_get_extractor_provider_defaults_to_landingai(monkeypatch):
    from yunwei_win.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", "landingai")

    provider = get_extractor_provider()

    assert isinstance(provider, LandingAIExtractorProvider)


def test_get_extractor_provider_can_select_deepseek(monkeypatch):
    from yunwei_win.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", "deepseek")

    provider = get_extractor_provider()

    assert isinstance(provider, DeepSeekSchemaExtractorProvider)


def test_get_extractor_provider_explicit_name_overrides_setting(monkeypatch):
    from yunwei_win.services.ingest.extractors.providers import factory

    monkeypatch.setattr(factory.settings, "extractor_provider", "landingai")

    provider = get_extractor_provider("deepseek")

    assert isinstance(provider, DeepSeekSchemaExtractorProvider)


def test_get_extractor_provider_rejects_unknown_value():
    with pytest.raises(ValueError, match="unknown extractor provider"):
        get_extractor_provider("not-real")


def test_extractor_provider_default_is_landingai():
    assert settings.extractor_provider == "landingai"


def test_extractor_provider_setting_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(extractor_provider="bogus")  # type: ignore[arg-type]


def test_extractor_provider_setting_rejects_none():
    with pytest.raises(ValidationError):
        Settings(extractor_provider=None)  # type: ignore[arg-type]
