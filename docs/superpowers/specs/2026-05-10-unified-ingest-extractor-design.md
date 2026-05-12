# Unified Ingest And Extractor Design

Date: 2026-05-10
Status: Proposed
Scope: Win app customer evidence intake, OCR, extraction, review, and DB writeback

## Background

The Win app currently exposes one user-facing intake surface: upload local files, take a photo, or paste text. Internally, the frontend still guesses a business `kind` and routes to one of several backend endpoints:

- `contract` -> `/api/ingest/contract`
- `business_card` -> `/api/ingest/business_card`
- `wechat_screenshot` -> `/api/ingest/wechat_screenshot`

That split made sense when UI controls were type-specific, but it is brittle for the current product shape. A photo can be a business card, contract page, quotation, delivery note, chat screenshot, or miscellaneous customer note. Filename and extension are not reliable business classifiers.

The deeper issue is not that backend modules are separated. `contract.py`, `business_card.py`, and memory-related modules encode different DB write semantics. The issue is that the frontend is deciding which business pipeline to run. That decision should happen after the backend has normalized the evidence into text/OCR and planned which database areas can be updated.

The current LLM configuration also matters: DeepSeek v4 flash is text-first and should not receive image blocks. Mistral OCR should handle image/document reading; DeepSeek should handle classification and structured extraction from text.

## First Principles

Users do not upload "a business card" or "a WeChat screenshot" as a database concept. Users provide evidence that may update the customer profile.

The system should therefore ask:

1. What business objects can be updated from this evidence?
2. Which extractors should run?
3. Which proposed fields need review before they become official records?

It should not ask first:

1. What does the file look like?
2. Which single endpoint should this file be sent to?

Document type can remain useful as audit metadata, but it should not be the primary routing primitive.

## DB-End-State Model

Design extractor boundaries from the tables we ultimately want to update.

### Evidence Layer

Target table:

- `documents`

Responsibilities:

- Store original file/text payload.
- Store `ocr_text`.
- Store raw LLM outputs.
- Track processing and review status.
- Link detected or assigned customer when available.

No extractor should "extract a document." Document creation is infrastructure that happens before planning and extraction.

### Identity Layer

Target tables:

- `customers`
- `contacts`

Important fields:

- `customers.full_name`
- `customers.short_name`
- `customers.address`
- `customers.tax_id`
- `contacts.name`
- `contacts.title`
- `contacts.phone`
- `contacts.mobile`
- `contacts.email`
- `contacts.role`
- `contacts.address`
- `contacts.wechat_id`

### Commercial Layer

Target tables:

- `orders`
- `contracts`

Important fields:

- `orders.amount_total`
- `orders.amount_currency`
- `orders.delivery_promised_date`
- `orders.delivery_address`
- `orders.description`
- `contracts.contract_no_external`
- `contracts.payment_milestones`
- `contracts.delivery_terms`
- `contracts.penalty_terms`
- `contracts.signing_date`
- `contracts.effective_date`
- `contracts.expiry_date`

### Customer Operations Layer

Target tables:

- `customer_events`
- `customer_commitments`
- `customer_tasks`
- `customer_risk_signals`
- `customer_memory_items`
- `customer_inbox_items`

Important output families:

- Events: meetings, payments, complaints, shipments, deliveries, disputes, etc.
- Commitments: promises by us, by the customer, or mutual.
- Tasks: next steps for our team.
- Risks: payment, quality, legal, supply, churn, relationship.
- Memory items: preferences, decision makers, context, history.

### Provenance Layer

Target table:

- `field_provenance`

This is not an extractor target by itself. Provenance is attached to proposed business fields so users and downstream QA can trace where each field came from.

## Proposed Architecture

```text
Evidence input
  file | camera | pasted_text
        |
        v
Document + OCR/text normalization
        |
        v
Ingest Planner
        |
        v
Selected business extractors
  identity | commercial | ops
        |
        v
Merge unified review draft
        |
        v
Human review / confirm
        |
        v
DB writeback + provenance
```

## Public API Shape

Add a new unified endpoint for the Win app:

```text
POST /api/ingest/auto
POST /api/ingest/auto/{document_id}/confirm
POST /api/ingest/auto/{document_id}/cancel
```

Keep legacy endpoints during migration:

```text
POST /api/ingest/contract
POST /api/ingest/business_card
POST /api/ingest/wechat_screenshot
```

Legacy endpoints should remain as compatibility wrappers or direct testing surfaces until the auto flow is stable.

### Auto Request

For file/photo:

```text
multipart/form-data
file=<upload>
source_hint=file|camera
uploader=<optional>
```

For pasted text:

```text
multipart/form-data
text=<content>
source_hint=pasted_text
uploader=<optional>
```

`source_hint` describes how the evidence entered the system. It is not a business document type.

### Auto Stream Response

Use NDJSON to preserve the existing progress pattern:

```json
{"status":"progress","stage":"received","message":"服务器已收到证据"}
{"status":"progress","stage":"stored","message":"原始证据已保存"}
{"status":"progress","stage":"ocr","message":"正在 OCR / 文本化"}
{"status":"progress","stage":"plan","message":"正在判断需要更新哪些档案区域"}
{"status":"progress","stage":"extract_identity","message":"正在抽取客户和联系人"}
{"status":"progress","stage":"extract_commercial","message":"正在抽取交易和合同"}
{"status":"progress","stage":"merge","message":"正在合并草稿"}
{"status":"done", ...}
```

Final response:

```json
{
  "status": "done",
  "document_id": "uuid",
  "planner": {
    "targets": {
      "identity": 0.92,
      "commercial": 0.18,
      "ops": 0.73
    },
    "extractors": [
      {"name": "identity", "confidence": 0.92},
      {"name": "ops", "confidence": 0.73}
    ],
    "reason": "包含公司名、联系人电话，以及客户承诺付款时间",
    "review_required": true
  },
  "draft": {
    "customer": {},
    "contacts": [],
    "order": {},
    "contract": {},
    "events": [],
    "commitments": [],
    "tasks": [],
    "risks": [],
    "memory_items": [],
    "provenance": [],
    "warnings": []
  },
  "needs_review_fields": []
}
```

## Evidence Normalization

Create one normalization layer before planning.

Responsibilities:

- Persist the original payload once.
- Compute `file_sha256`.
- Determine input modality: `pdf`, `image`, `text`, `voice`, `other`.
- Run OCR/text extraction once.
- Store `Document.ocr_text`.
- Reuse OCR text for all selected extractors.

Suggested module:

```text
platform/yinhu_brain/services/ingest/evidence.py
```

For images and scanned/Office documents:

- Use Mistral OCR.
- Store markdown/text in `Document.ocr_text`.
- Do not pass image blocks to DeepSeek.

For born-digital PDFs:

- Use local PDF text extraction first.
- Fall back to Mistral OCR if text is sparse.

For pasted text:

- Store as `DocumentType.text_note`.
- Set `ocr_text` to the pasted text.

## Planner

The planner decides which database areas can be updated. It should not output a single mutually exclusive document type.

Suggested module:

```text
platform/yinhu_brain/services/ingest/planner.py
```

Planner input:

```json
{
  "filename": "optional",
  "content_type": "optional",
  "source_hint": "file|camera|pasted_text",
  "input_modality": "pdf|image|text|other",
  "text": "OCR or pasted text, clipped for planning"
}
```

Planner output:

```json
{
  "targets": {
    "identity": 0.0,
    "commercial": 0.0,
    "ops": 0.0
  },
  "extractors": [
    {"name": "identity", "confidence": 0.0}
  ],
  "reason": "short reason",
  "review_required": true,
  "warnings": []
}
```

Activation thresholds for V1:

- `identity >= 0.55`: activate identity extractor.
- `commercial >= 0.65`: activate commercial extractor.
- `ops >= 0.60`: activate ops extractor.
- If all scores are low but text exists, activate `ops` as a low-confidence memory draft.

Deterministic fallback rules should complement the LLM planner:

- If OCR/text contains phone/email/company suffixes, raise identity score.
- If OCR/text contains contract number, payment ratio, total amount, Party A/Party B language, raise commercial score.
- If OCR/text contains due dates, promises, complaints, quality issues, payment delay language, raise ops score.

## Extractor Boundaries

Do not create one extractor per table. Tables are storage details; extractors should align with business aggregates.

### Identity Extractor

Suggested module:

```text
platform/yinhu_brain/services/ingest/extractors/identity.py
```

Targets:

- `customers`
- `contacts`

Input:

- `Document.id`
- normalized text/OCR
- optional source metadata

Output draft:

```json
{
  "customer": {
    "full_name": null,
    "short_name": null,
    "address": null,
    "tax_id": null
  },
  "contacts": [
    {
      "name": null,
      "title": null,
      "phone": null,
      "mobile": null,
      "email": null,
      "role": "other",
      "address": null,
      "wechat_id": null
    }
  ],
  "provenance": [],
  "field_confidence": {},
  "warnings": []
}
```

