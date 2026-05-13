# Schema-First Company Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Win ingest around the tenant company schema: upload/OCR/extract produces a table-based `ReviewDraft` containing every field defined by the selected schema tables, the user reviews/fills missing cells, and confirmation writes only reviewed data into the tenant company data layer.

**Architecture:** Keep OCR, schema routing, and extractor providers, but replace the old `UnifiedDraft -> Review` surface with a schema-first contract. The tenant schema catalog is stored in tenant Postgres, is readable by AI and humans, and drives extraction prompts, review tables, validation, and confirm writeback. AI writes `document_extractions`, `field_provenance`, and optional `schema_change_proposals`; business tables are updated only after human confirmation.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Pydantic v2, existing RQ ingest queue, existing OCR/extractor provider layer, React + TypeScript Vite app, pytest/pytest-asyncio, `npm run check`.

---

## Design Constraints

Follow `/Users/eason/agent-platform/coding-principle.md`:

- **Simple first:** do not patch the current `batchToReview()` mapping with more special cases. The root problem is the contract: the UI only renders fields that survived into `UnifiedDraft`.
- **Surgical boundary:** keep the existing `/win/api/ingest/jobs` and `/win/api/ingest/auto` working until the V2 flow is verified. Add `/win/api/ingest/v2/*` and switch Upload/Review after tests pass.
- **Explicit schema:** table/field definitions live in tenant DB catalog tables, not hard-coded frontend arrays. Backend may seed defaults, but runtime review uses `GET /win/api/company-schema`.
- **Human gate:** AI never directly writes high-impact business tables. Confirmation writes reviewed cells into `customers`, `orders`, `invoices`, etc.
- **Verifiable goal:** a selected `orders` table with 6 schema fields and only 4 extracted values must render 6 review cells: 4 filled, 2 empty/missing and editable.

Reference design from `yinhu-brain` repo:

- `DocumentExtraction`: persist an extraction attempt separately from the business rows.
- `FieldProvenance`: attach evidence to the field/cell, not only the document.
- Inbox/review separation: AI proposal is durable; confirmation applies the proposal.
- Pydantic extraction schemas generate LLM/tool contracts and avoid frontend-only schema drift.

## Current Root Cause

Current backend stores a merged `UnifiedDraft` in `IngestJob.result_json`. `normalize_pipeline_results()` only maps `identity`, `contract_order`, and `commitment_task_risk` into the draft. `finance`, `logistics`, and `manufacturing_requirement` stay in raw `pipeline_results`.

Frontend `Review.tsx` calls `jobToBatch()` then `batchToReview()`. `batchToReview()` renders only selected draft paths such as `customer.full_name`, `contract.contract_no_external`, `order.amount_total`, contacts, payment milestones, commitments, tasks, risks, memory items, and events. It does not render schema fields as tables. Therefore the schema summary can be rich while "AI 提取结论" is sparse.

The fix is a new table/cell review contract, not another normalizer patch.

## Target ReviewDraft Contract

Backend returns this shape from `GET /win/api/ingest/v2/extractions/{extraction_id}` and from extracted jobs:

```json
{
  "extraction_id": "uuid",
  "document_id": "uuid",
  "schema_version": 1,
  "status": "pending_review",
  "document": {
    "filename": "order.pdf",
    "summary": "客户订单，包含总金额和交付地址"
  },
  "route_plan": {
    "selected_pipelines": [
      { "name": "contract_order", "confidence": 0.92, "reason": "包含订单号、金额、交付条款" }
    ]
  },
  "tables": [
    {
      "table_name": "orders",
      "label": "订单",
      "purpose": "客户订单主表",
      "rows": [
        {
          "client_row_id": "orders:0",
          "operation": "create",
          "cells": [
            {
              "field_name": "amount_total",
              "label": "订单金额",
              "data_type": "decimal",
              "required": false,
              "value": 30000,
              "display_value": "30000",
              "status": "extracted",
              "confidence": 0.91,
              "evidence": { "page": 1, "excerpt": "合同总价人民币叁万元整" },
              "source": "ai"
            },
            {
              "field_name": "delivery_address",
              "label": "交付地址",
              "data_type": "text",
              "required": false,
              "value": null,
              "display_value": "",
              "status": "missing",
              "confidence": null,
              "evidence": null,
              "source": "empty"
            }
          ]
        }
      ]
    }
  ],
  "schema_warnings": [],
  "general_warnings": []
}
```

