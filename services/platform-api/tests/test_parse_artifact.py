from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
    ParseChunk,
    ParseSourceRef,
)


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def test_parse_artifact_round_trips_visual_grounding():
    artifact = ParseArtifact(
        version=1,
        provider="landingai",
        source_type="pdf",
        markdown="# Contract\n\nAmount 30000",
        pages=[{"id": "page:1", "page_number": 1}],
        chunks=[ParseChunk(id="chunk:1", type="text", text="Amount 30000", page=1)],
        grounding={"chunk:1": {"bbox": [1, 2, 3, 4], "page": 1}},
        tables=[],
        metadata={"page_count": 1},
        capabilities=ParseCapabilities(
            pages=True, chunks=True, visual_grounding=True, table_cells=True
        ),
    )

    dumped = artifact.model_dump(mode="json")

    assert dumped["chunks"][0]["id"] == "chunk:1"
    assert dumped["grounding"]["chunk:1"]["bbox"] == [1, 2, 3, 4]
    assert dumped["capabilities"]["visual_grounding"] is True


def test_parse_source_ref_accepts_sheet_cells_and_text_spans():
    sheet_ref = ParseSourceRef(
        ref_type="spreadsheet_cell",
        ref_id="sheet:报价单!R3C5",
        sheet="报价单",
        row=3,
        col=5,
    )
    text_ref = ParseSourceRef(
        ref_type="text_span",
        ref_id="text:0-10",
        start=0,
        end=10,
        excerpt="客户名称",
    )

    assert sheet_ref.ref_id == "sheet:报价单!R3C5"
    assert text_ref.excerpt == "客户名称"
