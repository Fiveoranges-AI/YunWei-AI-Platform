"""Tests for ``validate_pipeline_extraction``.

The orchestrator runs this against every extractor pipeline_result before
materializing the ReviewDraft. Failures should produce human-readable
warnings, not raise — the worker still wants to land ``extracted``.
"""

from __future__ import annotations

from typing import Any

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.extraction_validation import (
    validate_pipeline_extraction,
)


def _catalog_from_default() -> dict[str, Any]:
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


def test_validate_pipeline_extraction_passes_for_canonical_shape():
    catalog = _catalog_from_default()
    extraction = {
        "orders": {
            "amount_total": "30000",
            "amount_currency": "CNY",
            "delivery_promised_date": "2026-06-01",
        },
        "contracts": {
            "contract_no_external": "HT-001",
            "amount_total": "30000",
        },
        "contract_payment_milestones": [
            {"name": "预付款", "ratio": "0.3"},
        ],
    }
    warnings = validate_pipeline_extraction("contract_order", extraction, catalog)
    assert warnings == []


def test_validate_pipeline_extraction_rejects_unknown_top_level_key():
    catalog = _catalog_from_default()
    extraction = {
        "orders": {"amount_total": "1"},
        "ghosts": {"x": 1},
    }
    warnings = validate_pipeline_extraction("contract_order", extraction, catalog)
    assert any("ghosts" in w for w in warnings)
    assert all(w.startswith("contract_order:") for w in warnings)


def test_validate_pipeline_extraction_rejects_wrong_type():
    """A decimal field receiving a non-numeric string is a shape mismatch."""

    catalog = _catalog_from_default()
    extraction = {
        "orders": {"amount_total": "not a number"},
    }
    warnings = validate_pipeline_extraction("contract_order", extraction, catalog)
    assert any("amount_total" in w for w in warnings)
    assert any("decimal" in w for w in warnings)


def test_validate_pipeline_extraction_rejects_unknown_row_field():
    catalog = _catalog_from_default()
    extraction = {
        "orders": {"amount_total": "1", "totally_not_a_field": "x"},
    }
    warnings = validate_pipeline_extraction("contract_order", extraction, catalog)
    assert any("totally_not_a_field" in w for w in warnings)


def test_validate_pipeline_extraction_rejects_non_object_top_level():
    catalog = _catalog_from_default()
    warnings = validate_pipeline_extraction("contract_order", "not an object", catalog)
    assert len(warnings) == 1
    assert "top-level" in warnings[0]


def test_validate_pipeline_extraction_rejects_array_vs_object_mismatch():
    catalog = _catalog_from_default()
    # contract_payment_milestones is an array table but extraction provides
    # a single object.
    extraction = {
        "contract_payment_milestones": {"name": "预付款", "ratio": "0.3"},
    }
    warnings = validate_pipeline_extraction("contract_order", extraction, catalog)
    assert any(
        "contract_payment_milestones" in w and "list" in w for w in warnings
    )


def test_validate_pipeline_extraction_unknown_pipeline_returns_empty():
    """Unknown pipelines are skipped by the materializer; validation should
    not invent failures for them."""

    catalog = _catalog_from_default()
    warnings = validate_pipeline_extraction("totally_unknown", {}, catalog)
    assert warnings == []