Cell status values:

- `extracted`: AI produced a value.
- `missing`: schema field was expected for the selected table but no value was extracted.
- `low_confidence`: AI produced a value below confidence threshold.
- `edited`: user changed the value before confirm.
- `rejected`: user explicitly excludes this cell from confirm.
- `invalid`: user value fails server validation.

## File Structure

Create:

- `platform/yinhu_brain/models/company_schema.py`
- `platform/yinhu_brain/models/company_data.py`
- `platform/yinhu_brain/models/document_extraction.py`
- `platform/yinhu_brain/services/company_schema/__init__.py`
- `platform/yinhu_brain/services/company_schema/default_catalog.py`
- `platform/yinhu_brain/services/company_schema/catalog.py`
- `platform/yinhu_brain/services/ingest_v2/__init__.py`
- `platform/yinhu_brain/services/ingest_v2/schemas.py`
- `platform/yinhu_brain/services/ingest_v2/review_draft.py`
- `platform/yinhu_brain/services/ingest_v2/auto.py`
- `platform/yinhu_brain/services/ingest_v2/confirm.py`
- `platform/yinhu_brain/api/company_schema.py`
- `platform/yinhu_brain/api/ingest_v2.py`
- `platform/app-win/src/api/ingestV2.ts`
- `platform/app-win/src/components/review/ReviewTableWorkspace.tsx`
- `platform/app-win/src/components/review/ReviewCellEditor.tsx`
- `platform/tests/test_company_schema_catalog.py`
- `platform/tests/test_ingest_v2_review_draft.py`
- `platform/tests/test_ingest_v2_api.py`
- `platform/tests/test_ingest_v2_confirm.py`

Modify:

- `platform/yinhu_brain/models/__init__.py`
- `platform/yinhu_brain/models/field_provenance.py`
- `platform/yinhu_brain/models/ingest_job.py`
- `platform/yinhu_brain/db.py`
- `platform/yinhu_brain/workers/ingest_rq.py`
- `platform/yinhu_brain/__init__.py`
- `platform/app-win/src/api/ingest.ts`
- `platform/app-win/src/data/types.ts`
- `platform/app-win/src/screens/Upload.tsx`
- `platform/app-win/src/screens/Review.tsx`

## Task 1: Add Tenant Schema Catalog Models

**Files:**
- Create: `platform/yinhu_brain/models/company_schema.py`
- Modify: `platform/yinhu_brain/models/__init__.py`
- Test: `platform/tests/test_company_schema_catalog.py`

- [ ] **Step 1: Write model registration test**

Create a test that imports `yinhu_brain.models`, runs `Base.metadata.create_all()` on SQLite, and asserts these tables exist:

```python
expected = {
    "company_schema_tables",
    "company_schema_fields",
    "schema_change_proposals",
}
assert expected.issubset(set(Base.metadata.tables))
```

- [ ] **Step 2: Implement catalog models**

Create `CompanySchemaTable`, `CompanySchemaField`, and `SchemaChangeProposal`.

Required columns:

- `company_schema_tables`: `id`, `table_name`, `label`, `purpose`, `category`, `version`, `is_active`, `sort_order`, timestamps.
- `company_schema_fields`: `id`, `table_id`, `field_name`, `label`, `data_type`, `required`, `is_array`, `enum_values`, `default_value`, `description`, `extraction_hint`, `validation`, `sort_order`, `is_active`, timestamps.
- `schema_change_proposals`: `id`, `source_document_id`, `source_extraction_id`, `proposal_type`, `table_name`, `field_name`, `proposed_payload`, `reason`, `status`, `created_by`, `reviewed_by`, timestamps.

Use plain SQLAlchemy models and JSON columns for `enum_values`, `validation`, and `proposed_payload`.

