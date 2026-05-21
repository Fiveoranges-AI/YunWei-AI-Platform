"""Parse pipeline — file → candidate JSON (entities + confidence + source span).

P0 task ② skeleton. Produces candidate JSON only; does not write to DB.
Task ③ wires the candidate JSON into review / writeback.

Public surface:
    parse_to_candidates(file_ref, source_type, *, provider, ...) -> CandidateJSON
    CandidateJSON / CandidateEntity / FieldCandidate / SourceSpan
    ExtractionProvider, MockProvider, ClaudeProvider

The pipeline reuses repo infra rather than reinventing:
    - SpreadsheetParser (services.schema_ingest.parsers.spreadsheet) for Excel/CSV.
    - call_claude (services.llm) for contract + screenshot extraction, wrapped
      behind ExtractionProvider so tests use MockProvider and don't burn tokens.
    - pdfplumber for text PDFs; OcrProvider (services.ocr) for scanned PDFs.

Ontology mapping is grounded in models defined by P0 task ① — see
``ontology.py`` for the required-fields table.
"""

from __future__ import annotations

from yunwei_win.services.parse_pipeline.candidate import (
    CandidateEntity,
    CandidateJSON,
    FieldCandidate,
    Relationship,
    SourceSpan,
)
from yunwei_win.services.parse_pipeline.pipeline import parse_to_candidates
from yunwei_win.services.parse_pipeline.providers.base import (
    ExtractionPayload,
    ExtractionProvider,
    ProviderEntity,
    ProviderField,
    ProviderResult,
)
from yunwei_win.services.parse_pipeline.providers.mock import MockProvider

__all__ = [
    "CandidateEntity",
    "CandidateJSON",
    "ExtractionPayload",
    "ExtractionProvider",
    "FieldCandidate",
    "MockProvider",
    "ProviderEntity",
    "ProviderField",
    "ProviderResult",
    "Relationship",
    "SourceSpan",
    "parse_to_candidates",
]
