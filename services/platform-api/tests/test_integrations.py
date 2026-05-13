"""Tests for platform_app.integrations — per-enterprise integration creds."""
from __future__ import annotations
import pytest
from platform_app import db, integrations


@pytest.fixture(autouse=True)
def _init_db():
    db.init()


def _seed_enterprise(eid: str) -> None:
    db.main().execute(
        "INSERT INTO enterprises (id, legal_name, display_name, plan, "
        "onboarding_stage, created_at) "
        "VALUES (%s,%s,%s,'trial','active',0)",
        (eid, eid, eid),
    )


def test_get_integration_returns_none_when_absent():
    _seed_enterprise("yinhu")
    assert integrations.get_integration("yinhu", "dingtalk") is None


def test_upsert_then_get_roundtrips_config():
    _seed_enterprise("yinhu")
    cfg = {"client_id": "C1", "client_secret": "S1", "robot_code": "R1"}
    integrations.upsert_integration(enterprise_id="yinhu", kind="dingtalk", config=cfg)
    got = integrations.get_integration("yinhu", "dingtalk")
    assert got is not None
    assert got.enterprise_id == "yinhu"
    assert got.kind == "dingtalk"
    assert got.config == cfg
    assert got.active is True


def test_upsert_same_pk_updates_in_place():
    _seed_enterprise("yinhu")
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "OLD", "client_secret": "OLD", "robot_code": "OLD"},
    )
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "NEW", "client_secret": "NEW", "robot_code": "NEW"},
    )
    got = integrations.get_integration("yinhu", "dingtalk")
    assert got is not None
    assert got.config["client_id"] == "NEW"
    # One row, not two.
    row = db.main().execute(
        "SELECT COUNT(*) AS n FROM enterprise_integrations "
        "WHERE enterprise_id=%s AND kind=%s",
        ("yinhu", "dingtalk"),
    ).fetchone()
    assert row["n"] == 1


def test_disable_marks_inactive_but_keeps_row():
    _seed_enterprise("yinhu")
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "C", "client_secret": "S", "robot_code": "R"},
    )
    integrations.disable_integration(enterprise_id="yinhu", kind="dingtalk")
    got = integrations.get_integration("yinhu", "dingtalk")
    assert got is not None
    assert got.active is False
    # Re-upsert reactivates.
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "C2", "client_secret": "S2", "robot_code": "R2"},
    )
    again = integrations.get_integration("yinhu", "dingtalk")
    assert again is not None
    assert again.active is True
    assert again.config["client_id"] == "C2"


def test_get_distinguishes_kind():
    _seed_enterprise("yinhu")
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "C", "client_secret": "S", "robot_code": "R"},
    )
    assert integrations.get_integration("yinhu", "feishu") is None
    assert integrations.get_integration("yinhu", "dingtalk") is not None


def test_get_distinguishes_enterprise():
    _seed_enterprise("yinhu")
    _seed_enterprise("acme")
    integrations.upsert_integration(
        enterprise_id="yinhu", kind="dingtalk",
        config={"client_id": "Y", "client_secret": "Y", "robot_code": "Y"},
    )
    assert integrations.get_integration("acme", "dingtalk") is None
    yinhu = integrations.get_integration("yinhu", "dingtalk")
    assert yinhu is not None
    assert yinhu.config["client_id"] == "Y"
