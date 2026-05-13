"""Tests for ``platform_app.entitlements.entitlements_for``.

Plan → capabilities is a pure function over :class:`AuthContext`, so
these tests construct contexts directly rather than going through the
DB / middleware.
"""
from __future__ import annotations

from platform_app.context import AuthContext
from platform_app.entitlements import Entitlements, entitlements_for


def _ctx(plan: str) -> AuthContext:
    return AuthContext(
        user_id="u_test",
        username="test",
        display_name="Test",
        session_id="sid",
        enterprise_id="e_test",
        enterprise_plan=plan,
        enterprise_role="owner",
    )


def test_trial_plan_returns_pooled_trial_minimum_tools():
    ent = entitlements_for(_ctx("trial"))
    assert isinstance(ent, Entitlements)
    assert ent.runtime_mode == "pooled_trial"
    assert ent.can_use_shared_assistant is True
    assert ent.can_use_dedicated_runtime is False
    assert ent.allowed_tools == ("customer_profile", "document_qa")


def test_pro_plan_returns_dedicated_customer_with_erp_runtime():
    ent = entitlements_for(_ctx("pro"))
    assert ent.runtime_mode == "dedicated_customer"
    assert ent.can_use_shared_assistant is True
    assert ent.can_use_dedicated_runtime is True
    assert "erp_runtime" in ent.allowed_tools
    assert "customer_profile" in ent.allowed_tools


def test_lite_plan_returns_pooled_lite_shared_only():
    ent = entitlements_for(_ctx("lite"))
    assert ent.runtime_mode == "pooled_lite"
    assert ent.can_use_shared_assistant is True
    assert ent.can_use_dedicated_runtime is False
    assert "erp_runtime" not in ent.allowed_tools
    assert "cross_customer_summary" in ent.allowed_tools


def test_unknown_plan_downgrades_to_pooled_trial():
    ent = entitlements_for(_ctx("does-not-exist"))
    assert ent.runtime_mode == "pooled_trial"
    assert ent.can_use_dedicated_runtime is False
    assert ent.allowed_tools == ("customer_profile", "document_qa")


def test_plan_matching_is_case_insensitive():
    # Defensive: DB stores "trial" but if a row ever had "PRO" we still
    # want the user to land on dedicated_customer.
    ent = entitlements_for(_ctx("PRO"))
    assert ent.runtime_mode == "dedicated_customer"
