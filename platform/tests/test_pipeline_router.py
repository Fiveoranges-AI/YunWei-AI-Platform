from __future__ import annotations

import pytest

from yinhu_brain.services.ingest.pipeline_router import route_pipelines


@pytest.mark.asyncio
async def test_router_selects_identity_and_contract_order_for_contract_text():
    plan = await route_pipelines(
        markdown="甲方：测试客户有限公司\n合同编号：HT-001\n总金额：120000元\n付款方式：30%预付，70%验收后支付\n交货日期：2026-06-30",
        modality="pdf",
        source_hint="file",
    )

    names = [x.name for x in plan.selected_pipelines]
    assert names == ["identity", "contract_order"]
    assert plan.primary_pipeline == "contract_order"


@pytest.mark.asyncio
async def test_router_selects_commitment_task_risk_for_chat_text():
    plan = await route_pipelines(
        markdown="王经理：这周五前安排付款，下周一你们记得发货。最近质量问题客户有点不满。",
        modality="text",
        source_hint="pasted_text",
    )

    names = [x.name for x in plan.selected_pipelines]
    assert "commitment_task_risk" in names
    assert len(names) <= 3


@pytest.mark.asyncio
async def test_router_selects_finance_for_invoice_text():
    plan = await route_pipelines(
        markdown="增值税专用发票\n发票号码：12345678\n价税合计：¥88,000.00\n购买方名称：测试客户有限公司",
        modality="pdf",
        source_hint="file",
    )

    names = [x.name for x in plan.selected_pipelines]
    assert names == ["identity", "finance"]
