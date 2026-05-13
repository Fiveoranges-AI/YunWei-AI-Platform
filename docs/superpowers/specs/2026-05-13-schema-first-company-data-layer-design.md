# Schema-First Company Data Layer Design

Date: 2026-05-13
Status: proposed
Scope: Win tenant company data layer, ingest, extraction, review, and confirm writeback.

## Decision

Rebuild Win ingest/review around a schema-first company data layer.

The tenant company's business database schema is the source of truth. AI extraction, human review, confirm writeback, and AI querying all use the same canonical table and field paths. Upload review is no longer centered on "AI conclusions" or temporary merged drafts. It is centered on complete business tables, including fields that AI did not extract.

This replaces the current `pipeline_results -> UnifiedDraft -> ReviewExtraction` flow for new ingest work. The existing endpoints can remain temporarily for compatibility, but V2 should not extend the old contract.

## Current Problem

The current implementation has too many shapes for the same facts:

- `pipeline_results[].extraction` contains rich schema extraction output.
- `UnifiedDraft` keeps only some fields that current confirm supports.
- `ReviewExtraction` projects a smaller set of cards for the UI.
- `SchemaSummary` separately inspects raw pipeline outputs for diagnostics.

This makes the system hard to reason about. Finance, logistics, manufacturing, line items, and many contract details can be extracted successfully but disappear from the main review workflow because they are not represented in `UnifiedDraft` or `ReviewExtraction`.

The root issue is architectural: review should not be a hand-built summary of AI output. Review should be a direct table/cell editor over the tenant company schema.

## Reference From `yinhu-brain`

The external `yinhu-brain` repo has several patterns worth carrying forward:

- Pydantic extraction models are the source for LLM tool schemas.
- `DocumentExtraction` stores each AI extraction attempt with payload, missing fields, warnings, validation errors, confidence, and review status.
- `FieldProvenance` records document, entity, field path, value, source page/excerpt, confidence, and excerpt match status.
- Inbox/review separates AI proposals from confirmed business tables.
- `customer_journal_items` consolidates events, commitments, risks, and memories behind a `kind` discriminator instead of scattering similar timeline data across many tables.

The new design adopts these ideas, but makes the tenant company schema the primary contract rather than an ingest-specific shape.

## First Principles

The product workflow is:

```text
upload
  -> OCR/document text
  -> schema-aware extraction
  -> complete table review
  -> human confirmation/correction
  -> company database writeback
  -> AI and humans query the same company database
```

The rules:

- A field has one canonical path, such as `orders.amount_total`.
- Extractors may omit values, but the review draft must still include every field defined by the table schema.
- Empty fields are first-class review cells, not missing UI.
- The confirm endpoint accepts reviewed table rows, not frontend-specific card summaries.
- AI writes proposals and reads confirmed business data. Human-confirmed data is the trusted layer.
- Schema changes are controlled. AI can propose schema changes, but physical DB/schema catalog changes require explicit migration or human-approved schema operation.

## Canonical Schema Model

There are two layers:

1. Physical Postgres tables, owned by migrations.
2. A schema catalog that describes those tables/fields for extractor, review UI, confirm, and AI tools.

The schema catalog can be stored in code first for V2 bootstrap and synced into tenant DB metadata tables. The physical table remains authoritative for storage; the catalog is authoritative for UI/extraction/writeback behavior.

### Catalog Tables

Add metadata tables:

```text
company_schema_tables
  id
  tenant_id
  table_key              -- "orders"
  label                  -- "订单"
  description
  physical_table_name
  row_label_template
  write_policy           -- manual_confirm | auto_allowed | read_only
  active
  version

company_schema_fields
  id
  tenant_id
  table_key
  field_key              -- "amount_total"
  label                  -- "订单金额"
  field_type             -- text | number | amount | date | datetime | enum | json | relation
  required
  editable
  enum_values
  physical_column_name
  relation_target
  display_order
  extraction_hint
  active

schema_change_proposals
  id
  tenant_id
  proposed_by            -- user | ai | system
  proposal_type          -- add_table | add_field | alter_field | deactivate_field
  target_table_key
  target_field_key
  proposal_payload       -- JSONB, follows the catalog shape above
  reason
  status                 -- pending | approved | rejected | applied
  reviewed_by
  reviewed_at
  created_at
```

