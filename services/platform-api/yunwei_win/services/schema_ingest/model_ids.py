"""Resolve the model id recorded on parse / extraction rows.

``provider`` (a separate column) says WHICH engine ran; ``model`` should say
which concrete model of that engine — useful for audit and for diffing quality
across model versions. A model surfaced in the provider's response metadata
wins; otherwise we fall back to the configured model id for that provider.
Deterministic parsers (text / docx / spreadsheet) have no model → None.
"""

from __future__ import annotations

from typing import Any

from yunwei_win.config import settings


def _from_metadata(metadata: Any) -> str | None:
    if isinstance(metadata, dict):
        model = metadata.get("model")
        if isinstance(model, str) and model:
            return model
    return None


def parse_model_id(provider: str, metadata: Any = None) -> str | None:
    return _from_metadata(metadata) or (
        settings.landingai_parse_model if provider == "landingai" else None
    )


def extraction_model_id(provider: str, metadata: Any = None) -> str | None:
    model = _from_metadata(metadata)
    if model:
        return model
    if provider == "landingai":
        return settings.landingai_extract_model
    if provider == "deepseek":
        # The complete-json LLM defaults to settings.model_parse (llm_adapter).
        return settings.model_parse
    return None
