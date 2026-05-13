"""Customer-centric APIs (Super Customer Profile).

All routes scoped to a single customer_id under ``/api/win/customers/{id}``:

  POST   /api/win/customers/{id}/ingest                  (ingest.py)
  GET    /api/win/customers/{id}/inbox                   (inbox.py)
  POST   /api/win/customers/{id}/inbox/{inbox_id}/confirm
  POST   /api/win/customers/{id}/inbox/{inbox_id}/ignore
  GET    /api/win/customers/{id}/events                  (reads.py)
  GET    /api/win/customers/{id}/commitments
  GET    /api/win/customers/{id}/tasks
  GET    /api/win/customers/{id}/risks
  GET    /api/win/customers/{id}/memory-items
  GET    /api/win/customers/{id}/timeline
  GET    /api/win/customers/{id}/summary
  GET    /api/win/customers/{id}/metrics                 (metrics.py)
  POST   /api/win/customers/{id}/ask                     (ask.py)
"""

from fastapi import APIRouter

from yunwei_win.api.customer_profile.ask import router as _ask_router
from yunwei_win.api.customer_profile.inbox import router as _inbox_router
from yunwei_win.api.customer_profile.ingest import router as _ingest_router
from yunwei_win.api.customer_profile.metrics import router as _metrics_router
from yunwei_win.api.customer_profile.reads import router as _reads_router

router = APIRouter(prefix="/customers")
router.include_router(_ingest_router)
router.include_router(_inbox_router)
router.include_router(_reads_router)
router.include_router(_metrics_router)
router.include_router(_ask_router)

__all__ = ["router"]
