"""Parser selection facade.

Routes a ``DetectedSourceType`` (plus the actual bytes/path/text) to
the right parser instance and returns a normalized ``ParseArtifact``.
"""

from __future__ import annotations

from pathlib import Path

from yunwei_win.services.schema_ingest.file_type import DetectedSourceType
from yunwei_win.services.schema_ingest.parse_artifact import ParseArtifact
from yunwei_win.services.schema_ingest.parsers.docx import DocxParser
from yunwei_win.services.schema_ingest.parsers.landingai import LandingAIParser
from yunwei_win.services.schema_ingest.parsers.spreadsheet import SpreadsheetParser
from yunwei_win.services.schema_ingest.parsers.text import TextParser


async def parse_file(
    *,
    detected: DetectedSourceType,
    path: Path,
    filename: str,
    content_type: str | None,
) -> ParseArtifact:
    if detected.parser_provider == "landingai":
        return await LandingAIParser().parse_file(
            path,
            filename=filename,
            content_type=content_type,
            source_type=detected.source_type,
        )
    if detected.parser_provider == "docx":
        return await DocxParser().parse_file(
            path,
            filename=filename,
            content_type=content_type,
            source_type=detected.source_type,
        )
    if detected.parser_provider == "spreadsheet":
        return await SpreadsheetParser().parse_file(
            path,
            filename=filename,
            content_type=content_type,
            source_type=detected.source_type,
        )
    if detected.parser_provider == "text":
        text = path.read_text(encoding="utf-8")
        return await TextParser().parse_text(text, filename=filename)
    raise ValueError(f"no parser for provider {detected.parser_provider!r}")


async def parse_pasted_text(*, text: str, filename: str = "pasted.txt") -> ParseArtifact:
    return await TextParser().parse_text(text, filename=filename)
