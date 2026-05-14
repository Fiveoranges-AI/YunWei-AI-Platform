# Schema-First Company Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Win ingest around tenant company schema tables so extraction review always shows every active schema field, including empty fields AI did not extract.

**Architecture:** Add a V2 ingest surface under `/api/win/ingest/v2/*` while keeping V1 available. Store tenant schema metadata in each per-enterprise Win database, materialize a table/cell `ReviewDraft` from extractor output plus the schema catalog, and confirm reviewed cells into company data tables with provenance. Frontend V2 review renders `ReviewDraft.tables` directly instead of the old `UnifiedDraft -> batchToReview()` summary.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Pydantic v2, RQ worker, existing OCR/extractor provider layer, React 18 + TypeScript + Vite, pytest/pytest-asyncio.

---

## Ground Rules

Use the current v3 repo structure:

- Backend: `services/platform-api/yunwei_win/`
- Backend tests: `services/platform-api/tests/`
- Frontend: `apps/win-web/`
- Frontend tests/typecheck: `apps/win-web`
- API prefix: `/api/win/*`
- SPA route: `/win/`

Do not use legacy paths:

- `platform/yinhu_brain/*`
- `platform/app-win/*`
- `/win/api/*`

Follow `/Users/eason/agent-platform/coding-principle.md`: small focused changes, explicit contracts, no speculative abstractions, tests for new behavior.

## Current Root Cause

`services/platform-api/yunwei_win/services/ingest/auto.py` returns rich `pipeline_results`, but `landingai_normalize.py` folds only part of that into `UnifiedDraft`. `apps/win-web/src/api/ingest.ts::batchToReview()` then renders a fixed subset of `UnifiedDraft`, so fields from `finance`, `logistics`, and `manufacturing_requirement` can disappear from the main review.

The V2 fix is a new schema-first review contract. Do not keep adding paths to `batchToReview()`.

## Target Contract

`ReviewDraft` is the V2 review payload:

```json
{
  "extraction_id": "uuid",
  "document_id": "uuid",
  "schema_version": 1,
  "status": "pending_review",
  "document": {
    "filename": "order.pdf",
    "summary": "客户订单"
  },
  "tables": [
    {
      "table_name": "orders",
      "label": "订单",
      "rows": [
        {
          "client_row_id": "orders:0",
          "entity_id": null,
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
  ]
}
```

Invariant: selected table fields are complete. For example, if `orders` has six active catalog fields and AI extracts four values, the review draft still has six `orders` cells.

## File Structure

Create:

- `services/platform-api/yunwei_win/models/company_schema.py`
- `services/platform-api/yunwei_win/models/company_data.py`
- `services/platform-api/yunwei_win/models/document_extraction.py`
- `services/platform-api/yunwei_win/services/company_schema/__init__.py`
- `services/platform-api/yunwei_win/services/company_schema/default_catalog.py`
- `services/platform-api/yunwei_win/services/company_schema/catalog.py`
- `services/platform-api/yunwei_win/services/ingest_v2/__init__.py`
- `services/platform-api/yunwei_win/services/ingest_v2/schemas.py`
- `services/platform-api/yunwei_win/services/ingest_v2/review_draft.py`
- `services/platform-api/yunwei_win/services/ingest_v2/auto.py`
- `services/platform-api/yunwei_win/services/ingest_v2/confirm.py`
- `services/platform-api/yunwei_win/api/company_schema.py`
- `services/platform-api/yunwei_win/api/ingest_v2.py`
- `apps/win-web/src/api/ingestV2.ts`
- `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`
- `apps/win-web/src/components/review/ReviewCellEditor.tsx`
- `services/platform-api/tests/test_company_schema_catalog.py`
- `services/platform-api/tests/test_ingest_v2_review_draft.py`
- `services/platform-api/tests/test_ingest_v2_api.py`
- `services/platform-api/tests/test_ingest_v2_confirm.py`

Modify:

