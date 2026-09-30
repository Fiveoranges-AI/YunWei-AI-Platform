"""Audio → text parser (transcription).

Reads an audio file, runs it through the transcription seam, and returns a
ParseArtifact whose markdown is the transcript. When no STT provider is
configured the transcript is empty and the reason is surfaced as a warning so
the review draft can tell the user the clip is saved but not yet transcribed.
"""

from __future__ import annotations

from pathlib import Path

from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
    ParseChunk,
)
from yunwei_win.services.transcription import transcribe_audio


class TranscribeParser:
    async def parse_file(
        self,
        path: Path,
        *,
        filename: str,
        content_type: str | None,
        source_type: str,
    ) -> ParseArtifact:
        data = path.read_bytes()
        result = await transcribe_audio(
            data, content_type=content_type, filename=filename
        )
        text = result.text or ""
        chunks = [ParseChunk(id="audio:0", type="transcript", text=text)] if text else []
        return ParseArtifact(
            provider="transcribe",
            source_type=source_type,
            markdown=text,
            chunks=chunks,
            capabilities=ParseCapabilities(text_spans=bool(text)),
            metadata={
                "filename": filename,
                "content_type": content_type,
                "transcription_provider": result.provider,
                "warnings": result.warnings,
            },
        )
