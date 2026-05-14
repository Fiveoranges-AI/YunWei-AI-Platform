from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from yunwei_win.services.company_schema import DEFAULT_COMPANY_SCHEMA
from yunwei_win.services.schema_ingest.entity_resolution import (
    EntityCandidate,
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
    ParseChunk,
    ParseSourceRef,
)
from yunwei_win.services.schema_ingest.review_draft import (
    materialize_review_draft_vnext,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def _catalog() -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    for table_idx, table in enumerate(DEFAULT_COMPANY_SCHEMA):
        table_is_array = bool(table.get("is_array", False))
        fields = []
        for field_idx, field in enumerate(table["fields"]):
            fields.append(
                {
                    **field,
                    "required": bool(field.get("required", False)),
                    "is_array": bool(field.get("is_array", table_is_array)),
                    "is_active": True,
                    "sort_order": field.get("sort_order", field_idx),
                }
            )
        tables.append(
            {
                **table,
                "fields": fields,
                "is_active": True,
                "sort_order": table.get("sort_order", table_idx),
            }
        )
    return {"tables": tables}


def _empty_proposal_for(table_name: str, client_row_id: str) -> EntityResolutionProposal:
    return EntityResolutionProposal(
        rows=[
            EntityResolutionRow(
                table_name=table_name,
                client_row_id=client_row_id,
                proposed_operation="create",
                match_level="none",
            )
        ]
    )


def test_review_draft_hides_system_fields_and_assigns_steps():
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "orders": [
                NormalizedRow(
                    client_row_id="orders:0",
                    fields={
                        "amount_total": NormalizedFieldValue(
                            value="30000",
                            confidence=0.91,
                            source_refs=[
                                ParseSourceRef(
                                    ref_type="spreadsheet_cell",
                                    ref_id="sheet:报价单!R2C2",
                                )
                            ],
                        )
                    },
                )
            ]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="spreadsheet",
        source_type="spreadsheet",
        markdown="|金额|\n|30000|",
        chunks=[
            ParseChunk(id="sheet:报价单!R2C2", type="table_cell", text="30000")
        ],
        capabilities=ParseCapabilities(spreadsheet_cells=True),
    )
    proposal = _empty_proposal_for("orders", "orders:0")

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="quote.xlsx",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary="报价单",
        warnings=[],
    )

    assert draft.steps[0].key == "commercial"
    table = draft.tables[0]
    assert table.review_step == "commercial"
    assert table.presentation == "card"
    cells = {cell.field_name: cell for cell in table.rows[0].cells}
    assert "amount_total" in cells
    assert "customer_id" not in cells
    assert cells["amount_total"].source_refs[0].ref_id == "sheet:报价单!R2C2"


def test_default_only_row_is_not_writable():
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "orders": [NormalizedRow(client_row_id="orders:0", fields={})]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="",
        capabilities=ParseCapabilities(text_spans=True),
    )
    proposal = _empty_proposal_for("orders", "orders:0")

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="note.txt",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    row = draft.tables[0].rows[0]
    assert row.is_writable is False
    assert row.row_decision.operation == "ignore"


def test_customer_strong_match_maps_to_update_row_decision():
    existing_customer_id = uuid4()
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "customers": [
                NormalizedRow(
                    client_row_id="customers:0",
                    fields={
                        "full_name": NormalizedFieldValue(
                            value="测试有限公司", confidence=0.95
                        )
                    },
                )
            ]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="客户：测试有限公司",
        capabilities=ParseCapabilities(text_spans=True),
    )
    proposal = EntityResolutionProposal(
        rows=[
            EntityResolutionRow(
                table_name="customers",
                client_row_id="customers:0",
                proposed_operation="update",
                selected_entity_id=existing_customer_id,
                match_level="strong",
                match_keys=["full_name"],
                reason="existing customer matched by normalized full_name",
                candidates=[
                    EntityCandidate(
                        entity_id=existing_customer_id,
                        label="测试有限公司",
                        match_level="strong",
                        match_keys=["full_name"],
                    )
                ],
            )
        ]
    )

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="profile.txt",
        parse_artifact=parse,
        selected_tables=["customers"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    row = draft.tables[0].rows[0]
    assert row.row_decision.operation == "update"
    assert row.row_decision.selected_entity_id == existing_customer_id
    assert row.row_decision.match_level == "strong"
    assert row.entity_id == existing_customer_id
    assert row.is_writable is True


def test_low_confidence_cell_status():
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "orders": [
                NormalizedRow(
                    client_row_id="orders:0",
                    fields={
                        "amount_total": NormalizedFieldValue(
                            value="30000", confidence=0.3
                        )
                    },
                )
            ]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="金额 30000",
        capabilities=ParseCapabilities(text_spans=True),
    )
    proposal = _empty_proposal_for("orders", "orders:0")

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="note.txt",
        parse_artifact=parse,
        selected_tables=["orders"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    cells = {cell.field_name: cell for cell in draft.tables[0].rows[0].cells}
    assert cells["amount_total"].status == "low_confidence"


def test_empty_steps_are_skipped_but_summary_added():
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "contacts": [
                NormalizedRow(
                    client_row_id="contacts:0",
                    fields={"name": NormalizedFieldValue(value="张三")},
                )
            ]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="联系人：张三",
        capabilities=ParseCapabilities(text_spans=True),
    )
    proposal = _empty_proposal_for("contacts", "contacts:0")

    draft = materialize_review_draft_vnext(
        extraction_id=uuid4(),
        document_id=uuid4(),
        parse_id=uuid4(),
        document_filename="contacts.txt",
        parse_artifact=parse,
        selected_tables=["contacts"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    assert [s.key for s in draft.steps] == ["contacts", "summary"]


def test_review_draft_model_dump_json_has_uuid_strings():
    extraction_id = uuid4()
    document_id = uuid4()
    parse_id = uuid4()
    extraction = NormalizedExtraction(
        provider="deepseek",
        tables={
            "customers": [
                NormalizedRow(
                    client_row_id="customers:0",
                    fields={
                        "full_name": NormalizedFieldValue(value="测试有限公司")
                    },
                )
            ]
        },
        metadata={},
    )
    parse = ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="测试有限公司",
        capabilities=ParseCapabilities(text_spans=True),
    )
    proposal = _empty_proposal_for("customers", "customers:0")

    draft = materialize_review_draft_vnext(
        extraction_id=extraction_id,
        document_id=document_id,
        parse_id=parse_id,
        document_filename="profile.txt",
        parse_artifact=parse,
        selected_tables=["customers"],
        normalized_extraction=extraction,
        entity_resolution=proposal,
        catalog=_catalog(),
        document_summary=None,
        warnings=[],
    )

    dumped = draft.model_dump(mode="json")
    assert dumped["extraction_id"] == str(extraction_id)
    assert dumped["document_id"] == str(document_id)
    assert dumped["parse_id"] == str(parse_id)