- `services/platform-api/yunwei_win/models/__init__.py`
- `services/platform-api/yunwei_win/models/field_provenance.py`
- `services/platform-api/yunwei_win/models/ingest_job.py`
- `services/platform-api/yunwei_win/db.py`
- `services/platform-api/yunwei_win/routes.py`
- `services/platform-api/yunwei_win/workers/ingest_rq.py`
- `apps/win-web/src/api/ingest.ts`
- `apps/win-web/src/data/types.ts`
- `apps/win-web/src/screens/Upload.tsx`
- `apps/win-web/src/screens/Review.tsx`

## Task 1: Company Schema Catalog

**Files:**
- Create: `services/platform-api/yunwei_win/models/company_schema.py`
- Create: `services/platform-api/yunwei_win/services/company_schema/__init__.py`
- Create: `services/platform-api/yunwei_win/services/company_schema/default_catalog.py`
- Create: `services/platform-api/yunwei_win/services/company_schema/catalog.py`
- Create: `services/platform-api/yunwei_win/api/company_schema.py`
- Modify: `services/platform-api/yunwei_win/models/__init__.py`
- Modify: `services/platform-api/yunwei_win/routes.py`
- Test: `services/platform-api/tests/test_company_schema_catalog.py`

- [ ] **Step 1: Write failing model/API tests**

Create `services/platform-api/tests/test_company_schema_catalog.py` using the same in-memory SQLite pattern from `test_ingest_jobs.py`.

Include these tests:

```python
def test_company_schema_models_are_registered():
    assert "company_schema_tables" in Base.metadata.tables
    assert "company_schema_fields" in Base.metadata.tables
    assert "schema_change_proposals" in Base.metadata.tables
```

```python
@pytest.mark.asyncio
async def test_get_company_schema_seeds_default_catalog():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            res = await ac.get("/api/win/company-schema")
            assert res.status_code == 200, res.text
            body = res.json()
            table_names = [t["table_name"] for t in body["tables"]]
            assert "orders" in table_names
            orders = next(t for t in body["tables"] if t["table_name"] == "orders")
            fields = [f["field_name"] for f in orders["fields"]]
            assert fields[:6] == [
                "customer_id",
                "amount_total",
                "amount_currency",
                "delivery_promised_date",
                "delivery_address",
                "description",
            ]
    finally:
        await engine.dispose()
```

```python
@pytest.mark.asyncio
async def test_company_schema_seed_is_idempotent():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            assert (await ac.get("/api/win/company-schema")).status_code == 200
            assert (await ac.get("/api/win/company-schema")).status_code == 200
        async with AsyncSession(engine, expire_on_commit=False) as session:
            table_count = await session.scalar(select(func.count()).select_from(CompanySchemaTable))
            assert table_count == len(DEFAULT_COMPANY_SCHEMA)
    finally:
        await engine.dispose()
```

