"""FastAPI router assembly for the win API surface."""

from fastapi import APIRouter

from yunwei_win.api.ask import router as _ask_router
from yunwei_win.api.company_schema import router as _company_schema_router
from yunwei_win.api.customer_management import router as _customer_management_router
from yunwei_win.api.customer_profile import router as _customer_profile_router
from yunwei_win.api.schema_ingest import router as _ingest_router
from yunwei_win.api.read import router as _read_router
from yunwei_win.assistant.router import router as _assistant_router


def create_router() -> APIRouter:
    router = APIRouter()
    router.include_router(_ingest_router)
    router.include_router(_read_router)
    router.include_router(_ask_router)
    router.include_router(_assistant_router)
    router.include_router(_customer_profile_router)
    router.include_router(_customer_management_router)
    router.include_router(_company_schema_router)
    return router


router = create_router()