The catalog allows the same schema to drive:

- LLM extraction schema.
- Review table rendering.
- Required/missing field calculation.
- Confirm validation.
- AI query/tool descriptions.

## Initial Business Tables

V2 should create a coherent tenant company database foundation instead of continuing the partial current shape.

Core tables:

```text
customers
contacts
products
product_requirements
contracts
contract_payment_milestones
orders
order_items
invoices
invoice_items
payments
shipments
shipment_items
customer_journal_items
customer_tasks
documents
document_extractions
field_provenance
```

The table list is intentionally practical. It covers the schema families already present in current extraction:

- identity -> `customers`, `contacts`
- contract_order -> `contracts`, `contract_payment_milestones`, `orders`, `order_items`
- finance -> `invoices`, `invoice_items`, `payments`
- logistics -> `shipments`, `shipment_items`
- manufacturing_requirement -> `products`, `product_requirements`
- commitment_task_risk -> `customer_journal_items`, `customer_tasks`

### Initial Field Catalog

The first implementation should seed these fields into `company_schema_fields`.
This makes the extractor, review UI, and confirm writer align on one field set.

`customers`

```text
full_name              text      required
short_name             text
address                text
tax_id                 text
current_status         enum(active, inactive, blocked)
tags                   json
```

`contacts`

```text
customer_id            relation(customers) required
name                   text required
title                  text
phone                  text
mobile                 text
email                  text
role                   enum(seller, buyer, delivery, acceptance, invoice, other)
address                text
wechat_id              text
```

`products`

```text
product_name           text required
product_code           text
category               text
specification          text
material               text
grade                  text
```

`product_requirements`

```text
customer_id            relation(customers) required
product_id             relation(products)
requirement_type       enum(spec, delivery, quality, packaging, documentation, other)
description            text required
priority               enum(urgent, high, normal, low)
effective_date         date
raw_text               text
safety_stock_minimum   number
safety_stock_target    number
unit                   text
lead_time_days         number
monthly_usage          number
moq                    number
```

`contracts`

```text
customer_id            relation(customers) required
contract_no_external   text
contract_no_internal   text
signing_date           date
effective_date         date
expiry_date            date
delivery_terms         text
penalty_terms          text
risk_terms             text
amount_total           amount
amount_currency        enum(CNY, USD, EUR, other)
```

`contract_payment_milestones`

```text
contract_id            relation(contracts) required
name                   text
ratio                  number required
trigger_event          enum(contract_signed, before_shipment, on_delivery, on_acceptance, invoice_issued, warranty_end, on_demand, other)
trigger_offset_days    number
raw_text               text
```

`orders`

```text
customer_id            relation(customers) required
contract_id            relation(contracts)
order_no               text
amount_total           amount
amount_currency        enum(CNY, USD, EUR, other)
delivery_promised_date date
delivery_address       text
description            text
```

`order_items`

```text
order_id               relation(orders) required
product_id             relation(products)
description            text
specification          text
quantity               number
unit                   text
unit_price             amount
amount                 amount
```

`invoices`

```text
customer_id            relation(customers) required
invoice_number         text
invoice_code           text
invoice_type           enum(vat_special, vat_general, electronic, other)
issue_date             date
amount_without_tax     amount
tax_amount             amount
amount_total           amount
currency               enum(CNY, USD, EUR, other)
seller_name            text
buyer_name             text
status                 enum(paid, pending, cancelled, red, other)
```

`invoice_items`

```text
invoice_id             relation(invoices) required
description            text
specification          text
quantity               number
unit                   text
unit_price             amount
amount                 amount
```