```python
@pytest.mark.asyncio
async def test_approve_add_field_proposal_adds_field():
    engine = await _make_engine()
    app = _build_app(engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            proposal = await ac.post(
                "/api/win/company-schema/change-proposals",
                json={
                    "proposal_type": "add_field",
                    "table_name": "orders",
                    "field_name": "external_po_no",
                    "proposed_payload": {
                        "label": "外部采购单号",
                        "data_type": "text",
                        "required": False,
                        "description": "客户侧采购单号",
                    },
                    "reason": "Document mentions PO No.",
                    "created_by": "ai",
                },
            )
            assert proposal.status_code == 200, proposal.text
            pid = proposal.json()["id"]
            approved = await ac.post(f"/api/win/company-schema/change-proposals/{pid}/approve")
            assert approved.status_code == 200, approved.text
            schema = (await ac.get("/api/win/company-schema")).json()
            orders = next(t for t in schema["tables"] if t["table_name"] == "orders")
            assert "external_po_no" in [f["field_name"] for f in orders["fields"]]
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Expected: fails because `company_schema` modules do not exist.

- [ ] **Step 3: Add SQLAlchemy models**

Create `company_schema.py` with `CompanySchemaTable`, `CompanySchemaField`, and `SchemaChangeProposal`.

Use these constraints:

- Unique `company_schema_tables(table_name, version)`.
- Unique `company_schema_fields(table_id, field_name)`.
- JSON columns for `enum_values`, `default_value`, `validation`, `proposed_payload`.
- Timestamp columns match the style in `models/ingest_job.py`.

- [ ] **Step 4: Add default catalog**

`default_catalog.py` exports `DEFAULT_COMPANY_SCHEMA`, a list of table dictionaries. Include these table names:

```python
[
    "customers",
    "contacts",
    "products",
    "product_requirements",
    "contracts",
    "contract_payment_milestones",
    "orders",
    "invoices",
    "invoice_items",
    "payments",
    "shipments",
    "shipment_items",
    "customer_journal_items",
    "customer_tasks",
]
```

The `orders` table must define these first six fields in order:

```python
[
    {"field_name": "customer_id", "label": "客户", "data_type": "uuid", "required": True},
    {"field_name": "amount_total", "label": "订单金额", "data_type": "decimal", "required": False},
    {"field_name": "amount_currency", "label": "币种", "data_type": "text", "required": False, "default_value": "CNY"},
    {"field_name": "delivery_promised_date", "label": "承诺交期", "data_type": "date", "required": False},
    {"field_name": "delivery_address", "label": "交付地址", "data_type": "text", "required": False},
    {"field_name": "description", "label": "订单说明", "data_type": "text", "required": False},
]
```

- [ ] **Step 5: Add catalog service and API**

`catalog.py` exposes:

```python
async def ensure_default_company_schema(session: AsyncSession) -> None: ...
async def get_company_schema(session: AsyncSession) -> dict: ...
async def create_schema_change_proposal(session: AsyncSession, payload: dict) -> dict: ...
async def approve_schema_change_proposal(session: AsyncSession, proposal_id: UUID, reviewer: str | None = None) -> dict: ...
```

`api/company_schema.py` uses `APIRouter(prefix="/company-schema")`. Because `routes.py` is mounted at `/api/win`, final paths are `/api/win/company-schema`.

- [ ] **Step 6: Register router and models**

Update:

- `models/__init__.py` to import/export new models.
- `routes.py` to include `_company_schema_router`.

- [ ] **Step 7: Verify**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Expected: all tests pass.

Commit:

```bash
git add \
  services/platform-api/yunwei_win/models/company_schema.py \
  services/platform-api/yunwei_win/services/company_schema \
  services/platform-api/yunwei_win/api/company_schema.py \
  services/platform-api/yunwei_win/models/__init__.py \
  services/platform-api/yunwei_win/routes.py \
  services/platform-api/tests/test_company_schema_catalog.py
git commit -m "feat(win): add tenant company schema catalog"
```

## Task 2: Company Data Foundation Tables

**Files:**
- Create: `services/platform-api/yunwei_win/models/company_data.py`
- Modify: `services/platform-api/yunwei_win/models/__init__.py`
- Modify: `services/platform-api/yunwei_win/models/field_provenance.py`
- Test: extend `services/platform-api/tests/test_company_schema_catalog.py`

- [ ] **Step 1: Extend model registration test**

Add assertions for:

```python
expected = {
    "products",
    "product_requirements",
    "contract_payment_milestones",
    "invoices",
    "invoice_items",
    "payments",
    "shipments",
    "shipment_items",
    "customer_journal_items",
}
assert expected.issubset(Base.metadata.tables)
```

- [ ] **Step 2: Add company data models**

Create simple SQLAlchemy models for the missing tables. Use existing `Base` and `TimestampMixin` where appropriate. Keep columns minimal and aligned with the spec:

- `Product`: `sku`, `name`, `description`, `specification`, `unit`.
- `ProductRequirement`: `customer_id`, `product_id`, `requirement_type`, `requirement_text`, `tolerance`, `source_document_id`.
- `ContractPaymentMilestone`: `contract_id`, `name`, `ratio`, `amount`, `trigger_event`, `trigger_offset_days`, `due_date`, `raw_text`.
- `Invoice`: `customer_id`, `order_id`, `invoice_no`, `issue_date`, `amount_total`, `amount_currency`, `tax_amount`, `status`.
- `InvoiceItem`: `invoice_id`, `product_id`, `description`, `quantity`, `unit_price`, `amount`.
- `Payment`: `customer_id`, `invoice_id`, `payment_date`, `amount`, `currency`, `method`, `reference_no`.
- `Shipment`: `customer_id`, `order_id`, `shipment_no`, `carrier`, `tracking_no`, `ship_date`, `delivery_date`, `delivery_address`, `status`.
- `ShipmentItem`: `shipment_id`, `product_id`, `description`, `quantity`, `unit`.
- `CustomerJournalItem`: `customer_id`, `document_id`, `item_type`, `title`, `content`, `occurred_at`, `due_date`, `severity`, `status`, `confidence`, `raw_excerpt`.

- [ ] **Step 3: Extend provenance enum**

In `field_provenance.py`, extend `EntityType` with:

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

- [ ] **Step 4: Register models and verify**

Update `models/__init__.py`, then run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_company_schema_catalog.py -q
```