Notes:

- This replaces the business-card-specific mental model.
- It can extract identity information from a card, chat, contract, note, or email.
- It must be text-only for DeepSeek.

### Commercial Extractor

Suggested module:

```text
platform/yinhu_brain/services/ingest/extractors/commercial.py
```

Targets:

- `orders`
- `contracts`

Input:

- `Document.id`
- normalized text/OCR
- optional source metadata

Output draft:

```json
{
  "order": {
    "amount_total": null,
    "amount_currency": "CNY",
    "delivery_promised_date": null,
    "delivery_address": null,
    "description": null
  },
  "contract": {
    "contract_no_external": null,
    "payment_milestones": [],
    "delivery_terms": null,
    "penalty_terms": null,
    "signing_date": null,
    "effective_date": null,
    "expiry_date": null
  },
  "provenance": [],
  "field_confidence": {},
  "warnings": []
}
```

Notes:

- Reuse the existing contract extraction schemas where possible.
- Refactor existing contract extraction so it can accept an existing `Document` and already-normalized text.
- Do not OCR again inside this extractor.

### Ops Extractor

Suggested module:

```text
platform/yinhu_brain/services/ingest/extractors/ops.py
```

Targets:

- `customer_events`
- `customer_commitments`
- `customer_tasks`
- `customer_risk_signals`
- `customer_memory_items`

Output draft:

```json
{
  "events": [],
  "commitments": [],
  "tasks": [],
  "risks": [],
  "memory_items": [],
  "summary": "",
  "provenance": [],
  "warnings": []
}
```

Notes:

- Chat is not an extractor. Chat is evidence.
- This extractor captures operational meaning from any evidence source: chat, note, contract, email, meeting note, etc.
- Existing customer memory schemas can be reused, but V1 should allow drafts without an already selected customer. Customer binding can happen in merge/review.

## Merge Layer

Suggested module:

```text
platform/yinhu_brain/services/ingest/merge.py
```

Responsibilities:

- Combine extractor outputs into one unified review draft.
- Deduplicate customer/contact proposals.
- Prefer more specific commercial evidence for order/contract fields.
- Preserve provenance and warnings.
- Compute `needs_review_fields`.
- Run candidate matching against existing customers/contacts.

Merge output should be the single object consumed by the review UI and confirm endpoint.

## Confirm Writeback

Extractor tasks must not directly write final customer/profile rows.

Confirm endpoint should:

1. Load the `Document`.
2. Validate the user-reviewed draft.
3. Resolve customer:
   - merge into existing, or
   - create new.
4. Resolve contacts:
   - merge into existing, or
   - create new.
5. Write order/contract if commercial draft is present and confirmed.
6. Write ops rows into customer memory tables or inbox-confirmed flow.
7. Write `field_provenance`.
8. Mark document review status.

This keeps parallel extractors safe because they only generate proposals.

## Concurrency Model

Selected extractors can run in parallel because they read the same normalized text and produce independent drafts.

Important constraint:

- Do not share one SQLAlchemy `AsyncSession` across concurrent extractor tasks if those tasks call `call_claude()`, because `call_claude()` writes `llm_calls`.

Two safe options:

1. Each extractor task gets its own DB session for LLM audit writes. Merge and final writeback use a separate main session.
2. V1 runs extractors serially but keeps the API and code shape ready for parallelization.

Recommendation:

- Use independent sessions if implementation time allows.
- Otherwise start serial in V1 and parallelize after tests cover merge behavior.

## Frontend Changes

Files:

```text
platform/app-win/src/api/ingest.ts
platform/app-win/src/screens/Upload.tsx
```

Changes:

- Remove business `kind` routing from the frontend.
- Replace `endpointFor(kind)` with one `/win/api/ingest/auto` call.
- Keep `source_hint`: `file`, `camera`, `pasted_text`.
- Keep image preview and upload progress UI.
- Replace progress nodes with:

```text
上传 -> 保存 -> OCR/文本化 -> 规划 -> 身份/交易/运营抽取 -> 合并 -> 草稿
```

The UI can still show a user-editable hint later, but the hint must not be required for routing.

## Migration Plan

Phase 1: Add auto flow beside legacy flow.

- Add schemas.
- Add evidence normalization.
- Add planner.
- Add extractor modules.
- Add auto endpoint.
- Add tests.
- Keep current `/contract`, `/business_card`, `/wechat_screenshot`.

Phase 2: Switch Win app to auto flow.

