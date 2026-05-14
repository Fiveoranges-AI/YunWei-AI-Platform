from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yunwei_win.services.schema_ingest.parsers.landingai import LandingAIParser
from yunwei_win.services.schema_ingest.parsers.spreadsheet import SpreadsheetParser
from yunwei_win.services.schema_ingest.parsers.text import TextParser


@pytest.fixture(autouse=True)
def _clean_state():
    yield


@pytest.mark.asyncio
async def test_text_parser_creates_single_chunk_artifact():
    artifact = await TextParser().parse_text(
        "客户：测试有限公司\n金额：30000", filename="note.txt"
    )
    assert artifact.provider == "text"
    assert artifact.source_type == "text"
    assert artifact.markdown.startswith("客户：")
    assert artifact.chunks[0].id == "text:0"
    assert artifact.capabilities.text_spans is True


@pytest.mark.asyncio
async def test_landingai_parser_preserves_chunks_splits_and_grounding(
    monkeypatch, tmp_path
):
    async def fake_parse(path: Path):
        return SimpleNamespace(
            markdown="# Parsed",
            chunks=[{"id": "c1", "text": "客户"}],
            splits=[{"id": "page:1", "page_number": 1}],
            grounding={"c1": {"page": 1, "bbox": [0, 0, 10, 10]}},
            metadata={"page_count": 1},
        )

    monkeypatch.setattr(
        "yunwei_win.services.schema_ingest.parsers.landingai.parse_file_to_markdown",
        fake_parse,
    )
    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF")

    artifact = await LandingAIParser().parse_file(
        path,
        filename="contract.pdf",
        content_type="application/pdf",
        source_type="pdf",
    )

    assert artifact.provider == "landingai"
    assert artifact.markdown == "# Parsed"
    assert artifact.chunks[0].id == "c1"
    assert artifact.grounding["c1"]["bbox"] == [0, 0, 10, 10]
    assert artifact.capabilities.visual_grounding is True


@pytest.mark.asyncio
async def test_spreadsheet_parser_emits_sheet_cell_refs(tmp_path):
    import openpyxl

    path = tmp_path / "quote.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报价单"
    ws["A1"] = "客户"
    ws["B1"] = "金额"
    ws["A2"] = "测试有限公司"
    ws["B2"] = 30000
    wb.save(path)

    artifact = await SpreadsheetParser().parse_file(
        path,
        filename="quote.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        source_type="spreadsheet",
    )

    assert "报价单" in artifact.markdown
    ids = {chunk.id for chunk in artifact.chunks}
    assert "sheet:报价单!R2C2" in ids
    assert artifact.capabilities.spreadsheet_cells is True
