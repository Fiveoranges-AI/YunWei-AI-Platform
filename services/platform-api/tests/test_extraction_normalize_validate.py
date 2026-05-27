from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from yunwei_win.services.schema_ingest import extractors as extractors_module
from yunwei_win.services.schema_ingest.extraction_normalize import (
    normalize_extraction,
)
from yunwei_win.services.schema_ingest.extraction_validation import (
    validate_normalized_extraction,
)
from yunwei_win.services.schema_ingest.extractors import extract_from_parse_artifact
from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
    ParseChunk,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def _artifact() -> ParseArtifact:
    return ParseArtifact(
        version=1,
        provider="spreadsheet",
        source_type="spreadsheet",
        markdown="|金额|\n|30000|",
        chunks=[
            ParseChunk(
                id="sheet:报价单!R2C1",
                type="table_cell",
                text="30000",
            )
        ],
        grounding={"sheet:报价单!R2C1": {"sheet": "报价单", "row": 2, "col": 1}},
        capabilities=ParseCapabilities(spreadsheet_cells=True),
    )


def _catalog() -> dict:
    return {
        "tables": [
            {
                "table_name": "orders",
                "label": "订单",
                "is_active": True,
                "is_array": False,
                "fields": [
                    {
                        "field_name": "amount_total",
                        "label": "订单金额",
                        "data_type": "decimal",
                        "field_role": "extractable",
                        "review_visible": True,
                        "is_active": True,
                    },
                    {
                        "field_name": "customer_id",
                        "label": "客户",
                        "data_type": "uuid",
                        "field_role": "system_link",
                        "review_visible": False,
                        "is_active": True,
                    },
                ],
            },
            {
                "table_name": "customers",
                "label": "客户",
                "is_active": True,
                "is_array": False,
                "fields": [
                    {
                        "field_name": "full_name",
                        "label": "公司全称",
                        "data_type": "text",
                        "field_role": "identity_key",
                        "review_visible": True,
                        "is_active": True,
                    },
                ],
            },
        ]
    }


def test_normalize_deepseek_value_confidence_source_refs():
    raw = {
        "tables": {
            "orders": [
                {
                    "amount_total": {
                        "value": "30000",
                        "confidence": 0.91,
                        "source_refs": ["sheet:报价单!R2C1"],
                    }
                }
            ]
        }
    }
    normalized = normalize_extraction(
        raw, selected_tables=["orders"], provider="deepseek"
    )
    row = normalized.tables["orders"][0]
    assert row.client_row_id == "orders:0"
    assert row.fields["amount_total"].value == "30000"
    assert row.fields["amount_total"].confidence == 0.91
    assert row.fields["amount_total"].source_refs[0].ref_id == "sheet:报价单!R2C1"
    assert row.fields["amount_total"].source_refs[0].ref_type == "spreadsheet_cell"


def test_normalize_landingai_scalar_table_payload():
    raw = {"customers": {"full_name": "测试有限公司"}}
    normalized = normalize_extraction(
        raw, selected_tables=["customers"], provider="landingai"
    )
    assert normalized.provider == "landingai"
    rows = normalized.tables["customers"]
    assert len(rows) == 1
    assert rows[0].client_row_id == "customers:0"
    assert rows[0].fields["full_name"].value == "测试有限公司"
    assert rows[0].fields["full_name"].raw == "测试有限公司"


def test_normalize_landingai_array_table_payload():
    raw = {"contacts": [{"name": "张三"}, {"name": "李四"}]}
    normalized = normalize_extraction(
        raw, selected_tables=["contacts"], provider="landingai"
    )
    rows = normalized.tables["contacts"]
    assert [r.client_row_id for r in rows] == ["contacts:0", "contacts:1"]
    assert rows[0].fields["name"].value == "张三"
    assert rows[1].fields["name"].value == "李四"


def test_normalize_drops_table_not_in_selection_but_keeps_metadata():
    raw = {"tables": {"orders": [{"amount_total": {"value": "30000"}}]}}
    normalized = normalize_extraction(
        raw,
        selected_tables=["customers"],
        provider="deepseek",
        metadata={"job_id": "job-1"},
    )
    assert "orders" not in normalized.tables
    assert normalized.metadata.get("job_id") == "job-1"
    assert "orders" in normalized.metadata.get("dropped_tables", [])


def test_validate_rejects_unknown_system_field_and_bad_source_ref():
    raw = {
        "tables": {
            "orders": [
                {
                    "customer_id": {"value": "not-from-file"},
                    "amount_total": {
                        "value": "30000",
                        "source_refs": ["missing:ref"],
                    },
                }
            ]
        }
    }
    normalized = normalize_extraction(
        raw, selected_tables=["orders"], provider="deepseek"
    )
    warnings = validate_normalized_extraction(
        normalized,
        selected_tables=["orders"],
        catalog=_catalog(),
        parse_artifact=_artifact(),
    )
    assert any(
        "unknown or non-extractable field orders.customer_id" in w for w in warnings
    )
    assert any("source ref missing:ref not found" in w for w in warnings)