- Frontend calls `/auto`.
- Review screen adapts to unified draft.
- Keep legacy endpoints for fallback and tests.

Phase 3: Refactor legacy endpoint internals.

- Legacy endpoints become thin wrappers around the same evidence/extractor modules.
- Remove duplicate OCR calls.
- Remove image blocks from DeepSeek paths.

Phase 4: Optimize.

- Cache OCR by `file_sha256`.
- Cache extraction by `file_sha256 + extractor + prompt_version + model`.
- Clip commercial text to key sections before contract extraction.
- Parallelize extractors if V1 started serial.

## Multi-Agent Implementation Plan

Independent workstreams:

### Agent A: Schemas

Owns:

```text
platform/yinhu_brain/services/ingest/auto_schemas.py
```

Deliver:

- `IngestPlan`
- `PlannedExtractor`
- `UnifiedDraft`
- `IdentityDraft`
- `CommercialDraft`
- `OpsDraft`
- `AutoConfirmRequest`

### Agent B: Evidence Normalization

Owns:

```text
platform/yinhu_brain/services/ingest/evidence.py
```

Deliver:

- Save file/text into `Document`.
- Run OCR/text extraction once.
- Return normalized evidence object.
- Tests for image, PDF, Office, and pasted text.

### Agent C: Planner

Owns:

```text
platform/yinhu_brain/services/ingest/planner.py
```

Deliver:

- DeepSeek text-only planner.
- Deterministic fallback/boost rules.
- Threshold-based extractor selection.
- Tests for identity-only, commercial-only, mixed, and low-signal evidence.

### Agent D: Identity Extractor

Owns:

```text
platform/yinhu_brain/services/ingest/extractors/identity.py
```

Deliver:

- Text-only customer/contact extraction.
- No image blocks.
- Reuse/align with existing business card schema where useful.
- Candidate matching can be done here or in merge layer, but not both.

### Agent E: Commercial Extractor

Owns:

```text
platform/yinhu_brain/services/ingest/extractors/commercial.py
platform/yinhu_brain/services/ingest/contract.py
```

Deliver:

- Refactor contract extraction to accept existing `Document` and normalized text.
- No duplicate OCR.
- Preserve existing contract validation and confirm semantics.

### Agent F: Ops Extractor

Owns:

```text
platform/yinhu_brain/services/ingest/extractors/ops.py
```

Deliver:

- Extract events, commitments, tasks, risks, memory items from normalized text.
- Support no preselected customer in draft mode.
- Reuse customer memory schemas where possible.

### Agent G: Merge And Confirm

Owns:

```text
platform/yinhu_brain/services/ingest/merge.py
platform/yinhu_brain/api/ingest.py
```

Deliver:

- `/api/ingest/auto`
- `/api/ingest/auto/{document_id}/confirm`
- `/api/ingest/auto/{document_id}/cancel`
- Merge outputs into unified review draft.
- Confirm writes final DB rows.

### Agent H: Win Frontend

Owns:

```text
platform/app-win/src/api/ingest.ts
platform/app-win/src/screens/Upload.tsx
platform/app-win/src/screens/Review.tsx
```

Deliver:

- Call `/win/api/ingest/auto`.
- Remove frontend business-kind routing.
- Support pasted text in real ingest.
- Display new progress stages.
- Render unified draft in review.

### Agent I: Test Coverage

Owns:

```text
platform/tests/test_auto_ingest_*.py
platform/app-win frontend type/build checks
```

Deliver tests for:

- OCR runs once and is reused.
- Planner activates correct extractors.
- Extractors do not write final profile rows.
- Merge deduplicates identity proposals.
- Confirm writes customers/contacts/orders/contracts/ops rows.
- Legacy endpoints still work.
- Win frontend builds.

## Non-Goals

- Do not implement one extractor per table in V1.
- Do not run every extractor every time.
- Do not use one giant multimodal prompt to extract everything.
- Do not pass image blocks to DeepSeek.
- Do not let extractors write final customer/profile rows directly.
- Do not delete legacy endpoints until auto flow is stable.

## Acceptance Criteria

V1 is acceptable when:

- Win app uploads files/photos/text through `/auto`.
- Backend stores one `Document` per evidence item.
- OCR/text normalization runs once.
- Planner selects a subset of `identity`, `commercial`, `ops`.
- Selected extractors produce draft-only outputs.
- Review UI can display the unified draft.
- Confirm writes final rows and provenance.
- Existing contract/business-card/wechat tests continue passing.
- New auto-ingest tests cover mixed evidence where more than one extractor is selected.

