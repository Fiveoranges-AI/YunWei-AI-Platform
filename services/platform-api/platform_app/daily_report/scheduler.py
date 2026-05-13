"""Cron loop driving daily report generation.

Croniter computes next fire time per subscription; one async loop sleeps until
the soonest fire then dispatches orchestrator.run. Subscriptions are reloaded
from the DB once per loop iteration so adds/removes pick up without restart.

DingTalk credentials are looked up per (subscription.tenant_id) from
``enterprise_integrations`` immediately before each fire — subscriptions
whose enterprise has no active integration are skipped silently.
"""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo
from croniter import croniter
from . import orchestrator, storage
from .pushers.dingtalk import DingTalkPusher
from ..integrations import get_integration

_TICK_SECONDS: float = 60.0  # default cap; tests override


def compute_next_fire(sub: storage.Subscription, *, now: datetime) -> datetime:
    """Next fire time for this subscription strictly after `now`."""
    tz = ZoneInfo(sub.timezone)
    base = now.astimezone(tz)
    it = croniter(sub.push_cron, base)
    return it.get_next(datetime).replace(tzinfo=tz)


# Indirection for test monkeypatching.
async def _orchestrator_run(**kw):
    return await orchestrator.run(**kw)


async def run_forever() -> None:
    """Top-level scheduler loop. Cancellable from lifespan shutdown."""
    while True:
        try:
            await _tick_once()
        except Exception as e:
            # Never let scheduler die on a bad sub.
            print(f"[daily-report scheduler] tick error: {e!r}", flush=True)
        await asyncio.sleep(_TICK_SECONDS)


_LOOKBACK_SECONDS: float = 60.0  # cron's resolution; fire if a cron tick fell in last minute
_fired_at: dict[str, float] = {}  # subscription_id → last fire epoch


async def _tick_once() -> None:
    subs = storage.list_enabled_subscriptions()
    if not subs:
        return
    now = datetime.now(tz=ZoneInfo("UTC"))
    # Lookback wide enough that 5-field cron (1-minute resolution) always
    # has at least one fire instant in the window if the cron is currently due.
    lookback = max(_LOOKBACK_SECONDS, _TICK_SECONDS) + 1
    prev_dt = datetime.fromtimestamp(now.timestamp() - lookback, tz=ZoneInfo("UTC"))
    for sub in subs:
        next_fire = compute_next_fire(sub, now=prev_dt)
        if next_fire.timestamp() > now.timestamp():
            continue
        # Dedupe: don't re-fire the same cron tick within the same lookback window.
        last = _fired_at.get(sub.id)
        if last is not None and last >= next_fire.timestamp():
            continue
        _fired_at[sub.id] = next_fire.timestamp()
        asyncio.create_task(_dispatch(sub))


async def _dispatch(sub: storage.Subscription) -> None:
    today = date.today()
    # tenant_id on a subscription IS the enterprise id (= legacy client_id).
    integration = get_integration(sub.tenant_id, "dingtalk")
    if integration is None or not integration.active:
        # No DingTalk creds configured for this enterprise — skip push but
        # still log so ops sees the subscription is stranded.
        print(
            f"[daily-report scheduler] skip {sub.id}: "
            f"no active dingtalk integration for enterprise={sub.tenant_id}",
            flush=True,
        )
        return
    pusher = DingTalkPusher(integration.config)
    await _orchestrator_run(
        tenant_id=sub.tenant_id,
        report_date=today,
        pusher=pusher,
        subscription=sub,
    )
