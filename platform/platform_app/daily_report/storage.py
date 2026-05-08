"""Postgres CRUD for daily_reports and daily_report_subscriptions."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
import json
from .. import db

ReportStatus = str  # 'running' | 'ready' | 'partial' | 'timeout' | 'failed'
PushStatus = str    # 'pending' | 'sent' | 'failed'


@dataclass
class Report:
    id: str
    tenant_id: str
    report_date: date
    status: ReportStatus
    content_md: str | None
    content_html: str | None
    sections_json: dict[str, Any] | None
    raw_collectors: dict[str, Any] | None
    push_status: PushStatus | None
    push_error: str | None
    error: str | None
    generated_at: datetime | None
    created_at: datetime


@dataclass
class Subscription:
    id: str
    tenant_id: str
    recipient_label: str
    push_channel: str
    push_target: str
    push_cron: str
    timezone: str
    sections_enabled: list[str]
    enabled: bool


def _row_to_report(row: dict) -> Report:
    return Report(
        id=str(row["id"]),
        tenant_id=row["tenant_id"],
        report_date=row["report_date"],
        status=row["status"],
        content_md=row.get("content_md"),
        content_html=row.get("content_html"),
        sections_json=row.get("sections_json"),
        raw_collectors=row.get("raw_collectors"),
        push_status=row.get("push_status"),
        push_error=row.get("push_error"),
        error=row.get("error"),
        generated_at=row.get("generated_at"),
        created_at=row["created_at"],
    )


def create_running(*, tenant_id: str, report_date: date) -> str:
    """Insert a new running row. If one already exists for (tenant, date), return its id."""
    row = db.main().execute(
        "INSERT INTO daily_reports (tenant_id, report_date, status) "
        "VALUES (%s, %s, 'running') "
        "ON CONFLICT (tenant_id, report_date) DO UPDATE SET status='running' "
        "RETURNING id",
        (tenant_id, report_date),
    ).fetchone()
    return str(row["id"])


def get_by_id(report_id: str) -> Report | None:
    row = db.main().execute(
        "SELECT * FROM daily_reports WHERE id=%s", (report_id,)
    ).fetchone()
    return _row_to_report(row) if row else None


def write_result(
    *, report_id: str, status: ReportStatus,
    content_md: str, content_html: str,
    sections_json: dict[str, Any], raw_collectors: dict[str, Any],
    generated_at: datetime,
) -> None:
    db.main().execute(
        "UPDATE daily_reports SET status=%s, content_md=%s, content_html=%s, "
        "sections_json=%s, raw_collectors=%s, generated_at=%s, error=NULL "
        "WHERE id=%s",
        (status, content_md, content_html,
         json.dumps(sections_json), json.dumps(raw_collectors),
         generated_at, report_id),
    )


def write_failure(*, report_id: str, status: ReportStatus, error: str) -> None:
    db.main().execute(
        "UPDATE daily_reports SET status=%s, error=%s WHERE id=%s",
        (status, error, report_id),
    )


def update_push_status(*, report_id: str, status: PushStatus, error: str | None) -> None:
    db.main().execute(
        "UPDATE daily_reports SET push_status=%s, push_error=%s WHERE id=%s",
        (status, error, report_id),
    )


def list_reports(*, tenant_id: str, limit: int = 30) -> list[Report]:
    rows = db.main().execute(
        "SELECT * FROM daily_reports WHERE tenant_id=%s "
        "ORDER BY report_date DESC LIMIT %s",
        (tenant_id, limit),
    ).fetchall()
    return [_row_to_report(r) for r in rows]


def delete_by_tenant_date(*, tenant_id: str, report_date: date) -> None:
    db.main().execute(
        "DELETE FROM daily_reports WHERE tenant_id=%s AND report_date=%s",
        (tenant_id, report_date),
    )


def create_subscription(
    *, tenant_id: str, recipient_label: str,
    push_channel: str, push_target: str, push_cron: str,
    sections_enabled: list[str], timezone: str = "Asia/Shanghai",
) -> str:
    row = db.main().execute(
        "INSERT INTO daily_report_subscriptions "
        "(tenant_id, recipient_label, push_channel, push_target, push_cron, "
        "timezone, sections_enabled) VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id",
        (tenant_id, recipient_label, push_channel, push_target, push_cron,
         timezone, sections_enabled),
    ).fetchone()
    return str(row["id"])


def list_enabled_subscriptions() -> list[Subscription]:
    rows = db.main().execute(
        "SELECT * FROM daily_report_subscriptions WHERE enabled = true"
    ).fetchall()
    return [
        Subscription(
            id=str(r["id"]), tenant_id=r["tenant_id"],
            recipient_label=r["recipient_label"],
            push_channel=r["push_channel"], push_target=r["push_target"],
            push_cron=r["push_cron"], timezone=r["timezone"],
            sections_enabled=list(r["sections_enabled"]),
            enabled=r["enabled"],
        )
        for r in rows
    ]
