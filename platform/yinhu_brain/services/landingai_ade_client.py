"""Thin async wrapper around LandingAI ADE's synchronous Python client."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from landingai_ade import LandingAIADE

from yinhu_brain.config import settings


class LandingAIUnavailable(Exception):
    """LandingAI ADE is not configured or the upstream call failed."""


@dataclass
class LandingAIParseResult:
    markdown: str
    chunks: list[Any]
    metadata: dict[str, Any]
    grounding: dict[str, Any]
    splits: list[Any]


@dataclass
class LandingAIExtractResult:
    extraction: dict[str, Any]
    extraction_metadata: dict[str, Any]
    metadata: dict[str, Any]


def _client() -> LandingAIADE:
    key = settings.vision_agent_api_key.strip()
    if not key:
        raise LandingAIUnavailable("VISION_AGENT_API_KEY is not configured")
    os.environ.setdefault("VISION_AGENT_API_KEY", key)
    return LandingAIADE(environment=settings.landingai_environment)


async def parse_file_to_markdown(path: Path) -> LandingAIParseResult:
    def _run():
        client = _client()
        return client.parse(
            document=path,
            model=settings.landingai_parse_model,
        )

    try:
        response = await asyncio.to_thread(_run)
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI parse failed: {exc!s}") from exc

    return LandingAIParseResult(
        markdown=response.markdown or "",
        chunks=list(response.chunks or []),
        metadata=dict(response.metadata or {}),
        grounding=dict(response.grounding or {}),
        splits=list(response.splits or []),
    )


async def extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
    def _run():
        client = _client()
        return client.extract(
            schema=schema_json,
            markdown=markdown,
            model=settings.landingai_extract_model,
        )

    try:
        response = await asyncio.to_thread(_run)
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI extract failed: {exc!s}") from exc

    return LandingAIExtractResult(
        extraction=dict(response.extraction or {}),
        extraction_metadata=dict(response.extraction_metadata or {}),
        metadata=dict(response.metadata or {}),
    )
