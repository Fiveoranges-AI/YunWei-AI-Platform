"""Plain-text and pasted-text parser.

Wraps a string in a single-chunk ParseArtifact with character-span
source ids so downstream extraction can ground every extracted field
back to a substring of the original input.
"""

from __future__ import annotations

from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
    ParseChunk,
)


class TextParser:
    async def parse_text(self, text: str, *, filename: str) -> ParseArtifact:
        chunk = ParseChunk(
            id="text:0",
            type="text",
            text=text,
        )
        return ParseArtifact(
            version=1,
            provider="text",
            source_type="text",
            markdown=text,
            pages=[{"id": "page:1", "page_number": 1}],
            chunks=[chunk],
            grounding={
                "text:0": {"start": 0, "end": len(text)},
            },
            tables=[],
            metadata={"filename": filename, "char_count": len(text)},
            capabilities=ParseCapabilities(
                pages=True, chunks=True, text_spans=True
            ),
        )
