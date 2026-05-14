"""Schema-first V2 ingest surface.

Public exports cover the ReviewDraft contract + materializer. The V2 API
(auto/confirm modules) live next to these and are added in a separate task.
"""

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
