# Schema-First Company Data Layer Design

Date: 2026-05-14
Status: proposed
Scope: Win (`/win/`) ingest, extraction review, schema catalog, and confirmed tenant company data.

## Decision

Rebuild Win ingest/review around the tenant company schema.

The repo has moved to the v3 layout:

- Backend service: `services/platform-api/`
- Win backend package: `services/platform-api/yunwei_win/`
- Win frontend app: `apps/win-web/`
- Canonical API prefix: `/api/win/*`
- Browser SPA route: `/win/`

The new ingest flow must use this layout directly. Do not write new docs or code against the legacy `platform/yinhu_brain`, `platform/app-win`, or `/win/api/*` paths.

## Current Problem

The current V1 ingest flow still centers review around `UnifiedDraft` and frontend summary cards:

```text
upload / text
  -> collect evidence / OCR
  -> schema route
  -> provider pipeline_results
  -> normalize_pipeline_results()
  -> UnifiedDraft
  -> apps/win-web/src/api/ingest.ts batchToReview()
  -> Review cards
  -> AutoConfirmRequest
```

The schema router and extractor can produce rich `pipeline_results`, but `batchToReview()` only renders a fixed subset of the merged draft: customer, contacts, order amount/date, contract number/date, payment milestones, tasks, risks, events, and memory items. Pipelines such as `finance`, `logistics`, and `manufacturing_requirement` can succeed but still be absent from the main review UI.

This is not a prompt-quality issue. It is a contract issue. Review is not allowed to be a handcrafted summary of whichever fields survived normalizing. Review must be a table/cell editor over the tenant company schema.

## First Principles Workflow

The product workflow is:

```text
upload file or text
  -> persist Document and OCR text
  -> route to relevant schemas/pipelines
  -> extract candidate values
  -> materialize a complete table-based ReviewDraft from the tenant schema catalog
  -> user reviews, edits, rejects, or fills missing cells
  -> confirm writes reviewed cells into company data tables
  -> AI and humans query the same confirmed data layer
```

Rules:

- A business fact has one canonical table/field path, such as `orders.amount_total`.
- If a selected table has six active fields and AI finds four values, review still shows all six cells.
- Empty fields are first-class review cells with `status="missing"`.
- AI may propose values and schema changes; AI does not directly write high-impact business tables.
- Confirm writeback accepts reviewed table rows, not frontend card summaries.
- Existing V1 routes can remain until V2 is verified, but V2 must not extend the old `UnifiedDraft -> batchToReview()` contract.

## Current Code Anchors

Backend:

- `services/platform-api/platform_app/main.py` mounts `yunwei_win.routes.router` at `/api/win`.
- `services/platform-api/yunwei_win/routes.py` assembles Win routers.
- `services/platform-api/yunwei_win/api/ingest.py` owns V1 `/api/win/ingest/*`, including async `/jobs`.
- `services/platform-api/yunwei_win/workers/ingest_rq.py` runs queued ingest jobs.
- `services/platform-api/yunwei_win/services/ingest/auto.py` runs V1 evidence -> route -> extractor -> normalize.
- `services/platform-api/yunwei_win/services/ingest/landingai_normalize.py` folds selected pipeline outputs into `UnifiedDraft`.
- `services/platform-api/yunwei_win/db.py` provisions a per-enterprise tenant DB and currently has `ensure_ingest_job_tables()`.
- `services/platform-api/yunwei_win/models/` contains existing `customers`, `contacts`, `orders`, `contracts`, `documents`, `field_provenance`, and `ingest_jobs`.

Frontend:

- `apps/win-web/src/api/ingest.ts` defines V1 ingest/job types, `jobToBatch()`, `batchToReview()`, and confirm payload builders.
- `apps/win-web/src/screens/Upload.tsx` creates/polls V1 jobs.
- `apps/win-web/src/screens/Review.tsx` loads a job and renders V1 review state.
- `apps/win-web/src/data/types.ts` defines the V1 `Review`, `ReviewField`, `ReviewExtraction`, and schema summary types.

Tests:

