"""ParseArtifact contract (vNext).

Normalized parser output shared by every parser provider. Carries
markdown plus the structural metadata downstream extraction and review
need to ground every extracted field back to a physical source: page,
chunk, bbox for visual parsers; paragraph/table for DOCX; sheet/row/col
for spreadsheets; character spans for plain text.

The shape is provider-agnostic — capability flags say which fields are
actually populated, so an extractor can pick the right grounding form
without sniffing provider strings.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ParserProvider = Literal["landingai", "text", "docx", "spreadsheet"]


class ParseCapabilities(BaseModel):
    """Which source-ref forms this artifact actually carries."""

    model_config = ConfigDict(extra="forbid")

    pages: bool = False
    chunks: bool = False
    visual_grounding: bool = False
    table_cells: bool = False
    text_spans: bool = False
    docx_paragraphs: bool = False
    docx_tables: bool = False
    spreadsheet_cells: bool = False


class ParseSourceRef(BaseModel):
    """Stable pointer from an extracted field back into the parse artifact.

    ``ref_type`` selects which optional fields are meaningful:
      - ``chunk``              -> page, bbox
      - ``page``               -> page
      - ``text_span``          -> start, end, excerpt
      - ``docx_paragraph``     -> paragraph
      - ``docx_table_cell``    -> table_id, row, col
      - ``spreadsheet_cell``   -> sheet, row, col
    """

    model_config = ConfigDict(extra="allow")

    ref_type: str
    ref_id: str
    page: int | None = None
    bbox: list[float] | None = None
    start: int | None = None
    end: int | None = None
    excerpt: str | None = None
    paragraph: int | None = None
    table_id: str | None = None
    sheet: str | None = None
    row: int | None = None
    col: int | None = None


class ParseChunk(BaseModel):
    """One chunk of structured content surfaced by the parser."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: str = "text"
    text: str = ""
    page: int | None = None
    bbox: list[float] | None = None


class ParseTableCell(BaseModel):
    model_config = ConfigDict(extra="allow")

    row: int
    col: int
    text: str = ""
    ref_id: str | None = None


class ParseTable(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    page: int | None = None
    sheet: str | None = None
    cells: list[ParseTableCell] = Field(default_factory=list)


class ParseArtifact(BaseModel):
    """Normalized parser output. One per ``document_parses`` row."""

    model_config = ConfigDict(extra="allow")

    version: int = 1
    provider: ParserProvider
    source_type: str
    markdown: str = ""
    pages: list[dict[str, Any]] = Field(default_factory=list)
    chunks: list[ParseChunk] = Field(default_factory=list)
    grounding: dict[str, Any] = Field(default_factory=dict)
    tables: list[ParseTable] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    capabilities: ParseCapabilities = Field(default_factory=ParseCapabilities)
