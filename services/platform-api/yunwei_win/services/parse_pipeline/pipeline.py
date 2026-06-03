"""Unified entry point: dispatch by source_type to the right adapter."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal

from yunwei_win.services.parse_pipeline.adapters import (
    parse_contract,
    parse_excel,
    parse_screenshot,
)
from yunwei_win.services.parse_pipeline.candidate import CandidateJSON
from yunwei_win.services.parse_pipeline.providers.base import ExtractionProvider


logger = logging.getLogger(__name__)


SourceType = Literal["contract", "wechat_screenshot", "excel"]


async def parse_to_candidates(
    *,
    file_path: Path,
    source_type: SourceType,
    filename: str | None = None,
    content_type: str | None = None,
    provider: ExtractionProvider | None = None,
    file_ref: str = "",
    uploaded_by: str | None = None,
    existing_customer_names: list[str] | None = None,
) -> CandidateJSON:
    """Run the parse pipeline for one file.

    ``provider`` is required for ``contract`` and ``wechat_screenshot``
    (they need an LLM); ``excel`` ignores it. Tests should pass a
    ``MockProvider`` so no upstream calls happen.

    ``existing_customer_names`` is consumed only by the Excel adapter
    today (the contract / screenshot adapters surface dedup hints via
    the LLM warnings). Passing the list keeps the dedup-warning
    contract uniform from the caller's perspective.

    Emits structured info-level log on completion: ``parse_pipeline.done``
    with source_type, filename, entity_count, overall_confidence,
    duration_ms — single line per run, suitable for ELK ingestion.
    """
    filename = filename or file_path.name
    t0 = time.monotonic()

    if source_type == "excel":
        result = await parse_excel(
            file_path=file_path,
            filename=filename,
            content_type=content_type,
            file_ref=file_ref,
            uploaded_by=uploaded_by,
            existing_customer_names=existing_customer_names,
        )
    elif source_type == "contract":
        if provider is None:
            raise ValueError("provider is required for source_type='contract'")
        result = await parse_contract(
            file_path=file_path,
            filename=filename,
            content_type=content_type,
            provider=provider,
            file_ref=file_ref,
            uploaded_by=uploaded_by,
        )
    elif source_type == "wechat_screenshot":
        if provider is None:
            raise ValueError("provider is required for source_type='wechat_screenshot'")
        result = await parse_screenshot(
            file_path=file_path,
            filename=filename,
            content_type=content_type,
            provider=provider,
            file_ref=file_ref,
            uploaded_by=uploaded_by,
        )
    else:
        raise ValueError(f"unknown source_type {source_type!r}")

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "parse_pipeline.done source_type=%s filename=%s entities=%d overall_confidence=%.3f duration_ms=%d",
        source_type, filename, len(result.entities), result.overall_confidence, duration_ms,
    )
    return result