- Backend tests run from `services/platform-api`.
- Existing async job tests are in `services/platform-api/tests/test_ingest_jobs.py`.
- Existing worker tests are in `services/platform-api/tests/test_ingest_rq_worker.py`.
- Frontend typecheck runs from `apps/win-web`.

## Data Model

Win tenant data already lives in one Postgres database per enterprise. Because of that isolation, new Win tables do not need a `tenant_id` column. The enterprise boundary is the database itself.

### Schema Catalog

Add schema catalog tables to each tenant DB:

```text
company_schema_tables
  id
  table_name              -- "orders"
  label                   -- "订单"
  purpose
  category                -- profile | commercial | finance | logistics | manufacturing | memory
  version
  is_active
  sort_order
  created_at
  updated_at

company_schema_fields
  id
  table_id
  field_name              -- "amount_total"
  label                   -- "订单金额"
  data_type               -- text | uuid | date | datetime | decimal | integer | boolean | enum | json
  required
  is_array
  enum_values
  default_value
  description
  extraction_hint
  validation
  sort_order
  is_active
  created_at
  updated_at

schema_change_proposals
  id
  source_document_id
  source_extraction_id
  proposal_type           -- add_table | add_field | alter_field | deactivate_field
  table_name
  field_name
  proposed_payload
  reason
  status                  -- pending | approved | rejected | applied
  created_by
  reviewed_by
  reviewed_at
  created_at
  updated_at
```

The default catalog is seeded by code so every tenant starts with the same baseline. The API returns the tenant DB catalog, not frontend hard-coded fields.

### Company Data Tables

Keep existing:

- `customers`
- `contacts`
- `orders`
- `contracts`
- `documents`
- `field_provenance`
- customer memory tables already present in `models/customer_memory.py`

Add missing data foundation tables:

- `products`
- `product_requirements`
- `contract_payment_milestones`
- `invoices`
- `invoice_items`
- `payments`
- `shipments`
- `shipment_items`
- `customer_journal_items`

`customer_journal_items` is the V2 consolidation target for extracted events, commitments, risks, memories, and notes when those facts are better represented as timeline/journal items than as separate first-class records.

### Extraction Attempt Table

Add `document_extractions`:

```text
document_extractions
  id
  document_id
  schema_version
  provider
  route_plan
  raw_pipeline_results
  review_draft
  status                  -- pending_review | confirmed | ignored | failed
  warnings
  created_by
  confirmed_by
  confirmed_at
  created_at
  updated_at
```

This table is the durable AI proposal. It separates "what AI found" from "what humans confirmed."

### Provenance

Extend `FieldProvenance.EntityType` so confirmed values from new tables can be traced. Add at least:

- `product`
- `product_requirement`
- `invoice`
- `invoice_item`
- `payment`
- `shipment`
- `shipment_item`
- `contract_payment_milestone`
- `customer_journal_item`
- `customer_task`

Every confirmed non-empty cell should write provenance when it has document evidence or was manually edited during review.

## ReviewDraft Contract

V2 backend returns a `ReviewDraft` from:

- `GET /api/win/ingest/v2/jobs/{job_id}` when extracted
- `GET /api/win/ingest/v2/extractions/{extraction_id}`

Shape:

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
      {
        "name": "contract_order",
        "confidence": 0.92,
        "reason": "包含订单号、金额、交付条款"
      }
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
              "evidence": {
                "page": 1,
                "excerpt": "合同总价人民币叁万元整"
              },
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
      ],
      "raw_extraction": {
        "order": {
          "amount_total": 30000
        }
      }
    }
  ],
  "schema_warnings": [],
  "general_warnings": []
}
```

Cell status values:

- `extracted`: AI produced a value.
- `missing`: selected table has this schema field but AI did not produce a value.
- `low_confidence`: AI produced a value below the configured threshold.
- `edited`: user changed the value.
- `rejected`: user excluded this value from confirm.
- `invalid`: server validation rejected this value.

The key invariant:

```text
For every selected table:
  ReviewDraft table cells = active fields in company_schema_fields