- [ ] **Step 3: Export models**

Update `platform/yinhu_brain/models/__init__.py` so `create_all()` sees the new tables.

- [ ] **Step 4: Verify**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Commit:

```bash
git add platform/yinhu_brain/models/company_schema.py platform/yinhu_brain/models/__init__.py platform/tests/test_company_schema_catalog.py
git commit -m "feat(ingest): add company schema catalog models"
```

## Task 2: Add Company Data Foundation Tables

**Files:**
- Create: `platform/yinhu_brain/models/company_data.py`
- Modify: `platform/yinhu_brain/models/__init__.py`
- Modify: `platform/yinhu_brain/models/field_provenance.py`
- Test: extend `platform/tests/test_company_schema_catalog.py`

- [ ] **Step 1: Add missing business tables**

Keep existing `customers`, `contacts`, `orders`, and `contracts`. Add these tables for the schema-first company data layer:

- `products`
- `product_requirements`
- `contract_payment_milestones`
- `invoices`
- `invoice_items`
- `payments`
- `shipments`
- `shipment_items`
- `customer_journal_items`

Use simple columns only. Do not add speculative workflow fields.

Important fields:

- `products`: `sku`, `name`, `description`, `specification`, `unit`.
- `product_requirements`: `customer_id`, `product_id`, `requirement_type`, `requirement_text`, `tolerance`, `source_document_id`.
- `contract_payment_milestones`: `contract_id`, `name`, `ratio`, `amount`, `trigger_event`, `trigger_offset_days`, `due_date`, `raw_text`.
- `invoices`: `customer_id`, `order_id`, `invoice_no`, `issue_date`, `amount_total`, `amount_currency`, `tax_amount`, `status`.
- `invoice_items`: `invoice_id`, `product_id`, `description`, `quantity`, `unit_price`, `amount`.
- `payments`: `customer_id`, `invoice_id`, `payment_date`, `amount`, `currency`, `method`, `reference_no`.
- `shipments`: `customer_id`, `order_id`, `shipment_no`, `carrier`, `tracking_no`, `ship_date`, `delivery_date`, `delivery_address`, `status`.
- `shipment_items`: `shipment_id`, `product_id`, `description`, `quantity`, `unit`.
- `customer_journal_items`: `customer_id`, `document_id`, `item_type`, `title`, `content`, `occurred_at`, `due_date`, `severity`, `status`, `confidence`, `raw_excerpt`.

- [ ] **Step 2: Widen provenance entity enum**

Extend `EntityType` in `platform/yinhu_brain/models/field_provenance.py` to include:

```python
product = "product"
product_requirement = "product_requirement"
invoice = "invoice"
invoice_item = "invoice_item"
payment = "payment"
shipment = "shipment"
shipment_item = "shipment_item"
contract_payment_milestone = "contract_payment_milestone"
customer_journal_item = "customer_journal_item"
customer_task = "customer_task"
```

- [ ] **Step 3: Verify tables**

Extend the model test to assert all new table names are registered.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Commit:

```bash
git add platform/yinhu_brain/models/company_data.py platform/yinhu_brain/models/__init__.py platform/yinhu_brain/models/field_provenance.py platform/tests/test_company_schema_catalog.py
git commit -m "feat(ingest): add company data foundation tables"
```

## Task 3: Seed And Serve The Tenant Schema Catalog

**Files:**
- Create: `platform/yinhu_brain/services/company_schema/default_catalog.py`
- Create: `platform/yinhu_brain/services/company_schema/catalog.py`
- Create: `platform/yinhu_brain/api/company_schema.py`
- Modify: `platform/yinhu_brain/__init__.py`
- Test: `platform/tests/test_company_schema_catalog.py`

- [ ] **Step 1: Define default catalog**

`default_catalog.py` exports `DEFAULT_COMPANY_SCHEMA`. Each table entry includes `table_name`, `label`, `purpose`, `category`, and ordered `fields`.

Minimum default tables for V2:

