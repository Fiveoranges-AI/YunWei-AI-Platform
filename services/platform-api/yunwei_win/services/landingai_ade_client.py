"""Thin async wrapper around LandingAI ADE's synchronous Python client."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from landingai_ade import LandingAIADE

from yunwei_win.config import settings


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
    # SDK reads VISION_AGENT_API_KEY from env on its own, but pass apikey
    # explicitly so settings-only configuration (no env var) also works.
    return LandingAIADE(
        apikey=key,
        environment=settings.landingai_environment,
    )


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


async def parse_large_file_job(path: Path, *, poll_seconds: float = 5.0) -> LandingAIParseResult:
    """Submit a parse job for large documents and poll until completion.

    Use for documents likely to exceed LandingAI's synchronous parse limits
    (defaults to the page threshold ``settings.landingai_large_file_pages_threshold``,
    typically 50 pages). Not currently wired into the production pipeline —
    parse defaults to Mistral OCR; this wrapper is here so a later switch
    is small.
    """

    def _run():
        client = _client()
        job = client.parse_jobs.create(
            document=path,
            model=settings.landingai_parse_model,
        )
        while True:
            response = client.parse_jobs.get(job.job_id)
            if response.status == "completed":
                data = response.data
                return LandingAIParseResult(
                    markdown=data.markdown or "",
                    chunks=list(data.chunks or []),
                    metadata=dict(data.metadata or {}),
                    grounding=dict(data.grounding or {}),
                    splits=list(data.splits or []),
                )
            if response.status in {"failed", "error", "cancelled"}:
                raise LandingAIUnavailable(
                    f"LandingAI parse job {job.job_id} ended with {response.status}"
                )
            time.sleep(poll_seconds)

    try:
        return await asyncio.to_thread(_run)
    except LandingAIUnavailable:
        raise
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI parse job failed: {exc!s}") from exc
