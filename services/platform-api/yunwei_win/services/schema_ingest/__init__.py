"""Schema-first ingest surface (vNext).

Public exports:
- ``auto_ingest`` / ``AutoIngestResult``: end-to-end orchestrator the worker calls.
- ``route_tables`` + Pydantic results: selected-table router for the vNext pipeline.
- ``build_selected_tables_schema_json``: catalog-derived extractor JSON schema.
- ``confirm_review_draft``: write confirmed cells into company data tables.
- ``materialize_review_draft_vnext`` (re-exported via the submodule).
- The Pydantic schema family the API + frontend share.
"""

from yunwei_win.services.schema_ingest.auto import AutoIngestResult, auto_ingest
from yunwei_win.services.schema_ingest.confirm import confirm_review_draft
from yunwei_win.services.schema_ingest.extraction_schema import (
    build_selected_tables_schema_json,
)
from yunwei_win.services.schema_ingest.schemas import (
    ConfirmExtractionRequest,
    ConfirmExtractionResponse,
    ExtractionStatus,
    ReviewCell,
    ReviewCellEvidence,
    ReviewCellPatch,
    ReviewCellSource,
    ReviewCellStatus,
    ReviewDraft,
    ReviewDraftDocument,
    ReviewRow,
    ReviewRowOperation,
    ReviewTable,
)
from yunwei_win.services.schema_ingest.table_router import (
    RejectedTable,
    SelectedTable,
    TableRouteResult,
    route_tables,
)

__all__ = [
    "AutoIngestResult",
    "auto_ingest",
    "build_selected_tables_schema_json",
    "confirm_review_draft",
    "ConfirmExtractionRequest",
    "ConfirmExtractionResponse",
    "ExtractionStatus",
    "RejectedTable",
    "ReviewCell",
    "ReviewCellEvidence",
    "ReviewCellPatch",
    "ReviewCellSource",
    "ReviewCellStatus",
    "ReviewDraft",
    "ReviewDraftDocument",
    "ReviewRow",
    "ReviewRowOperation",
    "ReviewTable",
    "SelectedTable",
    "TableRouteResult",
    "route_tables",
]
