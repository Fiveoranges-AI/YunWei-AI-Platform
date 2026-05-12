# LandingAI Schema-Routed Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prompt-only OCR extraction with a LandingAI Parse + schema-routed Extract flow that chooses one or more fixed business schemas per upload and returns a unified review draft.

**Architecture:** Keep the current `/api/ingest/auto` shape: upload -> evidence -> planner/router -> selected parallel extractors -> merge -> review/confirm. LandingAI becomes the document parsing and schema extraction provider; the router selects fixed schema pipelines from parsed Markdown, not frontend file type guesses. Existing Mistral/DeepSeek flow remains as a fallback behind a config flag during rollout.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Pydantic v2, `landingai-ade`, LandingAI ADE Parse/Extract/Classify/Split, existing app-win NDJSON progress UI.

---

## Current Baseline

Latest `main` was fetched and the current branch was fast-forwarded to:

```text
6fbeed5 Merge pull request #61 from Fiveoranges-AI/feat/unified-ingest
```

Relevant current files:

- `platform/yinhu_brain/services/ingest/evidence.py` creates one `Document` and one `ocr_text` per upload.
- `platform/yinhu_brain/services/ingest/planner.py` selects among `identity | commercial | ops`.
- `platform/yinhu_brain/services/ingest/auto.py` runs selected extractors in parallel with separate `AsyncSession`s.
- `platform/yinhu_brain/services/ingest/extractors/identity.py` calls DeepSeek/Claude tool extraction.
- `platform/yinhu_brain/services/ingest/extractors/commercial.py` calls DeepSeek/Claude tool extraction.
- `platform/yinhu_brain/services/ingest/extractors/ops.py` calls DeepSeek/Claude tool extraction.
- `platform/app-win/src/api/ingest.ts` already sends all uploads to `/win/api/ingest/auto`.

Important constraint:

- Current canonical DB writeback only supports identity, order/contract, and customer-memory rows. Finance, logistics, and manufacturing schemas can be extracted in V1 as preview/raw pipeline results, but final DB writeback should wait for the V1.2 `win.*` schema tables unless those tables are added in the same implementation branch.

## Target Pipeline

```text
upload file/photo/text
  -> store original payload
  -> LandingAI Parse once for file/photo, direct text for pasted text
  -> schema router over parsed Markdown
  -> selected LandingAI Extract calls in parallel
  -> normalize schema outputs into UnifiedDraft + pipeline_results
  -> review UI
  -> confirm writes supported tables
```

Do not run all schemas by default. Selective activation keeps latency and credit usage bounded.

## Pipeline Registry

The router must choose from fixed business pipelines:

```python
PipelineName = Literal[
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
]
```

V1 active writeback:

- `identity` -> `customers`, `contacts`
- `contract_order` -> `orders`, `contracts`
- `commitment_task_risk` -> `customer_events`, `customer_commitments`, `customer_tasks`, `customer_risk_signals`, `customer_memory_items`

V1 extract-only preview until DB schema exists:

- `finance`
- `logistics`
- `manufacturing_requirement`

## Router Policy

Route from parsed Markdown evidence, not filename.

Default selected schema limits:

- Normal document: 1-2 schemas.
- Long mixed document: max 3 schemas.
- Always include `identity` if the evidence contains a Party A/customer company, buyer-side contacts, customer phone, address, tax ID, or business-card fields.

Route examples:

```text
contract PDF
  -> identity + contract_order

contract PDF with product specification appendix
  -> identity + contract_order + manufacturing_requirement

business card photo
  -> identity

WeChat/email/customer note
  -> identity + commitment_task_risk

invoice/payment proof/reconciliation sheet
  -> identity + finance

delivery note/shipment proof/inventory screenshot
  -> identity + logistics
```

Use LandingAI Classify/Split only for multi-document or multi-page bundles. Do not make Classify the only router in V1 because the product needs multi-label business pipeline selection, while page classification is usually single-label.

---

## Agent Assignment Map

- Agent A: LandingAI dependency, config, and client wrapper.
- Agent B: LandingAI schema registry and JSON schema files.
- Agent C: Pipeline router model and routing logic.
- Agent D: Orchestrator integration and parallel Extract execution.
- Agent E: Normalization into current `UnifiedDraft` and raw `pipeline_results`.
- Agent F: Frontend progress/result shape updates.
- Agent G: Integration tests, rollout guardrails, and docs.

Agents A and B can run in parallel. Agent C depends on Agent B's registry names. Agents D and E depend on A/B/C. Agent F depends on final response shape from D/E. Agent G runs after each task and again at the end.

---

### Task 1: Add LandingAI Config And Client Wrapper

**Owner:** Agent A

**Files:**

- Modify: `platform/pyproject.toml`
- Modify: `platform/yinhu_brain/config.py`
- Create: `platform/yinhu_brain/services/landingai_ade_client.py`
- Create: `platform/tests/test_landingai_ade_client.py`

- [ ] **Step 1: Add dependency**

Modify `platform/pyproject.toml` dependencies:

```toml
"landingai-ade>=0.1.0",
```

Keep the existing Mistral dependency path unchanged.

- [ ] **Step 2: Add settings**

Modify `platform/yinhu_brain/config.py`:

```python
from typing import Literal


class Settings(BaseSettings):
    # existing fields stay unchanged

    # ---- Document extraction provider ----------------------------------
    document_ai_provider: Literal["mistral", "landingai"] = "mistral"

    # ---- LandingAI ADE --------------------------------------------------
    # LandingAI's Python library reads VISION_AGENT_API_KEY from env. We keep
    # the value in settings too so Railway/.env config can be validated.
    vision_agent_api_key: str = ""
    landingai_environment: Literal["us", "eu"] = "us"
    landingai_parse_model: str = "dpt-2-latest"
    landingai_extract_model: str = "extract-latest"
    landingai_classify_model: str = "classify-latest"
    landingai_split_model: str = "split-latest"
    landingai_large_file_pages_threshold: int = 50
```

- [ ] **Step 3: Write failing wrapper tests**

Create `platform/tests/test_landingai_ade_client.py`:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yinhu_brain.services import landingai_ade_client as client_module
from yinhu_brain.services.landingai_ade_client import (
    LandingAIUnavailable,
    extract_with_schema,
    parse_file_to_markdown,
)


class _FakeADE:
    def __init__(self, *, environment="us"):
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
    monkeypatch.setattr(client_module.settings, "landingai_environment", "us")
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
```

- [ ] **Step 4: Run failing test**

Run:

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_ade_client.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError or ImportError for landingai_ade_client
```

- [ ] **Step 5: Implement wrapper**

Create `platform/yinhu_brain/services/landingai_ade_client.py`:

```python
"""Thin async wrapper around LandingAI ADE's synchronous Python client."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from landingai_ade import LandingAIADE

from yinhu_brain.config import settings


class LandingAIUnavailable(Exception):
    """LandingAI ADE is not configured or the upstream call failed."""


@dataclass
class LandingAIParseResult:
    markdown: str
    chunks: list[Any]
    metadata: dict[str, Any]
    grounding: dict[str, Any]
    splits: list[Any]


@dataclass
class LandingAIExtractResult:
    extraction: dict[str, Any]
    extraction_metadata: dict[str, Any]
    metadata: dict[str, Any]


def _client() -> LandingAIADE:
    key = settings.vision_agent_api_key.strip()
    if not key:
        raise LandingAIUnavailable("VISION_AGENT_API_KEY is not configured")
    os.environ.setdefault("VISION_AGENT_API_KEY", key)
    return LandingAIADE(environment=settings.landingai_environment)


async def parse_file_to_markdown(path: Path) -> LandingAIParseResult:
    def _run():
        client = _client()
        return client.parse(
            document=path,
            model=settings.landingai_parse_model,
        )

    try:
        response = await asyncio.to_thread(_run)
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI parse failed: {exc!s}") from exc

    return LandingAIParseResult(
        markdown=response.markdown or "",
        chunks=list(response.chunks or []),
        metadata=dict(response.metadata or {}),
        grounding=dict(response.grounding or {}),
        splits=list(response.splits or []),
    )


async def extract_with_schema(*, schema_json: str, markdown: str) -> LandingAIExtractResult:
    def _run():
        client = _client()
        return client.extract(
            schema=schema_json,
            markdown=markdown,
            model=settings.landingai_extract_model,
        )

    try:
        response = await asyncio.to_thread(_run)
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI extract failed: {exc!s}") from exc

    return LandingAIExtractResult(
        extraction=dict(response.extraction or {}),
        extraction_metadata=dict(response.extraction_metadata or {}),
        metadata=dict(response.metadata or {}),
    )
```

- [ ] **Step 6: Run test**

Run:

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_ade_client.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit**

```bash
git add platform/pyproject.toml platform/yinhu_brain/config.py platform/yinhu_brain/services/landingai_ade_client.py platform/tests/test_landingai_ade_client.py
git commit -m "feat(ingest): add LandingAI ADE client wrapper"
```

---

### Task 2: Add LandingAI Schema Registry And JSON Files

**Owner:** Agent B

**Files:**

- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/__init__.py`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/registry.py`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/identity.schema.json`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/contract_order.schema.json`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/finance.schema.json`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/logistics.schema.json`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/manufacturing_requirement.schema.json`
- Create: `platform/yinhu_brain/services/ingest/landingai_schemas/commitment_task_risk.schema.json`
- Create: `platform/tests/test_landingai_schema_registry.py`

- [ ] **Step 1: Write schema registry tests**

Create `platform/tests/test_landingai_schema_registry.py`:

```python
from __future__ import annotations

import json

import pytest

from yinhu_brain.services.ingest.landingai_schemas.registry import (
    PIPELINE_NAMES,
    load_schema_json,
    validate_landingai_schema,
)


def test_all_pipeline_schemas_load_as_json_objects():
    assert PIPELINE_NAMES == (
        "identity",
        "contract_order",
        "finance",
        "logistics",
        "manufacturing_requirement",
        "commitment_task_risk",
    )
    for name in PIPELINE_NAMES:
        raw = load_schema_json(name)
        schema = json.loads(raw)
        assert schema["type"] == "object"
        assert isinstance(schema["properties"], dict)


def test_contract_order_is_party_a_only():
    schema = json.loads(load_schema_json("contract_order"))
    props = schema["properties"]
    assert "seller" not in props
    assert "customer" in props
    desc = props["customer"]["description"]
    assert "Party A" in desc
    assert "Do not extract Party B" in desc


def test_schema_rejects_unsupported_keywords():
    with pytest.raises(ValueError, match="unsupported LandingAI schema keyword"):
        validate_landingai_schema(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"x": {"type": "string"}},
            }
        )
```

- [ ] **Step 2: Run failing test**

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_schema_registry.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError for landingai_schemas
```

- [ ] **Step 3: Implement registry**

Create `platform/yinhu_brain/services/ingest/landingai_schemas/__init__.py`:

```python
"""Static LandingAI Extract schemas for schema-routed ingest."""
```

Create `platform/yinhu_brain/services/ingest/landingai_schemas/registry.py`:

```python
from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Literal


PipelineName = Literal[
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
]

PIPELINE_NAMES: tuple[PipelineName, ...] = (
    "identity",
    "contract_order",
    "finance",
    "logistics",
    "manufacturing_requirement",
    "commitment_task_risk",
)

_SUPPORTED_KEYS = {
    "type",
    "properties",
    "description",
    "items",
    "enum",
    "format",
    "x-alternativeNames",
}


def _walk_schema(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in _SUPPORTED_KEYS:
                raise ValueError(f"unsupported LandingAI schema keyword {key!r} at {path}")
            if key == "properties":
                if not isinstance(value, dict):
                    raise ValueError(f"properties must be object at {path}")
                for prop_name, prop_schema in value.items():
                    _walk_schema(prop_schema, f"{path}.properties.{prop_name}")
            elif key == "items":
                _walk_schema(value, f"{path}.items")
            elif key == "enum":
                if not all(isinstance(item, str) for item in value):
                    raise ValueError(f"enum values must be strings at {path}")


def validate_landingai_schema(schema: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise ValueError("LandingAI schema top-level type must be object")
    if not isinstance(schema.get("properties"), dict):
        raise ValueError("LandingAI schema must include object properties")
    _walk_schema(schema)


def load_schema_json(name: PipelineName) -> str:
    if name not in PIPELINE_NAMES:
        raise ValueError(f"unknown LandingAI pipeline schema: {name}")
    raw = (
        files(__package__)
        .joinpath(f"{name}.schema.json")
        .read_text(encoding="utf-8")
    )
    validate_landingai_schema(json.loads(raw))
    return raw
```

- [ ] **Step 4: Create JSON schemas**

Create each schema as a LandingAI-compatible JSON object. Do not include `required`, `additionalProperties`, `oneOf`, `anyOf`, `nullable`, `$schema`, `minItems`, or `maxItems`.

`identity.schema.json` top-level fields:

```json
{
  "type": "object",
  "properties": {
    "customer": {
      "type": "object",
      "description": "Only extract the customer / buyer / Party A organization. Do not extract the supplier / seller / Party B as the customer.",
      "properties": {
        "full_name": {"type": "string", "description": "Full legal name of the customer, buyer, or Party A.", "x-alternativeNames": ["甲方", "买方", "客户", "Customer", "Buyer", "Party A"]},
        "short_name": {"type": "string", "description": "Short or commonly used name of the customer."},
        "tax_id": {"type": "string", "description": "Unified social credit code or tax registration number of the customer.", "x-alternativeNames": ["统一社会信用代码", "纳税人识别号", "Tax ID"]},
        "address": {"type": "string", "description": "Registered, office, or delivery address of the customer."}
      }
    },
    "contacts": {
      "type": "array",
      "description": "People belonging to the customer / buyer / Party A side only.",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "Party A / buyer-side contact name."},
          "title": {"type": "string", "description": "Job title, department, or responsibility."},
          "phone": {"type": "string", "description": "Landline phone number."},
          "mobile": {"type": "string", "description": "Mobile phone number."},
          "email": {"type": "string", "description": "Email address."},
          "role": {"type": "string", "description": "Functional role of this customer-side contact.", "enum": ["primary_business", "procurement", "delivery", "acceptance", "invoice", "payment", "legal", "other"]},
          "address": {"type": "string", "description": "Address associated with this contact if present."}
        }
      }
    },
    "extraction_warnings": {"type": "array", "description": "Warnings about missing or ambiguous identity fields.", "items": {"type": "string", "description": "One warning."}}
  }
}
```

`contract_order.schema.json` must use the tested Party-A-only version and include:

- `document_type`
- `customer`
- `contacts`
- `contract`
- `order`
- `items`
- `payment_milestones`
- `risk_terms`
- `extraction_warnings`

`finance.schema.json` top-level fields:

- `customer`
- `invoice` with `invoice_number`, `invoice_code`, `invoice_type`, `issue_date`, `amount_without_tax`, `tax_amount`, `amount_total`, `currency`, `seller_name`, `buyer_name`, `status`
- `items[]` with `description`, `specification`, `quantity`, `unit`, `unit_price`, `amount`
- `payment` with `payment_date`, `amount`, `payer_name`, `payee_name`, `bank_name`, `bank_account`, `transaction_id`, `method`
- `reconciliation` with `period_start`, `period_end`, `opening_balance`, `closing_balance`, `current_period_amount`, `unpaid_amount`
- `extraction_warnings`

`logistics.schema.json` top-level fields:

- `customer`
- `shipment` with `shipment_number`, `document_date`, `status`, `carrier`, `tracking_number`, `delivery_address`, `receiver_name`, `receiver_phone`, `signed_at`
- `items[]` with `product_name`, `specification`, `quantity`, `unit`, `batch_number`, `warehouse`, `remark`
- `inventory_items[]` with `product_name`, `specification`, `available_quantity`, `locked_quantity`, `unit`, `warehouse`, `snapshot_date`
- `extraction_warnings`

`manufacturing_requirement.schema.json` top-level fields:

- `customer`
- `product` with `product_name`, `product_code`, `category`
- `spec` with `specification`, `material`, `grade`, `technical_parameters`, `quality_standard`, `packaging_requirement`, `inspection_requirement`
- `customer_requirement` with `requirement_type`, `description`, `priority`, `effective_date`, `raw_text`
- `safety_stock_rule` with `minimum_quantity`, `target_quantity`, `unit`, `lead_time_days`, `monthly_usage`, `moq`, `replenishment_trigger`
- `extraction_warnings`

`commitment_task_risk.schema.json` top-level fields:

- `customer`
- `summary`
- `events[]` with `title`, `event_type`, `occurred_at`, `description`, `raw_excerpt`, `confidence`
- `commitments[]` with `summary`, `description`, `direction`, `due_date`, `raw_excerpt`, `confidence`
- `tasks[]` with `title`, `description`, `assignee`, `due_date`, `priority`, `raw_excerpt`
- `risk_signals[]` with `summary`, `description`, `severity`, `kind`, `raw_excerpt`, `confidence`
- `memory_items[]` with `content`, `kind`, `raw_excerpt`, `confidence`
- `extraction_warnings`

- [ ] **Step 5: Run registry test**

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_schema_registry.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Commit**

```bash
git add platform/yinhu_brain/services/ingest/landingai_schemas platform/tests/test_landingai_schema_registry.py
git commit -m "feat(ingest): add LandingAI extract schema registry"
```

---

### Task 3: Add Multi-Schema Router

**Owner:** Agent C

**Files:**

- Modify: `platform/yinhu_brain/services/ingest/unified_schemas.py`
- Create: `platform/yinhu_brain/services/ingest/pipeline_router.py`
- Create: `platform/tests/test_pipeline_router.py`

- [ ] **Step 1: Add router schema models**

Modify `platform/yinhu_brain/services/ingest/unified_schemas.py` without removing existing `IngestPlan` yet:

```python
from yinhu_brain.services.ingest.landingai_schemas.registry import PipelineName


class PipelineSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: PipelineName
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class PipelineRoutePlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_pipeline: PipelineName | None = None
    selected_pipelines: list[PipelineSelection] = Field(default_factory=list)
    rejected_pipelines: list[PipelineSelection] = Field(default_factory=list)
    document_summary: str = ""
    needs_human_review: bool = False
```

- [ ] **Step 2: Write router tests**

Create `platform/tests/test_pipeline_router.py`:

```python
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
```

- [ ] **Step 3: Implement deterministic router**

Create `platform/yinhu_brain/services/ingest/pipeline_router.py`:

```python
from __future__ import annotations

import re
from typing import Literal

from yinhu_brain.services.ingest.landingai_schemas.registry import PipelineName
from yinhu_brain.services.ingest.unified_schemas import PipelineRoutePlan, PipelineSelection


_RULES: dict[PipelineName, list[tuple[re.Pattern[str], float]]] = {
    "identity": [
        (re.compile(r"(甲方|买方|客户|联系人|电话|手机|邮箱|统一社会信用代码|有限公司|股份|集团)"), 0.35),
        (re.compile(r"1[3-9]\d{9}"), 0.35),
        (re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+"), 0.35),
    ],
    "contract_order": [
        (re.compile(r"(合同编号|合同号|订单号|采购订单|销售订单|报价单|\bPO\b)", re.I), 0.35),
        (re.compile(r"(总金额|价税合计|单价|数量|付款方式|预付|尾款|交货|交期)"), 0.35),
        (re.compile(r"(甲方|乙方|买方|卖方|供方|需方)"), 0.2),
    ],
    "finance": [
        (re.compile(r"(发票号码|发票代码|增值税|价税合计|开票日期|对账单|回款|付款|收款|银行流水)"), 0.45),
        (re.compile(r"(开户行|账号|交易流水|未付金额|应收|账期)"), 0.3),
    ],
    "logistics": [
        (re.compile(r"(送货单|发货单|签收|物流|运单|快递|仓库|库存|批次|到货|出库|入库)"), 0.45),
        (re.compile(r"(收货人|签收人|运输|承运|库存数量)"), 0.25),
    ],
    "manufacturing_requirement": [
        (re.compile(r"(规格书|技术要求|技术参数|材质|型号|牌号|质量标准|验收标准|包装要求|安全库存|MOQ|最小起订量)"), 0.45),
        (re.compile(r"(月用量|交期要求|提前期|备货|生产任务)"), 0.25),
    ],
    "commitment_task_risk": [
        (re.compile(r"(承诺|答应|确认|跟进|催|安排|下周|本周|月底|投诉|不满|质量问题|延期|风险|偏好|决策人)"), 0.35),
        (re.compile(r"(:\d\d|微信|聊天|消息|会议纪要|邮件)"), 0.25),
    ],
}

_THRESHOLDS: dict[PipelineName, float] = {
    "identity": 0.35,
    "contract_order": 0.55,
    "finance": 0.55,
    "logistics": 0.55,
    "manufacturing_requirement": 0.55,
    "commitment_task_risk": 0.50,
}


def _score(text: str, patterns: list[tuple[re.Pattern[str], float]]) -> float:
    score = 0.0
    for pattern, weight in patterns:
        if pattern.search(text):
            score += weight
    return min(round(score, 3), 1.0)


async def route_pipelines(
    *,
    markdown: str,
    modality: Literal["image", "pdf", "office", "text"],
    source_hint: Literal["file", "camera", "pasted_text"],
) -> PipelineRoutePlan:
    text = markdown or ""
    scores = {name: _score(text, rules) for name, rules in _RULES.items()}

    selected = [
        PipelineSelection(name=name, confidence=score, reason="heuristic match")
        for name, score in scores.items()
        if score >= _THRESHOLDS[name]
    ]

    if any(x.name != "identity" for x in selected) and scores["identity"] >= 0.25:
        if not any(x.name == "identity" for x in selected):
            selected.insert(
                0,
                PipelineSelection(
                    name="identity",
                    confidence=scores["identity"],
                    reason="customer identity likely present alongside business evidence",
                ),
            )

    selected.sort(key=lambda x: (x.name != "identity", -x.confidence, x.name))
    selected = selected[:3]

    if not selected and text.strip():
        selected = [
            PipelineSelection(
                name="commitment_task_risk",
                confidence=0.3,
                reason="fallback memory extraction for unclassified customer evidence",
            )
        ]

    non_identity = [x for x in selected if x.name != "identity"]
    primary = non_identity[0].name if non_identity else (selected[0].name if selected else None)

    rejected = [
        PipelineSelection(name=name, confidence=score, reason="below activation threshold")
        for name, score in scores.items()
        if name not in {x.name for x in selected}
    ]

    return PipelineRoutePlan(
        primary_pipeline=primary,
        selected_pipelines=selected,
        rejected_pipelines=rejected,
        document_summary=text.strip()[:300],
        needs_human_review=len(selected) > 2 or any(x.confidence < 0.6 for x in selected),
    )
```

This deterministic router is the V1 baseline. A later commit may add a DeepSeek rerank call using the same `PipelineRoutePlan` schema, with deterministic output as fallback.

- [ ] **Step 4: Run router tests**

```bash
cd platform
../.venv/bin/pytest tests/test_pipeline_router.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ingest/unified_schemas.py platform/yinhu_brain/services/ingest/pipeline_router.py platform/tests/test_pipeline_router.py
git commit -m "feat(ingest): add schema pipeline router"
```

---

### Task 4: Integrate LandingAI Parse Into Evidence

**Owner:** Agent D

**Files:**

- Modify: `platform/yinhu_brain/services/ingest/evidence.py`
- Modify: `platform/tests/test_evidence.py`

- [ ] **Step 1: Add failing evidence test**

Append to `platform/tests/test_evidence.py`:

```python
@pytest.mark.asyncio
async def test_landingai_provider_parses_file_once(monkeypatch) -> None:
    _patch_store_upload(monkeypatch)
    monkeypatch.setattr(evidence_module.settings, "document_ai_provider", "landingai")

    calls = []

    async def fake_landingai_parse(path):
        calls.append(str(path))
        from yinhu_brain.services.landingai_ade_client import LandingAIParseResult
        return LandingAIParseResult(
            markdown="# Parsed by LandingAI\n\n甲方：测试客户有限公司",
            chunks=[],
            metadata={"page_count": 1},
            grounding={},
            splits=[],
        )

    async def boom_mistral(*a, **k):
        raise AssertionError("Mistral OCR must not run when provider=landingai")

    monkeypatch.setattr(evidence_module, "parse_file_to_markdown", fake_landingai_parse)
    monkeypatch.setattr(evidence_module, "parse_image_to_markdown", boom_mistral)
    monkeypatch.setattr(evidence_module, "parse_pdf_to_markdown", boom_mistral)
    monkeypatch.setattr(evidence_module, "parse_document_to_markdown", boom_mistral)

    session, engine = await _make_session()
    try:
        result = await collect_evidence(
            session=session,
            file_bytes=b"%PDF",
            original_filename="contract.pdf",
            content_type="application/pdf",
            source_hint="file",
        )
        await session.commit()

        assert len(calls) == 1
        assert "Parsed by LandingAI" in result.ocr_text
        assert result.document.ocr_text == result.ocr_text
    finally:
        await session.close()
        await engine.dispose()
```

- [ ] **Step 2: Run failing test**

```bash
cd platform
../.venv/bin/pytest tests/test_evidence.py::test_landingai_provider_parses_file_once -q
```

Expected:

```text
FAILED ... parse_file_to_markdown missing or Mistral path still called
```

- [ ] **Step 3: Modify evidence to prefer LandingAI provider**

In `platform/yinhu_brain/services/ingest/evidence.py`, import:

```python
from yinhu_brain.config import settings
from yinhu_brain.services.landingai_ade_client import (
    LandingAIUnavailable,
    parse_file_to_markdown,
)
```

In `collect_evidence`, after `stored = store_upload(...)` and before modality-specific Mistral handling:

```python
    if modality != "text" and settings.document_ai_provider == "landingai":
        await emit_progress(progress, "landingai_parse", "正在调用 LandingAI Parse 解析文档")
        try:
            parsed = await parse_file_to_markdown(Path(stored.path))
            ocr_text = parsed.markdown or ""
            if parsed.metadata:
                warnings.append(f"LandingAI Parse metadata: {parsed.metadata}")
        except LandingAIUnavailable as exc:
            msg = f"LandingAI parse unavailable: {exc!s}"
            warnings.append(msg)
            logger.warning("landingai parse failed for %s: %s", filename_for_store, exc)
```

Then wrap the existing image/pdf/office Mistral blocks with:

```python
    if not ocr_text:
        # existing modality-specific Mistral/local fallback runs here
```

Do not change the text path.

- [ ] **Step 4: Run evidence tests**

```bash
cd platform
../.venv/bin/pytest tests/test_evidence.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/services/ingest/evidence.py platform/tests/test_evidence.py
git commit -m "feat(ingest): parse evidence with LandingAI when enabled"
```

---

### Task 5: Add LandingAI Extract Runner And Normalizers

**Owner:** Agent E

**Files:**

- Create: `platform/yinhu_brain/services/ingest/landingai_extract.py`
- Create: `platform/yinhu_brain/services/ingest/landingai_normalize.py`
- Modify: `platform/yinhu_brain/services/ingest/unified_schemas.py`
- Create: `platform/tests/test_landingai_extract_runner.py`
- Create: `platform/tests/test_landingai_normalize.py`

- [ ] **Step 1: Extend `UnifiedDraft` with raw pipeline results**

Modify `platform/yinhu_brain/services/ingest/unified_schemas.py`:

```python
class PipelineExtractResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    extraction: dict = Field(default_factory=dict)
    extraction_metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class UnifiedDraft(BaseModel):
    # existing fields stay
    pipeline_results: list[PipelineExtractResult] = Field(default_factory=list)
```

If adding this field breaks frontend typing, Agent F will mirror it in TypeScript.

- [ ] **Step 2: Write extract runner test**

Create `platform/tests/test_landingai_extract_runner.py`:

```python
from __future__ import annotations

import pytest

from yinhu_brain.services.ingest import landingai_extract as extract_module
from yinhu_brain.services.ingest.landingai_extract import extract_selected_pipelines
from yinhu_brain.services.ingest.unified_schemas import PipelineSelection


@pytest.mark.asyncio
async def test_extract_selected_pipelines_runs_each_schema(monkeypatch):
    calls = []

    async def fake_extract_with_schema(*, schema_json, markdown):
        calls.append(schema_json)
        from yinhu_brain.services.landingai_ade_client import LandingAIExtractResult
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
```

- [ ] **Step 3: Implement runner**

Create `platform/yinhu_brain/services/ingest/landingai_extract.py`:

```python
from __future__ import annotations

import asyncio

from yinhu_brain.services.ingest.landingai_schemas.registry import load_schema_json
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult, PipelineSelection
from yinhu_brain.services.landingai_ade_client import LandingAIUnavailable, extract_with_schema


async def _extract_one(selection: PipelineSelection, markdown: str) -> PipelineExtractResult:
    try:
        response = await extract_with_schema(
            schema_json=load_schema_json(selection.name),
            markdown=markdown,
        )
        return PipelineExtractResult(
            name=selection.name,
            extraction=response.extraction,
            extraction_metadata=response.extraction_metadata,
            warnings=[],
        )
    except LandingAIUnavailable as exc:
        return PipelineExtractResult(
            name=selection.name,
            extraction={},
            extraction_metadata={},
            warnings=[f"LandingAI extract failed for {selection.name}: {exc!s}"],
        )


async def extract_selected_pipelines(
    *,
    selections: list[PipelineSelection],
    markdown: str,
) -> list[PipelineExtractResult]:
    return list(
        await asyncio.gather(
            *[_extract_one(selection, markdown) for selection in selections]
        )
    )
```

- [ ] **Step 4: Write normalizer tests**

Create `platform/tests/test_landingai_normalize.py`:

```python
from __future__ import annotations

from yinhu_brain.services.ingest.landingai_normalize import normalize_pipeline_results
from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult


def test_normalize_identity_and_contract_order_into_unified_draft():
    draft = normalize_pipeline_results(
        [
            PipelineExtractResult(
                name="identity",
                extraction={
                    "customer": {"full_name": "测试客户有限公司", "short_name": "测试"},
                    "contacts": [{"name": "王经理", "mobile": "13800000000", "role": "primary_business"}],
                },
            ),
            PipelineExtractResult(
                name="contract_order",
                extraction={
                    "contract": {"contract_number": "HT-001", "signing_date": "2026-05-01"},
                    "order": {"total_amount": 120000, "currency": "CNY", "delivery_promised_date": "2026-06-30"},
                    "payment_milestones": [{"name": "预付款", "ratio": 30, "trigger_event": "contract_signed"}],
                },
            ),
        ]
    )

    assert draft.customer is not None
    assert draft.customer.full_name == "测试客户有限公司"
    assert draft.contacts[0].role == "buyer"
    assert draft.contract is not None
    assert draft.contract.contract_no_external == "HT-001"
    assert draft.order is not None
    assert draft.order.amount_total == 120000
    assert len(draft.pipeline_results) == 2
```

- [ ] **Step 5: Implement normalizers**

Create `platform/yinhu_brain/services/ingest/landingai_normalize.py`:

```python
from __future__ import annotations

from typing import Any

from yinhu_brain.services.ingest.schemas import (
    ContactExtraction,
    ContractExtraction,
    CustomerExtraction,
    OrderExtraction,
    PaymentMilestone,
)
from yinhu_brain.services.ingest.unified_schemas import (
    PipelineExtractResult,
    UnifiedDraft,
)


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.replace(",", "").replace("，", "").replace("¥", "").replace("￥", "").replace("元", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _ratio(v: Any) -> float:
    n = _num(v)
    if n is None:
        return 0.0
    return n / 100.0 if n > 1.0 else n


def _normalize_role(raw: Any) -> str:
    if raw in {"delivery", "acceptance", "invoice", "other"}:
        return raw
    return "buyer"


def normalize_pipeline_results(results: list[PipelineExtractResult]) -> UnifiedDraft:
    draft = UnifiedDraft(pipeline_results=results)
    warnings: list[str] = []

    for result in results:
        data = result.extraction or {}
        warnings.extend(result.warnings)
        warnings.extend(data.get("extraction_warnings") or [])

        if result.name in {"identity", "contract_order", "finance", "logistics", "manufacturing_requirement", "commitment_task_risk"}:
            customer = data.get("customer") or {}
            if customer and draft.customer is None:
                draft.customer = CustomerExtraction.model_validate(
                    {
                        "full_name": customer.get("full_name"),
                        "short_name": customer.get("short_name"),
                        "address": customer.get("address"),
                        "tax_id": customer.get("tax_id"),
                    }
                )

        if result.name in {"identity", "contract_order"}:
            contacts = data.get("contacts") or []
            for c in contacts:
                draft.contacts.append(
                    ContactExtraction.model_validate(
                        {
                            "name": c.get("name"),
                            "title": c.get("title"),
                            "phone": c.get("phone"),
                            "mobile": c.get("mobile"),
                            "email": c.get("email"),
                            "role": _normalize_role(c.get("role")),
                            "address": c.get("address"),
                        }
                    )
                )

        if result.name == "contract_order":
            contract = data.get("contract") or {}
            order = data.get("order") or {}
            milestones = data.get("payment_milestones") or contract.get("payment_milestones") or []
            draft.contract = ContractExtraction.model_validate(
                {
                    "contract_no_external": contract.get("contract_number") or contract.get("contract_no_external"),
                    "payment_milestones": [
                        PaymentMilestone.model_validate(
                            {
                                "name": m.get("name"),
                                "ratio": _ratio(m.get("ratio")),
                                "trigger_event": m.get("trigger_event") or "other",
                                "trigger_offset_days": m.get("trigger_offset_days"),
                                "raw_text": m.get("raw_text"),
                            }
                        )
                        for m in milestones
                    ],
                    "delivery_terms": contract.get("delivery_terms"),
                    "penalty_terms": contract.get("penalty_terms"),
                    "signing_date": contract.get("signing_date"),
                    "effective_date": contract.get("effective_date"),
                    "expiry_date": contract.get("expiry_date"),
                }
            )
            draft.order = OrderExtraction.model_validate(
                {
                    "amount_total": order.get("total_amount") or order.get("amount_total"),
                    "amount_currency": order.get("currency") or order.get("amount_currency") or contract.get("currency") or "CNY",
                    "delivery_promised_date": order.get("delivery_promised_date"),
                    "delivery_address": order.get("delivery_address"),
                    "description": order.get("summary") or order.get("description"),
                }
            )

        if result.name == "commitment_task_risk":
            draft.summary = data.get("summary") or draft.summary
            draft.events = data.get("events") or []
            draft.commitments = data.get("commitments") or []
            draft.tasks = data.get("tasks") or []
            draft.risk_signals = data.get("risk_signals") or []
            draft.memory_items = data.get("memory_items") or []

    draft.warnings = warnings
    draft.confidence_overall = 0.8 if any(r.extraction for r in results) else 0.3
    return draft
```

- [ ] **Step 6: Run tests**

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_extract_runner.py tests/test_landingai_normalize.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 7: Commit**

```bash
git add platform/yinhu_brain/services/ingest/landingai_extract.py platform/yinhu_brain/services/ingest/landingai_normalize.py platform/yinhu_brain/services/ingest/unified_schemas.py platform/tests/test_landingai_extract_runner.py platform/tests/test_landingai_normalize.py
git commit -m "feat(ingest): run LandingAI schema extracts"
```

---

### Task 6: Wire LandingAI Flow Into `/auto`

**Owner:** Agent D

**Files:**

- Modify: `platform/yinhu_brain/services/ingest/auto.py`
- Modify: `platform/yinhu_brain/services/ingest/merge.py`
- Modify: `platform/tests/test_ingest_auto_flow.py`

- [ ] **Step 1: Add orchestrator test**

Append to `platform/tests/test_ingest_auto_flow.py`:

```python
@pytest.mark.asyncio
async def test_auto_ingest_uses_landingai_schema_flow_when_enabled(monkeypatch) -> None:
    engine = await _make_engine()
    _patch_storage(monkeypatch)
    monkeypatch.setattr(auto_module.settings, "document_ai_provider", "landingai")

    async def fake_collect_evidence(**kwargs):
        from yinhu_brain.models import Document, DocumentProcessingStatus, DocumentReviewStatus, DocumentType
        doc = Document(
            type=DocumentType.contract,
            file_url="/tmp/fake.pdf",
            original_filename="contract.pdf",
            content_type="application/pdf",
            file_sha256="1" * 64,
            file_size_bytes=10,
            ocr_text="甲方：测试客户有限公司\n合同编号：HT-001\n总金额：120000元",
            processing_status=DocumentProcessingStatus.parsed,
            review_status=DocumentReviewStatus.pending_review,
        )
        kwargs["session"].add(doc)
        await kwargs["session"].flush()
        from yinhu_brain.services.ingest.evidence import Evidence
        return Evidence(document_id=doc.id, document=doc, ocr_text=doc.ocr_text, modality="pdf")

    async def fake_route_pipelines(**kwargs):
        from yinhu_brain.services.ingest.unified_schemas import PipelineRoutePlan, PipelineSelection
        return PipelineRoutePlan(
            primary_pipeline="contract_order",
            selected_pipelines=[
                PipelineSelection(name="identity", confidence=0.9),
                PipelineSelection(name="contract_order", confidence=0.9),
            ],
            document_summary="contract",
        )

    async def fake_extract_selected_pipelines(**kwargs):
        from yinhu_brain.services.ingest.unified_schemas import PipelineExtractResult
        return [
            PipelineExtractResult(name="identity", extraction={"customer": {"full_name": "测试客户有限公司"}}),
            PipelineExtractResult(name="contract_order", extraction={"contract": {"contract_number": "HT-001"}, "order": {"amount_total": 120000, "amount_currency": "CNY"}}),
        ]

    monkeypatch.setattr(auto_module, "collect_evidence", fake_collect_evidence)
    monkeypatch.setattr(auto_module, "route_pipelines", fake_route_pipelines)
    monkeypatch.setattr(auto_module, "extract_selected_pipelines", fake_extract_selected_pipelines)

    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await auto_ingest(
                session=session,
                file_bytes=b"%PDF",
                original_filename="contract.pdf",
                content_type="application/pdf",
                source_hint="file",
            )

            assert result.draft.customer is not None
            assert result.draft.customer.full_name == "测试客户有限公司"
            assert result.draft.contract is not None
            assert result.draft.contract.contract_no_external == "HT-001"
            assert len(result.draft.pipeline_results) == 2
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run failing test**

```bash
cd platform
../.venv/bin/pytest tests/test_ingest_auto_flow.py::test_auto_ingest_uses_landingai_schema_flow_when_enabled -q
```

Expected:

```text
FAILED ... auto_ingest still uses old planner/extractors
```

- [ ] **Step 3: Extract public candidate builder**

Modify `platform/yinhu_brain/services/ingest/merge.py` by adding this public helper below `_compute_candidates`:

```python
async def build_merge_candidates(
    *,
    session: AsyncSession,
    customer,
    contacts,
) -> MergeCandidates:
    """Compute match candidates from already-merged customer/contact drafts."""
    if customer is None and not contacts:
        return MergeCandidates()
    identity = IdentityDraft(
        customer=customer,
        contacts=list(contacts or []),
        field_provenance=[],
        confidence_overall=1.0,
        parse_warnings=[],
    )
    return await _compute_candidates(session=session, identity=identity)
