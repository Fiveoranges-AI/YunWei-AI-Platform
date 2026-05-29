"""Snapshot tests for parse_pipeline (P0 task ②).

Adapters are exercised with the MockProvider so no LLM tokens are spent.
Excel adapter is deterministic (no provider involved).

Asserts the candidate JSON shape contracted by task ②:
    - ingestion_id present
    - source.type / source.file_ref
    - entities[] entries each have entity_type, temp_id, fields[],
      missing_required[]
    - each field has name, value, confidence (0..1), source_span
    - relationships[] entries follow {from_temp_id, to_temp_id, type}
    - overall_confidence in [0, 1]
    - warnings is a list (may be empty)
"""

from __future__ import annotations

from pathlib import Path

import pytest


# Override the project-level Postgres-truncating fixture; this file
# doesn't touch any DB.
@pytest.fixture(autouse=True)
def _clean_state():  # noqa: PT004
    yield


_FIXTURES = Path(__file__).parent / "fixtures" / "parse_pipeline"


# ---------------------------------------------------------------------------
# Excel adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excel_adapter_extracts_customers_and_orders_per_row():
    from yunwei_win.services.parse_pipeline import parse_to_candidates

    result = await parse_to_candidates(
        file_path=_FIXTURES / "sample_orders.csv",
        source_type="excel",
        filename="sample_orders.csv",
        content_type="text/csv",
        file_ref="storage://test/sample_orders.csv",
        uploaded_by="tester",
    )

    payload = result.model_dump()

    assert payload["source"]["type"] == "excel"
    assert payload["source"]["file_ref"] == "storage://test/sample_orders.csv"
    assert payload["source"]["uploaded_by"] == "tester"
    assert payload["ingestion_id"]
    assert 0.0 <= payload["overall_confidence"] <= 1.0

    entity_types = [e["entity_type"] for e in payload["entities"]]
    # Two data rows × {Customer, Contact, Order} = 6 entities.
    assert entity_types.count("Customer") == 2
    assert entity_types.count("Order") == 2
    assert entity_types.count("Contact") == 2

    customer = next(e for e in payload["entities"] if e["entity_type"] == "Customer")
    full_name_field = next(f for f in customer["fields"] if f["name"] == "full_name")
    assert full_name_field["value"] == "上海建工集团股份有限公司"
    assert full_name_field["confidence"] >= 0.85
    assert full_name_field["source_span"]["cell"]
    assert full_name_field["source_span"]["cell"].startswith("sheet:")

    # Customer has only full_name required, and it's present → no missing.
    assert customer["missing_required"] == []

    # Customer-has-Order + Customer-has-Contact for each row.
    rel_types = [r["type"] for r in payload["relationships"]]
    assert rel_types.count("Customer-has-Order") == 2
    assert rel_types.count("Customer-has-Contact") == 2