def test_validate_passes_when_source_ref_matches_chunk():
    raw = {
        "tables": {
            "orders": [
                {
                    "amount_total": {
                        "value": "30000",
                        "source_refs": ["sheet:报价单!R2C1"],
                    }
                }
            ]
        }
    }
    normalized = normalize_extraction(
        raw, selected_tables=["orders"], provider="deepseek"
    )
    warnings = validate_normalized_extraction(
        normalized,
        selected_tables=["orders"],
        catalog=_catalog(),
        parse_artifact=_artifact(),
    )
    assert warnings == []


@pytest.mark.asyncio
async def test_extract_from_parse_artifact_uses_deepseek_llm_injection():
    class FakeDeepSeekLLM:
        def __init__(self) -> None:
            self.last_prompt: str | None = None
            self.last_schema: dict | None = None

        async def complete_json(self, *, prompt: str, response_schema: dict):
            self.last_prompt = prompt
            self.last_schema = response_schema
            return {
                "tables": {
                    "orders": [
                        {
                            "amount_total": {
                                "value": "30000",
                                "confidence": 0.9,
                                "source_refs": ["sheet:报价单!R2C1"],
                            }
                        }
                    ]
                }
            }

    llm = FakeDeepSeekLLM()
    result = await extract_from_parse_artifact(
        parse_artifact=_artifact(),
        selected_tables=["orders"],
        catalog=_catalog(),
        provider="deepseek",
        llm=llm,
    )

    assert result.provider == "deepseek"
    assert "orders" in result.tables
    row = result.tables["orders"][0]
    assert row.fields["amount_total"].value == "30000"
    assert row.fields["amount_total"].source_refs[0].ref_id == "sheet:报价单!R2C1"
    assert "amount_total" in llm.last_prompt
    assert llm.last_schema is not None


@pytest.mark.asyncio
async def test_extract_from_parse_artifact_uses_landingai_client(monkeypatch):
    captured: dict = {}

    async def fake_extract_with_schema(*, schema_json: str, markdown: str):
        captured["schema_json"] = schema_json
        captured["markdown"] = markdown
        return SimpleNamespace(
            extraction={"orders": {"amount_total": "30000"}},
            extraction_metadata={
                "orders.amount_total": {"chunk_references": ["sheet:报价单!R2C1"]}
            },
            metadata={"duration": 1.2},
        )

    monkeypatch.setattr(
        extractors_module, "extract_with_schema", fake_extract_with_schema
    )

    result = await extract_from_parse_artifact(
        parse_artifact=_artifact(),
        selected_tables=["orders"],
        catalog=_catalog(),
        provider="landingai",
    )

    assert result.provider == "landingai"
    assert "orders" in result.tables
    row = result.tables["orders"][0]
    assert row.fields["amount_total"].value == "30000"
    # extraction_metadata should be preserved on the normalized envelope so
    # downstream code can still consult LandingAI's raw chunk references.
    assert (
        result.metadata.get("extraction_metadata", {})
        .get("orders.amount_total", {})
        .get("chunk_references")
        == ["sheet:报价单!R2C1"]
    )
    assert result.metadata.get("landingai_metadata", {}).get("duration") == 1.2
    # The schema we asked for must be the selected-tables schema, not the
    # legacy pipeline schema — i.e. customer_id (system_link) must NOT be
    # present.
    schema = json.loads(captured["schema_json"])
    assert "orders" in schema["properties"]
    assert "customer_id" not in schema["properties"]["orders"]["properties"]


@pytest.mark.asyncio
async def test_extract_from_parse_artifact_maps_landingai_references(monkeypatch):
    async def fake_extract_with_schema(*, schema_json: str, markdown: str):
        return SimpleNamespace(
            extraction={
                "product_requirements": [
                    {"requirement_text": "表面粗糙度 ≤ Ra1.6"}
                ]
            },
            extraction_metadata={
                "product_requirements[0].requirement_text": {
                    "references": ["0-a"],
                }
            },
            metadata={},
        )

    monkeypatch.setattr(
        extractors_module, "extract_with_schema", fake_extract_with_schema
    )

    result = await extract_from_parse_artifact(
        parse_artifact=_artifact(),
        selected_tables=["product_requirements"],
        catalog=_catalog(),
        provider="landingai",
    )

    field = result.tables["product_requirements"][0].fields["requirement_text"]
    assert field.source_refs[0].ref_id == "0-a"
