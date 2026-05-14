"""Catalog helper + vNext smoke tests for the review-draft materializer.

The detailed vNext coverage lives in ``tests/test_review_draft_vnext.py``.
This file keeps the ``_catalog_from_default`` helper alive because the
legacy provider tests (LandingAI / DeepSeek) still import it, and adds
one smoke test against ``materialize_review_draft_vnext`` so the helper
is exercised against the vNext shape rather than the dropped
``selected_pipelines`` / ``pipeline_results`` contract.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.entity_resolution import (
    EntityResolutionProposal,
    EntityResolutionRow,
)
from yunwei_win.services.schema_ingest.extraction_normalize import (
    NormalizedExtraction,
    NormalizedFieldValue,
    NormalizedRow,
)
from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
)
from yunwei_win.services.schema_ingest.review_draft import (
    materialize_review_draft_vnext,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def _catalog_from_default() -> dict[str, Any]:
    """Build the runtime catalog shape from ``DEFAULT_COMPANY_SCHEMA``.

    Mirrors ``services.company_schema.catalog._table_to_dict`` enough for
    the materializer + legacy extractor-provider tests: every field gets
    ``is_array`` (inherited from the table), ``is_active=True``, and
    ``sort_order`` from enumerate, while ``field_role``/``review_visible``
    flow through from the default seed.
    """

    tables: list[dict[str, Any]] = []
    for table_idx, t in enumerate(DEFAULT_COMPANY_SCHEMA):
        table_is_array = bool(t.get("is_array", False))
        fields = []
        for field_idx, f in enumerate(t["fields"]):
            fields.append(
                {
                    **f,
                    "required": bool(f.get("required", False)),
                    "is_array": bool(f.get("is_array", table_is_array)),
                    "is_active": True,
                    "sort_order": f.get("sort_order", field_idx),
                }
            )
        tables.append(
            {
                **t,
                "fields": fields,
                "is_active": True,
                "sort_order": t.get("sort_order", table_idx),
            }
        )
    return {"tables": tables}


def test_catalog_helper_drives_vnext_materializer_for_orders():
    """Sanity: the catalog helper still produces a shape the vNext
    materializer can consume, and the resulting draft hides system
    fields the way Task 3+ promised.
    """

    catalog = _catalog_from_default()

    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "orders": [
                NormalizedRow(
                    client_row_id="orders:0",
                    fields={
                        "amount_total": NormalizedFieldValue(
                            value="30000", confidence=0.9
                        )
                    },
                )
            ]
        },
        metadata={},
    )
    proposal = EntityResolutionProposal(
        rows=[
            EntityResolutionRow(
                table_name="orders",
                client_row_id="orders:0",
                proposed_operation="create",
                match_level="none",
            )
        ]
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="金额 30000",
        capabilities=ParseCapabilities(text_spans=True),
    )

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="order.pdf",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=catalog,
        document_summary=None,
        warnings=[],
    )

    cells = {cell.field_name: cell for cell in draft.tables[0].rows[0].cells}
    assert "amount_total" in cells
    # System link FKs must not leak into the draft cells.
    assert "customer_id" not in cells
