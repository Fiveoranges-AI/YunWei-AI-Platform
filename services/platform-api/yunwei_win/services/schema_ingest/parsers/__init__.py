"""Parser provider package — one module per physical source type."""

from yunwei_win.services.schema_ingest.parsers.docx import DocxParser
from yunwei_win.services.schema_ingest.parsers.landingai import LandingAIParser
from yunwei_win.services.schema_ingest.parsers.spreadsheet import SpreadsheetParser
from yunwei_win.services.schema_ingest.parsers.text import TextParser

__all__ = [
    "DocxParser",
    "LandingAIParser",
    "SpreadsheetParser",
    "TextParser",
]
