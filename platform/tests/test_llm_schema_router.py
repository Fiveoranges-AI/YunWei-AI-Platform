from __future__ import annotations

from types import SimpleNamespace

import pytest

from yinhu_brain.services.ingest import llm_schema_router as router_module
from yinhu_brain.services.ingest.llm_schema_router import (
    SCHEMA_ROUTE_TOOL_NAME,
    _coerce_plan,
    _failopen_plan,
    route_schemas,
)
from yinhu_brain.services.ingest.landingai_schemas.registry import PIPELINE_NAMES
from yinhu_brain.services.llm import LLMCallFailed


@pytest.fixture(autouse=True)
def _clean_state():
    yield


def _fake_response(tool_input: dict) -> SimpleNamespace:
    """Build a fake Anthropic Message response carrying a tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        name=SCHEMA_ROUTE_TOOL_NAME,
        input=tool_input,
    )
    return SimpleNamespace(
        content=[block],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        model_dump=lambda: {"content": [{"type": "tool_use", "input": tool_input}]},
    )


def _names(plan):
    return [s.name for s in plan.selected_pipelines]


@pytest.mark.asyncio
async def test_router_picks_identity_and_contract_order_for_contract_without_number(monkeypatch):
    captured = {}

    async def fake_call(*args, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"][0]["text"]
        return _fake_response({
            "primary_pipeline": "contract_order",
            "selected_pipelines": [
                {"name": "identity", "confidence": 0.9, "reason": "甲方"},
                {"name": "contract_order", "confidence": 0.85, "reason": "购销合同 + 产品/数量/付款"},
            ],
            "rejected_pipelines": [],
            "document_summary": "购销合同，需方/供方/产品/付款",
            "needs_human_review": False,
        })

    monkeypatch.setattr(router_module, "call_claude", fake_call)

    plan = await route_schemas(
        session=None,
        document_id=None,
        markdown="购销合同\n需方：测试客户有限公司\n供方：XX 厂\n产品：石墨匣钵 1000 件\n付款方式：30%预付 70%尾款\n交货日期：2026-06-30",
        modality="pdf",
        source_hint="file",
    )

    assert set(_names(plan)) == {"identity", "contract_order"}
    assert plan.primary_pipeline == "contract_order"


@pytest.mark.asyncio
async def test_router_adds_manufacturing_requirement_for_spec_appendix(monkeypatch):
    async def fake_call(*args, **kwargs):
        return _fake_response({
            "selected_pipelines": [
                {"name": "identity", "confidence": 0.8, "reason": "甲方"},
                {"name": "contract_order", "confidence": 0.8, "reason": "合同"},
                {"name": "manufacturing_requirement", "confidence": 0.85, "reason": "规格/验收/包装"},
            ],
            "document_summary": "合同 + 规格附件",
            "needs_human_review": False,
        })

    monkeypatch.setattr(router_module, "call_claude", fake_call)

    plan = await route_schemas(
        session=None,
        document_id=None,
        markdown="规格书：材质 95% 石墨\n质量标准 GB/T xxxx\n包装要求 真空袋\n验收 …",
        modality="pdf",
        source_hint="file",
    )

    assert "manufacturing_requirement" in _names(plan)
    assert "identity" in _names(plan)


@pytest.mark.asyncio
async def test_router_picks_finance_for_invoice_payment(monkeypatch):
    async def fake_call(*args, **kwargs):
        return _fake_response({
            "selected_pipelines": [
                {"name": "identity", "confidence": 0.7, "reason": "买方名称"},
                {"name": "finance", "confidence": 0.9, "reason": "发票号 + 价税合计"},
            ],
        })

    monkeypatch.setattr(router_module, "call_claude", fake_call)
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="增值税专用发票\n发票号码 12345\n价税合计 ¥88,000.00\n购买方 测试客户",
        modality="pdf", source_hint="file",
    )
    assert set(_names(plan)) == {"identity", "finance"}


@pytest.mark.asyncio
async def test_router_picks_logistics_for_delivery_note(monkeypatch):
    async def fake_call(*args, **kwargs):
        return _fake_response({
            "selected_pipelines": [
                {"name": "identity", "confidence": 0.6, "reason": "收货客户"},
                {"name": "logistics", "confidence": 0.85, "reason": "送货单 + 签收"},
            ],
        })

    monkeypatch.setattr(router_module, "call_claude", fake_call)
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="送货单号 SD-001\n收货人 王经理\n签收时间 2026-05-01\n物流：顺丰",
        modality="pdf", source_hint="file",
    )
    assert "logistics" in _names(plan)


@pytest.mark.asyncio
async def test_router_picks_commitment_for_chat(monkeypatch):
    async def fake_call(*args, **kwargs):
        return _fake_response({
            "selected_pipelines": [
                {"name": "identity", "confidence": 0.55, "reason": "客户提到经理"},
                {"name": "commitment_task_risk", "confidence": 0.85, "reason": "承诺/风险/跟进"},
            ],
        })

    monkeypatch.setattr(router_module, "call_claude", fake_call)
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="王经理 16:30 说这周五前安排付款。最近质量问题，客户有点不满。",
        modality="text", source_hint="pasted_text",
    )
    assert "commitment_task_risk" in _names(plan)


@pytest.mark.asyncio
async def test_router_failopen_on_llm_failure(monkeypatch):
    async def boom(*args, **kwargs):
        raise LLMCallFailed("upstream down")

    monkeypatch.setattr(router_module, "call_claude", boom)
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="some text", modality="pdf", source_hint="file",
    )
    assert set(_names(plan)) == set(PIPELINE_NAMES)
    assert plan.needs_human_review is True
    assert "fail-open" in plan.selected_pipelines[0].reason or "LLM" in plan.document_summary


@pytest.mark.asyncio
async def test_router_failopen_on_unparseable_output(monkeypatch):
    """If extract_tool_use_input can't find a tool block we fail-open."""

    async def fake_call(*args, **kwargs):
        # No tool_use block, no JSON in text — extract_tool_use_input will raise.
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="just chatting")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            model_dump=lambda: {"content": []},
        )

    monkeypatch.setattr(router_module, "call_claude", fake_call)
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="something", modality="pdf", source_hint="file",
    )
    assert set(_names(plan)) == set(PIPELINE_NAMES)
    assert plan.needs_human_review is True


@pytest.mark.asyncio
async def test_router_empty_markdown_failopen(monkeypatch):
    plan = await route_schemas(
        session=None, document_id=None,
        markdown="   \n  ", modality="text", source_hint="pasted_text",
    )
    assert set(_names(plan)) == set(PIPELINE_NAMES)


def test_coerce_plan_filters_unknown_schema_names():
    plan = _coerce_plan({
        "selected_pipelines": [
            {"name": "identity", "confidence": 0.9},
            {"name": "not_a_real_schema", "confidence": 0.5},
            {"name": "contract_order", "confidence": 0.7},
        ],
        "needs_human_review": False,
    })
    assert _names(plan) == ["identity", "contract_order"]


def test_failopen_plan_includes_all_six_schemas():
    plan = _failopen_plan("any reason")
    assert set(_names(plan)) == set(PIPELINE_NAMES)
    assert plan.needs_human_review is True
