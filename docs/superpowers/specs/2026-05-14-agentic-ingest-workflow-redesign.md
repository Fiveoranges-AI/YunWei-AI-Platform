# Agentic Ingest Workflow Redesign

Date: 2026-05-14
Status: proposed
Scope: Win ingest, parsing, extraction, review, entity resolution, and confirmed tenant company data writeback.

## Decision

Rebuild Win ingest from first principles around a provider-aware document understanding pipeline:

```text
upload source
  -> physical file type detection
  -> parser provider
  -> ParseArtifact
  -> table router
  -> selected table extraction schema
  -> extractor provider
  -> validation
  -> entity resolution proposal
  -> progressive review wizard
  -> final atomic writeback
```

The first implementation does not need backward compatibility with older ingest contracts.

## Goals

- Preserve the full source grounding available from LandingAI ADE for visual documents.
- Avoid flattening parser output into only `ocr_text`.
- Extract only relevant company schema tables, not the full database schema.
- Never ask extractors to produce system-managed IDs such as `customer_id`.
- Propose entity matches before confirmation instead of blindly creating duplicate records.
- Let users review one card or table step at a time and return to earlier steps before final writeback.
- Keep confirmed business data isolated inside each enterprise tenant database.

## Non-Goals

- No Mistral OCR in the redesigned ingest path.
- No MinerU in the first version.
- No LandingAI/MinerU mixed parse-extract pipeline in the first version.
- No full-schema extraction for every upload.
- No direct write to official business tables before human final confirmation.
- No real-time collaborative review editing.

## Reference

The design follows the core pattern from `docs/reference/agentic doc extraction.md`:

```text
Parse API
  -> structured markdown
  -> chunks
  -> bounding boxes / grounding
  -> table and cell references

Extract API
  -> schema_json + parsed markdown
  -> extracted values
  -> extraction_metadata source references
```

Internally, this design names the normalized parse output `ParseArtifact`.

## Current Code Context

The current `main` branch already has a schema-first ingest surface:

- API: `services/platform-api/yunwei_win/api/schema_ingest.py`
- Worker: `services/platform-api/yunwei_win/workers/ingest_rq.py`
- Orchestrator: `services/platform-api/yunwei_win/services/schema_ingest/auto.py`
- Review draft: `services/platform-api/yunwei_win/services/schema_ingest/review_draft.py`
- Confirm writeback: `services/platform-api/yunwei_win/services/schema_ingest/confirm.py`
- Frontend review: `apps/win-web/src/components/review/ReviewTableWorkspace.tsx`

The remaining issue is architectural: parse, routing, extraction, entity matching, and review are still centered around a markdown-like evidence layer and table/cell drafts. The new design introduces an explicit parse layer, provider-specific extraction choices, entity resolution proposals, and progressive review state.

## Current DB Schema Review Findings

A parallel read-only schema review of ORM models, the default company catalog, confirm/writeback code, and API/frontend consumers found these issues that the redesign must address before implementation:

1. `document_parses` does not exist yet. The current tenant DB has `documents` and `document_extractions`, but no durable parse attempt layer. The redesign must add `document_parses` instead of storing only flattened text on `documents`.

2. `company_schema_fields` does not have `field_role` or `review_visible`. The current extractor schema builder emits every active catalog field, so relationship/source UUID fields such as `customer_id`, `order_id`, `invoice_id`, `shipment_id`, `product_id`, `document_id`, and `source_document_id` are treated as normal LLM-extractable fields. This is unsafe. These fields must become `system_link` or `audit` fields and be excluded from extraction and normal review UI.

3. `customer_tasks.owner` is a hard catalog/ORM mismatch. The default catalog defines `owner`, while the ORM/API/frontend use `assignee`. Non-empty `owner` cells will fail confirm parity because there is no ORM destination. vNext should standardize on `assignee`; there should be no alias layer unless a later migration needs one for existing data.