- `customers`
- `contacts`
- `products`
- `product_requirements`
- `contracts`
- `contract_payment_milestones`
- `orders`
- `invoices`
- `invoice_items`
- `payments`
- `shipments`
- `shipment_items`
- `customer_journal_items`
- `customer_tasks`

For `orders`, include at least these six fields to lock the missing-cell behavior:

```python
{
    "table_name": "orders",
    "label": "订单",
    "fields": [
        {"field_name": "customer_id", "label": "客户", "data_type": "uuid", "required": True},
        {"field_name": "amount_total", "label": "订单金额", "data_type": "decimal", "required": False},
        {"field_name": "amount_currency", "label": "币种", "data_type": "text", "required": False, "default_value": "CNY"},
        {"field_name": "delivery_promised_date", "label": "承诺交期", "data_type": "date", "required": False},
        {"field_name": "delivery_address", "label": "交付地址", "data_type": "text", "required": False},
        {"field_name": "description", "label": "订单说明", "data_type": "text", "required": False},
    ],
}
```

- [ ] **Step 2: Implement idempotent seed/read service**

`catalog.py` exposes:

```python
async def ensure_default_company_schema(session: AsyncSession) -> None: ...
async def get_company_schema(session: AsyncSession) -> CompanySchemaDTO: ...
async def create_schema_change_proposal(session: AsyncSession, payload: SchemaChangeProposalCreate) -> SchemaChangeProposalDTO: ...
async def approve_schema_change_proposal(session: AsyncSession, proposal_id: UUID, reviewer: str | None) -> CompanySchemaDTO: ...
```

The seed operation must not duplicate existing active tables/fields.

- [ ] **Step 3: Add API**

`platform/yinhu_brain/api/company_schema.py`:

- `GET /api/company-schema`
- `POST /api/company-schema/change-proposals`
- `POST /api/company-schema/change-proposals/{proposal_id}/approve`

Include router in `yinhu_brain/__init__.py`, so mounted paths become `/win/api/company-schema`.

- [ ] **Step 4: Verify**

Tests:

- `GET /win/api/company-schema` seeds and returns ordered tables.
- Calling it twice does not duplicate rows.
- Approving an `add_field` proposal creates a new active field.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Commit:

```bash
git add platform/yinhu_brain/services/company_schema platform/yinhu_brain/api/company_schema.py platform/yinhu_brain/__init__.py platform/tests/test_company_schema_catalog.py
git commit -m "feat(ingest): serve tenant company schema catalog"
```

## Task 4: Add DocumentExtraction And ReviewDraft Schemas

**Files:**
- Create: `platform/yinhu_brain/models/document_extraction.py`
- Create: `platform/yinhu_brain/services/ingest_v2/schemas.py`
- Modify: `platform/yinhu_brain/models/__init__.py`
- Test: `platform/tests/test_ingest_v2_review_draft.py`

- [ ] **Step 1: Add `DocumentExtraction` model**

Required columns:

- `id`
- `document_id`
- `schema_version`
- `provider`
- `route_plan`
- `raw_pipeline_results`
- `review_draft`
- `status`: `pending_review`, `confirmed`, `ignored`, `failed`
- `warnings`
- `created_by`
- `confirmed_by`
- timestamps

This model mirrors the `yinhu-brain` reference: extraction attempts are durable and separate from confirmed business rows.

- [ ] **Step 2: Add Pydantic schemas**

`services/ingest_v2/schemas.py` defines:

- `ReviewCellEvidence`
- `ReviewCell`
- `ReviewRow`
- `ReviewTable`
- `ReviewDraft`
- `ReviewCellPatch`
- `ConfirmExtractionRequest`
- `ConfirmExtractionResponse`

Keep values typed as `Any | None`; validation happens using `data_type` from catalog.

- [ ] **Step 3: Verify schema serialization**