@pytest.mark.asyncio
async def test_excel_adapter_flags_dedup_against_existing_customers():
    from yunwei_win.services.parse_pipeline import parse_to_candidates

    result = await parse_to_candidates(
        file_path=_FIXTURES / "sample_orders.csv",
        source_type="excel",
        filename="sample_orders.csv",
        content_type="text/csv",
        existing_customer_names=["上海建工集团股份有限公司"],
    )

    assert any("疑似重复" in w or "完全同名" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_excel_adapter_warns_when_no_known_headers_found(tmp_path):
    csv = tmp_path / "weird.csv"
    csv.write_text("一些奇怪的栏目,另一个奇怪的栏目\n值1,值2\n", encoding="utf-8")
    from yunwei_win.services.parse_pipeline import parse_to_candidates

    result = await parse_to_candidates(
        file_path=csv,
        source_type="excel",
        filename="weird.csv",
        content_type="text/csv",
    )

    assert result.entities == []
    assert any("未识别到本体字段表头" in w for w in result.warnings) or any(
        "未从该 Excel 抽取" in w for w in result.warnings
    )
    assert result.overall_confidence == 0.0


# ---------------------------------------------------------------------------
# Contract adapter (text PDF / text file fallback)
# ---------------------------------------------------------------------------


def _contract_mock_result():
    from yunwei_win.services.parse_pipeline.providers.base import (
        ProviderEntity, ProviderField, ProviderResult,
    )
    return ProviderResult(
        entities=[
            ProviderEntity(
                entity_type="Customer",
                temp_id="customer-1",
                fields=[
                    ProviderField(
                        name="full_name",
                        value="上海建工集团股份有限公司",
                        confidence=0.95,
                        source_excerpt="甲方（买方）：上海建工集团股份有限公司",
                        source_page=1,
                    ),
                    ProviderField(
                        name="tax_id",
                        value="91310000132206289X",
                        confidence=0.92,
                        source_excerpt="统一社会信用代码：91310000132206289X",
                        source_page=1,
                    ),
                ],
            ),
            ProviderEntity(
                entity_type="Contract",
                temp_id="contract-1",
                fields=[
                    ProviderField(
                        name="contract_no_external",
                        value="HT-2026-0042",
                        confidence=0.9,
                        source_excerpt="采购合同（编号：HT-2026-0042）",
                        source_page=1,
                    ),
                    ProviderField(
                        name="amount_total",
                        value="128000",
                        confidence=0.88,
                        source_excerpt="合同金额：壹拾贰万捌仟元整 ¥128,000.00",
                        source_page=1,
                    ),
                    ProviderField(
                        name="signing_date",
                        value="2026-04-20",
                        confidence=0.93,
                        source_excerpt="签订日期：2026-04-20",
                        source_page=1,
                    ),
                    ProviderField(
                        name="payment_terms",
                        value="货到验收合格后 30 天电汇",
                        confidence=0.8,
                        source_excerpt="账期：货到验收合格后 30 天电汇",
                        source_page=1,
                    ),
                    # Field with no source_excerpt should trigger
                    # confidence penalty + warning.
                    ProviderField(
                        name="status",
                        value="active",
                        confidence=0.7,
                        source_excerpt=None,
                        source_page=None,
                    ),
                ],
            ),
        ],
        relationships=[
            {"from_temp_id": "customer-1", "to_temp_id": "contract-1", "type": "Customer-has-Contract"},
        ],
        warnings=[],
        provider_name="mock",
    )


@pytest.mark.asyncio
async def test_contract_adapter_shapes_provider_output():
    from yunwei_win.services.parse_pipeline import MockProvider, parse_to_candidates

    provider = MockProvider(_contract_mock_result())
    result = await parse_to_candidates(
        file_path=_FIXTURES / "sample_contract.txt",
        source_type="contract",
        filename="sample_contract.txt",
        content_type="text/plain",
        provider=provider,
        file_ref="storage://test/sample_contract.txt",
    )

    payload = result.model_dump()

    assert payload["source"]["type"] == "contract"
    assert payload["ingestion_id"]
    # Provider received the file's text content as markdown.
    assert provider.calls[0].markdown.startswith("采购合同")

    customer = next(e for e in payload["entities"] if e["entity_type"] == "Customer")
    assert customer["temp_id"] == "customer-1"
    full_name = next(f for f in customer["fields"] if f["name"] == "full_name")
    assert full_name["value"] == "上海建工集团股份有限公司"
    assert full_name["source_span"]["text"].startswith("甲方")
    assert full_name["source_span"]["page"] == 1
    assert customer["missing_required"] == []

    contract = next(e for e in payload["entities"] if e["entity_type"] == "Contract")
    # status has no provenance → confidence capped + warning.
    status_field = next(f for f in contract["fields"] if f["name"] == "status")
    assert status_field["confidence"] <= 0.5
    assert any("未提供原文出处" in w for w in result.warnings)

    rels = payload["relationships"]
    assert rels and rels[0]["type"] == "Customer-has-Contract"

    assert 0.0 <= payload["overall_confidence"] <= 1.0


@pytest.mark.asyncio
async def test_contract_adapter_filters_unknown_field_names():
    """A provider can emit a field name that's not in the ontology;
    the adapter must drop it and add a warning rather than crash."""
    from yunwei_win.services.parse_pipeline import MockProvider, parse_to_candidates
    from yunwei_win.services.parse_pipeline.providers.base import (
        ProviderEntity, ProviderField, ProviderResult,
    )

    result_dict = ProviderResult(
        entities=[
            ProviderEntity(
                entity_type="Customer",
                temp_id="customer-1",
                fields=[
                    ProviderField(name="full_name", value="测试客户", confidence=0.9,
                                  source_excerpt="测试客户", source_page=1),
                    ProviderField(name="bogus_field", value="x", confidence=0.9,
                                  source_excerpt="x", source_page=1),
                ],
            ),
        ],
    )
    provider = MockProvider(result_dict)

    result = await parse_to_candidates(
        file_path=_FIXTURES / "sample_contract.txt",
        source_type="contract",
        filename="sample_contract.txt",
        content_type="text/plain",
        provider=provider,
    )

    customer = result.entities[0]
    assert {f.name for f in customer.fields} == {"full_name"}
    assert any("bogus_field" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Screenshot adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screenshot_adapter_passes_image_b64_to_provider():
    from yunwei_win.services.parse_pipeline import MockProvider, parse_to_candidates
    from yunwei_win.services.parse_pipeline.providers.base import (
        ProviderEntity, ProviderField, ProviderResult,
    )

    provider = MockProvider(ProviderResult(
        entities=[
            ProviderEntity(
                entity_type="Contact",
                temp_id="contact-1",
                fields=[
                    ProviderField(
                        name="name", value="张三", confidence=0.88,
                        source_excerpt="张三", source_page=1,
                    ),
                    ProviderField(
                        name="mobile", value="13800001111", confidence=0.86,
                        source_excerpt="13800001111", source_page=1,
                    ),
                ],
            ),
        ],
    ))

    result = await parse_to_candidates(
        file_path=_FIXTURES / "sample_screenshot.png",
        source_type="wechat_screenshot",
        filename="sample_screenshot.png",
        content_type="image/png",
        provider=provider,
    )

    assert provider.calls[0].image_b64  # provider got base64 bytes
    assert provider.calls[0].image_media_type == "image/png"
    assert result.source.type == "wechat_screenshot"
    contact = result.entities[0]
    assert contact.entity_type == "Contact"
    # Contact only requires "name", which is present.
    assert contact.missing_required == []


# ---------------------------------------------------------------------------
# Ontology required-fields contract — guards against silent schema drift
# ---------------------------------------------------------------------------


def test_required_fields_match_task_one_ontology():
    """Cross-check that ontology.required_fields() matches the schema
    that task ① committed. If task ① adds a new NOT NULL column without
    a default to one of these tables, this test fails and forces us to
    decide whether the parser needs to start emitting it."""

    from yunwei_win.services.parse_pipeline.ontology import required_fields

    assert required_fields("Customer") == {"full_name"}
    # Contact.role has SQLEnum default → not required from parser side.
    assert required_fields("Contact") == {"name"}
    # Order.amount_currency has default "CNY" → not required.
    assert required_fields("Order") == set()
    assert required_fields("Contract") == set()
    # Product.name is required; sku optional.
    assert required_fields("Product") == {"name"}
    # OrderItem.sort_order has default=0; system FKs filtered.
    assert required_fields("OrderLine") == set()
    # Invoice.amount_currency has default "CNY"; customer_id is system FK.
    assert required_fields("Invoice") == set()
    # Payment.amount is required (no default), currency has default.
    assert required_fields("Payment") == {"amount"}


def test_unknown_entity_type_returns_empty_required():
    from yunwei_win.services.parse_pipeline.ontology import required_fields

    assert required_fields("ZzzUnknown") == set()