4. `contacts.role` is semantically wrong in the current catalog. The catalog labels it as a free-text job title, but the ORM column is a constrained `ContactRole` enum. The actual free-text fields `title`, `phone`, and `address` exist in ORM/API/frontend but are absent from the current catalog. vNext should add `title`, `phone`, and `address`; `role` should either be an enum with explicit `enum_values` or system-defaulted to `other` and not extracted from free text.

5. Contract fields are split between new schema-first columns and legacy surfaces. `contracts.delivery_terms` and `contracts.penalty_terms` exist in ORM and are useful extractable fields but are absent from the current catalog. Legacy `contract_no_internal`, JSON `payment_milestones`, and `confidence_overall` are still visible in some read/assistant paths but should not be part of the new extraction schema. vNext should use `contracts.amount_total`, `contracts.amount_currency`, and `contract_payment_milestones` as the canonical contract money/payment model.

6. Required/nullability mismatches need an explicit policy. Examples: catalog requires `contacts.customer_id` and `contracts.customer_id`, while ORM columns are nullable; catalog requires `product_requirements.requirement_text`, while ORM allows null. In vNext, catalog `required` is a review/writeback policy, not proof that the document contains a value. System-managed required FKs must be validated through row links, not through extracted UUID cells.

7. Default-only rows can currently become real rows. The materializer can create a row with only defaults such as `amount_currency="CNY"` and linked FK cells, and confirm may treat it as non-empty. vNext row writeability must be based on AI-extracted values, user edits, or explicit user row decisions. Defaults should be applied only after a row is otherwise selected for creation/update.

8. Current FK auto-link behavior is too implicit. Validation can waive a missing required FK if any parent row exists, while writeback can only fill the FK when exactly one parent row exists. With multiple parent rows, validation can pass and writeback can still fail or create orphan nullable rows. vNext must use explicit row-level link metadata: child rows reference a parent `client_row_id` or selected existing entity.

9. Schema version drift can silently skip validation. Current confirm validates against the active catalog but only walks cells present in the stored draft. If the catalog changes after extraction, new required fields may be missed and removed fields may be skipped. vNext must snapshot the field specs used for extraction/review into `document_extractions` and either validate against that snapshot or force rematerialization on version mismatch.

10. Provenance is incomplete. Current provenance is mainly written for AI evidence or user edits and stores raw cell values. vNext provenance must record final persisted values and review actions for `ai`, `edited`, `default`, `linked`, and `system` values, including `parse_id`, `extraction_id`, and source refs.

11. Several confirmed schema-first tables are not visible after writeback. Confirm can write products, requirements, invoices, invoice items, payments, shipments, shipment items, payment milestones, journal items, and tasks, while current profile/frontend/assistant reads focus mostly on customers, contacts, orders, contracts, and legacy memory tables. vNext must either make every first-version review-visible table readable in profile/assistant surfaces or defer that table from first-version review.

12. `customers.industry` and `customers.notes` exist in ORM/catalog but are not surfaced in current customer profile/edit APIs and frontend models. Either add them to read/edit/profile surfaces, or mark them `review_visible=false` until there is a user-facing home.

13. `contacts.needs_review` is a legacy workflow flag. It is returned by some APIs, not used by the frontend, and not written by the current contact management flow. vNext review state belongs in `document_extractions.review_draft`, `ReviewCell.status`, `row_decision`, and review lock/version fields. `contacts.needs_review` should not be extracted, shown, or written; it can be dropped if destructive schema cleanup is allowed.

14. Source document display is inconsistent. Backend timeline/read paths can expose documents and raw OCR/LLM payloads, while frontend profile code currently does not consistently consume source documents. vNext should make source refs and document preview a first-class review/profile capability backed by `document_parses`; raw parser/LLM payloads should stay debug-only.

15. Frontend customer `tag` filters are mock-era fields without a backend source of truth. They should not be treated as ingest schema fields. Either add real customer segmentation/risk fields later or remove tag-based UX from the ingest redesign scope.

## Tenant Data Boundary

All ingest business data belongs in the enterprise tenant database:

```text
tenant_<enterprise_id>
  documents
  document_parses
  document_extractions
  company_schema_tables
  company_schema_fields
  customers
  contacts
  orders
  contracts
  invoices
  ...
```