Test `ReviewDraft.model_validate(...).model_dump(mode="json")` for one table with one extracted and one missing cell.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_v2_review_draft.py -q
```

Commit:

```bash
git add platform/yinhu_brain/models/document_extraction.py platform/yinhu_brain/services/ingest_v2 platform/yinhu_brain/models/__init__.py platform/tests/test_ingest_v2_review_draft.py
git commit -m "feat(ingest): add document extraction review schemas"
```

## Task 5: Materialize Table-Based Review Drafts

**Files:**
- Create: `platform/yinhu_brain/services/ingest_v2/review_draft.py`
- Test: `platform/tests/test_ingest_v2_review_draft.py`

- [ ] **Step 1: Define pipeline-to-table mapping**

In `review_draft.py`:

```python
PIPELINE_TABLES = {
    "identity": ["customers", "contacts"],
    "contract_order": ["customers", "contacts", "contracts", "contract_payment_milestones", "orders"],
    "finance": ["invoices", "invoice_items", "payments"],
    "logistics": ["shipments", "shipment_items"],
    "manufacturing_requirement": ["products", "product_requirements"],
    "commitment_task_risk": ["customer_journal_items", "customer_tasks"],
}
```

- [ ] **Step 2: Implement materializer**

Expose:

```python
def materialize_review_draft(
    *,
    extraction_id: UUID,
    document_id: UUID,
    schema_version: int,
    document_filename: str,
    route_plan: dict[str, Any],
    pipeline_results: list[dict[str, Any]],
    catalog: CompanySchemaDTO,
    document_summary: str | None = None,
    warnings: list[str] | None = None,
) -> ReviewDraft: ...
```

Rules:

- Use selected pipelines from `route_plan.selected_pipelines`.
- For every selected table, render every active field from the catalog.
- If the extracted object has a value, status is `extracted`.
- If the value is empty and field has `default_value`, use default with source `default`.
- If the value is empty and no default exists, status is `missing`.
- Preserve raw extraction under `ReviewTable.raw_extraction` for debugging, but UI should render cells.
- For array tables (`contacts`, `invoice_items`, `shipment_items`, `contract_payment_milestones`, `customer_tasks`, `customer_journal_items`), create one row per extracted item. If none extracted, create one empty row so the user can add values.
- Evidence is attached by matching `field_provenance` paths when provider returns them; otherwise keep `evidence=null`.

- [ ] **Step 3: Add the key failing test**

Test case:

- Catalog has `orders` with 6 fields.
- Route selects `contract_order`.
- Pipeline extraction contains only `amount_total`, `amount_currency`, `delivery_promised_date`, `description`.
- `materialize_review_draft()` returns an `orders` table with exactly 6 cells.
- `delivery_address` and `customer_id` are present with `status == "missing"`.

- [ ] **Step 4: Verify**

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_v2_review_draft.py -q
```

Commit:

```bash
git add platform/yinhu_brain/services/ingest_v2/review_draft.py platform/tests/test_ingest_v2_review_draft.py
git commit -m "feat(ingest): materialize schema review drafts"
```

## Task 6: Add V2 Ingest Orchestrator And Worker Dispatch

**Files:**
- Create: `platform/yinhu_brain/services/ingest_v2/auto.py`
- Modify: `platform/yinhu_brain/models/ingest_job.py`
- Modify: `platform/yinhu_brain/db.py`
- Modify: `platform/yinhu_brain/workers/ingest_rq.py`
- Test: `platform/tests/test_ingest_rq_worker.py`

- [ ] **Step 1: Extend `IngestJob` minimally**

Add nullable columns:

- `workflow_version`: string, default `"v1"`.
- `extraction_id`: FK to `document_extractions.id`, nullable.

Add an idempotent ensure helper in `db.py` for existing tenant DBs:

```python
async def ensure_ingest_v2_tables(engine: AsyncEngine) -> None:
    ...
```

It must create new V2 tables and add missing `ingest_jobs.workflow_version` / `ingest_jobs.extraction_id` columns for already-provisioned tenant databases.

- [ ] **Step 2: Implement `auto_ingest_v2()`**

`auto_ingest_v2()` follows the existing `auto_ingest()` stages:

1. `collect_evidence()`
2. `route_schemas()`
3. `get_extractor_provider().extract_selected()`
4. `ensure_default_company_schema()`
5. `materialize_review_draft()`
6. Insert `DocumentExtraction`
7. Set `Document.raw_llm_response` to include `workflow_version="v2"` and `extraction_id`

