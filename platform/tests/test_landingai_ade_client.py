from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yunwei_win.services import landingai_ade_client as client_module
from yunwei_win.services.landingai_ade_client import (
    LandingAIUnavailable,
    extract_with_schema,
    parse_file_to_markdown,
)


class _FakeADE:
    def __init__(self, *, apikey=None, environment="production"):
        self.apikey = apikey
        self.environment = environment

    def parse(self, *, document, model, save_to=None):
        assert isinstance(document, Path)
        assert model == "dpt-2-latest"
        return SimpleNamespace(
            markdown="# Parsed\n\n甲方：测试客户有限公司",
            chunks=[],
            metadata={"page_count": 1},
            grounding={},
            splits=[],
        )

    def extract(self, *, schema, markdown, model, save_to=None):
        assert '"type": "object"' in schema
        assert "甲方" in markdown
        assert model == "extract-latest"
        return SimpleNamespace(
            extraction={"customer": {"full_name": "测试客户有限公司"}},
            extraction_metadata={"customer.full_name": {"chunk_references": ["c1"]}},
            metadata={"duration": 1.2},
        )


@pytest.mark.asyncio
async def test_parse_file_to_markdown_uses_landingai_client(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module, "LandingAIADE", _FakeADE)
    monkeypatch.setattr(client_module.settings, "vision_agent_api_key", "test-key")
    monkeypatch.setattr(client_module.settings, "landingai_environment", "production")
    monkeypatch.setattr(client_module.settings, "landingai_parse_model", "dpt-2-latest")

    path = tmp_path / "contract.pdf"
    path.write_bytes(b"%PDF")

    parsed = await parse_file_to_markdown(path)

    assert parsed.markdown.startswith("# Parsed")
    assert parsed.metadata["page_count"] == 1


@pytest.mark.asyncio
async def test_extract_with_schema_returns_extraction(monkeypatch):
    monkeypatch.setattr(client_module, "LandingAIADE", _FakeADE)
    monkeypatch.setattr(client_module.settings, "vision_agent_api_key", "test-key")
    monkeypatch.setattr(client_module.settings, "landingai_extract_model", "extract-latest")

    response = await extract_with_schema(
        schema_json='{"type": "object", "properties": {"customer": {"type": "object", "properties": {"full_name": {"type": "string"}}}}}',
        markdown="甲方：测试客户有限公司",
    )

    assert response.extraction["customer"]["full_name"] == "测试客户有限公司"


@pytest.mark.asyncio
async def test_parse_raises_when_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module.settings, "vision_agent_api_key", "")
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF")

    with pytest.raises(LandingAIUnavailable):
        await parse_file_to_markdown(path)
