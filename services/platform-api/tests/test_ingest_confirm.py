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
