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
