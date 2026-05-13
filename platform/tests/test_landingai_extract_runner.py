from __future__ import annotations

import pytest

from yunwei_win.services.ingest import landingai_extract as extract_module
from yunwei_win.services.ingest.landingai_extract import extract_selected_pipelines
from yunwei_win.services.ingest.unified_schemas import PipelineSelection


@pytest.mark.asyncio
async def test_extract_selected_pipelines_runs_each_schema(monkeypatch):
    calls = []

    async def fake_extract_with_schema(*, schema_json, markdown):
        calls.append(schema_json)
        from yunwei_win.services.landingai_ade_client import LandingAIExtractResult
        return LandingAIExtractResult(
            extraction={"ok": True},
            extraction_metadata={},
            metadata={"duration": 1},
        )

    monkeypatch.setattr(extract_module, "extract_with_schema", fake_extract_with_schema)
    monkeypatch.setattr(extract_module, "load_schema_json", lambda name: f'{{"type": "object", "properties": {{"{name}": {{"type": "string"}}}}}}')

    results = await extract_selected_pipelines(
        selections=[
            PipelineSelection(name="identity", confidence=0.9),
            PipelineSelection(name="contract_order", confidence=0.8),
        ],
        markdown="甲方：测试客户有限公司",
    )

    assert [r.name for r in results] == ["identity", "contract_order"]
    assert len(calls) == 2
