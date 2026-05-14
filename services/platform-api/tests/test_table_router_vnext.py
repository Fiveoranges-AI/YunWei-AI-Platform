from __future__ import annotations

import pytest

from yunwei_win.services.schema_ingest.parse_artifact import (
    ParseArtifact,
    ParseCapabilities,
)
from yunwei_win.services.schema_ingest.table_router import route_tables


@pytest.fixture(autouse=True)
def _clean_state():
    yield


class FakeRouterLLM:
    async def complete_json(self, *, prompt: str, response_schema: dict):
        assert "customers" in prompt
        return {
            "selected_tables": [
                {"table_name": "customers", "confidence": 0.94, "reason": "包含客户名称"}
            ],
            "rejected_tables": [
                {"table_name": "shipments", "reason": "无物流信息"}
            ],
            "document_summary": "客户资料",
            "needs_human_attention": False,
        }


class FailingRouterLLM:
    async def complete_json(self, *, prompt: str, response_schema: dict):
        raise RuntimeError("llm down")


class WeirdRouterLLM:
    """Returns a real catalog table plus a hallucinated one."""

    async def complete_json(self, *, prompt: str, response_schema: dict):
        return {
            "selected_tables": [
                {"table_name": "customers", "confidence": 0.9},
                {"table_name": "imaginary_table", "confidence": 0.5},
            ],
            "rejected_tables": [],
            "document_summary": "客户 + 凭空表",
            "needs_human_attention": False,
        }


def _artifact() -> ParseArtifact:
    return ParseArtifact(
        version=1,
        provider="text",
        source_type="text",
        markdown="客户：测试有限公司",
        capabilities=ParseCapabilities(text_spans=True),
    )


def _catalog() -> dict:
    return {
        "tables": [
            {
                "table_name": "customers",
                "label": "客户",
                "purpose": "客户主档",
                "is_active": True,
                "fields": [],
            },
            {
                "table_name": "contacts",
                "label": "联系人",
                "purpose": "联系人",
                "is_active": True,
                "fields": [],
            },
            {
                "table_name": "shipments",
                "label": "发货",
                "purpose": "物流",
                "is_active": True,
                "fields": [],
            },
        ]
    }


@pytest.mark.asyncio
async def test_route_tables_returns_selected_table_names():
    result = await route_tables(
        parse_artifact=_artifact(), catalog=_catalog(), llm=FakeRouterLLM()
    )
    assert result.selected_tables[0].table_name == "customers"
    assert result.selected_tables[0].confidence == 0.94
    assert result.rejected_tables[0].table_name == "shipments"
    assert result.document_summary == "客户资料"
    assert result.needs_human_attention is False
    assert result.warnings == []


@pytest.mark.asyncio
async def test_route_tables_fail_open_to_core_tables():
    result = await route_tables(
        parse_artifact=_artifact(), catalog=_catalog(), llm=FailingRouterLLM()
    )
    assert [t.table_name for t in result.selected_tables] == [
        "customers",
        "contacts",
        "customer_journal_items",
    ]
    assert result.needs_human_attention is True
    assert result.warnings
    assert "router failed" in result.warnings[0]


@pytest.mark.asyncio
async def test_route_tables_drops_unknown_table_from_selection():
    result = await route_tables(
        parse_artifact=_artifact(), catalog=_catalog(), llm=WeirdRouterLLM()
    )
    names = [t.table_name for t in result.selected_tables]
    assert "customers" in names
    assert "imaginary_table" not in names
    assert any("imaginary_table" in w for w in result.warnings)