```

Keep `_compute_candidates` private so the old `merge_drafts` call path stays unchanged.

- [ ] **Step 4: Add LandingAI branch to orchestrator**

Modify `platform/yinhu_brain/services/ingest/auto.py` imports:

```python
from yinhu_brain.config import settings
from yinhu_brain.services.ingest.landingai_extract import extract_selected_pipelines
from yinhu_brain.services.ingest.landingai_normalize import normalize_pipeline_results
from yinhu_brain.services.ingest.merge import (
    MergeCandidates,
    build_merge_candidates,
    merge_drafts,
)
from yinhu_brain.services.ingest.pipeline_router import route_pipelines
```

Inside `auto_ingest`, after `evidence = await collect_evidence(...)`, add:

```python
    if settings.document_ai_provider == "landingai":
        await emit_progress(progress, "route", "正在判断需要使用哪些 LandingAI 提取 schema")
        route_plan = await route_pipelines(
            markdown=evidence.ocr_text,
            modality=evidence.modality,
            source_hint=source_hint,
        )
        await emit_progress(progress, "extract", "正在并行执行 LandingAI schema 提取")
        pipeline_results = await extract_selected_pipelines(
            selections=route_plan.selected_pipelines,
            markdown=evidence.ocr_text,
        )
        await emit_progress(progress, "merge", "正在合并 LandingAI 提取结果")
        draft = normalize_pipeline_results(pipeline_results)
        draft.needs_review_fields = list(draft.needs_review_fields)
        if route_plan.needs_human_review:
            draft.warnings = list(draft.warnings) + ["router requested human review"]
        draft.summary = draft.summary or route_plan.document_summary

        evidence.document.raw_llm_response = {
            "provider": "landingai",
            "route_plan": route_plan.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
        }
        await session.flush()
        await emit_progress(progress, "auto_done", "LandingAI 提取完成，等待用户确认")

        legacy_plan = IngestPlan(
            targets={
                "identity": next((s.confidence for s in route_plan.selected_pipelines if s.name == "identity"), 0.0),
                "commercial": next((s.confidence for s in route_plan.selected_pipelines if s.name == "contract_order"), 0.0),
                "ops": next((s.confidence for s in route_plan.selected_pipelines if s.name == "commitment_task_risk"), 0.0),
            },
            extractors=[],
            reason=route_plan.document_summary,
            review_required=route_plan.needs_human_review,
        )
        candidates = await build_merge_candidates(
            session=session,
            customer=draft.customer,
            contacts=draft.contacts,
        )
        return AutoIngestResult(
            document_id=evidence.document_id,
            plan=legacy_plan,
            draft=draft,
            candidates=candidates,
        )
```

- [ ] **Step 5: Run orchestrator tests**

```bash
cd platform
../.venv/bin/pytest tests/test_ingest_auto_flow.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 6: Commit**

```bash
git add platform/yinhu_brain/services/ingest/auto.py platform/yinhu_brain/services/ingest/merge.py platform/tests/test_ingest_auto_flow.py
git commit -m "feat(ingest): wire LandingAI schema flow into auto ingest"
```

---

### Task 7: Update API And Frontend Types For Pipeline Results

**Owner:** Agent F

**Files:**

- Modify: `platform/yinhu_brain/api/ingest.py`
- Modify: `platform/app-win/src/api/ingest.ts`
- Modify: `platform/app-win/src/screens/Upload.tsx`

- [ ] **Step 1: Add backend response field**

Modify `/auto` response in `platform/yinhu_brain/api/ingest.py`:

```python
return {
    "document_id": str(result.document_id),
    "plan": result.plan.model_dump(mode="json"),
    "draft": result.draft.model_dump(mode="json"),
    "pipeline_results": [
        r.model_dump(mode="json") for r in getattr(result.draft, "pipeline_results", [])
    ],
    "candidates": {
        "customer": [_candidate_dict(c) for c in result.candidates.customer_candidates],
        "contacts": [[_candidate_dict(c) for c in slot] for slot in result.candidates.contact_candidates],
    },
    "needs_review_fields": list(result.draft.needs_review_fields),
}
```

- [ ] **Step 2: Update TypeScript types**

Modify `platform/app-win/src/api/ingest.ts`:

```ts
export type PipelineName =
  | "identity"
  | "contract_order"
  | "finance"
  | "logistics"
  | "manufacturing_requirement"
  | "commitment_task_risk";

export type PipelineExtractResult = {
  name: PipelineName | string;
  extraction: Record<string, unknown>;
  extraction_metadata: Record<string, unknown>;
  warnings: string[];
};

export type UnifiedDraft = {
  // existing fields stay unchanged
  pipeline_results?: PipelineExtractResult[];
};

export type AutoIngestRaw = {
  plan: IngestPlan;
  draft: UnifiedDraft;
  candidates: AutoCandidates;
  needs_review_fields: string[];
  pipeline_results?: PipelineExtractResult[];
};
```

In `finalizeAutoResult`, include:

```ts
pipeline_results: body.pipeline_results ?? body.draft?.pipeline_results ?? [],
```

- [ ] **Step 3: Update progress labels**

In `platform/app-win/src/screens/Upload.tsx`, ensure progress stages render these names:

```ts
const STAGE_LABELS: Record<string, string> = {
  upload: "上传",
  received: "接收",
  stored: "保存",
  landingai_parse: "解析",
  ocr: "OCR",
  route: "路由",
  extract: "提取",
  identity_extract: "身份",
  commercial_extract: "合同",
  ops_extract: "运营",
  merge: "合并",
  auto_done: "草稿",
};
```

- [ ] **Step 4: Run frontend checks**

```bash
cd platform/app-win
npm run build
```

Expected:

```text
build succeeds
```

- [ ] **Step 5: Commit**

```bash
git add platform/yinhu_brain/api/ingest.py platform/app-win/src/api/ingest.ts platform/app-win/src/screens/Upload.tsx
git commit -m "feat(win): surface LandingAI pipeline extraction results"
```

---

### Task 8: Add LandingAI Large-Document Follow-Up Hooks

**Owner:** Agent A or D

**Files:**

- Modify: `platform/yinhu_brain/services/landingai_ade_client.py`
- Create: `platform/tests/test_landingai_large_parse_jobs.py`

- [ ] **Step 1: Add parse job wrapper test**

Create `platform/tests/test_landingai_large_parse_jobs.py`:

```python
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from yinhu_brain.services import landingai_ade_client as client_module
from yinhu_brain.services.landingai_ade_client import parse_large_file_job


class _FakeParseJobs:
    def __init__(self):
        self.polls = 0

    def create(self, *, document, model):
        assert isinstance(document, Path)
        return SimpleNamespace(job_id="job-1")

    def get(self, job_id):
        self.polls += 1
        if self.polls == 1:
            return SimpleNamespace(status="running", progress=0.5)
        return SimpleNamespace(
            status="completed",
            progress=1.0,
            data=SimpleNamespace(markdown="# Done", chunks=[], metadata={}, grounding={}, splits=[]),
        )


class _FakeADE:
    def __init__(self, *, environment="us"):
        self.parse_jobs = _FakeParseJobs()


@pytest.mark.asyncio
async def test_parse_large_file_job_polls_until_completed(monkeypatch, tmp_path):
    monkeypatch.setattr(client_module, "LandingAIADE", _FakeADE)
    monkeypatch.setattr(client_module.settings, "vision_agent_api_key", "test-key")
    path = tmp_path / "large.pdf"
    path.write_bytes(b"%PDF")

    parsed = await parse_large_file_job(path, poll_seconds=0)

    assert parsed.markdown == "# Done"
```

- [ ] **Step 2: Implement parse job wrapper**

Add to `platform/yinhu_brain/services/landingai_ade_client.py`:

```python
import time


async def parse_large_file_job(path: Path, *, poll_seconds: float = 5.0) -> LandingAIParseResult:
    def _run():
        client = _client()
        job = client.parse_jobs.create(
            document=path,
            model=settings.landingai_parse_model,
        )
        while True:
            response = client.parse_jobs.get(job.job_id)
            if response.status == "completed":
                data = response.data
                return LandingAIParseResult(
                    markdown=data.markdown or "",
                    chunks=list(data.chunks or []),
                    metadata=dict(data.metadata or {}),
                    grounding=dict(data.grounding or {}),
                    splits=list(data.splits or []),
                )
            if response.status in {"failed", "error", "cancelled"}:
                raise LandingAIUnavailable(f"LandingAI parse job {job.job_id} ended with {response.status}")
            time.sleep(poll_seconds)

    try:
        return await asyncio.to_thread(_run)
    except LandingAIUnavailable:
        raise
    except Exception as exc:
        raise LandingAIUnavailable(f"LandingAI parse job failed: {exc!s}") from exc
```

Do not wire this into evidence until there is a reliable page-count or file-size gate. This task creates the tested wrapper so the production switch is small.

- [ ] **Step 3: Run tests**

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_large_parse_jobs.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 4: Commit**

```bash
git add platform/yinhu_brain/services/landingai_ade_client.py platform/tests/test_landingai_large_parse_jobs.py
git commit -m "feat(ingest): add LandingAI parse job wrapper"
```

---

### Task 9: Integration Verification And Rollout

**Owner:** Agent G

**Files:**

- Modify: `.env.example`
- Modify: `docs/superpowers/specs/2026-05-10-unified-ingest-extractor-design.md`
- Create: `docs/superpowers/runbooks/landingai-schema-routed-ingest.md`

- [ ] **Step 1: Update environment example**

Modify `.env.example`:

```env
# Document AI provider. Keep mistral until LandingAI route is verified in staging.
DOCUMENT_AI_PROVIDER=mistral

# LandingAI ADE
VISION_AGENT_API_KEY=replace-me
LANDINGAI_ENVIRONMENT=us
LANDINGAI_PARSE_MODEL=dpt-2-latest
LANDINGAI_EXTRACT_MODEL=extract-latest
LANDINGAI_CLASSIFY_MODEL=classify-latest
LANDINGAI_SPLIT_MODEL=split-latest
```

- [ ] **Step 2: Write runbook**

Create `docs/superpowers/runbooks/landingai-schema-routed-ingest.md`:

```markdown
# LandingAI Schema-Routed Ingest Runbook

## Enable In Staging

Set:

```env
DOCUMENT_AI_PROVIDER=landingai
VISION_AGENT_API_KEY=<LandingAI key>
LANDINGAI_ENVIRONMENT=us
```

Restart the backend.

## Smoke Test Inputs

1. Business card image: expect `identity`.
2. Contract PDF: expect `identity + contract_order`.
3. Payment proof or invoice: expect `identity + finance`.
4. Delivery note: expect `identity + logistics`.
5. Customer chat screenshot/text: expect `identity + commitment_task_risk`.

## Success Criteria

- `/win/api/ingest/auto` streams `landingai_parse`, `route`, `extract`, `merge`, `auto_done`.
- Final response includes `draft.pipeline_results`.
- Confirm still writes customers/contacts/order/contract/memory rows for supported pipelines.
- Unsupported preview pipelines appear in raw `pipeline_results` and do not break confirm.

## Rollback

Set:

```env
DOCUMENT_AI_PROVIDER=mistral
```

Restart the backend.
```

- [ ] **Step 3: Run backend tests**

```bash
cd platform
../.venv/bin/pytest tests/test_landingai_ade_client.py tests/test_landingai_schema_registry.py tests/test_pipeline_router.py tests/test_landingai_extract_runner.py tests/test_landingai_normalize.py tests/test_evidence.py tests/test_ingest_auto_flow.py tests/test_ingest_progress_stream.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 4: Run frontend build**

```bash
cd platform/app-win
npm run build
```

Expected:

```text
build succeeds
```

- [ ] **Step 5: Commit**

```bash
git add .env.example docs/superpowers/specs/2026-05-10-unified-ingest-extractor-design.md docs/superpowers/runbooks/landingai-schema-routed-ingest.md
git commit -m "docs(ingest): document LandingAI schema-routed rollout"
```

---

## Acceptance Criteria

- `DOCUMENT_AI_PROVIDER=mistral` keeps existing behavior.
- `DOCUMENT_AI_PROVIDER=landingai` parses uploaded files with LandingAI ADE and stores parsed Markdown in `Document.ocr_text`.
- Router selects fixed pipeline schemas from parsed Markdown.
- LandingAI Extract runs only selected schemas, in parallel.
- Contract/order extraction remains Party-A/customer-first and does not extract Party B as the customer.
- `identity`, `contract_order`, and `commitment_task_risk` normalize into the current `UnifiedDraft`.
- `finance`, `logistics`, and `manufacturing_requirement` are preserved in `pipeline_results` without breaking confirm.
- Frontend progress shows parse, route, extract, merge stages.
- Backend tests and frontend build pass.

## Risks And Guardrails

- LandingAI schema keywords are stricter than generic JSON Schema. Keep schema files limited to `type`, `properties`, `items`, `description`, `enum`, `format`, and `x-alternativeNames`.
- LandingAI Extract is optimized for LandingAI Parse Markdown. Do not edit parsed Markdown before extracting unless a test proves the extraction still works.
- Avoid DB writeback for finance/logistics/manufacturing until the corresponding `win.*` tables exist in this repo.
- Do not remove legacy `/contract`, `/business_card`, or `/wechat_screenshot` endpoints in this branch.
- Keep Mistral fallback available until staging verifies LandingAI on real customer samples.
