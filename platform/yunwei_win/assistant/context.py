"""Bundle of (AuthContext, Entitlements) for assistant request handling.

Kept as its own tiny module so future runtime-resolver code (Task 7) and
the assistant router can share the same frozen pair without circular
imports between ``platform_app`` and ``yunwei_win``.
"""
from __future__ import annotations

from dataclasses import dataclass

from platform_app.context import AuthContext
from platform_app.entitlements import Entitlements


@dataclass(frozen=True)
class AssistantContext:
    auth: AuthContext
    entitlements: Entitlements