`payments`

```text
customer_id            relation(customers) required
contract_id            relation(contracts)
order_id               relation(orders)
invoice_id             relation(invoices)
payment_date           date
amount                 amount required
currency               enum(CNY, USD, EUR, other)
payer_name             text
payee_name             text
bank_name              text
bank_account           text
transaction_id         text
method                 enum(transfer, cash, check, card, online, other)
status                 enum(pending, expected, received, partial, overdue, reversed, cancelled)
```

`shipments`

```text
customer_id            relation(customers) required
order_id               relation(orders)
shipment_number        text
document_date          date
status                 enum(pending, shipped, in_transit, delivered, signed, rejected, other)
carrier                text
tracking_number        text
delivery_address       text
receiver_name          text
receiver_phone         text
signed_at              datetime
```

`shipment_items`

```text
shipment_id            relation(shipments) required
product_id             relation(products)
product_name           text
specification          text
quantity               number
unit                   text
batch_number           text
warehouse              text
remark                 text
```

`customer_journal_items`

```text
customer_id            relation(customers) required
kind                   enum(event, commitment, risk, memory) required
category               text
title                  text required
description            text
event_date             datetime
due_date               date
amount                 amount
currency               enum(CNY, USD, EUR, other)
severity               enum(low, medium, high, critical)
status                 text
importance             enum(low, medium, high)
related_contact_id     relation(contacts)
related_contract_id    relation(contracts)
related_order_id       relation(orders)
source_excerpt         text
```

`customer_tasks`

```text
customer_id            relation(customers) required
title                  text required
description            text
assignee               text
due_date               date
priority               enum(urgent, high, normal, low)
status                 enum(open, in_progress, done, cancelled)
source_excerpt         text
```

### Relationship Defaults

Use explicit foreign keys:

- `contacts.customer_id`
- `orders.customer_id`
- `orders.contract_id`
- `order_items.order_id`
- `contracts.customer_id`
- `contract_payment_milestones.contract_id`
- `invoices.customer_id`
- `invoice_items.invoice_id`
- `payments.customer_id`, optional `contract_id`, optional `order_id`, optional `invoice_id`
- `shipments.customer_id`, optional `order_id`
- `shipment_items.shipment_id`, optional `product_id`
- `product_requirements.customer_id`, optional `product_id`
- `customer_journal_items.customer_id`
- `customer_tasks.customer_id`

Do not use generic EAV tables for confirmed business data. The schema catalog describes normal relational tables; it does not replace them.

## Extraction Contract

The extractor receives:

```json
{
  "document_id": "...",
  "ocr_text": "...",
  "selected_tables": ["customers", "orders", "contracts"],
  "schema": {
    "tables": [
      {
        "table_key": "orders",
        "fields": [
          {"field_key": "order_no", "field_type": "text"},
          {"field_key": "amount_total", "field_type": "amount"},
          {"field_key": "amount_currency", "field_type": "enum"},
          {"field_key": "delivery_promised_date", "field_type": "date"},
          {"field_key": "delivery_address", "field_type": "text"},
          {"field_key": "description", "field_type": "text"}
        ]
      }
    ]
  }
}
```

The extractor returns only found values:

```json
{
  "tables": [
    {
      "table_key": "orders",
      "rows": [
        {
          "client_row_id": "tmp_order_1",
          "cells": {
            "amount_total": {
              "value": 120000,
              "confidence": 0.91,
              "source_page": 1,
              "source_excerpt": "合同总金额为人民币120000元"
            },
            "amount_currency": {
              "value": "CNY",
              "confidence": 0.86
            }
          }
        }
      ]
    }
  ],
  "warnings": [],
  "confidence": 0.82
}
```

The extractor must not invent fields outside the catalog. Unknown fields are validation errors and stay in `document_extractions.validation_errors`.

## Review Draft Contract

`ReviewDraftMaterializer` combines schema catalog + extraction payload into a complete table/cell draft.