Platform-level auth, enterprise registration, sessions, and permissions remain in the platform database.

Original file bytes should stay in storage. Tenant DB rows store file metadata and storage URLs.

## First-Principles Tenant Schema

Because the redesign does not need backward compatibility and can assume no existing tenant data, vNext should simplify the tenant database around three responsibilities:

```text
1. Evidence
   What did the user upload, and how did parsers/extractors interpret it?

2. Review process
   What did AI propose, what did humans change, and who confirmed it?

3. Confirmed business facts
   What official customer/company data should downstream UI and assistant use?
```

### Keep / Build

Evidence and review:

```text
documents
document_parses
document_extractions
ingest_batches
ingest_jobs
llm_calls
```

Schema metadata:

```text
company_schema_tables
company_schema_fields
schema_change_proposals
```

Confirmed business facts:

```text
customers
contacts
products
product_requirements
orders
contracts
contract_payment_milestones
invoices
invoice_items
payments
shipments
shipment_items
customer_journal_items
customer_tasks
field_provenance
```

### Drop From vNext Mainline

These old customer-memory/inbox tables should not remain first-class vNext ingest targets:

```text
customer_events
customer_commitments
customer_risk_signals
customer_memory_items
customer_inbox_items
```

Their responsibilities collapse into:

```text
customer_journal_items
  item_type = event | commitment | risk | note | preference | complaint | meeting | delivery | payment | other

customer_tasks
```

This removes duplicate ways to represent the same customer timeline and prevents the assistant/UI from needing to merge several parallel memory models.

### Core Extraction Principle

LLMs extract business facts. The system owns identity, relationships, audit, source, workflow, and versioning.

Therefore extractor schemas may include only:

```text
field_role = extractable
field_role = identity_key
```

Extractor schemas must exclude:

```text
primary keys
foreign keys
document/source ids
timestamps
workflow statuses
model confidence fields
sort order fields
raw parser/LLM payload fields
```

Confirm writeback fills relationships and audit fields from entity resolution, review row decisions, current document/extraction context, and DB-generated values.

## Provider Matrix

First version:

```text
PDF / image / PPTX
  parser: LandingAI Parse
  extractor: LandingAI Extract
  evidence: chunk/cell/bbox grounding

plain text / pasted text
  parser: TextParser
  extractor: DeepSeek
  evidence: source excerpt and optional character span

DOCX
  parser: DocxParser
  extractor: DeepSeek
  evidence: paragraph/table reference where available

XLSX / XLS / CSV
  parser: SpreadsheetParser
  extractor: DeepSeek
  evidence: sheet/cell reference
```

Rationale:

- LandingAI Parse and LandingAI Extract should be paired for visual documents because the extract model can reference parse-generated chunk and cell IDs.
- Plain text does not benefit from LandingAI Parse or visual grounding, so DeepSeek is cheaper and sufficient.
- Spreadsheets already contain native sheet/cell structure; parsing them as images would lose useful structure.
- DOCX can be parsed natively into paragraphs and tables; PPTX is more visual and should use LandingAI.

## Data Model

### `documents`

Represents the original uploaded source.

Fields:

```text
id
file_url
file_sha256
original_filename
content_type
file_size_bytes
uploaded_by
created_at
updated_at
```

`documents` should not be the primary home for parse artifacts or extraction attempts.

### `document_parses`

Represents one parser attempt for one document.

Fields:

```text
id
document_id
provider              landingai | text | docx | spreadsheet
model                 dpt-2-latest | parser version | null
status                parsed | failed
artifact              ParseArtifact JSON
raw_metadata          provider metadata, job_id, duration, filename
warnings              JSON list
error_message
created_at
updated_at
```

The same document may have multiple parse attempts later. First version only needs one successful parse attempt per ingest job.

### `document_extractions`

Represents one extraction attempt over one parse attempt.

Fields:

```text
id
document_id
parse_id
provider              landingai | deepseek
model
status                pending_review | confirmed | ignored | failed
selected_tables       router output
extraction            normalized extracted field payload
extraction_metadata   source refs and provider metadata
validation_warnings
entity_resolution     proposed matches and row operations
review_draft
review_version        integer default 0
locked_by             nullable user id / email / display id
lock_token            nullable uuid
lock_expires_at       nullable timestamp
last_reviewed_by
last_reviewed_at
confirmed_by
confirmed_at
created_at
updated_at
```

`review_draft` remains the server-side source of truth for in-progress edits.

## Company Schema Field Roles

`company_schema_fields` needs field role metadata so extractors and review UI do not treat system fields as document facts.

Minimum required fields:

```text
field_role       extractable | identity_key | system_link | audit
review_visible   boolean
```

Semantics:

```text
extractable
  File may contain this value. Extractor should extract it. User can review it.

identity_key
  File may contain this value. Extractor should extract it. Entity resolution can use it.

system_link
  System-managed relationship field. Extractor must not extract it. Usually hidden.

audit
  System-managed audit field. Extractor must not extract it. Hidden.
```

Examples:

```text
customers.full_name            identity_key
customers.tax_id               identity_key
contacts.mobile                identity_key
contracts.contract_no_external identity_key
orders.amount_total            extractable
orders.customer_id             system_link
invoice_items.invoice_id       system_link
field_provenance.document_id   audit
```

The extraction schema builder includes only:

```text
field_role in (extractable, identity_key)
```

The review UI displays only:

```text
review_visible = true
```

Final confirm fills `system_link` fields after parent rows are confirmed or created.

### vNext Field Classification

The first implementation should seed or migrate the catalog toward this classification. `id`, timestamps, primary keys, raw parser/LLM fields, workflow status fields, and relationship UUIDs are omitted from extractor schemas unless listed as extractable.

| Table | Extractable / Review-Visible | Identity Keys | System-Managed / Hidden |
| --- | --- | --- | --- |
| `customers` | `short_name`, `address`, `industry`, `notes` if surfaced in profile | `full_name`, `tax_id` | `id`, timestamps |
| `contacts` | `name`, `title`, `phone`, `mobile`, `email`, `wechat_id`, `address` | `mobile`, `email`, `name + customer` | `customer_id`, `id`, timestamps, `needs_review`; `role` is enum/system default unless made explicit enum |
| `products` | `sku`, `name`, `description`, `specification`, `unit` | `sku`, `name` | `id`, timestamps |
| `product_requirements` | `requirement_type`, `requirement_text`, `tolerance` | none in first version | `customer_id`, `product_id`, `source_document_id`, `id`, timestamps |
| `contracts` | `contract_no_external`, `signing_date`, `effective_date`, `expiry_date`, `amount_total`, `amount_currency`, `delivery_terms`, `penalty_terms` | `contract_no_external + customer` | `customer_id`, `order_id`, `id`, `contract_no_internal`, legacy `payment_milestones`, `confidence_overall`, timestamps |
| `contract_payment_milestones` | `name`, `ratio`, `amount`, `trigger_event`, `trigger_offset_days`, `due_date`, `raw_text` | none in first version | `contract_id`, `id`, `sort_order`, timestamps |
| `orders` | `amount_total`, `amount_currency`, `delivery_promised_date`, `delivery_address`, `description` | external order number if added later | `customer_id`, `id`, timestamps |
| `invoices` | `invoice_no`, `issue_date`, `amount_total`, `amount_currency`, `tax_amount`, `status` | `invoice_no + customer` | `customer_id`, `order_id`, `id`, timestamps |
| `invoice_items` | `description`, `quantity`, `unit_price`, `amount` | none in first version | `invoice_id`, `product_id`, `id`, timestamps |
| `payments` | `payment_date`, `amount`, `currency`, `method`, `reference_no` | `reference_no` when reliable | `customer_id`, `invoice_id`, `id`, timestamps |
| `shipments` | `shipment_no`, `carrier`, `tracking_no`, `ship_date`, `delivery_date`, `delivery_address`, `status` | `shipment_no`, `tracking_no` | `customer_id`, `order_id`, `id`, timestamps |
| `shipment_items` | `description`, `quantity`, `unit` | none in first version | `shipment_id`, `product_id`, `id`, timestamps |
| `customer_journal_items` | `item_type`, `title`, `content`, `occurred_at`, `due_date`, `severity`, `status`, `raw_excerpt` | none in first version | `customer_id`, `document_id`, `confidence`, `id`, timestamps |
| `customer_tasks` | `title`, `description`, `assignee`, `due_date`, `priority` | none in first version | `customer_id`, `document_id`, `id`, timestamps; `status` defaults to open unless explicitly reviewed |

