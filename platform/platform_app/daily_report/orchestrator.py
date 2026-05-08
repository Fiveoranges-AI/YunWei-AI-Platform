"""Orchestrator: drives one report generation tick.

Flow: insert running row → HMAC POST container → write result → push.
Spec §3.2.
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from typing import Any
import httpx
from . import storage, markdown_render
from .pushers.base import Pusher
from .. import db, hmac_sign

_RETRY_DELAY_SECONDS = 30  # overridable in tests
_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)


async def run(
    *,
    tenant_id: str,
    report_date: date,
    pusher: Pusher | None,
    subscription: storage.Subscription | None,
) -> str:
    """Run one tick. Returns the report id (existing or newly created)."""
    rid = storage.create_running(tenant_id=tenant_id, report_date=report_date)

    tenant = db.get_tenant(tenant_id, "daily-report")
    if tenant is None:
        storage.write_failure(report_id=rid, status="failed",
                              error="tenant (yinhu, daily-report) not registered")
        return rid

    try:
        payload = await _call_container_with_retry(tenant=tenant, report_date=report_date)
    except _ContainerTimeout as e:
        storage.write_failure(report_id=rid, status="timeout", error=str(e))
        return rid
    except _ContainerError as e:
        storage.write_failure(report_id=rid, status="failed", error=str(e))
        return rid

    storage.write_result(
        report_id=rid,
        status=_status_from_payload(payload),
        content_md=payload["markdown"],
        content_html=markdown_render.render(payload["markdown"]),
        sections_json=payload["sections"],
        raw_collectors=payload,
        generated_at=datetime.fromisoformat(payload["generated_at"]),
    )

    if pusher and subscription:
        link = f"https://{_dashboard_host()}/daily-report/{rid}"
        result = await pusher.push(
            subscription=subscription,
            markdown_body=payload["markdown"],
            link_url=link,
            title=_card_title(report_date),
        )
        storage.update_push_status(
            report_id=rid,
            status="sent" if result.success else "failed",
            error=result.error,
        )
    return rid


def _status_from_payload(payload: dict[str, Any]) -> str:
    sections = payload.get("sections", {})
    statuses = {s.get("status") for s in sections.values()}
    if statuses <= {"ok"}:
        return "ready"
    return "partial"


def _card_title(d: date) -> str:
    weekday = "一二三四五六日"[d.weekday()]
    return f"银湖经营快报 · {d.isoformat()} 周{weekday}"


def _dashboard_host() -> str:
    from ..settings import settings
    return settings.host_app


class _ContainerTimeout(Exception):
    pass


class _ContainerError(Exception):
    pass


async def _call_container_with_retry(*, tenant: dict, report_date: date) -> dict:
    """Try once, retry once after 30s on 5xx or transient connection error."""
    try:
        return await _call_container(tenant=tenant, report_date=report_date)
    except httpx.ReadTimeout as e:
        raise _ContainerTimeout(f"read timeout: {e}")
    except (httpx.HTTPStatusError, httpx.ConnectError) as first:
        await asyncio.sleep(_RETRY_DELAY_SECONDS)
        try:
            return await _call_container(tenant=tenant, report_date=report_date)
        except httpx.ReadTimeout as e:
            raise _ContainerTimeout(f"read timeout on retry: {e}")
        except (httpx.HTTPStatusError, httpx.ConnectError) as second:
            raise _ContainerError(f"first={_short(first)} retry={_short(second)}")


def _short(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"{e.response.status_code}"
    return type(e).__name__


async def _call_container(*, tenant: dict, report_date: date) -> dict:
    from ..settings import settings
    upstream_path = f"/daily-report/_internal/generate?date={report_date.isoformat()}"
    upstream_url = tenant["container_url"].rstrip("/") + upstream_path
    body = b""
    headers = hmac_sign.sign(
        secret=tenant["hmac_secret_current"], key_id=tenant["hmac_key_id_current"],
        method="POST", host=settings.host_app, path=upstream_path,
        client=tenant["client_id"], agent=tenant["agent_id"],
        user_id="system", user_role="system", user_name="daily-report-orchestrator",
        body=body,
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(upstream_url, headers=headers, content=body)
    resp.raise_for_status()
    return resp.json()
