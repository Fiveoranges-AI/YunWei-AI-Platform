"""Tests for the ReviewDraft materializer.

The materializer turns extractor pipeline_results + catalog into a fully-
populated table/cell payload. Key invariant: for every selected table the
draft has one cell per active catalog field, even when AI extracted
nothing for it (`status="missing"`).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest  # noqa: F401 — pytest fixtures registered via conftest

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest import (
    PIPELINE_TABLES,
    ReviewDraft,
    materialize_review_draft,
)
from yunwei_win.services.ingest.unified_schemas import PipelineExtractResult


# ---- helpers ----------------------------------------------------------


def _catalog_from_default() -> dict[str, Any]:
    """Build the runtime catalog shape from ``DEFAULT_COMPANY_SCHEMA``.

    Mirrors ``services.company_schema.catalog._table_to_dict`` enough for
    the materializer: every field gets ``is_array`` (inherited from the
    table) and ``is_active=True``, with ``sort_order`` from enumerate.
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


def _table(draft: ReviewDraft, table_name: str):
    return next(t for t in draft.tables if t.table_name == table_name)


# ---- tests ------------------------------------------------------------


def test_orders_with_partial_extraction_shows_all_six_cells():
    """orders has 6 active fields; extraction provides 4 -> 6 cells, 4
    extracted + 2 missing, in catalog order."""

    catalog = _catalog_from_default()
    route_plan = {
        "selected_pipelines": [
            {"name": "contract_order", "confidence": 0.92, "reason": "包含订单号、金额"}
        ]
    }
    pipeline_results = [
        {
            "name": "contract_order",
            "result": {
                "orders": {
                    "amount_total": 30000,
                    "amount_currency": "USD",
                    "delivery_promised_date": "2026-06-01",
                    "description": "客户订单",
                }
            },
        }
    ]

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="order.pdf",
        route_plan=route_plan,
        pipeline_results=pipeline_results,
        catalog=catalog,
    )

    orders = _table(draft, "orders")
    assert len(orders.rows) == 1
    cells = orders.rows[0].cells
    assert [c.field_name for c in cells] == [
        "customer_id",
        "amount_total",
        "amount_currency",
        "delivery_promised_date",
        "delivery_address",
        "description",
    ]

    cell_by_name = {c.field_name: c for c in cells}

    extracted_names = {
        "amount_total",
        "amount_currency",
        "delivery_promised_date",
        "description",
    }
    for name in extracted_names:
        cell = cell_by_name[name]
        assert cell.status == "extracted", f"{name} expected extracted"
        assert cell.source == "ai"

    # customer_id is required uuid with no default -> missing.
    customer_id_cell = cell_by_name["customer_id"]
    assert customer_id_cell.status == "missing"
    assert customer_id_cell.source == "empty"
    assert customer_id_cell.value is None

    # delivery_address is optional text with no default -> missing.
    delivery_cell = cell_by_name["delivery_address"]
    assert delivery_cell.status == "missing"
    assert delivery_cell.source == "empty"
    assert delivery_cell.value is None


def test_materializer_consumes_pipeline_extract_result_extraction_envelope():
    """Providers return ``PipelineExtractResult.model_dump()`` with the
    extracted payload under ``extraction``. The ReviewDraft materializer must
    consume that canonical envelope directly."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    pipeline_results = [
        PipelineExtractResult(
            name="contract_order",
            extraction={
                "orders": {
                    "amount_total": "30000",
                    "amount_currency": "USD",
                    "delivery_promised_date": "2026-06-01",
                    "description": "客户订单",
                },
                "contracts": {
                    "contract_no_external": "HT-001",
                    "amount_total": "30000",
                    "amount_currency": "USD",
                },
                "contract_payment_milestones": [
                    {
                        "name": "预付款",
                        "ratio": "0.3",
                        "trigger_event": "contract_signed",
                        "raw_text": "合同签订后支付 30%",
                    }
                ],
            },
        ).model_dump(mode="json")
    ]

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="order.pdf",
        route_plan=route_plan,
        pipeline_results=pipeline_results,
        catalog=catalog,
    )

    orders = _table(draft, "orders")
    order_cells = {c.field_name: c for c in orders.rows[0].cells}
    assert order_cells["amount_total"].value == "30000"
    assert order_cells["amount_total"].status == "extracted"
    assert order_cells["amount_currency"].value == "USD"

    contracts = _table(draft, "contracts")
    contract_cells = {c.field_name: c for c in contracts.rows[0].cells}
    assert contract_cells["contract_no_external"].value == "HT-001"
    assert contract_cells["amount_total"].value == "30000"

    milestones = _table(draft, "contract_payment_milestones")
    assert len(milestones.rows) == 1
    milestone_cells = {c.field_name: c for c in milestones.rows[0].cells}
    assert milestone_cells["name"].value == "预付款"
    assert milestone_cells["ratio"].value == "0.3"


def test_default_values_fill_missing_cells():
    """When AI omits a field that has a catalog default and the field is
    non-required + non-uuid, the cell uses the default value, status
    ``extracted``, source ``default``."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    # No amount_currency in extraction -> default ``CNY`` should win.
    pipeline_results = [
        {
            "name": "contract_order",
            "result": {"orders": {"amount_total": 1234}},
        }
    ]

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="order.pdf",
        route_plan=route_plan,
        pipeline_results=pipeline_results,
        catalog=catalog,
    )

    orders = _table(draft, "orders")
    cells = {c.field_name: c for c in orders.rows[0].cells}
    currency = cells["amount_currency"]
    assert currency.value == "CNY"
    assert currency.status == "extracted"
    assert currency.source == "default"


