"""Per-enterprise integration credentials (DingTalk, Feishu, WeCom, ...).

One row per (enterprise_id, kind) in ``enterprise_integrations``. The
``config`` blob is opaque to platform — each ``kind`` defines its own
shape. Callers (scheduler / orchestrator) read the row and pass the
dict into the channel-specific pusher constructor.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from . import db


@dataclass(frozen=True)
class Integration:
    enterprise_id: str
    kind: str
    config: dict
    active: bool


def get_integration(enterprise_id: str, kind: str) -> Integration | None:
    row = db.main().execute(
        "SELECT enterprise_id, kind, config_json, active "
        "FROM enterprise_integrations "
        "WHERE enterprise_id=%s AND kind=%s",
        (enterprise_id, kind),
    ).fetchone()
    if not row:
        return None
    return Integration(
        enterprise_id=row["enterprise_id"],
        kind=row["kind"],
        config=json.loads(row["config_json"]),
        active=bool(row["active"]),
    )


def upsert_integration(*, enterprise_id: str, kind: str, config: dict) -> None:
    """Insert or replace the credentials for (enterprise_id, kind).

    Re-asserts ``active=1`` and stamps ``rotated_at`` on every call so
    that rotating creds also un-disables an integration in one step.
    """
    now = int(time.time())
    db.main().execute(
        "INSERT INTO enterprise_integrations "
        "(enterprise_id, kind, config_json, active, created_at) "
        "VALUES (%s, %s, %s, 1, %s) "
        "ON CONFLICT (enterprise_id, kind) DO UPDATE SET "
        "config_json=EXCLUDED.config_json, "
        "active=1, "
        "rotated_at=EXCLUDED.created_at",
        (enterprise_id, kind, json.dumps(config), now),
    )


def disable_integration(*, enterprise_id: str, kind: str) -> None:
    db.main().execute(
        "UPDATE enterprise_integrations SET active=0 "
        "WHERE enterprise_id=%s AND kind=%s",
        (enterprise_id, kind),
    )
