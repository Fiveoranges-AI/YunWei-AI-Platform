"""REST + HTML routes for daily report dashboard."""
from __future__ import annotations
from datetime import date as _date_cls
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from .. import api as platform_api, db
from . import orchestrator, storage
from .pushers.dingtalk import DingTalkPusher

router = APIRouter()

_pusher = DingTalkPusher()


class RegenerateBody(BaseModel):
    date: str  # YYYY-MM-DD


# Indirection for tests.
async def _orchestrator_run(**kw):
    return await orchestrator.run(**kw)


@router.get("/api/daily-report/reports")
def list_reports(request: Request, tenant: str = Query(...), limit: int = Query(30, le=100)):
    user = platform_api._user_from_request(request)
    _enforce_tenant_acl(user, tenant)
    rows = storage.list_reports(tenant_id=tenant, limit=limit)
    return {"reports": [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "report_date": r.report_date.isoformat(),
            "status": r.status,
            "push_status": r.push_status,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        } for r in rows
    ]}


@router.get("/api/daily-report/reports/{report_id}")
def get_report(request: Request, report_id: str):
    user = platform_api._user_from_request(request)
    row = storage.get_by_id(report_id)
    if row is None:
        raise HTTPException(404, {"error": "not_found"})
    _enforce_tenant_acl(user, row.tenant_id)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "report_date": row.report_date.isoformat(),
        "status": row.status,
        "content_html": row.content_html,
        "content_md": row.content_md,
        "sections_json": row.sections_json,
        "push_status": row.push_status,
        "push_error": row.push_error,
        "error": row.error,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


@router.post("/api/daily-report/reports/{tenant}/regenerate")
async def regenerate(request: Request, tenant: str, body: RegenerateBody):
    user = platform_api._user_from_request(request)
    _enforce_tenant_acl(user, tenant)
    try:
        rd = _date_cls.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, {"error": "bad_date"})
    storage.delete_by_tenant_date(tenant_id=tenant, report_date=rd)
    # Look up active subscription for this tenant (single recipient in MVP).
    sub = next((s for s in storage.list_enabled_subscriptions() if s.tenant_id == tenant), None)
    rid = await _orchestrator_run(
        tenant_id=tenant, report_date=rd,
        pusher=_pusher if sub else None, subscription=sub,
    )
    return {"report_id": rid}


def _enforce_tenant_acl(user: dict, tenant: str) -> None:
    """Allow if user has has_acl(user, tenant, 'daily-report'). Admin bypasses.

    Reuses platform's ACL helper (post-migration 004), which checks
    enterprise_members ∪ agent_grants.
    """
    if user.get("role") == "admin":
        return
    if not db.has_acl(user["id"], tenant, "daily-report"):
        raise HTTPException(403, {"error": "not_authorized_for_tenant"})
