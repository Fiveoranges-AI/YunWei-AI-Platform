"""Extractor provider contracts.

The extractor layer turns selected business schemas plus OCR markdown into a
list of `PipelineExtractResult`. Providers normalize external model APIs
(LandingAI Extract, DeepSeek JSON, etc.) into this single internal shape so
the ingest orchestrator does not branch per provider.

Providers do not decide which schemas apply (that's `route_schemas`) and do
not write DB rows directly (normalization + writeback live elsewhere).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from yunwei_win.services.ingest.unified_schemas import (
    PipelineExtractResult,
    PipelineSelection,
)

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class ExtractionInput:
    document_id: uuid.UUID
    session: AsyncSession
    markdown: str
    selections: list[PipelineSelection]
    company_schema: dict[str, Any] | None = None


class ExtractorProvider(Protocol):
    async def extract_selected(
        self,
        input: ExtractionInput,
        progress: ProgressCallback | None = None,
    ) -> list[PipelineExtractResult]: ...