Every active field in the selected table appears in every row:

```json
{
  "document_id": "...",
  "extraction_id": "...",
  "tables": [
    {
      "table_key": "orders",
      "label": "订单",
      "coverage": {
        "filled": 4,
        "total": 6,
        "required_missing": 1
      },
      "rows": [
        {
          "client_row_id": "tmp_order_1",
          "operation": "create",
          "target_entity_id": null,
          "cells": {
            "order_no": {
              "value": null,
              "status": "missing",
              "required": false,
              "editable": true
            },
            "amount_total": {
              "value": 120000,
              "status": "extracted",
              "required": true,
              "editable": true,
              "confidence": 0.91,
              "source_page": 1,
              "source_excerpt": "合同总金额为人民币120000元"
            },
            "amount_currency": {
              "value": "CNY",
              "status": "extracted",
              "required": true,
              "editable": true,
              "confidence": 0.86
            }
          }
        }
      ]
    }
  ],
  "warnings": []
}
```

Cell statuses:

```text
extracted   AI found a value
missing     field exists in schema but AI did not find a value
edited      human changed or filled the value
confirmed   human explicitly accepted the value
rejected    human ignored this cell or row
conflict    extracted value conflicts with an existing entity
invalid     value failed type or required validation
```

The Review UI renders `ReviewDraft.tables`. It does not build a separate conclusion-card model.

## Ingest Persistence

Create or extend `document_extractions`:

```text
document_extractions
  id
  tenant_id
  document_id
  extraction_type          -- company_schema_v2
  schema_version
  model_provider
  model_name
  prompt_version
  selected_tables          -- JSONB
  extraction_payload       -- raw found values
  review_draft             -- materialized complete table/cell draft
  missing_fields           -- canonical paths
  risk_flags               -- structured flags
  parse_warnings           -- strings
  validation_errors        -- structured errors
  confidence
  review_status            -- pending | confirmed | ignored | failed
  reviewed_by
  reviewed_at
  created_at
```

`review_draft` is stored because review must survive refresh and worker/job boundaries. It is not the final source of truth after confirm; confirmed business tables are.

## Confirm Writeback

Confirm accepts a reviewed draft:

```text
POST /win/api/ingest/v2/extractions/{extraction_id}/confirm
```

Rules:

1. Load schema catalog for tenant + schema version.
2. Validate all table and field keys.
3. Validate field types and required fields.
4. Apply row operations: create, update, link_existing, ignore.
5. Write business tables.
6. Write `field_provenance` for every confirmed non-null cell with document evidence.
7. Mark `document_extractions.review_status = confirmed`.
8. Mark `documents.review_status = confirmed`.

Confirm should fail loudly on unknown table/field paths, invalid values, and missing required values for rows the user chooses to write.

## Field Provenance

Use field-level provenance as a first-class table:

```text
field_provenance
  id
  tenant_id
  document_id
  extraction_id
  table_key
  entity_id
  field_key
  canonical_path          -- "orders.amount_total"
  value
  source_page
  source_excerpt
  confidence
  excerpt_match
  extracted_by
  reviewed_by
  created_at
```

For nested/child rows, provenance belongs to the actual row's table and ID. Example:

- `contract_payment_milestones.ratio`
- `order_items.quantity`
- `shipment_items.product_name`

Avoid storing all child fields as opaque JSON on the parent when the product needs to review, query, and update them as rows.

## API Surface

New endpoints:

```text
POST   /win/api/ingest/v2/jobs
GET    /win/api/ingest/v2/jobs/{job_id}
GET    /win/api/ingest/v2/extractions/{extraction_id}
POST   /win/api/ingest/v2/extractions/{extraction_id}/confirm
POST   /win/api/ingest/v2/extractions/{extraction_id}/ignore
GET    /win/api/company-schema
```

`GET /company-schema` returns catalog metadata for the current tenant. The frontend uses it to render table labels, field labels, field types, enum values, and required/editable state.