Commit:

```bash
git add \
  services/platform-api/yunwei_win/models/company_data.py \
  services/platform-api/yunwei_win/models/__init__.py \
  services/platform-api/yunwei_win/models/field_provenance.py \
  services/platform-api/tests/test_company_schema_catalog.py
git commit -m "feat(win): add company data foundation tables"
```

## Task 3: ReviewDraft Schemas And Materializer

**Files:**
- Create: `services/platform-api/yunwei_win/models/document_extraction.py`
- Create: `services/platform-api/yunwei_win/services/ingest_v2/__init__.py`
- Create: `services/platform-api/yunwei_win/services/ingest_v2/schemas.py`
- Create: `services/platform-api/yunwei_win/services/ingest_v2/review_draft.py`
- Modify: `services/platform-api/yunwei_win/models/__init__.py`
- Test: `services/platform-api/tests/test_ingest_v2_review_draft.py`

- [ ] **Step 1: Write failing ReviewDraft tests**

Create tests for these cases:

1. `orders` has six active catalog fields and extraction has four values; materializer returns six cells.
2. Missing fields are present with `status == "missing"`.
3. Array table selected with no extracted items returns one empty row.

The central assertion:

```python
orders = next(t for t in draft.tables if t.table_name == "orders")
cells = {c.field_name: c for c in orders.rows[0].cells}
assert set(cells) == {
    "customer_id",
    "amount_total",
    "amount_currency",
    "delivery_promised_date",
    "delivery_address",
    "description",
}
assert cells["amount_total"].status == "extracted"
assert cells["delivery_address"].status == "missing"
```

- [ ] **Step 2: Add `DocumentExtraction` model**

Columns:

- `id`
- `document_id`
- `schema_version`
- `provider`
- `route_plan`
- `raw_pipeline_results`
- `review_draft`
- `status`
- `warnings`
- `created_by`
- `confirmed_by`
- `confirmed_at`
- timestamps

- [ ] **Step 3: Add Pydantic schemas**

`schemas.py` defines:

- `ReviewCellEvidence`
- `ReviewCell`
- `ReviewRow`
- `ReviewTable`
- `ReviewDraft`
- `ReviewCellPatch`
- `ConfirmExtractionRequest`
- `ConfirmExtractionResponse`

Use `Any | None` for cell values and explicit string literal unions for statuses.

- [ ] **Step 4: Add materializer**

`review_draft.py` defines `PIPELINE_TABLES` exactly:

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
    catalog: dict[str, Any],
    document_summary: str | None = None,
    warnings: list[str] | None = None,
) -> ReviewDraft:
    ...
```

Rules:

- Selected pipelines decide selected tables.
- Selected table cells are generated from catalog fields.
- Value present -> `status="extracted"`, `source="ai"`.
- Default present and value missing -> default value with `source="default"`.
- Value missing and no default -> `status="missing"`, `source="empty"`.
- Array tables with no extracted rows get one empty row.

- [ ] **Step 5: Verify**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_ingest_v2_review_draft.py -q
```

Commit:

```bash
git add \
  services/platform-api/yunwei_win/models/document_extraction.py \
  services/platform-api/yunwei_win/services/ingest_v2 \
  services/platform-api/yunwei_win/models/__init__.py \
  services/platform-api/tests/test_ingest_v2_review_draft.py
git commit -m "feat(win): materialize schema-first review drafts"
```

## Task 4: V2 Ingest Job API And Worker Dispatch

**Files:**
- Create: `services/platform-api/yunwei_win/services/ingest_v2/auto.py`
- Create: `services/platform-api/yunwei_win/api/ingest_v2.py`
- Modify: `services/platform-api/yunwei_win/models/ingest_job.py`
- Modify: `services/platform-api/yunwei_win/db.py`
- Modify: `services/platform-api/yunwei_win/routes.py`
- Modify: `services/platform-api/yunwei_win/workers/ingest_rq.py`
- Test: `services/platform-api/tests/test_ingest_v2_api.py`
- Test: `services/platform-api/tests/test_ingest_rq_worker.py`

- [ ] **Step 1: Write API and worker tests**

Test expectations:

- `POST /api/win/ingest/v2/jobs` creates jobs with `workflow_version == "v2"`.
- `GET /api/win/ingest/v2/jobs/{id}` returns `review_draft` when extracted.
- Worker dispatches V2 jobs to `auto_ingest_v2()`.
- Existing V1 `tests/test_ingest_jobs.py` still passes.

- [ ] **Step 2: Extend `IngestJob`**

Add nullable/minimal columns:

- `workflow_version: str`, default `"v1"`.
- `extraction_id: UUID | None`, FK to `document_extractions.id`.

Update `_job_dict()` equivalent in V2 API to include both fields.

- [ ] **Step 3: Add existing-tenant ensure helper**

In `db.py`, add:

```python
async def ensure_ingest_v2_tables(engine: AsyncEngine) -> None:
    ...
```

It must:

- create V2 tables with `Base.metadata.create_all(..., checkfirst=True)`;
- add missing columns `ingest_jobs.workflow_version` and `ingest_jobs.extraction_id` for already-provisioned tenant DBs using idempotent DDL.

Keep the existing `ensure_ingest_job_tables_for()` behavior intact for V1.

- [ ] **Step 4: Implement `auto_ingest_v2()`**

Use the same stages as V1:

1. `collect_evidence()`
2. `route_schemas()`
3. `get_extractor_provider().extract_selected()`
4. `ensure_default_company_schema()`
5. `get_company_schema()`
6. `materialize_review_draft()`
7. insert `DocumentExtraction`
8. set `Document.raw_llm_response` with `workflow_version="v2"`

Return:

```python
@dataclass
class AutoIngestV2Result:
    document_id: UUID
    extraction_id: UUID
    route_plan: PipelineRoutePlan
    review_draft: ReviewDraft
```

- [ ] **Step 5: Add V2 API router**

`api/ingest_v2.py` uses `APIRouter(prefix="/ingest/v2")`, because parent mount is `/api/win`.

Implement:

- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/retry`
- `POST /jobs/{job_id}/cancel`
- `GET /extractions/{extraction_id}`
- `PATCH /extractions/{extraction_id}`
- `POST /extractions/{extraction_id}/ignore`

Do not implement confirm here; Task 5 owns confirm.

- [ ] **Step 6: Dispatch worker by workflow version**

In `workers/ingest_rq.py`, branch inside extraction:

```python
if job.workflow_version == "v2":
    result = await auto_ingest_v2(...)
else:
    result = await auto_ingest(...)
```

For V2 success, write:

- `j.document_id`
- `j.extraction_id`
- `j.result_json = review_draft.model_dump(mode="json")`
- `j.status = extracted`
- `j.stage = done`

- [ ] **Step 7: Verify**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest \
  tests/test_ingest_v2_api.py \
  tests/test_ingest_rq_worker.py \
  tests/test_ingest_jobs.py \
  -q
```

Commit:

```bash
git add \
  services/platform-api/yunwei_win/services/ingest_v2/auto.py \
  services/platform-api/yunwei_win/api/ingest_v2.py \
  services/platform-api/yunwei_win/models/ingest_job.py \
  services/platform-api/yunwei_win/db.py \
  services/platform-api/yunwei_win/routes.py \
  services/platform-api/yunwei_win/workers/ingest_rq.py \
  services/platform-api/tests/test_ingest_v2_api.py \
  services/platform-api/tests/test_ingest_rq_worker.py
git commit -m "feat(win): add schema-first v2 ingest jobs"
```

## Task 5: Confirm Reviewed Tables

**Files:**
- Create: `services/platform-api/yunwei_win/services/ingest_v2/confirm.py`
- Modify: `services/platform-api/yunwei_win/api/ingest_v2.py`
- Test: `services/platform-api/tests/test_ingest_v2_confirm.py`

- [ ] **Step 1: Write confirm tests**

Cover:

- confirming an `orders` draft creates/updates an `orders` row;
- user-filled missing cells persist;
- provenance rows are created for AI and edited cells;
- missing required cells return `400` and do not mark extraction confirmed.

- [ ] **Step 2: Implement validation**

Support catalog data types:

- `text`
- `uuid`
- `date`
- `datetime`
- `decimal`
- `integer`
- `boolean`
- `enum`
- `json`

Rules:

- Empty required non-rejected cell is invalid.
- `rejected` cells are skipped.
- Invalid confirm response includes `invalid_cells`.

- [ ] **Step 3: Implement writeback**

Expose:

```python
async def confirm_review_draft(
    *,
    session: AsyncSession,
    extraction_id: UUID,
    request: ConfirmExtractionRequest,
    confirmed_by: str | None,
) -> ConfirmExtractionResponse:
    ...
```

Write parent rows before child rows:

```text
customers
contacts / orders / products
contracts / invoices / shipments / product_requirements
contract_payment_milestones / invoice_items / shipment_items / payments
customer_journal_items / customer_tasks
```

For MVP:

- update by `ReviewRow.entity_id` when present;
- otherwise create;
- use `client_row_id -> entity_id` mapping inside the same confirm request;
- no fuzzy merge.

- [ ] **Step 4: Wire confirm endpoint**

Add:

```text
POST /api/win/ingest/v2/extractions/{extraction_id}/confirm
```

Mark:

- `DocumentExtraction.status = confirmed`
- `Document.review_status = confirmed`
- linked `IngestJob.status = confirmed`

- [ ] **Step 5: Verify**

Run:

```bash
cd services/platform-api
./.venv/bin/pytest tests/test_ingest_v2_confirm.py -q
```

Commit:

```bash
git add \
  services/platform-api/yunwei_win/services/ingest_v2/confirm.py \
  services/platform-api/yunwei_win/api/ingest_v2.py \
  services/platform-api/tests/test_ingest_v2_confirm.py
git commit -m "feat(win): confirm reviewed schema tables"
```

## Task 6: Frontend V2 API Types

**Files:**
- Create: `apps/win-web/src/api/ingestV2.ts`
- Modify: `apps/win-web/src/data/types.ts`

- [ ] **Step 1: Add frontend V2 types**

Define:

- `ReviewCellEvidence`
- `ReviewCellStatus`
- `ReviewCell`
- `ReviewRow`
- `ReviewTable`
- `ReviewDraft`
- `ReviewCellPatch`
- `IngestV2Job`
- `ConfirmExtractionResponse`
- `CompanySchema`

Do not reuse V1 `ReviewField` or `ReviewExtraction` for V2 table state.

- [ ] **Step 2: Add API client**

`ingestV2.ts` uses base:

```ts
const API_BASE = "/api/win";
```

Exports:

```ts
createIngestV2Jobs()
listIngestV2Jobs()
getIngestV2Job()
getReviewDraft()
patchReviewDraft()
confirmReviewDraft()
ignoreReviewDraft()
getCompanySchema()
```

Endpoints must use `/api/win/ingest/v2/*` and `/api/win/company-schema`.

- [ ] **Step 3: Verify**

Run:

```bash
cd apps/win-web
npm run check
```

Commit:

```bash
git add apps/win-web/src/api/ingestV2.ts apps/win-web/src/data/types.ts
git commit -m "feat(win-web): add schema-first ingest client"
```

## Task 7: Frontend Table Review UI

**Files:**
- Create: `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`
- Create: `apps/win-web/src/components/review/ReviewCellEditor.tsx`
- Modify: `apps/win-web/src/screens/Review.tsx`
- Modify: `apps/win-web/src/screens/Upload.tsx`
- Modify: `apps/win-web/src/api/ingest.ts` only if legacy job detection needs compatibility types.

- [ ] **Step 1: Add table workspace**

Render `ReviewDraft.tables` directly:

- one section per table;
- columns/cells follow backend catalog order;
- `missing` cells are visible and editable;
- `rejected` cells are visible but skipped on confirm;
- evidence excerpt/page is visible when present;
- array tables support adding one local row.

Use the existing Win design language from `apps/win-web/src/components/*`. Keep the workspace dense and operational, not marketing-style.

- [ ] **Step 2: Wire Review screen**

In `Review.tsx`:

- load V2 job when `workflow_version === "v2"` or `result_json.tables` exists;
- render `ReviewTableWorkspace` for V2;
- keep V1 `jobToBatch()` / `batchToReview()` path for legacy jobs.

- [ ] **Step 3: Wire Upload screen**

Switch new upload submissions to `createIngestV2Jobs()` after backend V2 API tests pass.

V1 APIs can remain for history/fallback.

- [ ] **Step 4: Wire confirm/ignore**

For V2:

- confirm sends local patches to `/api/win/ingest/v2/extractions/{id}/confirm`;
- ignore calls `/api/win/ingest/v2/extractions/{id}/ignore`;
- success clears local state and navigates consistently with current archive flow.

- [ ] **Step 5: Verify**

Run:

```bash
cd apps/win-web
npm run check
```

Commit:

```bash
git add \
  apps/win-web/src/components/review \
  apps/win-web/src/screens/Review.tsx \
  apps/win-web/src/screens/Upload.tsx \
  apps/win-web/src/api/ingest.ts
git commit -m "feat(win-web): review extracted data as schema tables"
```

## Task 8: Final Verification

**Files:**
- Update docs only if implementation differs from this plan.

- [ ] **Step 1: Run backend tests**

```bash
cd services/platform-api
./.venv/bin/pytest \
  tests/test_company_schema_catalog.py \
  tests/test_ingest_v2_review_draft.py \
  tests/test_ingest_v2_api.py \
  tests/test_ingest_v2_confirm.py \
  tests/test_ingest_rq_worker.py \
  tests/test_ingest_jobs.py \
  -q
```

- [ ] **Step 2: Run frontend typecheck**

```bash
cd apps/win-web
npm run check
```

- [ ] **Step 3: Manual smoke**

Verify:

1. User opens `/win/`.
2. Upload creates V2 job via `/api/win/ingest/v2/jobs`.
3. Job reaches `extracted`.
4. Review page renders schema tables.
5. `orders` table displays every active field including empty `missing` cells.
6. User fills a missing field and confirms.
7. Tenant DB contains confirmed business row and `field_provenance`.

- [ ] **Step 4: Commit final docs if needed**

```bash
git status --short
git add \
  docs/superpowers/specs/2026-05-13-schema-first-company-data-layer-design.md \
  docs/superpowers/plans/2026-05-13-schema-first-company-data-layer.md \
  docs/superpowers/task-briefs/2026-05-13-schema-first-company-data-layer.md
git commit -m "docs(win): align schema-first ingest plan with v3 layout"
```

## Notes For Subagents

- You are not alone in the codebase. Do not revert edits made by other agents.
- If splitting work across agents, use disjoint file ownership:
  - Agent A: schema catalog.
  - Agent B: ReviewDraft schemas/materializer.
  - Agent C: V2 API/worker/confirm.
  - Agent D: frontend V2 client/UI.
- Do not dispatch multiple agents that both edit `routes.py`, `models/__init__.py`, or `apps/win-web/src/screens/Review.tsx` at the same time.
