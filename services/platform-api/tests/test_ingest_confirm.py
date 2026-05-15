"""Smoke import test for the confirm module.

The detailed vNext coverage lives in ``tests/test_confirm_vnext.py``.
After the Task 8 rewrite the legacy pipeline assertions no longer apply;
this file only guards that the public surface still imports cleanly.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_state():  # override Postgres+Redis fixture
    yield


def test_confirm_review_draft_is_exported():
    from yunwei_win.services.schema_ingest import confirm_review_draft

    assert callable(confirm_review_draft)


def test_confirm_request_response_round_trip():
    """vNext ConfirmExtractionRequest accepts lock_token + base_version."""

    from uuid import uuid4

    from yunwei_win.services.schema_ingest.schemas import (
        ConfirmExtractionRequest,
        ConfirmExtractionResponse,
    )

    req = ConfirmExtractionRequest(lock_token=uuid4(), base_version=3)
    dumped = req.model_dump(mode="json")
    assert dumped["base_version"] == 3

    resp = ConfirmExtractionResponse(
        extraction_id=uuid4(),
        document_id=uuid4(),
        status="confirmed",
        written_rows={"customers": [uuid4()]},
        invalid_cells=[],
    )
    payload = resp.model_dump(mode="json")
    assert payload["status"] == "confirmed"
    assert isinstance(payload["written_rows"]["customers"][0], str)


# ---------------------------------------------------------------------------
# OCR-string normalization for decimal cells (ratio / amount / etc.)
#
# Backed by a real bug report: contract payment milestones with ``ratio``
# extracted as ``"90%"`` / ``"10%"`` were tagged ``invalid_value`` because
# ``Decimal("90%")`` raises ``InvalidOperation``. Catalog convention stores
# ratio as a 0-1 fraction (see read.py / qa.py multiplying by 100 for
# display), so ``"90%"`` must coerce to ``Decimal("0.9")``.
# ---------------------------------------------------------------------------


def test_to_decimal_handles_percent_and_thousands():
    from decimal import Decimal, InvalidOperation

    from yunwei_win.services.schema_ingest.confirm import _to_decimal

    assert _to_decimal("90%") == Decimal("0.9")
    assert _to_decimal("10%") == Decimal("0.1")
    assert _to_decimal(" 5.5% ") == Decimal("0.055")
    assert _to_decimal("30,000.00") == Decimal("30000.00")
    assert _to_decimal("1,000,000") == Decimal("1000000")
    assert _to_decimal(0.5) == Decimal("0.5")
    assert _to_decimal(Decimal("1.25")) == Decimal("1.25")

    with pytest.raises(InvalidOperation):
        _to_decimal("not-a-number")
    with pytest.raises(InvalidOperation):
        _to_decimal(True)


def test_value_matches_type_accepts_percent_for_decimal_field():
    from yunwei_win.services.schema_ingest.confirm import _value_matches_type

    spec = {"data_type": "decimal"}
    assert _value_matches_type(spec, "90%") is True
    assert _value_matches_type(spec, "30,000.00") is True
    assert _value_matches_type(spec, 0.9) is True
    assert _value_matches_type(spec, "garbage") is False


def test_coerce_value_normalizes_percent_for_decimal_field():
    from decimal import Decimal

    from yunwei_win.services.schema_ingest.confirm import _coerce_value

    spec = {"data_type": "decimal"}
    assert _coerce_value(spec, "90%") == Decimal("0.9")
    assert _coerce_value(spec, "30,000.00") == Decimal("30000.00")
    assert _coerce_value(spec, None) is None


# ---------------------------------------------------------------------------
# Validation defenses against the IntegrityError 500 from production:
#   confirm: link_existing for contracts.contracts:0 without selected_entity_id
#   confirm: flush failed for contract_payment_milestones row ... null value
#     in column "contract_id" of relation "contract_payment_milestones"
# Both should now surface as ``invalid_cells`` (200) instead of a 500.
# ---------------------------------------------------------------------------


def _draft(tables: list) -> object:
    from yunwei_win.services.schema_ingest.schemas import (
        ReviewDraft,
        ReviewDraftDocument,
    )

    return ReviewDraft(
        extraction_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        parse_id="00000000-0000-0000-0000-000000000003",
        document=ReviewDraftDocument(filename="x.pdf"),
        tables=tables,
    )


def _row(client_row_id: str, *, decision_op: str | None, target=None, writable=True):
    from yunwei_win.services.schema_ingest.schemas import (
        ReviewRow,
        ReviewRowDecision,
    )

    decision = (
        ReviewRowDecision(operation=decision_op, selected_entity_id=target)
        if decision_op is not None
        else None
    )
    return ReviewRow(
        client_row_id=client_row_id,
        operation="create" if (decision_op or "create") != "update" else "update",
        cells=[],
        row_decision=decision,
        is_writable=writable,
    )


def _table(name: str, rows: list):
    from yunwei_win.services.schema_ingest.schemas import ReviewTable

    return ReviewTable(table_name=name, label=name, rows=rows)


def test_validate_link_decisions_flags_link_existing_without_target():
    from yunwei_win.services.schema_ingest.confirm import (
        _validate_link_decisions,
    )

    draft = _draft([
        _table("contracts", [
            _row("contracts:0", decision_op="link_existing", target=None),
        ]),
    ])
    out = _validate_link_decisions(draft)
    assert len(out) == 1
    assert out[0]["table_name"] == "contracts"
    assert out[0]["client_row_id"] == "contracts:0"
    assert out[0]["reason"] == "link_existing_missing_target"


def test_validate_link_decisions_passes_when_target_is_set():
    from uuid import uuid4

    from yunwei_win.services.schema_ingest.confirm import (
        _validate_link_decisions,
    )

    draft = _draft([
        _table("contracts", [
            _row("contracts:0", decision_op="link_existing", target=uuid4()),
            _row("contracts:1", decision_op="create"),
            _row("contracts:2", decision_op=None),  # no decision attached
        ]),
    ])
    assert _validate_link_decisions(draft) == []


def test_validate_parent_links_flags_orphan_milestone_when_no_contract():
    """The exact production bug: milestones with no contracts row to link to."""
    from yunwei_win.services.schema_ingest.confirm import (
        _validate_parent_links,
    )

    draft = _draft([
        _table("contracts", [
            # link_existing without target — won't produce a row UUID
            _row("contracts:0", decision_op="link_existing", target=None),
        ]),
        _table("contract_payment_milestones", [
            _row("contract_payment_milestones:0", decision_op="create"),
        ]),
    ])
    out = _validate_parent_links(draft)
    reasons = {(c["table_name"], c["field_name"], c["reason"]) for c in out}
    assert (
        "contract_payment_milestones",
        "contract_id",
        "missing_parent_link",
    ) in reasons


def test_validate_parent_links_accepts_contract_create_then_milestone():
    from yunwei_win.services.schema_ingest.confirm import (
        _validate_parent_links,
    )

    draft = _draft([
        _table("contracts", [
            _row("contracts:0", decision_op="create"),
        ]),
        _table("contract_payment_milestones", [
            _row("contract_payment_milestones:0", decision_op="create"),
        ]),
    ])
    assert _validate_parent_links(draft) == []


def test_validate_parent_links_accepts_link_existing_with_target():
    from uuid import uuid4

    from yunwei_win.services.schema_ingest.confirm import (
        _validate_parent_links,
    )

    draft = _draft([
        _table("contracts", [
            _row("contracts:0", decision_op="link_existing", target=uuid4()),
        ]),
        _table("contract_payment_milestones", [
            _row("contract_payment_milestones:0", decision_op="create"),
        ]),
    ])
    assert _validate_parent_links(draft) == []


def test_validate_parent_links_skips_ignored_child_rows():
    from yunwei_win.services.schema_ingest.confirm import (
        _validate_parent_links,
    )

    # No contracts at all, but milestone is ignored — nothing to flag.
    draft = _draft([
        _table("contract_payment_milestones", [
            _row(
                "contract_payment_milestones:0",
                decision_op="ignore",
                writable=False,
            ),
        ]),
    ])
    assert _validate_parent_links(draft) == []
