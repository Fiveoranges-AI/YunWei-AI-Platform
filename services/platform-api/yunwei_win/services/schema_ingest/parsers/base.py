"""Protocols for parser providers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact


@runtime_checkable
class FileParser(Protocol):
    async def parse_file(
        self,
        path: Path,
        *,
        filename: str,
        content_type: str | None,
        source_type: str,
    ) -> ParseArtifact: ...


@runtime_checkable
class TextSourceParser(Protocol):
    async def parse_text(self, text: str, *, filename: str) -> ParseArtifact: ...
