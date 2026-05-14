"""Schema-first V2 ingest surface.

Public exports:
- ``PIPELINE_TABLES`` / ``materialize_review_draft``: build the ReviewDraft
  payload from extractor output + tenant catalog.
- ``auto_ingest_v2``: V2 end-to-end orchestrator the worker calls.
- ``confirm_review_draft``: write confirmed cells into company data tables.
- The Pydantic schema family the API + frontend share.
"""

from yunwei_win.services.ingest_v2.auto import AutoIngestV2Result, auto_ingest_v2
from yunwei_win.services.ingest_v2.confirm import confirm_review_draft
from yunwei_win.services.ingest_v2.review_draft import (
    PIPELINE_TABLES,
    materialize_review_draft,
)
from yunwei_win.services.ingest_v2.schemas import (
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

__all__ = [
    "PIPELINE_TABLES",
    "AutoIngestV2Result",
    "auto_ingest_v2",
    "confirm_review_draft",
    "materialize_review_draft",
    "ConfirmExtractionRequest",
    "ConfirmExtractionResponse",
    "ExtractionStatus",
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
]