### Catalog Parity Requirements

Before the new workflow ships, add tests that assert:

```text
every active extractable/review-visible catalog field maps to an ORM destination
no system_link/audit field is emitted in extractor JSON schema
no default catalog field name differs from ORM without an explicit alias
required system_link fields are satisfied by row links, not extracted values
read/profile/assistant surfaces expose every table that first-version review can confirm
```

## ParseArtifact Contract

`ParseArtifact` is the normalized parser output.

Shape:

```json
{
  "version": 1,
  "provider": "landingai",
  "source_type": "pdf",
  "markdown": "...",
  "pages": [],
  "chunks": [],
  "grounding": {},
  "tables": [],
  "metadata": {},
  "capabilities": {
    "pages": true,
    "chunks": true,
    "visual_grounding": true,
    "table_cells": true,
    "text_spans": false,
    "spreadsheet_cells": false
  }
}
```

### LandingAI Adapter

Mapping:

```text
ParseResponse.markdown  -> artifact.markdown
ParseResponse.splits    -> artifact.pages
ParseResponse.chunks    -> artifact.chunks
ParseResponse.grounding -> artifact.grounding
ParseResponse.metadata  -> artifact.metadata
```

Capabilities:

```json
{
  "pages": true,
  "chunks": true,
  "visual_grounding": true,
  "table_cells": true
}
```

### TextParser Adapter

Creates a synthetic single-page artifact:

```text
input text -> markdown
single text chunk
optional character spans
```

### DocxParser Adapter

Creates structured markdown from:

```text
paragraphs
headings
tables
```

Paragraph and table IDs should be stable enough to use as source refs.

### SpreadsheetParser Adapter

Creates markdown tables and cell references from sheets.

Example source ref:

```text
sheet:报价单!R3C5
```

Example chunk:

```json
{
  "id": "sheet:报价单!R3C5",
  "type": "table_cell",
  "sheet": "报价单",
  "row": 3,
  "col": 5,
  "value": "30000"
}
```

## File Type Detection

File type detection is physical, not business semantic.

Rules:

```text
pasted text
  -> text

text/plain / .txt / .md
  -> text

.csv
  -> spreadsheet

.xlsx / .xls
  -> spreadsheet

.docx
  -> docx

.pptx
  -> landingai visual

image/*
  -> landingai visual

application/pdf / .pdf
  -> landingai visual
```

Unsupported inputs fail early with a clear message.

## Router

Router decides which company schema tables to extract.

Input:

```text
ParseArtifact.markdown
first page markdown if available
active company schema table summaries
source_type
provider capabilities
```

Output:

```json
{
  "selected_tables": [
    {
      "table_name": "customers",
      "confidence": 0.94,
      "reason": "文档包含客户公司名称和税号"
    }
  ],
  "rejected_tables": [],
  "document_summary": "客户订单，包含金额、交付日期和联系人信息",
  "needs_human_attention": false
}
```

Router provider:

```text
DeepSeek Flash / parse model
```

Failure policy:

```text
fail open to conservative core tables:
  customers
  contacts
  customer_journal_items
```

The warning is stored in `document_extractions.validation_warnings` and surfaced in review.

## Extraction

The extraction schema builder receives:

```text
selected_tables
company_schema_fields
```

It emits JSON schema containing only extractable and identity fields.

### LandingAI Extract

Used for:

```text
PDF
image
PPTX
```

Input:

```text
schema_json
ParseArtifact.markdown from LandingAI Parse
```

Output:

```text
extraction
extraction_metadata
```

The `extraction_metadata` references are mapped back through `ParseArtifact.grounding`.

### DeepSeek Extract

