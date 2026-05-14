"""Schema-first ingest surface.

Public exports:
- ``PIPELINE_TABLES`` / ``materialize_review_draft``: build the ReviewDraft
  payload from extractor output + tenant catalog.
- ``auto_ingest``: end-to-end orchestrator the worker calls.
- ``confirm_review_draft``: write confirmed cells into company data tables.
- The Pydantic schema family the API + frontend share.
"""

from yunwei_win.services.schema_ingest.auto import AutoIngestResult, auto_ingest
from yunwei_win.services.schema_ingest.confirm import confirm_review_draft
from yunwei_win.services.schema_ingest.extraction_schema import (
    build_selected_tables_schema_json,
)
from yunwei_win.services.schema_ingest.review_draft import (
    PIPELINE_TABLES,
    materialize_review_draft,
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
    ReviewDraftRoutePlan,
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
    "PIPELINE_TABLES",
    "AutoIngestResult",
    "auto_ingest",
    "build_selected_tables_schema_json",
    "confirm_review_draft",
    "materialize_review_draft",
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
    "ReviewDraftRoutePlan",
    "ReviewRow",
    "ReviewRowOperation",
    "ReviewTable",
    "SelectedTable",
    "TableRouteResult",
    "route_tables",
]
