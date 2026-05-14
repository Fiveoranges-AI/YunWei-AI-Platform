"""LandingAI ADE Parse adapter.

Delegates to ``parse_file_to_markdown`` (imported at module level so
tests can monkeypatch it) and normalizes the SDK response into a
``ParseArtifact`` that preserves chunks, splits as pages, grounding,
and metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yunwei_win.services.landingai_ade_client import parse_file_to_markdown
from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
    ParseChunk,
)


class LandingAIParser:
    async def parse_file(
        self,
        path: Path,
        *,
        filename: str,
        content_type: str | None,
        source_type: str,
    ) -> ParseArtifact:
        result = await parse_file_to_markdown(path)

        chunks = [_normalize_chunk(c) for c in (result.chunks or [])]
        pages = [_normalize_page(p) for p in (result.splits or [])]
        grounding = dict(result.grounding or {})
        metadata = dict(result.metadata or {})
        metadata.setdefault("filename", filename)
        if content_type:
            metadata.setdefault("content_type", content_type)

        return ParseArtifact(
            version=1,
            provider="landingai",
            source_type=source_type,
            markdown=result.markdown or "",
            pages=pages,
            chunks=chunks,
            grounding=grounding,
            tables=[],
            metadata=metadata,
            capabilities=ParseCapabilities(
                pages=bool(pages),
                chunks=bool(chunks),
                visual_grounding=bool(grounding),
                table_cells=True,
            ),
        )


def _normalize_chunk(raw: Any) -> ParseChunk:
    if isinstance(raw, ParseChunk):
        return raw
    if isinstance(raw, dict):
        data = raw
    else:
        data = {
            "id": getattr(raw, "id", None),
            "type": getattr(raw, "type", "text"),
            "text": getattr(raw, "text", ""),
            "page": getattr(raw, "page", None),
            "bbox": getattr(raw, "bbox", None),
        }
    return ParseChunk(
        id=str(data.get("id") or ""),
        type=str(data.get("type") or "text"),
        text=str(data.get("text") or ""),
        page=data.get("page"),
        bbox=data.get("bbox"),
    )


def _normalize_page(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    return {
        "id": getattr(raw, "id", None),
        "page_number": getattr(raw, "page_number", None),
    }