```

Extraction sparsity changes cell status, not cell existence.

## Pipeline To Table Mapping

Initial mapping:

```python
PIPELINE_TABLES = {
    "identity": ["customers", "contacts"],
    "contract_order": [
        "customers",
        "contacts",
        "contracts",
        "contract_payment_milestones",
        "orders",
    ],
    "finance": ["invoices", "invoice_items", "payments"],
    "logistics": ["shipments", "shipment_items"],
    "manufacturing_requirement": ["products", "product_requirements"],
    "commitment_task_risk": ["customer_journal_items", "customer_tasks"],
}
```

Array/multi-row tables include:

- `contacts`
- `contract_payment_milestones`
- `invoice_items`
- `shipment_items`
- `customer_tasks`
- `customer_journal_items`

When an array table is selected and AI extracts no rows, V2 still creates one empty row so the reviewer can add values.

## API Surface

Canonical APIs:

```text
GET  /api/win/company-schema
POST /api/win/company-schema/change-proposals
POST /api/win/company-schema/change-proposals/{proposal_id}/approve

POST /api/win/ingest/v2/jobs
GET  /api/win/ingest/v2/jobs
GET  /api/win/ingest/v2/jobs/{job_id}
POST /api/win/ingest/v2/jobs/{job_id}/retry
POST /api/win/ingest/v2/jobs/{job_id}/cancel

GET   /api/win/ingest/v2/extractions/{extraction_id}
PATCH /api/win/ingest/v2/extractions/{extraction_id}
POST  /api/win/ingest/v2/extractions/{extraction_id}/confirm
POST  /api/win/ingest/v2/extractions/{extraction_id}/ignore
```

Do not add `/win/api/*` aliases. The v3 URL contract is `/api/win/*`.

## Confirm Writeback

Confirm receives cell patches plus the server-stored `ReviewDraft`.

Rules:

- Validate values by catalog `data_type`.
- Reject confirmation if a non-rejected required cell is empty.
- Skip `rejected` cells.
- Create/update parent rows before child rows.
- Use `ReviewRow.entity_id` when present; otherwise create a row.
- Use `client_row_id -> entity_id` mapping inside one confirm operation for child rows.
- Write `FieldProvenance` for each confirmed non-empty cell.
- Mark `DocumentExtraction.status = confirmed`.
- Mark linked `Document.review_status = confirmed`.
- Mark linked V2 `IngestJob.status = confirmed`.

V2 MVP does not implement fuzzy merge. Existing V1 merge behavior stays untouched.

## Frontend Design

Add V2-specific frontend types and API client instead of expanding V1 types:

- `apps/win-web/src/api/ingestV2.ts`
- `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`
- `apps/win-web/src/components/review/ReviewCellEditor.tsx`

`Review.tsx` chooses the renderer:

- V2 job or `result_json.tables` present -> render `ReviewTableWorkspace`.
- V1 job -> keep existing `batchToReview()` path temporarily.

`Upload.tsx` switches new uploads to V2 jobs after V2 backend tests pass. V1 APIs remain available for existing rows and fallback.

The V2 review UI renders `ReviewDraft.tables` directly. It must not hide `missing` cells.

## Non-Goals

- Do not rewrite OCR providers.
- Do not rewrite LandingAI/DeepSeek provider contracts.
- Do not delete V1 ingest routes in this pass.
- Do not add a full schema-management UI.
- Do not implement fuzzy customer/order merge in V2 confirm.
- Do not use the old `platform/yinhu_brain`, `platform/app-win`, or `/win/api` paths in new work.

## Verification

Backend:

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

Frontend:

```bash
cd apps/win-web
npm run check
```

Manual smoke:

1. Build or run `apps/win-web`.
2. Upload an order/contract document from `/win/`.
3. Wait for a V2 job to reach `extracted`.
4. Open review and verify `orders` shows every catalog field.
5. Fill an empty `missing` cell.
6. Confirm.
7. Verify business rows and `field_provenance` rows exist in the tenant DB.

## Open Risk

Existing tenant databases were already provisioned with older `create_all()` metadata. New tables are easy to create with `create_all(checkfirst=True)`, but adding columns to existing tables such as `ingest_jobs.workflow_version` and `ingest_jobs.extraction_id` requires explicit idempotent DDL in `yunwei_win.db`. The implementation plan must include that migration/ensure step.
