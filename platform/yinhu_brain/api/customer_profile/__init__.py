"""Customer-centric APIs (Super Customer Profile).

All routes scoped to a single customer_id under ``/api/customers/{id}``:

  POST   /api/customers/{id}/ingest                  (ingest.py)
  GET    /api/customers/{id}/inbox                   (inbox.py)
  POST   /api/customers/{id}/inbox/{inbox_id}/confirm
  POST   /api/customers/{id}/inbox/{inbox_id}/ignore
  GET    /api/customers/{id}/events                  (reads.py)
  GET    /api/customers/{id}/commitments
  GET    /api/customers/{id}/tasks
  GET    /api/customers/{id}/risks
  GET    /api/customers/{id}/memory-items
  GET    /api/customers/{id}/timeline
  GET    /api/customers/{id}/summary
  GET    /api/customers/{id}/metrics                 (metrics.py)
  POST   /api/customers/{id}/ask                     (ask.py)
"""

from fastapi import APIRouter

from yinhu_brain.api.customer_profile.ask import router as _ask_router
from yinhu_brain.api.customer_profile.inbox import router as _inbox_router
from yinhu_brain.api.customer_profile.ingest import router as _ingest_router
from yinhu_brain.api.customer_profile.metrics import router as _metrics_router
from yinhu_brain.api.customer_profile.reads import router as _reads_router

router = APIRouter(prefix="/api/customers")
router.include_router(_ingest_router)
router.include_router(_inbox_router)
router.include_router(_reads_router)
router.include_router(_metrics_router)
router.include_router(_ask_router)

__all__ = ["router"]