Used for:

```text
plain text
DOCX
XLSX / XLS / CSV
```

Input:

```text
schema_json
ParseArtifact.markdown
instructions to return value + confidence + source_refs
```

Expected normalized output:

```json
{
  "tables": {
    "orders": [
      {
        "amount_total": {
          "value": "30000",
          "confidence": 0.91,
          "source_refs": ["sheet:报价单!R3C5"]
        }
      }
    ]
  }
}
```

## Extraction Validation

Validation happens before review draft materialization.

Checks:

```text
JSON shape matches generated extraction schema
unknown table / field is rejected or warned
data type validation for decimal, integer, date, datetime, enum, boolean
source_refs resolve against ParseArtifact where applicable
required business fields become invalid or missing review cells
```

Failures do not write official data. They become:

```text
ReviewCell.status = invalid | missing | low_confidence
ReviewDraft.general_warnings
```

## Entity Resolution

Entity resolution proposes create/update/link decisions before review.

First version covers:

```text
customers
contacts
contracts
orders
invoices
```

Out of scope for first version:

```text
invoice_items
shipment_items
contract_payment_milestones
payments
customer_journal_items
customer_tasks
```

### Strong Match Rules

```text
customers
  exact tax_id
  exact normalized full_name

contacts
  exact mobile/email within selected customer

contracts
  contract_no_external + selected customer

orders
  external order number if schema has it

invoices
  invoice_no + selected customer
```

### Weak Candidate Rules

```text
contacts
  name + selected customer

orders
  selected customer + amount_total + date
```

LLM/semantic matching may provide explanations or weak candidates, but must not create high-confidence default updates without deterministic keys.

### Default Decisions

```text
strong match
  -> default update or link_existing

weak match
  -> default create, show candidates

no match
  -> create
```

Entity resolution JSON:

```json
{
  "rows": [
    {
      "table_name": "customers",
      "client_row_id": "customers:0",
      "proposed_operation": "update",
      "selected_entity_id": "uuid",
      "confidence": 0.98,
      "match_level": "strong",
      "match_keys": ["tax_id"],
      "reason": "tax_id exact match",
      "candidates": []
    }
  ]
}
```

## ReviewDraft

The backend contract remains table-shaped:

```text
tables -> rows -> cells
```

But the review experience is card/table aware.

Additions:

```text
presentation: card | table
review_step: customer | contacts | commercial | finance | logistics_product | memory | summary
row_decision:
  operation: create | update | link_existing | ignore
  selected_entity_id
  candidate_entities
source_refs:
  provider refs
  chunk ids
  bbox
  sheet/cell refs
  excerpts
```

System fields are not ordinary cells unless a future admin/debug mode needs them.

## Progressive Review Wizard

Review uses fixed steps:

```text
1. 客户
2. 联系人
3. 合同 / 订单
4. 发票 / 付款
5. 物流 / 产品
6. 时间线 / 待办
7. 总览确认
```

Step mapping:

```text
客户
  customers

联系人
  contacts

合同 / 订单
  contracts
  orders
  contract_payment_milestones

发票 / 付款
  invoices
  invoice_items
  payments

物流 / 产品
  shipments
  shipment_items
  products
  product_requirements

时间线 / 待办
  customer_journal_items
  customer_tasks
```

Steps with no selected or materialized rows are skipped.

Presentation:

```text
core/master rows -> card
  customers
  contacts
  contracts
  orders
  invoices

detail rows -> table
  invoice_items
  shipment_items
  contract_payment_milestones
  product_requirements

fallback -> generic table
```

Autosave:

```text
PATCH /api/win/ingest/extractions/{id}/review
```

Saves:

```text
cell edits
row decisions
current_step
step status
ignored rows
selected candidate entity
```

Final confirm:

```text
POST /api/win/ingest/extractions/{id}/confirm
```

Final confirm validates the latest server-side draft and then writes official rows in one transaction.

## Multi-Reviewer Control

First version supports many viewers but only one active editor.

Use an exclusive edit lock plus optimistic versioning.

Fields on `document_extractions`:

