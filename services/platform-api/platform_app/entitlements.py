"""Plan-driven capability policy.

Given an :class:`AuthContext`, ``entitlements_for`` returns a frozen
:class:`Entitlements` describing what runtime / tools the caller is
allowed to use. This is the only place plan → capability mappings
should live.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .context import AuthContext

Plan = Literal["trial", "lite", "pro", "max", "enterprise", "standard"]


@dataclass(frozen=True)
class Entitlements:
    runtime_mode: str
    can_use_shared_assistant: bool
    can_use_dedicated_runtime: bool
    allowed_tools: tuple[str, ...]


def entitlements_for(ctx: AuthContext) -> Entitlements:
    plan = (ctx.enterprise_plan or "trial").lower()
    if plan in {"pro", "max", "enterprise"}:
        return Entitlements(
            runtime_mode="dedicated_customer",
            can_use_shared_assistant=True,
            can_use_dedicated_runtime=True,
            allowed_tools=(
                "customer_profile",
                "document_qa",
                "cross_customer_summary",
                "erp_runtime",
            ),
        )
    if plan in {"lite", "standard"}:
        return Entitlements(
            runtime_mode="pooled_lite",
            can_use_shared_assistant=True,
            can_use_dedicated_runtime=False,
            allowed_tools=(
                "customer_profile",
                "document_qa",
                "cross_customer_summary",
            ),
        )
    # trial + unknown → smallest capability set.
    return Entitlements(
        runtime_mode="pooled_trial",
        can_use_shared_assistant=True,
        can_use_dedicated_runtime=False,
        allowed_tools=("customer_profile", "document_qa"),
    )