def test_array_table_with_no_items_creates_one_empty_row():
    """``contracts_order`` selects ``contacts``; with no contacts in the
    extraction, the table still has exactly one row of ``missing`` cells."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    pipeline_results = [
        {
            "name": "contract_order",
            "result": {"orders": {"amount_total": 1}},
        }
    ]

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="x.pdf",
        route_plan=route_plan,
        pipeline_results=pipeline_results,
        catalog=catalog,
    )

    contacts = _table(draft, "contacts")
    assert contacts.is_array is True
    assert len(contacts.rows) == 1
    for cell in contacts.rows[0].cells:
        assert cell.status == "missing"
        assert cell.value is None
        assert cell.source == "empty"


def test_unknown_pipeline_is_ignored_not_crashed():
    """Unknown pipelines in the route plan are skipped, not fatal."""

    catalog = _catalog_from_default()
    route_plan = {
        "selected_pipelines": [
            {"name": "totally_unknown"},
            {"name": "still_bogus"},
        ]
    }

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="weird.pdf",
        route_plan=route_plan,
        pipeline_results=[],
        catalog=catalog,
    )

    # No known pipelines -> no selected tables -> empty list.
    assert draft.tables == []


def test_low_confidence_marks_low_confidence_status():
    """A value with confidence < 0.6 gets ``status="low_confidence"``."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    # Wrap value with confidence side-channel.
    pipeline_results = [
        {
            "name": "contract_order",
            "result": {
                "orders": {
                    "amount_total": {"value": 999, "confidence": 0.3},
                }
            },
        }
    ]

    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="low_conf.pdf",
        route_plan=route_plan,
        pipeline_results=pipeline_results,
        catalog=catalog,
    )

    orders = _table(draft, "orders")
    cells = {c.field_name: c for c in orders.rows[0].cells}
    amount = cells["amount_total"]
    assert amount.status == "low_confidence"
    assert amount.value == 999
    assert amount.confidence == pytest.approx(0.3)
    assert amount.source == "ai"


def test_pipeline_tables_map_matches_spec():
    """Sanity: the canonical pipeline -> table map matches the spec."""

    assert PIPELINE_TABLES["identity"] == ["customers", "contacts"]
    assert PIPELINE_TABLES["contract_order"] == [
        "customers",
        "contacts",
        "contracts",
        "contract_payment_milestones",
        "orders",
    ]
    assert PIPELINE_TABLES["finance"] == ["invoices", "invoice_items", "payments"]


def test_materializer_threads_source_text_into_document():
    """The materializer accepts ``document_source_text`` and stamps it onto
    ``ReviewDraft.document.source_text``."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="x.pdf",
        route_plan=route_plan,
        pipeline_results=[],
        catalog=catalog,
        document_source_text="OCR 文本",
    )
    assert draft.document.source_text == "OCR 文本"


def test_materializer_source_text_defaults_to_none():
    """``document_source_text`` is optional; default is ``None``."""

    catalog = _catalog_from_default()
    route_plan = {"selected_pipelines": [{"name": "contract_order"}]}
    draft = materialize_review_draft(
        extraction_id=uuid4(),
        document_id=uuid4(),
        schema_version=1,
        document_filename="x.pdf",
        route_plan=route_plan,
        pipeline_results=[],
        catalog=catalog,
    )
    assert draft.document.source_text is None