It returns:

```python
@dataclass
class AutoIngestV2Result:
    document_id: UUID
    extraction_id: UUID
    route_plan: PipelineRoutePlan
    review_draft: ReviewDraft
```

- [ ] **Step 3: Dispatch worker by `workflow_version`**

In `workers/ingest_rq.py`, after loading the job:

```python
if job.workflow_version == "v2":
    result = await auto_ingest_v2(...)
else:
    result = await auto_ingest(...)
```

For V2 jobs:

- set `j.extraction_id`
- set `j.document_id`
- set `j.result_json = review_draft.model_dump(mode="json")`
- set `j.status = extracted`, `j.stage = done`

Do not break existing V1 worker tests.

- [ ] **Step 4: Verify**

Add worker test with monkeypatched `auto_ingest_v2()` returning a small `ReviewDraft`. Assert the job has `workflow_version == "v2"`, `status == extracted`, `extraction_id` set, and `result_json.tables[0].table_name == "orders"`.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_rq_worker.py -q
```

Commit:

```bash
git add platform/yinhu_brain/services/ingest_v2/auto.py platform/yinhu_brain/models/ingest_job.py platform/yinhu_brain/db.py platform/yinhu_brain/workers/ingest_rq.py platform/tests/test_ingest_rq_worker.py
git commit -m "feat(ingest): run schema-first v2 worker jobs"
```

## Task 7: Add V2 API Surface

**Files:**
- Create: `platform/yinhu_brain/api/ingest_v2.py`
- Modify: `platform/yinhu_brain/__init__.py`
- Test: `platform/tests/test_ingest_v2_api.py`

- [ ] **Step 1: Add endpoints**

`APIRouter(prefix="/api/ingest/v2")`:

- `POST /jobs`: same multipart input as V1, but creates jobs with `workflow_version="v2"`.
- `GET /jobs/{job_id}`: returns job plus `review_draft` when extracted.
- `GET /extractions/{extraction_id}`: returns persisted `DocumentExtraction.review_draft`.
- `PATCH /extractions/{extraction_id}`: accepts cell patches and updates `review_draft`.
- `POST /extractions/{extraction_id}/ignore`: marks extraction ignored.
- `POST /extractions/{extraction_id}/confirm`: confirm reviewed draft.

Keep V2 separate from V1 so upload can switch without breaking history.

- [ ] **Step 2: Include router**

Update `yinhu_brain/__init__.py`:

```python
from yinhu_brain.api.ingest_v2 import router as _ingest_v2_router
router.include_router(_ingest_v2_router)
```

- [ ] **Step 3: Verify API**

Tests:

- `POST /win/api/ingest/v2/jobs` creates queued V2 jobs.
- `GET /win/api/ingest/v2/jobs/{id}` returns `workflow_version == "v2"`.
- `GET /win/api/ingest/v2/extractions/{id}` returns tables from persisted draft.
- `PATCH` changes one cell to `edited`.
- `ignore` is idempotent.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_v2_api.py -q
```

Commit:

```bash
git add platform/yinhu_brain/api/ingest_v2.py platform/yinhu_brain/__init__.py platform/tests/test_ingest_v2_api.py
git commit -m "feat(ingest): expose schema-first v2 APIs"
```

## Task 8: Confirm Reviewed Tables Into Business Tables

**Files:**
- Create: `platform/yinhu_brain/services/ingest_v2/confirm.py`
- Modify: `platform/yinhu_brain/api/ingest_v2.py`
- Test: `platform/tests/test_ingest_v2_confirm.py`

- [ ] **Step 1: Implement validation helpers**

Validate values using catalog `data_type`:

- `text`, `uuid`, `date`, `datetime`, `decimal`, `integer`, `boolean`, `enum`, `json`.
- Empty required fields return 400 with `invalid_cells`.
- Rejected cells are skipped.

- [ ] **Step 2: Implement confirm writer**

Expose:

```python
async def confirm_review_draft(
    *,
    session: AsyncSession,
    extraction_id: UUID,
    request: ConfirmExtractionRequest,
    confirmed_by: str | None,
) -> ConfirmExtractionResponse: ...
```

Rules:

- Load `DocumentExtraction` and catalog.
- Apply submitted patches to server copy of `review_draft`.
- Upsert/create parent rows before child rows: `customers -> contacts/orders/products -> contracts/invoices/shipments -> line items/milestones/payments/journal/tasks`.
- Insert `FieldProvenance` for every confirmed non-empty cell, including edited values with `extracted_by="human"` when source is user edited.
- Mark `DocumentExtraction.status = confirmed`.
- Mark linked `Document.review_status = confirmed`.
- If invoked through V2 job confirm, mark `IngestJob.status = confirmed`.

- [ ] **Step 3: Keep linking simple**

For MVP:

- If a table row has an existing entity id in `ReviewRow.entity_id`, update that row.
- Otherwise create a new row.
- If a child row needs a parent created in the same confirm request, use table order and in-memory `client_row_id -> entity_id` mapping.
- Do not implement fuzzy merge in V2 confirm. Existing V1 merge logic can remain untouched.

- [ ] **Step 4: Verify**

Tests:

- Confirm an `orders` draft with two missing cells filled by user; assert `orders` row contains user values.
- Confirm an `invoices` draft writes `invoices` and `invoice_items`.
- Confirm writes `field_provenance` rows for AI and human-edited cells.
- Missing required `customer_id` returns 400 and does not mark extraction confirmed.

Run:

```bash
cd platform && ./.venv/bin/pytest tests/test_ingest_v2_confirm.py -q
```

Commit:

```bash
git add platform/yinhu_brain/services/ingest_v2/confirm.py platform/yinhu_brain/api/ingest_v2.py platform/tests/test_ingest_v2_confirm.py
git commit -m "feat(ingest): confirm reviewed tables into company data"
```

## Task 9: Add Frontend V2 Types And API Client

**Files:**
- Create: `platform/app-win/src/api/ingestV2.ts`
- Modify: `platform/app-win/src/data/types.ts`

- [ ] **Step 1: Add TypeScript types**

Mirror backend schema names:

- `ReviewCellEvidence`
- `ReviewCellStatus`
- `ReviewCell`
- `ReviewRow`
- `ReviewTable`
- `ReviewDraft`
- `ReviewCellPatch`
- `IngestV2Job`
- `ConfirmExtractionResponse`

Do not reuse `ReviewField`, `ReviewExtraction`, or `SchemaSummary` for V2; those are summary-card concepts.

- [ ] **Step 2: Add API functions**

`ingestV2.ts` exports:

```ts
export async function createIngestV2Jobs(input: { files: File[]; text?: string; sourceHint: SourceHint; uploader?: string }): Promise<CreateIngestV2JobsResponse>
export async function getIngestV2Job(jobId: string): Promise<IngestV2Job>
export async function getReviewDraft(extractionId: string): Promise<ReviewDraft>
export async function patchReviewDraft(extractionId: string, patches: ReviewCellPatch[]): Promise<ReviewDraft>
export async function confirmReviewDraft(extractionId: string, patches: ReviewCellPatch[]): Promise<ConfirmExtractionResponse>
export async function ignoreReviewDraft(extractionId: string): Promise<void>
export async function getCompanySchema(): Promise<CompanySchema>
```

- [ ] **Step 3: Verify**

Run:

```bash
cd platform/app-win && npm run check
```

Commit:

```bash
git add platform/app-win/src/api/ingestV2.ts platform/app-win/src/data/types.ts
git commit -m "feat(win): add schema-first ingest api client"
```

## Task 10: Replace Review Screen With Table Workspace For V2 Jobs

**Files:**
- Create: `platform/app-win/src/components/review/ReviewTableWorkspace.tsx`
- Create: `platform/app-win/src/components/review/ReviewCellEditor.tsx`
- Modify: `platform/app-win/src/screens/Review.tsx`

- [ ] **Step 1: Add table workspace component**

Render `ReviewDraft.tables` directly:

- One section per table.
- One grid/table per `ReviewTable`.
- Columns are schema fields in catalog order.
- Rows are `ReviewRow[]`.
- Empty/missing cells are visible, editable, and styled as missing.
- Evidence chip opens excerpt/page when available.
- Users can reject a cell.
- Users can add a row for array/line-item tables.

Do not place cards inside cards. Use the existing app visual language and keep the layout dense.

- [ ] **Step 2: Wire V2 job loading**

In `Review.tsx`:

- If `params.jobId` loads a V2 job (`workflow_version === "v2"` or `result_json.tables` exists), render `ReviewTableWorkspace`.
- Keep legacy `batchToReview()` path only for V1 jobs and cold preview fallback.

- [ ] **Step 3: Wire confirm/ignore**

For V2:

- Confirm sends all local edits as `ReviewCellPatch[]` to `/extractions/{id}/confirm`.
- Ignore calls `/extractions/{id}/ignore`.
- On confirm success, clear local V2 draft state and navigate consistently with current archive flow.

- [ ] **Step 4: Verify with compile**

Run:

```bash
cd platform/app-win && npm run check
```

Commit:

```bash
git add platform/app-win/src/components/review platform/app-win/src/screens/Review.tsx
git commit -m "feat(win): review extracted data as schema tables"
```

## Task 11: Switch Upload To V2 Jobs

**Files:**
- Modify: `platform/app-win/src/screens/Upload.tsx`
- Modify: `platform/app-win/src/api/ingest.ts` only if shared job list types need compatibility.

- [ ] **Step 1: Submit new uploads to V2**

Replace upload creation call in `Upload.tsx`:

- From `createIngestJobs()`
- To `createIngestV2Jobs()`

Keep active/history polling compatible by either:

- using V2 job list endpoints in `ingestV2.ts`, or
- adding `workflow_version` to the shared `IngestJob` type and filtering both V1/V2 from their own endpoints.

Prefer the simpler path: V2 upload screen uses V2 list endpoints.

- [ ] **Step 2: Preserve legacy history**

Do not delete V1 job history or V1 API client functions. Existing confirmed/failed V1 rows should still render in history if the current screen expects them.

- [ ] **Step 3: Verify**

Run:

```bash
cd platform/app-win && npm run check
```

Commit:

```bash
git add platform/app-win/src/screens/Upload.tsx platform/app-win/src/api/ingest.ts
git commit -m "feat(win): route uploads through schema-first ingest"
```

## Task 12: End-To-End Verification And Cleanup

**Files:**
- Modify docs only if implementation details changed from this plan.

- [ ] **Step 1: Run backend tests**

```bash
cd platform && ./.venv/bin/pytest tests/test_company_schema_catalog.py tests/test_ingest_v2_review_draft.py tests/test_ingest_v2_api.py tests/test_ingest_v2_confirm.py tests/test_ingest_rq_worker.py tests/test_ingest_jobs.py -q
```

- [ ] **Step 2: Run frontend typecheck**

```bash
cd platform/app-win && npm run check
```

- [ ] **Step 3: Manual flow**

Start backend/frontend as normally used in this repo, then verify:

1. Upload a document.
2. Job progresses through OCR/route/extract.
3. Review opens a table workspace.
4. `orders` table displays all schema fields, including empty missing cells.
5. Fill a missing field and confirm.
6. Confirmed business rows and `field_provenance` exist in tenant DB.

- [ ] **Step 4: Final commit**

If all checks pass and no extra files remain:

```bash
git status --short
git commit -m "feat(ingest): rebuild review flow around company schema"
```

Do not include unrelated `.gitignore` changes unless they were intentionally made for this implementation.

## Execution Notes

- Keep old V1 code in place until the V2 Upload/Review path is verified.
- Prefer small commits after each task. If a task becomes too large, split by file ownership: backend models/catalog, backend ingest, frontend API, frontend UI.
- Do not add a schema editor UI in this implementation unless all ingest V2 tasks are complete. The required maintenance surface for this pass is the catalog API and `schema_change_proposals`.
- Do not hide missing fields. Missing schema fields are first-class review cells.