```text
review_version integer default 0
locked_by string nullable
lock_token uuid nullable
lock_expires_at datetime nullable
last_reviewed_by string nullable
last_reviewed_at datetime nullable
```

Open review:

```text
GET /api/win/ingest/extractions/{id}/review
```

Acquire lock:

```text
POST /api/win/ingest/extractions/{id}/review/lock
```

If unlocked:

```json
{
  "locked_by": "user_a",
  "lock_token": "uuid",
  "lock_expires_at": "...",
  "review_version": 12
}
```

If locked by another user:

```json
{
  "locked_by": "user_b",
  "lock_expires_at": "...",
  "mode": "read_only"
}
```

Autosave must include:

```json
{
  "lock_token": "...",
  "base_version": 12,
  "patches": []
}
```

Backend accepts autosave only when:

```text
lock_token matches
lock has not expired
base_version == current review_version
```

On success:

```text
review_version += 1
review_draft updated
lock_expires_at refreshed
```

On mismatch:

```text
409 conflict
```

Final confirm also requires the valid lock token and latest version.

## Confirm Writeback

Final confirm:

```text
1. Validate latest ReviewDraft.
2. Resolve row decisions.
3. Open DB transaction.
4. Write parent rows first.
5. Fill system_link fields.
6. Write child/detail rows.
7. Write FieldProvenance.
8. Mark extraction confirmed.
9. Release review lock.
```

Write order:

```text
customers
contacts
contracts / orders / invoices / products / shipments
contract_payment_milestones / invoice_items / shipment_items / payments / product_requirements
customer_journal_items / customer_tasks
```

Update rules:

```text
only update user-confirmed fields
do not use AI null values to overwrite existing values
allow explicit user-cleared values only when represented as an explicit clear action
```

Provenance records:

```text
document_id
parse_id
extraction_id
entity_type
entity_id
field_name
source_refs
confidence
review_action
```

## API Shape

Candidate endpoints:

```text
POST /api/win/ingest/jobs
GET  /api/win/ingest/jobs
GET  /api/win/ingest/jobs/{job_id}

GET  /api/win/ingest/extractions/{extraction_id}/review
POST /api/win/ingest/extractions/{extraction_id}/review/lock
PATCH /api/win/ingest/extractions/{extraction_id}/review
POST /api/win/ingest/extractions/{extraction_id}/confirm
POST /api/win/ingest/extractions/{extraction_id}/ignore
```

Existing paths can be reused if implementation replaces the old contract.

## Testing Strategy

Backend tests:

```text
file type detection routes each extension/content type to the expected parser
LandingAI adapter preserves markdown, chunks, grounding, splits
TextParser creates valid ParseArtifact
DocxParser preserves paragraphs and tables
SpreadsheetParser emits stable sheet/cell refs
router emits selected_tables and fail-open warnings
schema builder excludes system_link/audit fields
LandingAI extraction maps metadata refs into ReviewCell source_refs
DeepSeek extraction validates source_refs for text/docx/spreadsheet
entity resolution proposes strong matches for deterministic keys
weak matches default to create
review lock rejects concurrent edits
autosave increments review_version
confirm requires latest version and valid lock
confirm writes system_link fields and provenance
confirm does not overwrite existing values with AI nulls
```

Frontend tests or type checks:

```text
review wizard skips empty steps
cards render row decisions and candidates
detail tables render rows/cells
read-only mode when another reviewer holds lock
409 autosave conflict is surfaced
final summary lists creates, updates, ignored rows, edited fields
```

## Rollout Notes

Because backward compatibility is not required, implementation can replace the current schema ingest internals rather than layering adapters over old `ocr_text` behavior.

Recommended order:

```text
1. ParseArtifact models and document_parses.
2. Parser selection and adapters.
3. Router selected_tables contract.
4. Extraction schema builder with field roles.
5. LandingAI visual extraction path.
6. DeepSeek text/docx/spreadsheet extraction path.
7. Entity resolution proposal.
8. ReviewDraft vNext and progressive review API.
9. Review lock/version.
10. Final confirm writeback and provenance.
11. Frontend wizard.
```