The old `/win/api/ingest/auto`, `/jobs`, and old confirm routes may stay during migration, but new UI should use V2 only.

## Frontend Review UX

The Review page becomes a table review workspace.

Layout:

- Top: document name, OCR status, extraction status, overall confidence.
- Left or top navigation: tables detected in the document.
- Main: table sections.
- Each section shows coverage: `订单 4/6`, `发票 5/9`, `规格要求 2/7`.
- Rows are editable.
- Cells show status and provenance.
- Missing required cells are visible and highlighted.
- Users can add rows, delete rows, link rows to existing records, or ignore entire tables.

There is no primary `AI 提取结论` card list in V2. If a summary is needed, it should be derived from table coverage and warnings, not from a separate data model.

## AI Access Model

AI reads:

- `company_schema_*` catalog.
- confirmed business tables.
- `field_provenance`.
- documents/chunks for evidence and citations.
- pending `document_extractions` only when helping with review/debug.

AI writes:

- `document_extractions` proposals.
- optional schema change proposals.
- never direct high-impact business table changes without review unless a later explicit auto-confirm policy permits it.

Schema change workflow:

- AI may propose changes as structured `schema_change_proposals`.
- Human approval creates a migration or controlled catalog update.
- Runtime arbitrary DDL by AI is out of scope for V2.
- Catalog-only changes that do not alter physical tables may be applied by a controlled admin action, but they must still leave an audit trail.

## Migration Strategy

Because breaking changes are allowed, build V2 beside the current flow:

1. Add V2 schema catalog and business table migrations.
2. Add V2 extraction and review draft contracts.
3. Add V2 job/extraction/confirm endpoints.
4. Build V2 Review UI from `ReviewDraft.tables`.
5. Point upload flow to V2.
6. Keep old endpoints temporarily for existing history and rollback.
7. Stop extending `UnifiedDraft`, `SchemaSummary`, and `ReviewExtraction`.
8. Remove old flow after V2 has parity for the active tenant workflow.

Do not attempt a big in-place patch of the current `UnifiedDraft` pipeline. That would preserve the core complexity problem.

## Testing Plan

Backend tests:

- Schema catalog validates unique table/field keys per tenant/version.
- Extractor output with partial fields materializes a review draft with all fields present.
- Unknown table/field returns validation errors.
- Missing required field blocks confirm for rows marked for write.
- Edited cell writes business table value and provenance with `reviewed_by`.
- Ignored row does not write business data.
- Confirm is idempotent or explicitly rejects repeated confirm.
- Tenant isolation prevents cross-tenant schema/data access.

Frontend tests:

- Table section renders all schema fields, including missing cells.
- Editing a missing field changes status to `edited`.
- Coverage count updates after edits.
- Confirm payload preserves table/row/cell structure.
- V2 review screen does not depend on `ReviewExtraction` or `SchemaSummary`.

Integration tests:

- Upload contract-like text -> extraction -> review draft -> confirm -> customers/orders/contracts/milestones/provenance.
- Upload invoice-like text -> extraction -> review draft -> confirm -> invoices/payments/provenance.
- Upload logistics-like text -> extraction -> review draft -> confirm -> shipments/shipment_items/provenance.

## Non-Goals For V2

- Arbitrary AI-driven database DDL without human approval.
- Rewriting OCR providers.
- Rewriting model provider adapters unless needed to fit the new extraction payload.
- Migrating all old historical extraction rows into V2 before launch.
- Preserving old frontend review shapes for new ingest.

## Success Criteria

- A user reviews extracted data by table and field, not by incomplete AI cards.
- Every schema-defined field is visible in review even when AI did not extract it.
- Confirm writes all supported table rows into tenant business tables.
- Every confirmed non-null extracted/edited field can be traced through `field_provenance`.
- Adding a new business table requires adding table/field schema and a write adapter, not editing scattered frontend summary logic.
- AI and humans use the same tenant company schema as the data foundation.
